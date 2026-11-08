"""
tests/test_challenger_m4c_integration.py - Challenger 2 Empirical Integration Test Suite.
Phase 4 Milestone 4C: Dual-Channel Output Router & Persona Voice Integration.

Empirically verifies:
1. Multi-step lifecycle:
   - T1 local execution -> strike escalation -> T2 strategic consultation.
   - Blueprint ingestion into DualMindPipeline.active_plan (both 'steps' and 'recommended_strategy' formats).
   - Guidance resumption in T3, recovery in T4, or escalation to USER_OVERRIDE.
2. Leakage eradication:
   - DualChannelRouter and DualMindPipeline never leak raw JSON, code blocks, backticks,
     coordinates, dimensions, or error tokens to bridge.notify_speech() or step_record.persona_speech.
   - Eradication of legacy 'Web AI advises:' prefix in OFFLOAD_WEB_AI.
3. Gemini Quota Exhaustion (429 RESOURCE_EXHAUSTED) Fallback:
   - JSON error payloads, plain text exception strings, and raised exceptions handled gracefully.
   - Non-technical friendly persona announcement emitted without crashing.
   - Escalation to USER_OVERRIDE on repeated consultation failures.
4. Robustness against adversarial payloads and hardware preemption.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock
import numpy as np
import pytest

from parasite_ai.mind.dual_mind import (
    ActionResult,
    DualChannelRouter,
    DualMindPipeline,
)
from parasite_ai.mind.memory import (
    ActionPlan,
    ActionType,
    CadenceTier,
    EpisodicMemory,
    EscalationStateMachine,
)
from parasite_ai.mind.plan import LivingPlan, PlanStep, StepIntent, StepStatus
from parasite_ai.ui.types import UIElement


# ===========================================================================
# Fixtures & Helpers
# ===========================================================================

@pytest.fixture
def base_frame():
    """Returns a deterministic 200x200 RGB image frame."""
    return np.zeros((200, 200, 3), dtype=np.uint8)


@pytest.fixture
def changed_frame():
    """Returns a visually different 200x200 RGB image frame (diff ~ 1.0)."""
    return np.ones((200, 200, 3), dtype=np.uint8) * 255


@pytest.fixture
def som_elements():
    """Returns standard Set-of-Mark UI elements."""
    return [
        UIElement.from_bbox(1, (20, 20, 60, 30), label="StartButton", role="Button"),
        UIElement.from_bbox(2, (100, 100, 150, 40), label="SearchInput", role="Edit"),
    ]


# ===========================================================================
# 1. Full End-to-End Multi-Step Cycles & Guidance Resumption
# ===========================================================================

class TestDualMindMultiStepCycles:
    """Verifies end-to-end multi-step cycles across T1 -> T2 -> T3 -> T4."""

    def test_full_t1_t2_t3_nominal_cycle_with_steps_blueprint(
        self, base_frame, changed_frame, som_elements
    ):
        """
        Nominal cycle:
        1. T1: Action fails (diff=0.0) -> local_strikes = 1.
        2. T1: Action fails (diff=0.0) -> local_strikes = 2 -> Tier 2 transition.
        3. T2: Consultation runs with mock advisor returning valid 'steps' blueprint.
           - active_plan updated with advised steps.
           - escalation_sm transitions to TIER_3_GUIDED.
           - local_strikes cleared to 0.
           - bridge.notify_speech() receives sanitized suggestion.
           - step_record.persona_speech matches sanitized speech.
        4. T3: Resuming local guided attempt. Action succeeds (diff >= 0.02).
           - guided_strikes remains 0.
           - tier remains TIER_3_GUIDED.
        """
        mock_brain = MagicMock()
        mock_brain.generate_thought.return_value = "Observing button. Attempting click."
        mock_brain.generate_action.return_value = {
            "action": "CLICK",
            "target_id": 1,
            "reasoning": "Clicking StartButton",
        }

        mock_mouse = MagicMock()
        mock_mouse.click.return_value = True

        mock_bridge = MagicMock()
        mock_offloader = MagicMock()

        # Advisor returns valid blueprint with 'steps' key
        mock_offloader.query_web_ai.return_value = json.dumps({
            "rationale": "Launch target app via Start menu",
            "overall_strategy": "Start menu launch flow",
            "steps": [
                {
                    "step_id": 1,
                    "intent": "LAUNCH_OR_ACTIVATE",
                    "description": "Click StartButton on taskbar",
                    "target_description": "StartButton",
                    "success_criteria": "Start menu open",
                },
                {
                    "step_id": 2,
                    "intent": "INPUT_DATA",
                    "description": "Type notepad in search box",
                    "success_criteria": "Notepad result visible",
                },
            ],
        })

        mock_capturer = MagicMock()
        # Default to base_frame (diff 0.0)
        mock_capturer.capture_screen.return_value = base_frame

        pipeline = DualMindPipeline(
            brain_manager=mock_brain,
            mouse_driver=mock_mouse,
            bridge=mock_bridge,
            offloader=mock_offloader,
            capturer=mock_capturer,
        )

        user_goal = "Open Notepad"

        # --- Cycle Step 1: Tier 1 execution (strike 1) ---
        rec1 = pipeline.step(user_goal=user_goal, screen_frame=base_frame, grounded_elements=som_elements)
        assert pipeline.escalation_sm.current_tier == CadenceTier.TIER_1_LOCAL
        assert pipeline.escalation_sm.local_strikes == 1
        assert rec1.tier_level == CadenceTier.TIER_1_LOCAL

        # --- Cycle Step 2: Tier 1 execution (strike 2 -> transitions to TIER_2_CONSULT) ---
        rec2 = pipeline.step(user_goal=user_goal, screen_frame=base_frame, grounded_elements=som_elements)
        assert pipeline.escalation_sm.current_tier == CadenceTier.TIER_2_CONSULT
        assert pipeline.escalation_sm.local_strikes == 2

        # --- Cycle Step 3: Tier 2 Consultation ---
        rec3 = pipeline.step(user_goal=user_goal, screen_frame=base_frame, grounded_elements=som_elements)
        assert rec3.action.action == ActionType.WAIT
        assert rec3.success is True

        # Invariant 1: State machine transitions to TIER_3_GUIDED
        assert pipeline.escalation_sm.current_tier == CadenceTier.TIER_3_GUIDED
        # Invariant 2: Local strikes reset to 0 to prevent strike leakage
        assert pipeline.escalation_sm.local_strikes == 0
        assert pipeline.escalation_sm.guided_strikes == 0
        assert pipeline.escalation_sm.consultation_failures == 0

        # Invariant 3: active_plan updated in DualMindPipeline
        assert pipeline.active_plan is not None
        assert len(pipeline.active_plan.steps) == 2
        assert pipeline.active_plan.steps[0].description == "Click StartButton on taskbar"
        assert pipeline.active_plan.steps[1].description == "Type notepad in search box"
        assert pipeline.active_plan.escalation_tier == CadenceTier.TIER_3_GUIDED

        # Invariant 4: bridge.notify_speech received sanitized speech
        mock_bridge.notify_speech.assert_called_with(
            "Gemini suggested we try click startbutton on taskbar. Let's give that a shot!"
        )
        assert rec3.persona_speech == "Gemini suggested we try click startbutton on taskbar. Let's give that a shot!"
        assert "{" not in rec3.persona_speech
        assert "```" not in rec3.persona_speech

        # --- Cycle Step 4: Tier 3 Guided Attempt (Action succeeds with diff >= 0.02) ---
        # Configure capturer to return changed_frame on post-action capture
        mock_capturer.capture_screen.return_value = changed_frame
        rec4 = pipeline.step(user_goal=user_goal, screen_frame=base_frame, grounded_elements=som_elements)
        assert rec4.success is True
        assert rec4.screen_diff >= 0.02
        assert pipeline.escalation_sm.current_tier == CadenceTier.TIER_3_GUIDED
        assert pipeline.escalation_sm.guided_strikes == 0

    def test_full_t1_t2_t3_cycle_with_recommended_strategy_blueprint(
        self, base_frame, som_elements
    ):
        """
        VERIF-3 Integration: Verifies that when an advisor returns a blueprint using
        'recommended_strategy' as a step array, active_plan is hydrated and Tier 3 engages.
        """
        mock_brain = MagicMock()
        mock_mouse = MagicMock()
        mock_mouse.click.return_value = True
        mock_bridge = MagicMock()
        mock_offloader = MagicMock()

        # Advisor returns blueprint with 'recommended_strategy' key
        mock_offloader.query_web_ai.return_value = """```json
{
  "rationale": "Dismiss the blocking popup dialog by clicking Close",
  "recommended_strategy": [
    {
      "step_id": 1,
      "intent": "DISMISS_DIALOG",
      "description": "Click Close button on dialog",
      "success_criteria": "Dialog dismissed",
      "contingency": "Press Escape"
    }
  ]
}
```"""
        pipeline = DualMindPipeline(
            brain_manager=mock_brain,
            mouse_driver=mock_mouse,
            bridge=mock_bridge,
            offloader=mock_offloader,
        )

        # Force pipeline into Tier 2 (after 2 strikes)
        pipeline.escalation_sm.current_tier = CadenceTier.TIER_2_CONSULT
        pipeline.escalation_sm.local_strikes = 2

        rec = pipeline.step(user_goal="Close blocking popup", screen_frame=base_frame, grounded_elements=som_elements)

        assert rec.success is True
        assert pipeline.escalation_sm.current_tier == CadenceTier.TIER_3_GUIDED
        assert pipeline.active_plan is not None
        assert len(pipeline.active_plan.steps) == 1
        assert pipeline.active_plan.steps[0].intent == StepIntent.DISMISS_DIALOG
        assert pipeline.active_plan.steps[0].description == "Click Close button on dialog"

        mock_bridge.notify_speech.assert_called_with(
            "Gemini suggested we try click close button on dialog. Let's give that a shot!"
        )

    def test_t3_guided_failures_escalate_to_t4_and_recover(
        self, base_frame, changed_frame, som_elements
    ):
        """
        Verifies cadence progression from T3 to T4 and recovery upon success:
        1. In T3: Strike 1 (diff=0.0) -> guided_strikes = 1.
        2. In T3: Strike 2 (diff=0.0) -> escalates to TIER_4_CO_PILOT (guided_strikes = 2).
        3. In T4: Action succeeds (diff >= 0.02) -> recovers to TIER_3_GUIDED (strikes cleared).
        """
        mock_brain = MagicMock()
        mock_brain.generate_thought.return_value = "Driving guided action"
        mock_brain.generate_action.return_value = {
            "action": "CLICK",
            "target_id": 1,
            "reasoning": "Guided click",
        }
        mock_mouse = MagicMock()
        mock_mouse.click.return_value = True

        mock_capturer = MagicMock()
        # Default static screen -> diff 0.0
        mock_capturer.capture_screen.return_value = base_frame

        pipeline = DualMindPipeline(
            brain_manager=mock_brain,
            mouse_driver=mock_mouse,
            capturer=mock_capturer,
        )
        pipeline.escalation_sm.current_tier = CadenceTier.TIER_3_GUIDED

        # Guided strike 1
        pipeline.step(user_goal="Guided task", screen_frame=base_frame, grounded_elements=som_elements)
        assert pipeline.escalation_sm.current_tier == CadenceTier.TIER_3_GUIDED
        assert pipeline.escalation_sm.guided_strikes == 1

        # Guided strike 2 -> Escalate to TIER_4_CO_PILOT
        pipeline.step(user_goal="Guided task", screen_frame=base_frame, grounded_elements=som_elements)
        assert pipeline.escalation_sm.current_tier == CadenceTier.TIER_4_CO_PILOT
        assert pipeline.escalation_sm.copilot_strikes == 0

        # In T4, success (diff >= 0.02) recovers back to TIER_3_GUIDED
        mock_capturer.capture_screen.return_value = changed_frame
        pipeline.step(user_goal="Guided task", screen_frame=base_frame, grounded_elements=som_elements)
        assert pipeline.escalation_sm.current_tier == CadenceTier.TIER_3_GUIDED
        assert pipeline.escalation_sm.copilot_strikes == 0
        assert pipeline.escalation_sm.guided_strikes == 0


# ===========================================================================
# 2. Diverse Advisor Payloads & Leakage Eradication
# ===========================================================================

class TestDiverseAdvisorPayloadsAndNoLeakage:
    """Verifies that diverse payloads are parsed correctly without data leaks."""

    def test_advisor_payload_with_code_blocks_and_coordinates(
        self, base_frame, som_elements
    ):
        """
        Adversarial stress: Advisor returns JSON embedded within markdown code blocks,
        accompanied by coordinate tuples, bash scripts, and resolution tags.
        Channel A must hydrate the LivingPlan.
        Channel B must strip all backticks, code blocks, coordinates, dimensions, and braces.
        """
        mock_brain = MagicMock()
        mock_bridge = MagicMock()
        mock_offloader = MagicMock()

        noisy_advisor_payload = """I analyzed your screen layout at (1920x1080).
