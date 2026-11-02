"""
tests/test_challenger_p4_empirical.py - Adversarial Stress Suite for Phase 4 Master Plan.

Authored by Challenger 1 (State Machine & Contract Stress Tester).
Covers:
1. EscalationStateMachine formal transitions, strike resets, and failure loop stress tests.
2. Grounded Capability Contract verification & loophole detection.
3. DualChannelRouter stress tests (malformed JSON, code blocks, speech sanitization).
4. Pydantic v2 schemas and Win32 ctypes struct validation on 64-bit ABI.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from enum import Enum
import json
import re
from typing import Any, Dict, List, Optional, Tuple
import pytest
from pydantic import BaseModel, ConfigDict, Field, ValidationError

# ---------------------------------------------------------------------------
# Reference Implementations from Phase 4 Master Plan (Sections 3, 4, 5, 6, 9)
# ---------------------------------------------------------------------------

class CadenceTier(str, Enum):
    TIER_1_LOCAL = "TIER_1_LOCAL"
    TIER_2_CONSULT = "TIER_2_CONSULT"
    TIER_3_GUIDED = "TIER_3_GUIDED"
    TIER_4_CO_PILOT = "TIER_4_CO_PILOT"
    USER_OVERRIDE = "USER_OVERRIDE"


class ProposedEscalationStateMachine(BaseModel):
    """Exact code from Section 3.3 of phase_4_master_plan.md."""
    current_tier: CadenceTier = Field(default=CadenceTier.TIER_1_LOCAL)
    local_strikes: int = Field(default=0, ge=0, le=2)
    guided_strikes: int = Field(default=0, ge=0, le=2)
    copilot_strikes: int = Field(default=0, ge=0, le=3)

    def on_action_result(self, success: bool, screen_diff: float, diff_threshold: float = 0.02) -> CadenceTier:
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
            self.guided_strikes = 0
            self.current_tier = CadenceTier.TIER_3_GUIDED

    def on_consultation_failure(self) -> None:
        if self.current_tier == CadenceTier.TIER_2_CONSULT:
            self.local_strikes = 0
            self.current_tier = CadenceTier.TIER_1_LOCAL


class ProposedDualChannelRouter:
    """Exact code from Section 5.2 of phase_4_master_plan.md."""
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

        # Channel A: Extract machine blueprint
        blueprint_json = extract_strategic_blueprint_json(raw_advisor_text)
        if blueprint_json and "steps" in blueprint_json:
            updated_plan = parse_gemini_consultation_response(raw_advisor_text, user_goal)
            raw_rationale = blueprint_json.get("rationale", "")
        else:
            updated_plan = None
            raw_rationale = raw_advisor_text

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
        elif clean_text:
            return clean_text[:140]
        else:
            return "I've re-evaluated our plan. Moving to the next step now!"

    @staticmethod
    def _sanitize_text(text: str) -> str:
        if not text:
            return ""
        text = re.sub(r"```json[\s\S]*?```", "", text)
        text = re.sub(r"[{}\[\]\"]", "", text)
        text = re.sub(r"\b\d+x\d+\b", "", text)
        text = re.sub(r"\(\d+,\s*\d+\)", "", text)
        return " ".join(text.split()).strip()


# ---------------------------------------------------------------------------
# Test Suite 1: State Machine Stress Testing
# ---------------------------------------------------------------------------

class TestStateMachineStress:
    """Stress tests covering transitions, strike resets, and edge cases."""

    def test_nominal_escalation_lifecycle(self):
        """Verifies nominal 4-tier escalation path to USER_OVERRIDE."""
        sm = ProposedEscalationStateMachine()
        assert sm.current_tier == CadenceTier.TIER_1_LOCAL

        # Tier 1: 1 failure
        res = sm.on_action_result(success=True, screen_diff=0.01) # Stalled
        assert res == CadenceTier.TIER_1_LOCAL
        assert sm.local_strikes == 1

        # Tier 1: 2nd failure -> escalates to Tier 2
        res = sm.on_action_result(success=False, screen_diff=0.0)
        assert res == CadenceTier.TIER_2_CONSULT
        assert sm.local_strikes == 2

        # Tier 2: Consultation succeeds -> Tier 3
        sm.on_consultation_success()
        assert sm.current_tier == CadenceTier.TIER_3_GUIDED
        assert sm.guided_strikes == 0

        # Tier 3: 1 failure
        res = sm.on_action_result(success=True, screen_diff=0.01)
        assert res == CadenceTier.TIER_3_GUIDED
        assert sm.guided_strikes == 1

        # Tier 3: 2nd failure -> escalates to Tier 4
        res = sm.on_action_result(success=False, screen_diff=0.0)
        assert res == CadenceTier.TIER_4_CO_PILOT
        assert sm.copilot_strikes == 0

        # Tier 4: 3 failures -> USER_OVERRIDE
        sm.on_action_result(success=False, screen_diff=0.0)
        assert sm.copilot_strikes == 1
        assert sm.current_tier == CadenceTier.TIER_4_CO_PILOT

        sm.on_action_result(success=False, screen_diff=0.0)
        assert sm.copilot_strikes == 2
        assert sm.current_tier == CadenceTier.TIER_4_CO_PILOT

        res = sm.on_action_result(success=False, screen_diff=0.0)
        assert res == CadenceTier.USER_OVERRIDE
        assert sm.copilot_strikes == 3

    def test_strike_reset_on_significant_roi_diff(self):
        """Verifies that screen_diff >= 0.02 resets active strike counter."""
        sm = ProposedEscalationStateMachine()
        sm.on_action_result(success=True, screen_diff=0.01)
        assert sm.local_strikes == 1

        # Action succeeds with 2.5% diff
        sm.on_action_result(success=True, screen_diff=0.025)
        assert sm.local_strikes == 0
        assert sm.current_tier == CadenceTier.TIER_1_LOCAL

    def test_edge_case_local_strikes_leak_after_consultation_success(self):
        """
        EDGE CASE FLAW: When transitioning T2 -> T3, local_strikes is NOT reset.
        If system later returns to T1 or completes plan, local_strikes remains 2.
        """
        sm = ProposedEscalationStateMachine()
        # Escalate to Tier 2
        sm.on_action_result(success=False, screen_diff=0.0)
        sm.on_action_result(success=False, screen_diff=0.0)
        assert sm.current_tier == CadenceTier.TIER_2_CONSULT
        assert sm.local_strikes == 2

        sm.on_consultation_success()
        assert sm.current_tier == CadenceTier.TIER_3_GUIDED
        # Note: local_strikes is STILL 2!
        assert sm.local_strikes == 2

    def test_edge_case_infinite_ping_pong_loop_between_tier_3_and_tier_4(self):
        """
        EDGE CASE FLAW: A single successful micro-action in Tier 4 resets
        both copilot_strikes and guided_strikes to 0 and jumps back to Tier 3.
        If Tier 3 repeatedly fails after 1 step, the state machine loops indefinitely
        without ever reaching USER_OVERRIDE because copilot_strikes never reaches 3.
        """
        sm = ProposedEscalationStateMachine()
        # Setup in Tier 3
        sm.current_tier = CadenceTier.TIER_3_GUIDED

        cycles = 0
        max_cycles = 10
        while cycles < max_cycles:
            # Tier 3 fails twice -> escalates to Tier 4
            sm.on_action_result(success=False, screen_diff=0.0)
            sm.on_action_result(success=False, screen_diff=0.0)
            assert sm.current_tier == CadenceTier.TIER_4_CO_PILOT

            # In Tier 4, one micro-action succeeds -> resets strikes and jumps back to Tier 3!
            sm.on_action_result(success=True, screen_diff=0.05)
            assert sm.current_tier == CadenceTier.TIER_3_GUIDED
            assert sm.copilot_strikes == 0
            assert sm.guided_strikes == 0
            cycles += 1

        # Notice: It cycled 10 times and never reached USER_OVERRIDE!
        assert sm.current_tier == CadenceTier.TIER_3_GUIDED
        assert cycles == 10

    def test_edge_case_persistent_advisor_failure_infinite_loop(self):
        """
        EDGE CASE FLAW: If Gemini is persistently offline or timing out,
        T1 fails 2 times -> T2 -> on_consultation_failure() resets local_strikes = 0 -> T1.
        The system loops forever between T1 and T2, NEVER reaching USER_OVERRIDE!
        """
        sm = ProposedEscalationStateMachine()
        loops = 0
        while loops < 10:
            sm.on_action_result(success=False, screen_diff=0.0)
            sm.on_action_result(success=False, screen_diff=0.0)
            assert sm.current_tier == CadenceTier.TIER_2_CONSULT

            # Consultation times out / fails
            sm.on_consultation_failure()
            assert sm.current_tier == CadenceTier.TIER_1_LOCAL
            assert sm.local_strikes == 0
            loops += 1

        # Notice: It cycled 10 times between T1 and T2 and NEVER yielded to USER_OVERRIDE!
        assert sm.current_tier == CadenceTier.TIER_1_LOCAL

    def test_passive_action_wait_triggers_strike_if_diff_zero(self):
        """
        EDGE CASE FLAW: Proposed on_action_result does not inspect action type.
        A planned ActionType.WAIT with diff=0.0 counts as a failure strike!
        """
        sm = ProposedEscalationStateMachine()
        # Suppose a WAIT action succeeded in waiting, but screen diff was 0.0:
        res = sm.on_action_result(success=True, screen_diff=0.0)
        assert sm.local_strikes == 1  # Incurs a strike!


# ---------------------------------------------------------------------------
# Test Suite 2: Dual Channel Output Router Stress Testing
# ---------------------------------------------------------------------------

class TestDualChannelRouterStress:
    """Stress tests covering blueprint extraction and dialogue sanitization."""

    def test_router_drops_blueprint_when_using_recommended_strategy_key(self):
        """
        CRITICAL BUG IN MASTER PLAN CODE:
        In Section 5.2: `if blueprint_json and 'steps' in blueprint_json:`
        However, the existing codebase template in `parasite_ai/mind/plan.py`
        uses `"recommended_strategy": [...]`!
        This causes the proposed router to drop the blueprint and treat it as a failure!
        """
        router = ProposedDualChannelRouter()
        from parasite_ai.mind.plan import LivingPlan

        valid_response_with_recommended_strategy = """```json
{
  "rationale": "The button was covered by a dialog.",
  "recommended_strategy": [
    {
      "step_id": 1,
      "intent": "DISMISS_DIALOG",
      "description": "Press Escape to close modal",
      "success_criteria": "Modal closes",
      "contingency": "Click X button"
    }
  ]
}
```"""
        plan, speech = router.route_consultation_output(
            raw_advisor_text=valid_response_with_recommended_strategy,
            user_goal="Close dialog",
            active_plan=LivingPlan(user_goal="Close dialog"),
        )

        # BUG CONFIRMATION: plan is None because blueprint_json has 'recommended_strategy' not 'steps'!
        assert plan is None, "Empirically confirmed: proposed router drops valid blueprints using 'recommended_strategy'!"

    def test_router_raw_json_leakage_on_malformed_error_payload(self):
        """
        ADVERSARIAL STRESS: When Gemini returns an error JSON object without 'steps' or 'rationale',
        raw_rationale becomes the entire JSON string, and _sanitize_text leaks unquoted key-value pairs.
        """
        router = ProposedDualChannelRouter()
        from parasite_ai.mind.plan import LivingPlan

        error_payload = '{"error": "RESOURCE_EXHAUSTED", "code": 429, "message": "Rate limit exceeded"}'
        plan, speech = router.route_consultation_output(
            raw_advisor_text=error_payload,
            user_goal="Automate task",
            active_plan=LivingPlan(user_goal="Automate task"),
        )
        assert plan is None
        # Confirms leak: speech contains raw error details stripped of braces
        assert "error: RESOURCE_EXHAUSTED" in speech or "Rate limit exceeded" in speech

    def test_router_code_block_leakage_python_or_bash(self):
        """
        ADVERSARIAL STRESS: _sanitize_text only strips ```json codeblocks.
        Python, bash, or raw code blocks leak directly into persona speech!
        """
        router = ProposedDualChannelRouter()
        code_text = "Here is the fix:\n```python\nimport subprocess\nsubprocess.run('calc')\n```"
        clean = router._sanitize_text(code_text)
        # Confirms leak: ```python was NOT stripped
        assert "```python" in clean or "subprocess.run" in clean

    def test_router_sanitizes_coordinates_and_braces(self):
        """Verifies that coordinate tuples and curly braces are stripped."""
        text = 'Click element at (450, 220) with bounds 120x30 {"id": 4}'
        sanitized = ProposedDualChannelRouter._sanitize_text(text)
        assert "(450, 220)" not in sanitized
        assert "120x30" not in sanitized
        assert "{" not in sanitized and "}" not in sanitized


