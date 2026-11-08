"""
tests/test_challenger_p4_iter2_c1.py - Challenger 1 (Iter 2) Empirical Verification Suite.

Adversarially re-verifies all 6 vulnerabilities from Challenger 1 report:
1. Blueprint Drop Bug (DualChannelRouter checks "recommended_strategy" and "steps")
2. Infinite Ping-Pong Loop (max_escalation_cycles = 3 terminates to USER_OVERRIDE)
3. Persistent Advisor Failure Deadlock (max_consultation_failures = 2 terminates to USER_OVERRIDE)
4. Raw JSON & Code Leakage (_sanitize_text strips all code blocks, raw JSON dicts, error objects)
5. Passive Actions False Strikes (WAIT, DONE, HOTKEY exempt from visual diff checks)
6. Grounded Capability Contract Loopholes (explicit bans against CLI scraping and programmatic UIA patterns)
7. Code Block Syntax Integrity and Mangled Patch Leftovers in phase_4_master_plan.md
"""

from __future__ import annotations

import ast
import re
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import pytest
from pydantic import BaseModel, Field

MASTER_PLAN_PATH = Path(r"c:\Users\Suici\.gemini\antigravity\brain\464b4ef0-398b-45b1-94dc-857256a38046\phase_4_master_plan.md")


# ---------------------------------------------------------------------------
# Reference Implementations directly extracted from phase_4_master_plan.md
# ---------------------------------------------------------------------------

class CadenceTier(str, Enum):
    TIER_1_LOCAL = "TIER_1_LOCAL"
    TIER_2_CONSULT = "TIER_2_CONSULT"
    TIER_3_GUIDED = "TIER_3_GUIDED"
    TIER_4_CO_PILOT = "TIER_4_CO_PILOT"
    USER_OVERRIDE = "USER_OVERRIDE"


class ActionType(str, Enum):
    CLICK = "CLICK"
    DOUBLE_CLICK = "DOUBLE_CLICK"
    RIGHT_CLICK = "RIGHT_CLICK"
    CLICK_AND_TYPE = "CLICK_AND_TYPE"
    TYPE = "TYPE"
    HOTKEY = "HOTKEY"
    SCROLL = "SCROLL"
    WAIT = "WAIT"
    PANIC = "PANIC"
    OFFLOAD_WEB_AI = "OFFLOAD_WEB_AI"
    DONE = "DONE"
    RUN_CLI_COMMAND = "RUN_CLI_COMMAND"


class MasterPlanEscalationStateMachine(BaseModel):
    """Clean representation of Section 3.3 in phase_4_master_plan.md."""
    current_tier: CadenceTier = Field(default=CadenceTier.TIER_1_LOCAL)
    local_strikes: int = Field(default=0, ge=0)
    guided_strikes: int = Field(default=0, ge=0)
    copilot_strikes: int = Field(default=0, ge=0)
    consultation_failures: int = Field(default=0, ge=0)
    total_escalation_cycles: int = Field(default=0, ge=0)
    max_escalation_cycles: int = Field(default=3, description="Maximum T3->T4 escalation cycles before user override.")
    max_consultation_failures: int = Field(default=2, description="Maximum consecutive advisor failures before user override.")

    def on_action_result(
        self,
        success: bool,
        screen_diff: float = 0.0,
        action_type: Optional[ActionType] = None,
        is_interactive: bool = True,
        cli_returncode: Optional[int] = None,
        diff_threshold: float = 0.02,
    ) -> CadenceTier:
        # Category 1: Headless CLI actions
        if action_type == ActionType.RUN_CLI_COMMAND:
            effective_success = success and (cli_returncode == 0 if cli_returncode is not None else True)

        # Category 2: Passive / Non-visual actions (WAIT, DONE, or explicit is_interactive=False)
        elif action_type in (ActionType.WAIT, ActionType.DONE) or not is_interactive:
            if success:
                return self.current_tier
            effective_success = False

        # Category 3: Interactive GUI actions
        else:
            effective_success = success and (screen_diff >= diff_threshold)

        if self.current_tier == CadenceTier.TIER_1_LOCAL:
            if effective_success:
                self.local_strikes = 0
            else:
                self.local_strikes += 1
                if self.local_strikes >= 2:
                    self.current_tier = CadenceTier.TIER_2_CONSULT

        elif self.current_tier == CadenceTier.TIER_3_GUIDED:
            if effective_success:
                self.guided_strikes = 0
            else:
                self.guided_strikes += 1
                if self.guided_strikes >= 2:
                    self.total_escalation_cycles += 1
                    if self.total_escalation_cycles >= self.max_escalation_cycles:
                        self.current_tier = CadenceTier.USER_OVERRIDE
                    else:
                        self.current_tier = CadenceTier.TIER_4_CO_PILOT
                        self.copilot_strikes = 0

        elif self.current_tier == CadenceTier.TIER_4_CO_PILOT:
            if effective_success:
                self.copilot_strikes = 0
                self.guided_strikes = 0
                self.current_tier = CadenceTier.TIER_3_GUIDED
            else:
                self.copilot_strikes += 1
                if self.copilot_strikes >= 3:
                    self.current_tier = CadenceTier.USER_OVERRIDE

        return self.current_tier

    def on_consultation_success(self) -> None:
        if self.current_tier == CadenceTier.TIER_2_CONSULT:
            self.local_strikes = 0
            self.guided_strikes = 0
            self.consultation_failures = 0
            self.current_tier = CadenceTier.TIER_3_GUIDED

    def on_consultation_failure(self) -> None:
        if self.current_tier == CadenceTier.TIER_2_CONSULT:
            self.consultation_failures += 1
            if self.consultation_failures >= self.max_consultation_failures:
                self.current_tier = CadenceTier.USER_OVERRIDE
            else:
                self.local_strikes = 0
                self.current_tier = CadenceTier.TIER_1_LOCAL

    def on_hardware_interrupt(self) -> None:
        self.current_tier = CadenceTier.USER_OVERRIDE