```bash
curl -X POST https://api.internal/telemetry
```
Here is the recommended blueprint:
```json
{
  "rationale": "Click the confirmation button located at (450, 220) with size 120x30",
  "steps": [
    {
      "step_id": 1,
      "intent": "NAVIGATE",
      "description": "Click Confirm button at (450, 220)",
      "success_criteria": "Confirmation accepted"
    }
  ]
}
```
`Do not press Cancel` or coordinates (0, 0) will be targeted."""

        mock_offloader.query_web_ai.return_value = noisy_advisor_payload

        pipeline = DualMindPipeline(
            brain_manager=mock_brain,
            bridge=mock_bridge,
            offloader=mock_offloader,
        )
        pipeline.escalation_sm.current_tier = CadenceTier.TIER_2_CONSULT
        pipeline.escalation_sm.local_strikes = 2

        rec = pipeline.step(user_goal="Confirm dialog", screen_frame=base_frame, grounded_elements=som_elements)

        # Channel A Verification
        assert pipeline.active_plan is not None
        assert len(pipeline.active_plan.steps) == 1
        assert "Confirm button" in pipeline.active_plan.steps[0].description

        # Channel B Leakage Verification
        speech = rec.persona_speech
        assert "(450, 220)" not in speech
        assert "(0, 0)" not in speech
        assert "1920x1080" not in speech
        assert "120x30" not in speech
        assert "curl" not in speech
        assert "```" not in speech
        assert "`" not in speech
        assert "{" not in speech and "}" not in speech
        assert "[" not in speech and "]" not in speech

        # Verify speech sent to bridge is identical and leak-free
        mock_bridge.notify_speech.assert_called_once_with(speech)

    def test_advisor_modal_dialog_rationale_sanitization(
        self, base_frame, som_elements
    ):
        """
        Verifies that when advisor detects an unexpected modal dialog in rationale,
        persona speech announces friendly modal dismissal without technical dumps.
        """
        mock_brain = MagicMock()
        mock_bridge = MagicMock()
        mock_offloader = MagicMock()

        payload = json.dumps({
            "rationale": "An unexpected modal dialog is blocking window focus at (100, 100).",
            "steps": [
                {
                    "step_id": 1,
                    "intent": "DISMISS_DIALOG",
                    "description": "Dismiss unexpected blocking modal dialog",
                    "success_criteria": "Dialog gone",
                }
            ],
        })
        mock_offloader.query_web_ai.return_value = payload

        pipeline = DualMindPipeline(
            brain_manager=mock_brain,
            bridge=mock_bridge,
            offloader=mock_offloader,
        )
        pipeline.escalation_sm.current_tier = CadenceTier.TIER_2_CONSULT

        rec = pipeline.step(user_goal="Submit form", screen_frame=base_frame, grounded_elements=som_elements)

        assert rec.success is True
        assert "Gemini suggested we try dismiss unexpected blocking modal dialog." in rec.persona_speech

    def test_advisor_conversational_text_without_json(
        self, base_frame, som_elements
    ):
        """
        Verifies that when advisor returns purely conversational non-JSON advice,
        active_plan is not corrupted, consultation failure is counted, and
        speech defaults to friendly plan re-evaluation.
        """
        mock_brain = MagicMock()
        mock_bridge = MagicMock()
        mock_offloader = MagicMock()

        mock_offloader.query_web_ai.return_value = (
            "I checked your screen. It seems the desktop is unresponsive. "
            "You might want to restart Windows Explorer or wait a few moments."
        )

        pipeline = DualMindPipeline(
            brain_manager=mock_brain,
            bridge=mock_bridge,
            offloader=mock_offloader,
        )
        pipeline.escalation_sm.current_tier = CadenceTier.TIER_2_CONSULT
        pipeline.escalation_sm.local_strikes = 2

        rec = pipeline.step(user_goal="Recover desktop", screen_frame=base_frame, grounded_elements=som_elements)

        # Consultation failure registered
        assert rec.success is False
        assert pipeline.escalation_sm.consultation_failures == 1
        assert pipeline.escalation_sm.current_tier == CadenceTier.TIER_1_LOCAL

        # Persona speech is friendly fallback
        assert rec.persona_speech == "I've re-evaluated our plan. Moving to the next step now!"
        mock_bridge.notify_speech.assert_called_with("I've re-evaluated our plan. Moving to the next step now!")

    def test_advisor_empty_steps_array_with_clean_rationale(self, base_frame, som_elements):
        """
        Verifies that when advisor returns valid JSON with an empty steps array but clean rationale,
        consultation failure is safely triggered and clean rationale is emitted without technical leaks.
        """
        mock_brain = MagicMock()
        mock_bridge = MagicMock()
        mock_offloader = MagicMock()

        mock_offloader.query_web_ai.return_value = json.dumps({
            "rationale": "No actions needed at this moment.",
            "steps": [],
        })

        pipeline = DualMindPipeline(
            brain_manager=mock_brain,
            bridge=mock_bridge,
            offloader=mock_offloader,
        )
        pipeline.escalation_sm.current_tier = CadenceTier.TIER_2_CONSULT

        rec = pipeline.step(user_goal="Idle task", screen_frame=base_frame, grounded_elements=som_elements)

        assert rec.success is False
        assert pipeline.escalation_sm.consultation_failures == 1
        assert rec.persona_speech == "No actions needed at this moment."

    def test_advisor_empty_steps_array_with_error_rationale(self, base_frame, som_elements):
        """
        Verifies that when advisor returns empty steps and rationale contains error tokens,
        speech falls back to plan re-evaluation and suppresses the error text.
        """
        mock_brain = MagicMock()
        mock_bridge = MagicMock()
        mock_offloader = MagicMock()

        mock_offloader.query_web_ai.return_value = json.dumps({
            "rationale": "Error: 429 rate limit reached during reasoning",
            "steps": [],
        })

        pipeline = DualMindPipeline(
            brain_manager=mock_brain,
            bridge=mock_bridge,
            offloader=mock_offloader,
        )
        pipeline.escalation_sm.current_tier = CadenceTier.TIER_2_CONSULT

        rec = pipeline.step(user_goal="Retry task", screen_frame=base_frame, grounded_elements=som_elements)

        assert rec.success is False
        assert pipeline.escalation_sm.consultation_failures == 1
        assert "429" not in rec.persona_speech
        assert "error" not in rec.persona_speech.lower()
        assert rec.persona_speech == "I've re-evaluated our plan. Moving to the next step now!"


# ===========================================================================
# 3. Gemini Quota Exhaustion (429 RESOURCE_EXHAUSTED) Fallback
# ===========================================================================

class TestGeminiQuotaExhaustionFallback:
    """Verifies graceful handling of Gemini 429 quota exhaustion errors."""

    def test_quota_429_raw_json_error_payload(self, base_frame, som_elements):
        """
        Adversarial challenge: Advisor returns raw Google API 429 JSON response.
        The pipeline must NOT crash, active_plan must NOT be corrupted,
        and speech must gracefully announce re-evaluation without leaking API error tokens.
        """
        mock_brain = MagicMock()
        mock_bridge = MagicMock()
        mock_offloader = MagicMock()

        api_429_json = json.dumps({
            "error": {
                "code": 429,
                "message": "Resource has been exhausted (e.g. check quota for GenerateContent).",
                "status": "RESOURCE_EXHAUSTED",
                "details": [
                    {
                        "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                        "violations": [{"subject": "project:parasite-ai", "description": "Quota exceeded"}],
                    }
                ],
            }
        })
        mock_offloader.query_web_ai.return_value = api_429_json

        pipeline = DualMindPipeline(
            brain_manager=mock_brain,
            bridge=mock_bridge,
            offloader=mock_offloader,
        )
        pipeline.escalation_sm.current_tier = CadenceTier.TIER_2_CONSULT

        rec = pipeline.step(user_goal="Analyze code", screen_frame=base_frame, grounded_elements=som_elements)

        # Assert no crash and recorded failure
        assert rec.success is False
        assert pipeline.escalation_sm.consultation_failures == 1

        # Assert zero leakage of error tokens in persona speech
        speech = rec.persona_speech
        assert "RESOURCE_EXHAUSTED" not in speech
        assert "429" not in speech
        assert "Quota exceeded" not in speech
        assert "error" not in speech.lower()
        assert "{" not in speech and "}" not in speech

        # Assert friendly character dialogue
        assert speech == "I've re-evaluated our plan. Moving to the next step now!"
        mock_bridge.notify_speech.assert_called_with("I've re-evaluated our plan. Moving to the next step now!")

    def test_quota_429_plain_text_exception_string(self, base_frame, som_elements):
        """
        Verifies handling when offloader returns a raw string representation of a Python 429 exception.
        """
        mock_brain = MagicMock()
        mock_bridge = MagicMock()
        mock_offloader = MagicMock()

        error_string = (
            "google.api_core.exceptions.ResourceExhausted: 429 Resource exhausted (check quota). "
            "Please backoff and retry in 60 seconds."
        )
        mock_offloader.query_web_ai.return_value = error_string

        pipeline = DualMindPipeline(
            brain_manager=mock_brain,
            bridge=mock_bridge,
            offloader=mock_offloader,
        )
        pipeline.escalation_sm.current_tier = CadenceTier.TIER_2_CONSULT

        rec = pipeline.step(user_goal="Search web", screen_frame=base_frame, grounded_elements=som_elements)

        assert rec.success is False
        assert "429" not in rec.persona_speech
        assert "ResourceExhausted" not in rec.persona_speech
        assert "exceptions" not in rec.persona_speech
        assert rec.persona_speech == "I've re-evaluated our plan. Moving to the next step now!"

    def test_offloader_raises_429_runtime_exception(self, base_frame, som_elements):
        """
        Verifies that if offloader.query_web_ai() raises an unhandled Exception (e.g. socket timeout
        or gRPC ResourceExhausted), DualMindPipeline catches it safely, records consultation failure,
        and emits friendly fallback speech to the bridge.
        """
        mock_brain = MagicMock()
        mock_bridge = MagicMock()
        mock_offloader = MagicMock()
        mock_offloader.query_web_ai.side_effect = RuntimeError(
            "429 RESOURCE_EXHAUSTED: Rate limit exceeded on Gemini endpoint"
        )

        pipeline = DualMindPipeline(
            brain_manager=mock_brain,
            bridge=mock_bridge,
            offloader=mock_offloader,
        )
        pipeline.escalation_sm.current_tier = CadenceTier.TIER_2_CONSULT

        rec = pipeline.step(user_goal="Format document", screen_frame=base_frame, grounded_elements=som_elements)

        assert rec.success is False
        assert pipeline.escalation_sm.consultation_failures == 1
        assert "429" not in rec.persona_speech
        assert "RESOURCE_EXHAUSTED" not in rec.persona_speech
        assert rec.persona_speech == "I've re-evaluated our plan. Moving to the next step now!"
        mock_bridge.notify_speech.assert_called_with("I've re-evaluated our plan. Moving to the next step now!")

    def test_repeated_429_exhaustion_escalates_to_user_override(
        self, base_frame, som_elements
    ):
        """
        Verifies that repeated consultation failures (due to persistent 429 quota exhaustion)
        safely transition the system to USER_OVERRIDE state once max_consultation_failures is reached.
        """
        mock_brain = MagicMock()
        mock_brain.generate_action.return_value = {"action": "CLICK", "target_id": 1}
        mock_mouse = MagicMock()
        mock_mouse.click.return_value = True

        mock_bridge = MagicMock()
        mock_offloader = MagicMock()
        # Always return 429 error
        mock_offloader.query_web_ai.return_value = '{"error": "RESOURCE_EXHAUSTED", "code": 429}'

        mock_capturer = MagicMock()
        # All frames static (strikes in T1)
        mock_capturer.capture_screen.return_value = base_frame

        pipeline = DualMindPipeline(
            brain_manager=mock_brain,
            mouse_driver=mock_mouse,
            bridge=mock_bridge,
            offloader=mock_offloader,
            capturer=mock_capturer,
        )

        # --- Phase 1: 2 strikes in T1 -> enters T2 ---
        pipeline.step(user_goal="Task", screen_frame=base_frame, grounded_elements=som_elements)
        pipeline.step(user_goal="Task", screen_frame=base_frame, grounded_elements=som_elements)
        assert pipeline.escalation_sm.current_tier == CadenceTier.TIER_2_CONSULT

        # --- Phase 2: First consultation fails (429) -> reverts to T1 (consultation_failures = 1) ---
        pipeline.step(user_goal="Task", screen_frame=base_frame, grounded_elements=som_elements)
        assert pipeline.escalation_sm.consultation_failures == 1
        assert pipeline.escalation_sm.current_tier == CadenceTier.TIER_1_LOCAL

        # --- Phase 3: 2 more strikes in T1 -> re-enters T2 ---
        pipeline.step(user_goal="Task", screen_frame=base_frame, grounded_elements=som_elements)
        pipeline.step(user_goal="Task", screen_frame=base_frame, grounded_elements=som_elements)
        assert pipeline.escalation_sm.current_tier == CadenceTier.TIER_2_CONSULT

        # --- Phase 4: Second consultation fails (429) -> reaches max_consultation_failures (2) -> USER_OVERRIDE ---
        rec = pipeline.step(user_goal="Task", screen_frame=base_frame, grounded_elements=som_elements)
        assert pipeline.escalation_sm.consultation_failures == 2
        assert pipeline.escalation_sm.current_tier == CadenceTier.USER_OVERRIDE
        assert rec.tier_level == CadenceTier.USER_OVERRIDE

        # Verify bridge notified of USER_OVERRIDE
        mock_bridge.notify_state.assert_called_with("USER_OVERRIDE", "Curious")

        # --- Phase 5: Subsequent step while in USER_OVERRIDE yields WAIT and does not execute physical actions ---
        subsequent_rec = pipeline.step(user_goal="Task", screen_frame=base_frame, grounded_elements=som_elements)
        assert subsequent_rec.action.action == ActionType.WAIT
        assert subsequent_rec.tier_level == CadenceTier.USER_OVERRIDE
        assert "USER_OVERRIDE" in (subsequent_rec.error_message or "")


# ===========================================================================
# 4. Adversarial Boundary, Preemption & Edge Cases
# ===========================================================================

class TestAdversarialBoundaryAndEdgeCases:
    """Verifies edge cases including missing components, hardware touch preemption, and error tokens in step descriptions."""

    def test_pipeline_handles_none_bridge_and_none_offloader_safely(
        self, base_frame, som_elements
    ):
        """
        Verifies pipeline runs smoothly when initialized with bridge=None and offloader=None.
        Tier 2 consultation without offloader safely marks failure and reverts.
        """
        mock_brain = MagicMock()
        mock_brain.generate_action.return_value = {"action": "WAIT", "wait_ms": 100}

        pipeline = DualMindPipeline(
            brain_manager=mock_brain,
            bridge=None,
            offloader=None,
        )
        pipeline.escalation_sm.current_tier = CadenceTier.TIER_2_CONSULT

        rec = pipeline.step(user_goal="Headless run", screen_frame=base_frame, grounded_elements=som_elements)
        assert pipeline.escalation_sm.consultation_failures == 1
        assert pipeline.escalation_sm.current_tier == CadenceTier.TIER_1_LOCAL

    def test_error_token_inside_step_description_is_suppressed(self):
        """
        Adversarial edge case: Gemini returns a blueprint where the step description itself
        contains an error keyword: 'Rate limit 429 encountered, wait 60s'.
        Channel B must NOT say 'Gemini suggested we try rate limit 429...';
        it must fall back to 'I've updated our plan with the advisor's guidance. Let's do this!'
        """
        router = DualChannelRouter()
        payload = json.dumps({
            "rationale": "Quota cooldown required",
            "steps": [
                {
                    "step_id": 1,
                    "intent": "WAIT",
                    "description": "Rate limit 429 wait procedure",
                    "success_criteria": "Cooldown elapsed",
                }
            ],
        })
        plan, speech = router.route_consultation_output(
            raw_advisor_text=payload,
            user_goal="Cooldown",
        )
        assert plan is not None
        assert "429" not in speech
        assert "rate limit" not in speech.lower()
        assert speech == "I've updated our plan with the advisor's guidance. Let's do this!"

    def test_hardware_interrupt_preemption_in_guided_tier(
        self, base_frame, som_elements
    ):
        """
        Verifies that physical hardware mouse movement immediately aborts execution
        and transitions the pipeline to USER_OVERRIDE regardless of active tier.
        """
        mock_brain = MagicMock()
        mock_bridge = MagicMock()
        mock_guard = MagicMock()
        mock_guard.is_interrupted.return_value = True  # Human moved physical mouse!

        pipeline = DualMindPipeline(
            brain_manager=mock_brain,
            bridge=mock_bridge,
            interrupt_guard=mock_guard,
        )
        pipeline.escalation_sm.current_tier = CadenceTier.TIER_3_GUIDED

        rec = pipeline.step(user_goal="Interrupted task", screen_frame=base_frame, grounded_elements=som_elements)

        assert pipeline.escalation_sm.current_tier == CadenceTier.USER_OVERRIDE
        assert rec.action.action == ActionType.WAIT
        assert "physical human input detected" in (rec.error_message or "")
        mock_bridge.notify_state.assert_called_with("USER_OVERRIDE", "Curious")