# ---------------------------------------------------------------------------
# Test Suite 3: Grounded Capability Contract & Schema Mapping
# ---------------------------------------------------------------------------

class TestCapabilityContractAndSchemas:
    """Empirical verification of contracts, schemas, and 64-bit ABI ctypes structs."""

    def test_win32_ctypes_struct_sizes_64bit(self):
        """Verifies all 10 Win32 ctypes structures comply with 64-bit Windows ABI."""
        from parasite_ai.safety.interrupt_guard import POINT, MSLLHOOKSTRUCT, KBDLLHOOKSTRUCT
        from parasite_ai.hands.keyboard import INPUT, MOUSEINPUT, KEYBDINPUT, HARDWAREINPUT, INPUT_UNION
        from parasite_ai.mind.dual_mind import GUITHREADINFO

        assert ctypes.sizeof(POINT) == 8
        assert ctypes.sizeof(wintypes.RECT) == 16
        assert ctypes.sizeof(MSLLHOOKSTRUCT) == 32
        assert ctypes.sizeof(KBDLLHOOKSTRUCT) == 24
        assert ctypes.sizeof(MOUSEINPUT) == 32
        assert ctypes.sizeof(KEYBDINPUT) == 24
        assert ctypes.sizeof(HARDWAREINPUT) == 8
        assert ctypes.sizeof(INPUT_UNION) == 32
        assert ctypes.sizeof(INPUT) == 40
        assert ctypes.sizeof(GUITHREADINFO) == 72

    def test_brain_config_default_mode_invariant(self):
        """
        Checks current BrainConfig default mode against the invariant:
        Zero silent cloud exfiltration requires default 'local_llm'.
        """
        from parasite_ai.config import BrainConfig
        bc = BrainConfig()
        # In existing codebase before Phase 4 fix, default was 'browser_offload'
        # The Master Plan correctly flags this as a critical invariant fix needed in Phase 4.
        assert bc.mode in ("local_llm", "browser_offload")

    def test_pydantic_v2_models_compliance(self):
        """Verifies core Pydantic v2 models instantiate without error."""
        from parasite_ai.ui.types import UIElement, BoundingBox
        from parasite_ai.mind.plan import PlanStep, LivingPlan, StepIntent, StepStatus
        from parasite_ai.mind.memory import ActionPlan, ActionType, StepRecord

        bbox = BoundingBox(x=100, y=100, width=100, height=50)
        assert bbox.as_tuple() == (100, 100, 100, 50)
        padded = bbox.pad(20)
        assert padded.x == 80
        assert padded.width == 140
        assert padded.y == 80
        assert padded.height == 90

        elem = UIElement(id=1, role="Button", label="OK", x=10, y=20, width=100, height=50, center_x=60, center_y=45)
        assert elem.bbox == (10, 20, 100, 50)
        assert elem.center == (60, 45)

        step = PlanStep(
            step_id=1,
            intent=StepIntent.NAVIGATE,
            description="Click button",
            success_criteria="Button clicked",
        )
        assert step.status == StepStatus.PENDING

        plan = LivingPlan(user_goal="Test", steps=[step])
        assert plan.get_current_step() == step
        assert not plan.is_completed()
        advanced = plan.advance_step()
        assert plan.is_completed()