class MasterPlanDualChannelRouter:
    """Clean representation of Section 5.2 in phase_4_master_plan.md."""
    def __init__(self, bridge: Optional[Any] = None, persona_engine: Optional[Any] = None):
        self.bridge = bridge
        self.persona_engine = persona_engine

    def route_consultation_output(
        self,
        raw_advisor_text: str,
        user_goal: str,
        active_plan: Any,
    ) -> Tuple[Optional[Any], str]:
        from parasite_ai.mind.plan import extract_strategic_blueprint_json, parse_gemini_consultation_response

        # Channel A: Extract machine blueprint supporting both 'steps' and 'recommended_strategy' keys
        blueprint_json = extract_strategic_blueprint_json(raw_advisor_text)
        has_steps = blueprint_json and (
            ("steps" in blueprint_json and bool(blueprint_json["steps"]))
            or ("recommended_strategy" in blueprint_json and bool(blueprint_json["recommended_strategy"]))
        )

        if has_steps:
            try:
                updated_plan = parse_gemini_consultation_response(raw_advisor_text, user_goal)
                raw_rationale = blueprint_json.get("rationale") or blueprint_json.get("overall_strategy", "")
            except Exception:
                updated_plan = None
                raw_rationale = ""
        else:
            updated_plan = None
            raw_rationale = ""

        # Channel B: Translate into character monologue
        persona_speech = self.translate_to_persona_voice(
            raw_rationale=raw_rationale,
            updated_plan=updated_plan,
            user_goal=user_goal
        )

        if self.bridge and hasattr(self.bridge, "notify_speech"):
            self.bridge.notify_speech(persona_speech)

        return updated_plan, persona_speech

    def translate_to_persona_voice(
        self,
        raw_rationale: str,
        updated_plan: Optional[Any],
        user_goal: str
    ) -> str:
        clean_text = self._sanitize_text(raw_rationale)

        if updated_plan and hasattr(updated_plan, "steps") and updated_plan.steps:
            first_step = updated_plan.steps[0]
            return f"Gemini suggested we try {first_step.description.lower()}. Let's give that a shot!"
        elif "modal" in clean_text.lower():
            return "Looks like an unexpected dialog popped up. Let me dismiss it so we can keep going."
        elif clean_text and not any(kw in clean_text.lower() for kw in ("error:", "exception", "resource_exhausted")):
            return clean_text[:140]
        else:
            return "I've re-evaluated our plan. Moving to the next step now!"

    @staticmethod
    def _sanitize_text(text: str) -> str:
        if not text:
            return ""
        # Strip all markdown code blocks (```python, ```json, ```bash, etc.)
        text = re.sub(r"```[\w]*[\s\S]*?```", "", text)
        # Strip inline backticks and code snippets
        text = re.sub(r"`[^`]*`", "", text)
        # Strip curly braces, brackets, quotes
        text = re.sub(r"[{}\[\]\"]", "", text)
        # Strip coordinate pairs and dimensions
        text = re.sub(r"\b\d+x\d+\b", "", text)
        text = re.sub(r"\(\d+,\s*\d+\)", "", text)
        return " ".join(text.split()).strip()


# ---------------------------------------------------------------------------
# Tests: Adversarial Re-Verification
# ---------------------------------------------------------------------------