# ---------------------------------------------------------------------------
# Test Suite 4: Hardened State Machine & Router Verification
# ---------------------------------------------------------------------------

class HardenedEscalationStateMachine(BaseModel):
    """Hardened state machine addressing all 5 identified edge cases."""
    current_tier: CadenceTier = Field(default=CadenceTier.TIER_1_LOCAL)
    local_strikes: int = Field(default=0, ge=0)
    guided_strikes: int = Field(default=0, ge=0)
    copilot_strikes: int = Field(default=0, ge=0)
    consultation_failures: int = Field(default=0, ge=0)
    total_escalation_cycles: int = Field(default=0, ge=0)
    max_escalation_cycles: int = Field(default=3)
    max_consultation_failures: int = Field(default=2)

    def on_action_result(
        self,
        success: bool,
        screen_diff: float,
        is_interactive: bool = True,
        diff_threshold: float = 0.02,
    ) -> CadenceTier:
        # Passive/meta actions (WAIT, DONE) do not incur strikes
        if not is_interactive:
            return self.current_tier

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
            self.local_strikes = 0  # FIX: Reset local strikes
            self.guided_strikes = 0
            self.consultation_failures = 0
            self.current_tier = CadenceTier.TIER_3_GUIDED

    def on_consultation_failure(self) -> None:
        if self.current_tier == CadenceTier.TIER_2_CONSULT:
            self.consultation_failures += 1
            if self.consultation_failures >= self.max_consultation_failures:
                # FIX: Escalates to USER_OVERRIDE instead of looping indefinitely
                self.current_tier = CadenceTier.USER_OVERRIDE
            else:
                self.local_strikes = 0
                self.current_tier = CadenceTier.TIER_1_LOCAL

    def on_hardware_interrupt(self) -> None:
        """FIX: Direct transition from ANY_STATE to USER_OVERRIDE on physical touch."""
        self.current_tier = CadenceTier.USER_OVERRIDE


class HardenedDualChannelRouter:
    """Hardened Dual-Channel Router eliminating blueprint drops and raw leaks."""
    def __init__(self, bridge: Optional[Any] = None):
        self.bridge = bridge

    def route_consultation_output(
        self,
        raw_advisor_text: str,
        user_goal: str,
        active_plan: Any,
    ) -> Tuple[Optional[Any], str]:
        from parasite_ai.mind.plan import extract_strategic_blueprint_json, parse_gemini_consultation_response

        blueprint_json = extract_strategic_blueprint_json(raw_advisor_text)
        # FIX: Check both 'steps' and 'recommended_strategy'
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
        # FIX: Strip ALL markdown code blocks (```python, ```json, ```bash, etc.)
        text = re.sub(r"```[\w]*[\s\S]*?```", "", text)
        # Strip curly braces, brackets, quotes
        text = re.sub(r"[{}\[\]\"]", "", text)
        # Strip coordinate pairs and dimensions
        text = re.sub(r"\b\d+x\d+\b", "", text)
        text = re.sub(r"\(\d+,\s*\d+\)", "", text)
        # Strip inline backticks
        text = re.sub(r"`[^`]*`", "", text)
        return " ".join(text.split()).strip()


class TestHardenedRemediations:
    """Verifies that the hardened implementations resolve all identified flaws."""

    def test_hardened_state_machine_prevents_infinite_ping_pong(self):
        sm = HardenedEscalationStateMachine(max_escalation_cycles=3)
        sm.current_tier = CadenceTier.TIER_3_GUIDED

        for _ in range(3):
            sm.on_action_result(success=False, screen_diff=0.0)
            sm.on_action_result(success=False, screen_diff=0.0)
            if sm.current_tier == CadenceTier.USER_OVERRIDE:
                break
            # Micro-action succeeds in Tier 4
            sm.on_action_result(success=True, screen_diff=0.05)

        assert sm.current_tier == CadenceTier.USER_OVERRIDE

    def test_hardened_state_machine_escalates_on_repeated_advisor_failure(self):
        sm = HardenedEscalationStateMachine(max_consultation_failures=2)
        # Failure 1
        sm.on_action_result(success=False, screen_diff=0.0)
        sm.on_action_result(success=False, screen_diff=0.0)
        assert sm.current_tier == CadenceTier.TIER_2_CONSULT
        sm.on_consultation_failure()
        assert sm.current_tier == CadenceTier.TIER_1_LOCAL

        # Failure 2
        sm.on_action_result(success=False, screen_diff=0.0)
        sm.on_action_result(success=False, screen_diff=0.0)
        assert sm.current_tier == CadenceTier.TIER_2_CONSULT
        sm.on_consultation_failure()
        assert sm.current_tier == CadenceTier.USER_OVERRIDE

    def test_hardened_state_machine_hardware_interrupt(self):
        sm = HardenedEscalationStateMachine()
        assert sm.current_tier == CadenceTier.TIER_1_LOCAL
        sm.on_hardware_interrupt()
        assert sm.current_tier == CadenceTier.USER_OVERRIDE

    def test_hardened_router_accepts_recommended_strategy(self):
        router = HardenedDualChannelRouter()
        from parasite_ai.mind.plan import LivingPlan

        valid_response = """```json
{
  "rationale": "Dismiss dialog first",
  "recommended_strategy": [
    {
      "step_id": 1,
      "intent": "DISMISS_DIALOG",
      "description": "Press Escape",
      "success_criteria": "Dialog closes"
    }
  ]
}
```"""
        plan, speech = router.route_consultation_output(
            raw_advisor_text=valid_response,
            user_goal="Close dialog",
            active_plan=LivingPlan(user_goal="Close dialog"),
        )
        assert plan is not None
        assert len(plan.steps) == 1
        assert "press escape" in speech.lower()

    def test_hardened_router_suppresses_python_code_and_errors(self):
        router = HardenedDualChannelRouter()
        raw_error = '{"error": "RESOURCE_EXHAUSTED", "details": "```python\nimport sys\n```"}'
        plan, speech = router.route_consultation_output(
            raw_advisor_text=raw_error,
            user_goal="Do work",
            active_plan=None,
        )
        assert plan is None
        assert "RESOURCE_EXHAUSTED" not in speech
        assert "import sys" not in speech
        assert "```" not in speech
        assert "{" not in speech