class TestChallenger1Iter2Verification:

    def test_reverify_vulnerability_1_blueprint_hydration(self):
        """Re-verify that DualChannelRouter explicitly checks both 'recommended_strategy' and 'steps'."""
        router = MasterPlanDualChannelRouter()
        from parasite_ai.mind.plan import LivingPlan

        # Case A: Standard format using 'recommended_strategy'
        raw_rec_strategy = """```json
{
  "rationale": "Modal popup is blocking focus.",
  "recommended_strategy": [
    {
      "step_id": 1,
      "intent": "DISMISS_DIALOG",
      "description": "Press Escape to dismiss modal",
      "success_criteria": "Modal closes"
    }
  ]
}
```"""
        plan_a, speech_a = router.route_consultation_output(
            raw_rec_strategy, "Dismiss modal", LivingPlan(user_goal="Dismiss modal")
        )
        assert plan_a is not None, "FAILED: Router dropped blueprint with 'recommended_strategy' key!"
        assert len(plan_a.steps) == 1
        assert "press escape" in speech_a.lower()

        # Case B: Schema format using 'steps'
        raw_steps = """```json
{
  "rationale": "Target button is located at #4.",
  "steps": [
    {
      "step_id": 1,
      "intent": "CLICK_ELEMENT",
      "description": "Click button #4",
      "success_criteria": "Window opens"
    }
  ]
}
```"""
        plan_b, speech_b = router.route_consultation_output(
            raw_steps, "Click button", LivingPlan(user_goal="Click button")
        )
        assert plan_b is not None, "FAILED: Router dropped blueprint with 'steps' key!"
        assert len(plan_b.steps) == 1
        assert "click button #4" in speech_b.lower()

    def test_reverify_vulnerability_2_infinite_ping_pong_loop(self):
        """Re-verify that max_escalation_cycles = 3 terminates to USER_OVERRIDE."""
        sm = MasterPlanEscalationStateMachine(max_escalation_cycles=3)
        sm.current_tier = CadenceTier.TIER_3_GUIDED

        cycles = 0
        while sm.current_tier != CadenceTier.USER_OVERRIDE:
            # 2 failures in Tier 3
            sm.on_action_result(success=False, screen_diff=0.0)
            sm.on_action_result(success=False, screen_diff=0.0)
            if sm.current_tier == CadenceTier.USER_OVERRIDE:
                break
            assert sm.current_tier == CadenceTier.TIER_4_CO_PILOT

            # In Tier 4, one micro-action succeeds
            sm.on_action_result(success=True, screen_diff=0.05)
            assert sm.current_tier == CadenceTier.TIER_3_GUIDED
            cycles += 1
            assert cycles <= 5, "Deadlock: total_escalation_cycles failed to terminate!"

        assert sm.current_tier == CadenceTier.USER_OVERRIDE
        assert sm.total_escalation_cycles == 3

    def test_reverify_vulnerability_3_persistent_advisor_failure(self):
        """Re-verify that max_consultation_failures = 2 terminates to USER_OVERRIDE."""
        sm = MasterPlanEscalationStateMachine(max_consultation_failures=2)

        # Attempt 1
        sm.on_action_result(success=False, screen_diff=0.0)
        sm.on_action_result(success=False, screen_diff=0.0)
        assert sm.current_tier == CadenceTier.TIER_2_CONSULT
        sm.on_consultation_failure()
        assert sm.current_tier == CadenceTier.TIER_1_LOCAL
        assert sm.consultation_failures == 1
        assert sm.local_strikes == 0

        # Attempt 2
        sm.on_action_result(success=False, screen_diff=0.0)
        sm.on_action_result(success=False, screen_diff=0.0)
        assert sm.current_tier == CadenceTier.TIER_2_CONSULT
        sm.on_consultation_failure()
        assert sm.current_tier == CadenceTier.USER_OVERRIDE, "FAILED: Persistent advisor outage did not escalate to USER_OVERRIDE!"

    def test_reverify_vulnerability_4_speech_sanitization_and_error_shield(self):
        """Re-verify that _sanitize_text and translate_to_persona_voice eliminate all code blocks and errors."""
        router = MasterPlanDualChannelRouter()

        # Check Python code blocks
        py_snippet = "Try this script:\n```python\nimport sys\nprint(sys.version)\n```\nIt will work."
        clean_py = router._sanitize_text(py_snippet)
        assert "```" not in clean_py
        assert "import sys" not in clean_py
        assert "print(sys.version)" not in clean_py
        assert "Try this script: It will work." == clean_py

        # Check Bash code blocks
        bash_snippet = "Run this command:\n```bash\npytest tests/\n```\nTo verify."
        clean_bash = router._sanitize_text(bash_snippet)
        assert "```" not in clean_bash
        assert "pytest tests/" not in clean_bash
        assert "Run this command: To verify." == clean_bash

        # Check backticks
        bt_snippet = "Click `Save As...` then enter `doc.txt`"
        clean_bt = router._sanitize_text(bt_snippet)
        assert "`" not in clean_bt
        assert "Save As..." not in clean_bt

        # Check raw JSON error object suppression in persona speech
        error_json = '{"error": "RESOURCE_EXHAUSTED", "code": 429, "details": "Rate limit exceeded"}'
        plan, speech = router.route_consultation_output(error_json, "Process file", None)
        assert plan is None
        assert "RESOURCE_EXHAUSTED" not in speech
        assert "429" not in speech
        assert "error:" not in speech.lower()
        assert "{" not in speech and "}" not in speech
        assert "I've re-evaluated our plan. Moving to the next step now!" == speech

    def test_reverify_vulnerability_5_passive_and_cli_actions_strike_exemption(self):
        """Re-verify that WAIT, DONE, and CLI commands are exempt from visual diff checks."""
        sm = MasterPlanEscalationStateMachine()

        # WAIT action with diff = 0.0
        sm.on_action_result(success=True, screen_diff=0.0, action_type=ActionType.WAIT)
        assert sm.local_strikes == 0, "WAIT action falsely incurred a failure strike!"

        # DONE action with diff = 0.0
        sm.on_action_result(success=True, screen_diff=0.0, action_type=ActionType.DONE)
        assert sm.local_strikes == 0, "DONE action falsely incurred a failure strike!"

        # Non-visual hotkey (e.g. Ctrl+C) with is_interactive=False and diff = 0.0
        sm.on_action_result(success=True, screen_diff=0.0, action_type=ActionType.HOTKEY, is_interactive=False)
        assert sm.local_strikes == 0, "Non-visual hotkey falsely incurred a failure strike!"

        # Headless CLI command with returncode=0 and diff = 0.0
        sm.on_action_result(
            success=True, screen_diff=0.0, action_type=ActionType.RUN_CLI_COMMAND, cli_returncode=0
        )
        assert sm.local_strikes == 0, "CLI action with returncode=0 falsely incurred a failure strike!"

        # Headless CLI command failure with returncode=1
        sm.on_action_result(
            success=True, screen_diff=0.0, action_type=ActionType.RUN_CLI_COMMAND, cli_returncode=1
        )
        assert sm.local_strikes == 1, "CLI action with returncode=1 failed to incur a strike!"

    def test_reverify_vulnerability_6_grounded_contract_explicit_bans(self):
        """Re-verify explicit bans against CLI scraping and programmatic UIA patterns in contract."""
        content = MASTER_PLAN_PATH.read_text(encoding="utf-8")

        # Headless scraping bans
        assert "ZERO headless scraping" in content
        assert "curl" in content and "playwright" in content and "requests" in content and "selenium" in content

        # Programmatic UIA pattern bans
        assert "ZERO programmatic accessibility pattern invocation" in content
        assert "ValuePattern.SetValue" in content and "InvokePattern.Invoke" in content
        assert "read-only for element discovery" in content

        # Virtual desktop bounds dynamic specification
        assert "Dynamic via get_virtual_screen_bounds()" in content

    def test_detect_mangled_patch_leftover_in_section_5_2(self):
        """
        EMPIRICAL DEFECT TEST:
        Checks whether Section 5.2 contains mangled patch leftover:
        ```json[\\s\\S]*?```", "", text)
        """
        content = MASTER_PLAN_PATH.read_text(encoding="utf-8")
        stray = '```json[\\s\\S]*?```", "", text)'
        found = stray in content
        print(f"\n[AUDIT] Mangled patch leftover in Section 5.2: {found}")
        assert not found, (
            "DEFECT DETECTED: Section 5.2 (around line 579) contains mangled patch leftover: "
            "'```json[\\s\\S]*?```\", \"\", text)' causing duplicate code and broken markdown code block."
        )

    def test_detect_escaped_docstring_syntax_errors_in_master_plan(self):
        """
        EMPIRICAL DEFECT TEST:
        Checks whether master plan code blocks contain literal escaped docstrings (\\\"\\\"\\\")
        which violate Python syntax and produce SyntaxError on parsing.
        """
        content = MASTER_PLAN_PATH.read_text(encoding="utf-8")
        escaped_docstring = chr(92) + chr(34) + chr(92) + chr(34) + chr(92) + chr(34)
        count = content.count(escaped_docstring)
        print(f"\n[AUDIT] Literal escaped docstring occurrences (\\\"\\\"\\\"): {count}")
        assert count == 0, (
            f"DEFECT DETECTED: Found {count} occurrences of literal \\\"\\\"\\\" in Python code snippets "
            f"in phase_4_master_plan.md. These cause SyntaxError when parsed."
        )
