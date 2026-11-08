"""
tests/test_escalation_cadence.py - Complete Test Suite for Milestone 4B & VERIF-1.

Validates the 4-Tier Escalation State Machine and DualMindPipeline integration:
1. Nominal 4-tier lifecycle: T1 (0-2 strikes) -> T2 (Gemini consult) -> T3 (0-2 guided strikes) -> T4 (0-3 co-pilot strikes) -> USER_OVERRIDE.
2. Action-aware strike evaluation:
   - CLI actions evaluated by returncode == 0 (screen diff bypassed).
   - Passive actions (WAIT, DONE, is_interactive=False) exempt from visual diff check (strikes unchanged).
   - Interactive GUI actions (CLICK, TYPE, SCROLL) evaluated by physical success AND localized ROI diff >= 0.02.
3. Strike resets & recovery cadence upon successful action execution.
4. Strike leakage prevention: local_strikes reset to 0 upon consultation success.
5. Loop protection counters:
   - Persistent advisor failure transitions to USER_OVERRIDE after max_consultation_failures (default 2).
   - Cumulative oscillation between T3 and T4 transitions to USER_OVERRIDE after max_escalation_cycles (default 3).
6. Hardware interrupt handler: immediate transition from ANY state to USER_OVERRIDE.
7. Integration with DualMindPipeline:
   - Full pipeline step progression across all tiers.
   - Invariant preservation: touch preemption and safe failure yielding.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from parasite_ai.mind.dual_mind import ActionResult, DualMindPipeline
from parasite_ai.mind.memory import (
    ActionPlan,
    ActionType,
    CadenceTier,
    EpisodicMemory,
    EscalationStateMachine,
    INTERACTIVE_ACTION_TYPES,
)
from parasite_ai.mind.plan import LivingPlan, PlanStep, StepIntent
from parasite_ai.ui.types import UIElement


# ===========================================================================
# 1. Unit Tests for EscalationStateMachine
# ===========================================================================

class TestEscalationStateMachineLifecycle:
    """Verifies core state transitions, strike counters, and tier progression."""

    def test_initial_state_defaults(self):
        sm = EscalationStateMachine()
        assert sm.current_tier == CadenceTier.TIER_1_LOCAL
        assert sm.local_strikes == 0
        assert sm.guided_strikes == 0
        assert sm.copilot_strikes == 0
        assert sm.consultation_failures == 0
        assert sm.total_escalation_cycles == 0
        assert sm.current_strikes == 0

    def test_nominal_progression_t1_to_t2(self):
        sm = EscalationStateMachine()
        # Strike 1 in Tier 1
        res = sm.on_action_result(success=True, screen_diff=0.01)
        assert res == CadenceTier.TIER_1_LOCAL
        assert sm.local_strikes == 1
        assert sm.current_strikes == 1

        # Strike 2 in Tier 1 -> Transition to Tier 2
        res = sm.on_action_result(success=False, screen_diff=0.0)
        assert res == CadenceTier.TIER_2_CONSULT
        assert sm.local_strikes == 2
        assert sm.current_tier == CadenceTier.TIER_2_CONSULT

    def test_consultation_success_transitions_to_tier_3_and_clears_local_strikes(self):
        sm = EscalationStateMachine()
        # Trip 2 strikes to enter Tier 2
        sm.on_action_result(success=False, screen_diff=0.0)
        sm.on_action_result(success=False, screen_diff=0.0)
        assert sm.current_tier == CadenceTier.TIER_2_CONSULT
        assert sm.local_strikes == 2

        # Advisor consultation succeeds
        sm.on_consultation_success()
        assert sm.current_tier == CadenceTier.TIER_3_GUIDED
        # Invariant: local_strikes must be cleared to 0 to prevent strike leakage
        assert sm.local_strikes == 0
        assert sm.guided_strikes == 0
        assert sm.consultation_failures == 0
        assert sm.current_strikes == 0

    def test_nominal_progression_t3_to_t4(self):
        sm = EscalationStateMachine(current_tier=CadenceTier.TIER_3_GUIDED)
        # Guided Strike 1
        res = sm.on_action_result(success=True, screen_diff=0.015)
        assert res == CadenceTier.TIER_3_GUIDED
        assert sm.guided_strikes == 1
        assert sm.current_strikes == 1

        # Guided Strike 2 -> Escalate to Tier 4
        res = sm.on_action_result(success=False, screen_diff=0.0)
        assert res == CadenceTier.TIER_4_CO_PILOT
        assert sm.guided_strikes == 2
        assert sm.copilot_strikes == 0
        assert sm.total_escalation_cycles == 1

    def test_nominal_progression_t4_to_user_override(self):
        sm = EscalationStateMachine(current_tier=CadenceTier.TIER_4_CO_PILOT)
        # Co-Pilot Strike 1
        res = sm.on_action_result(success=False, screen_diff=0.0)
        assert res == CadenceTier.TIER_4_CO_PILOT
        assert sm.copilot_strikes == 1

        # Co-Pilot Strike 2
        res = sm.on_action_result(success=False, screen_diff=0.0)
        assert res == CadenceTier.TIER_4_CO_PILOT
        assert sm.copilot_strikes == 2

        # Co-Pilot Strike 3 -> USER_OVERRIDE
        res = sm.on_action_result(success=False, screen_diff=0.0)
        assert res == CadenceTier.USER_OVERRIDE
        assert sm.copilot_strikes == 3
        assert sm.current_tier == CadenceTier.USER_OVERRIDE

    def test_copilot_success_recovers_to_tier_3(self):
        sm = EscalationStateMachine(current_tier=CadenceTier.TIER_4_CO_PILOT, copilot_strikes=2, guided_strikes=2)
        # In Tier 4, one micro-action succeeds
        res = sm.on_action_result(success=True, screen_diff=0.05, action_type=ActionType.CLICK)
        assert res == CadenceTier.TIER_3_GUIDED
        assert sm.copilot_strikes == 0
        assert sm.guided_strikes == 0
        assert sm.current_tier == CadenceTier.TIER_3_GUIDED


# ===========================================================================
# 2. Action-Aware Strike Evaluation Tests
# ===========================================================================

class TestActionAwareStrikeEvaluation:
    """Verifies that evaluation logic respects action modality (CLI vs Passive vs Interactive)."""

    def test_cli_action_success_resets_strikes_without_screen_diff(self):
        sm = EscalationStateMachine()
        # Accumulate 1 failure
        sm.on_action_result(success=False, screen_diff=0.0, action_type=ActionType.CLICK)
        assert sm.local_strikes == 1

        # Execute headless CLI action with returncode == 0 and screen_diff == 0.0
        res = sm.on_action_result(
            success=True,
            screen_diff=0.0,
            action_type=ActionType.RUN_CLI_COMMAND,
            cli_returncode=0,
        )
        assert res == CadenceTier.TIER_1_LOCAL
        # Invariant: CLI returncode 0 resets strikes even with 0.0 screen diff
        assert sm.local_strikes == 0

    def test_cli_action_failure_increments_strikes(self):
        sm = EscalationStateMachine()
        res = sm.on_action_result(
            success=True,
            screen_diff=0.0,
            action_type=ActionType.RUN_CLI_COMMAND,
            cli_returncode=1,
        )
        assert sm.local_strikes == 1

        # Second CLI failure escalates to Tier 2
        res = sm.on_action_result(
            success=False,
            screen_diff=0.0,
            action_type=ActionType.RUN_CLI_COMMAND,
            cli_returncode=127,
        )
        assert res == CadenceTier.TIER_2_CONSULT
        assert sm.local_strikes == 2

    def test_passive_action_wait_does_not_incur_strikes_on_zero_diff(self):
        sm = EscalationStateMachine()
        sm.on_action_result(success=False, screen_diff=0.0, action_type=ActionType.CLICK)
        assert sm.local_strikes == 1

        # WAIT action succeeds with 0.0 screen diff
        res = sm.on_action_result(
            success=True,
            screen_diff=0.0,
            action_type=ActionType.WAIT,
            is_interactive=False,
        )
        assert res == CadenceTier.TIER_1_LOCAL
        # Invariant: Successful passive action does NOT increment strike counter
        assert sm.local_strikes == 1

    def test_passive_action_done_does_not_incur_strikes(self):
        sm = EscalationStateMachine()
        res = sm.on_action_result(
            success=True,
            screen_diff=0.0,
            action_type=ActionType.DONE,
            is_interactive=False,
        )
        assert res == CadenceTier.TIER_1_LOCAL
        assert sm.local_strikes == 0

    def test_explicit_non_interactive_flag_exempts_from_visual_diff(self):
        sm = EscalationStateMachine()
        # Even if action_type is HOTKEY, if is_interactive=False (e.g. non-visual clipboard copy)
        res = sm.on_action_result(
            success=True,
            screen_diff=0.0,
            action_type=ActionType.HOTKEY,
            is_interactive=False,
        )
        assert sm.local_strikes == 0

    def test_interactive_gui_action_requires_diff_threshold(self):
        sm = EscalationStateMachine()
        # 1.9% diff is below 2.0% threshold -> Incurs strike
        sm.on_action_result(success=True, screen_diff=0.019, action_type=ActionType.CLICK)
        assert sm.local_strikes == 1

        # 2.0% diff meets threshold -> Resets strikes
        sm.on_action_result(success=True, screen_diff=0.020, action_type=ActionType.CLICK)
        assert sm.local_strikes == 0


# ===========================================================================
# 3. Loop Protection & Oscillation Termination Tests
# ===========================================================================

class TestLoopProtectionCounters:
    """Verifies termination of infinite T1 <-> T2 and T3 <-> T4 oscillation loops."""

    def test_persistent_advisor_failure_terminates_to_user_override(self):
        sm = EscalationStateMachine(max_consultation_failures=2)

        # Cycle 1: 2 strikes -> T2
        sm.on_action_result(success=False, screen_diff=0.0)
        sm.on_action_result(success=False, screen_diff=0.0)
        assert sm.current_tier == CadenceTier.TIER_2_CONSULT

        # Advisor failure 1 -> fallback to T1
        sm.on_consultation_failure()
        assert sm.current_tier == CadenceTier.TIER_1_LOCAL
        assert sm.consultation_failures == 1
        assert sm.local_strikes == 0

        # Cycle 2: 2 strikes -> T2 again
        sm.on_action_result(success=False, screen_diff=0.0)
        sm.on_action_result(success=False, screen_diff=0.0)
        assert sm.current_tier == CadenceTier.TIER_2_CONSULT

        # Advisor failure 2 -> Reaches max_consultation_failures (2)
        sm.on_consultation_failure()
        assert sm.current_tier == CadenceTier.USER_OVERRIDE
        assert sm.consultation_failures == 2

    def test_cumulative_t3_t4_oscillation_terminates_to_user_override(self):
        sm = EscalationStateMachine(max_escalation_cycles=3)
        sm.current_tier = CadenceTier.TIER_3_GUIDED

        # Oscillation Cycle 1:
        sm.on_action_result(success=False, screen_diff=0.0)
        sm.on_action_result(success=False, screen_diff=0.0)
        assert sm.current_tier == CadenceTier.TIER_4_CO_PILOT
        assert sm.total_escalation_cycles == 1
        # Recover via micro-success
        sm.on_action_result(success=True, screen_diff=0.05)
        assert sm.current_tier == CadenceTier.TIER_3_GUIDED

        # Oscillation Cycle 2:
        sm.on_action_result(success=False, screen_diff=0.0)
        sm.on_action_result(success=False, screen_diff=0.0)
        assert sm.current_tier == CadenceTier.TIER_4_CO_PILOT
        assert sm.total_escalation_cycles == 2
        # Recover via micro-success
        sm.on_action_result(success=True, screen_diff=0.05)
        assert sm.current_tier == CadenceTier.TIER_3_GUIDED

        # Oscillation Cycle 3:
        sm.on_action_result(success=False, screen_diff=0.0)
        res = sm.on_action_result(success=False, screen_diff=0.0)
        # Cap reached -> Transitions directly to USER_OVERRIDE!
        assert res == CadenceTier.USER_OVERRIDE
        assert sm.current_tier == CadenceTier.USER_OVERRIDE
        assert sm.total_escalation_cycles == 3


# ===========================================================================
# 4. Hardware Interrupt & Preemption Tests
# ===========================================================================

class TestHardwareInterruptHandler:
    """Verifies immediate transition to USER_OVERRIDE from all states."""

    @pytest.mark.parametrize("start_tier", [
        CadenceTier.TIER_1_LOCAL,
        CadenceTier.TIER_2_CONSULT,
        CadenceTier.TIER_3_GUIDED,
        CadenceTier.TIER_4_CO_PILOT,
    ])
    def test_hardware_interrupt_from_any_tier(self, start_tier: CadenceTier):
        sm = EscalationStateMachine(current_tier=start_tier)
        sm.on_hardware_interrupt()
        assert sm.current_tier == CadenceTier.USER_OVERRIDE

    def test_user_override_persists_across_subsequent_action_results(self):
        sm = EscalationStateMachine(current_tier=CadenceTier.USER_OVERRIDE)
        res = sm.on_action_result(success=True, screen_diff=0.10)
        assert res == CadenceTier.USER_OVERRIDE
        assert sm.current_tier == CadenceTier.USER_OVERRIDE

    def test_manual_reset(self):
        sm = EscalationStateMachine(
            current_tier=CadenceTier.USER_OVERRIDE,
            local_strikes=2,
            guided_strikes=2,
            copilot_strikes=3,
            consultation_failures=2,
            total_escalation_cycles=3,
        )
        sm.reset()
        assert sm.current_tier == CadenceTier.TIER_1_LOCAL
        assert sm.local_strikes == 0
        assert sm.guided_strikes == 0
        assert sm.copilot_strikes == 0
        assert sm.consultation_failures == 0
        assert sm.total_escalation_cycles == 0


# ===========================================================================
# 5. DualMindPipeline Integration Tests
# ===========================================================================

class TestDualMindPipelineEscalationIntegration:
    """Verifies end-to-end integration of EscalationStateMachine into DualMindPipeline."""

    def test_pipeline_local_strike_accumulation_advances_to_tier_2(self):
        mock_brain = MagicMock()
        mock_brain.generate_thought.return_value = "Trying to click button."
        mock_brain.generate_action.return_value = {"action": "CLICK", "target_id": 1}

        mock_mouse = MagicMock()
        mock_mouse.click.return_value = True

        pipeline = DualMindPipeline(
            brain_manager=mock_brain,
            mouse_driver=mock_mouse,
        )

        elements = [UIElement.from_bbox(1, (10, 10, 50, 30), label="Button", role="Button")]
        frame = np.zeros((100, 100, 3), dtype=np.uint8)

        # Step 1: Click produces 0% diff -> Strike 1
        rec1 = pipeline.step(user_goal="Click button", screen_frame=frame, grounded_elements=elements)
        assert pipeline.escalation_sm.local_strikes == 1
        assert pipeline.escalation_sm.current_tier == CadenceTier.TIER_1_LOCAL
        assert rec1.tier_level == CadenceTier.TIER_1_LOCAL

        # Step 2: Click produces 0% diff again -> Strike 2 -> Escalates to TIER_2_CONSULT!
        rec2 = pipeline.step(user_goal="Click button", screen_frame=frame, grounded_elements=elements)
        assert pipeline.escalation_sm.local_strikes == 2
        assert pipeline.escalation_sm.current_tier == CadenceTier.TIER_2_CONSULT
        assert pipeline.active_plan.escalation_tier == CadenceTier.TIER_2_CONSULT

    def test_pipeline_tier_2_consultation_success_hydrates_living_plan(self):
        mock_brain = MagicMock()
        mock_offloader = MagicMock()
        # Return structured blueprint with 'recommended_strategy'
        mock_offloader.query_web_ai.return_value = """```json
{
  "rationale": "Window needs to be activated before clicking.",
  "recommended_strategy": [
    {
      "step_id": 1,
      "intent": "NAVIGATE",
      "description": "Click title bar to focus",
      "success_criteria": "Window focused"
    }
  ]
}
```"""
        pipeline = DualMindPipeline(
            brain_manager=mock_brain,
            offloader=mock_offloader,
        )
        # Place pipeline directly into Tier 2
        pipeline.escalation_sm.current_tier = CadenceTier.TIER_2_CONSULT
        pipeline.escalation_sm.local_strikes = 2

        rec = pipeline.step(user_goal="Focus window")
        assert rec.success is True
        assert rec.action.action == ActionType.WAIT
        # Invariant: Consultation success transitions to TIER_3_GUIDED and clears local_strikes
        assert pipeline.escalation_sm.current_tier == CadenceTier.TIER_3_GUIDED
        assert pipeline.escalation_sm.local_strikes == 0
        assert pipeline.escalation_sm.guided_strikes == 0
        assert len(pipeline.active_plan.steps) == 1

    def test_pipeline_tier_2_consultation_failure_falls_back_or_overrides(self):
        mock_brain = MagicMock()
        mock_offloader = MagicMock()
        mock_offloader.query_web_ai.side_effect = TimeoutError("Connection timed out")

        pipeline = DualMindPipeline(
            brain_manager=mock_brain,
            offloader=mock_offloader,
        )
        # Attempt 1 in Tier 2
        pipeline.escalation_sm.current_tier = CadenceTier.TIER_2_CONSULT
        pipeline.escalation_sm.local_strikes = 2

        rec1 = pipeline.step(user_goal="Do work")
        assert rec1.success is False
        # Fallback to Tier 1 on attempt 1
        assert pipeline.escalation_sm.current_tier == CadenceTier.TIER_1_LOCAL
        assert pipeline.escalation_sm.consultation_failures == 1

        # Force back to Tier 2 for attempt 2
        pipeline.escalation_sm.current_tier = CadenceTier.TIER_2_CONSULT
        rec2 = pipeline.step(user_goal="Do work")
        # Attempt 2 fails -> Escalates directly to USER_OVERRIDE!
        assert pipeline.escalation_sm.current_tier == CadenceTier.USER_OVERRIDE
        assert pipeline.escalation_sm.consultation_failures == 2

    def test_pipeline_hardware_interrupt_immediately_sets_user_override(self):
        mock_interrupt_guard = MagicMock()
        mock_interrupt_guard.is_interrupted.return_value = True

        pipeline = DualMindPipeline(
            brain_manager=MagicMock(),
            interrupt_guard=mock_interrupt_guard,
        )

        rec = pipeline.step(user_goal="Test interrupt")
        assert rec.success is False
        assert "User override active" in (rec.error_message or "")
        assert pipeline.escalation_sm.current_tier == CadenceTier.USER_OVERRIDE
        assert rec.tier_level == CadenceTier.USER_OVERRIDE

    def test_pipeline_passive_action_exempt_from_strikes(self):
        mock_brain = MagicMock()
        mock_brain.generate_thought.return_value = "Just waiting."
        pipeline = DualMindPipeline(brain_manager=mock_brain)
        rec = pipeline.step(
            user_goal="Wait",
            override_action=ActionPlan(action=ActionType.WAIT, wait_ms=10, reasoning="Just wait"),
        )
        assert rec.success is True
        assert pipeline.escalation_sm.local_strikes == 0
        assert pipeline.escalation_sm.current_tier == CadenceTier.TIER_1_LOCAL

    def test_sequential_full_cadence_progression_no_premature_panic(self):
        """
        End-to-end integration test verifying complete sequential progression:
        T1 (2 strikes) -> T2 (Gemini consult success) -> T3 (2 guided strikes) -> T4 (3 co-pilot strikes) -> USER_OVERRIDE.
        Specifically verifies:
        - Strike leakage between T1 and T3 is eliminated (reset_loop_detector on consult).
        - Step 5 (second T3 guided attempt) does NOT prematurely trip ActionType.PANIC.
        - T4 co-pilot 3 strikes advance cleanly to USER_OVERRIDE.
        - Subsequent steps in USER_OVERRIDE safely yield WAIT without crashing.
        """
        import json

        mock_brain = MagicMock()
        mock_brain.generate_thought.return_value = "Attempting button click."
        mock_brain.generate_action.return_value = {"action": "CLICK", "target_id": 1}

        mock_mouse = MagicMock()
        mock_mouse.click.return_value = True

        mock_offloader = MagicMock()
        mock_offloader.query_web_ai.return_value = json.dumps({
            "rationale": "Advisor strategy blueprint",
            "steps": [
                {
                    "step_id": 1,
                    "intent": "NAVIGATE",
                    "description": "Guided action 1",
                    "success_criteria": "Action successful",
                }
            ],
        })

        pipeline = DualMindPipeline(
            brain_manager=mock_brain,
            mouse_driver=mock_mouse,
            offloader=mock_offloader,
        )

        elements = [UIElement.from_bbox(1, (10, 10, 50, 30), label="TargetBtn", role="Button")]
        frame = np.zeros((100, 100, 3), dtype=np.uint8)

        # -------------------------------------------------------------
        # Step 1: Tier 1 - Strike 1 (interactive zero-diff failure)
        # -------------------------------------------------------------
        rec1 = pipeline.step(user_goal="Test Cadence", screen_frame=frame, grounded_elements=elements)
        assert rec1.action.action == ActionType.CLICK
        assert pipeline.escalation_sm.current_tier == CadenceTier.TIER_1_LOCAL
        assert pipeline.escalation_sm.local_strikes == 1
        assert rec1.consecutive_strikes == 1

        # -------------------------------------------------------------
        # Step 2: Tier 1 - Strike 2 -> Escalates to TIER_2_CONSULT
        # -------------------------------------------------------------
        rec2 = pipeline.step(user_goal="Test Cadence", screen_frame=frame, grounded_elements=elements)
        assert rec2.action.action == ActionType.CLICK
        assert pipeline.escalation_sm.current_tier == CadenceTier.TIER_2_CONSULT
        assert pipeline.escalation_sm.local_strikes == 2
        assert rec2.consecutive_strikes == 2

        # -------------------------------------------------------------
        # Step 3: Tier 2 - Gemini Consultation -> Transitions to TIER_3_GUIDED
        # -------------------------------------------------------------
        rec3 = pipeline.step(user_goal="Test Cadence", screen_frame=frame, grounded_elements=elements)
        assert rec3.action.action == ActionType.WAIT
        assert rec3.success is True
        assert pipeline.escalation_sm.current_tier == CadenceTier.TIER_3_GUIDED
        assert pipeline.escalation_sm.local_strikes == 0
        assert pipeline.escalation_sm.guided_strikes == 0
        assert pipeline.memory.get_consecutive_strikes() == 0  # Strike leakage prevented!

        # -------------------------------------------------------------
        # Step 4: Tier 3 - Guided Strike 1
        # -------------------------------------------------------------
        rec4 = pipeline.step(user_goal="Test Cadence", screen_frame=frame, grounded_elements=elements)
        assert rec4.action.action == ActionType.CLICK
        assert rec4.action.action != ActionType.PANIC
        assert pipeline.escalation_sm.current_tier == CadenceTier.TIER_3_GUIDED
        assert pipeline.escalation_sm.guided_strikes == 1
        assert pipeline.memory.get_consecutive_strikes() == 1

        # -------------------------------------------------------------
        # Step 5: Tier 3 - Guided Strike 2 -> Escalates to TIER_4_CO_PILOT
        # Invariant: Must NOT trip legacy 3-strike PANIC abort!
        # -------------------------------------------------------------
        rec5 = pipeline.step(user_goal="Test Cadence", screen_frame=frame, grounded_elements=elements)
        assert rec5.action.action == ActionType.CLICK
        assert rec5.action.action != ActionType.PANIC, "Regression: Premature PANIC aborted Tier 3 guided step"
        assert pipeline.escalation_sm.current_tier == CadenceTier.TIER_4_CO_PILOT
        assert pipeline.escalation_sm.guided_strikes == 2
        assert pipeline.escalation_sm.copilot_strikes == 0

        # -------------------------------------------------------------
        # Step 6: Tier 4 - Co-Pilot Strike 1
        # -------------------------------------------------------------
        rec6 = pipeline.step(user_goal="Test Cadence", screen_frame=frame, grounded_elements=elements)
        assert rec6.action.action == ActionType.CLICK
        assert rec6.action.action != ActionType.PANIC
        assert pipeline.escalation_sm.current_tier == CadenceTier.TIER_4_CO_PILOT
        assert pipeline.escalation_sm.copilot_strikes == 1

        # -------------------------------------------------------------
        # Step 7: Tier 4 - Co-Pilot Strike 2
        # -------------------------------------------------------------
        rec7 = pipeline.step(user_goal="Test Cadence", screen_frame=frame, grounded_elements=elements)
        assert rec7.action.action == ActionType.CLICK
        assert rec7.action.action != ActionType.PANIC
        assert pipeline.escalation_sm.current_tier == CadenceTier.TIER_4_CO_PILOT
        assert pipeline.escalation_sm.copilot_strikes == 2

        # -------------------------------------------------------------
        # Step 8: Tier 4 - Co-Pilot Strike 3 -> Escalates to USER_OVERRIDE
        # -------------------------------------------------------------
        rec8 = pipeline.step(user_goal="Test Cadence", screen_frame=frame, grounded_elements=elements)
        assert rec8.action.action == ActionType.CLICK
        assert rec8.action.action != ActionType.PANIC
        assert pipeline.escalation_sm.current_tier == CadenceTier.USER_OVERRIDE
        assert pipeline.escalation_sm.copilot_strikes == 3

        # -------------------------------------------------------------
        # Step 9: USER_OVERRIDE Terminal State
        # Invariant: Must safely yield WAIT without infinite loop or crashing
        # -------------------------------------------------------------
        rec9 = pipeline.step(user_goal="Test Cadence", screen_frame=frame, grounded_elements=elements)
        assert pipeline.escalation_sm.current_tier == CadenceTier.USER_OVERRIDE
        assert rec9.action.action == ActionType.WAIT
        assert rec9.tier_level == CadenceTier.USER_OVERRIDE
        assert "User override active" in (rec9.error_message or "")

    def test_sequential_offloader_none_loop_termination(self):
        """
        Verifies that when offloader is None, persistent advisor consultation failure
        increments consultation_failures and cleanly terminates in USER_OVERRIDE after 2 failures,
        preventing infinite cycles between T1 and T2.
        """
        mock_brain = MagicMock()
        mock_brain.generate_thought.return_value = "Offline local thought."
        mock_brain.generate_action.return_value = {"action": "CLICK", "target_id": 1}

        mock_mouse = MagicMock()
        mock_mouse.click.return_value = True

        pipeline = DualMindPipeline(
            brain_manager=mock_brain,
            mouse_driver=mock_mouse,
            offloader=None,
        )

        elements = [UIElement.from_bbox(1, (10, 10, 50, 30), label="TargetBtn", role="Button")]
        frame = np.zeros((100, 100, 3), dtype=np.uint8)

        # Step 1: T1 Strike 1
        pipeline.step(user_goal="Offline test", screen_frame=frame, grounded_elements=elements)
        assert pipeline.escalation_sm.current_tier == CadenceTier.TIER_1_LOCAL
        assert pipeline.escalation_sm.local_strikes == 1
        assert pipeline.escalation_sm.consultation_failures == 0

        # Step 2: T1 Strike 2 -> Transitions to TIER_2_CONSULT
        pipeline.step(user_goal="Offline test", screen_frame=frame, grounded_elements=elements)
        assert pipeline.escalation_sm.current_tier == CadenceTier.TIER_2_CONSULT
        assert pipeline.escalation_sm.local_strikes == 2
        assert pipeline.escalation_sm.consultation_failures == 0

        # Step 3: T2 with offloader=None -> consultation_failure 1 -> falls back to T1 and executes action (Strike 1)
        rec3 = pipeline.step(user_goal="Offline test", screen_frame=frame, grounded_elements=elements)
        assert pipeline.escalation_sm.consultation_failures == 1
        assert pipeline.escalation_sm.local_strikes == 1
        assert pipeline.escalation_sm.current_tier == CadenceTier.TIER_1_LOCAL

        # Step 4: T1 Strike 2 -> Transitions to TIER_2_CONSULT again
        pipeline.step(user_goal="Offline test", screen_frame=frame, grounded_elements=elements)
        assert pipeline.escalation_sm.current_tier == CadenceTier.TIER_2_CONSULT
        assert pipeline.escalation_sm.local_strikes == 2
        assert pipeline.escalation_sm.consultation_failures == 1

        # Step 5: T2 with offloader=None -> consultation_failure 2 -> Transitions directly to USER_OVERRIDE!
        rec5 = pipeline.step(user_goal="Offline test", screen_frame=frame, grounded_elements=elements)
        assert pipeline.escalation_sm.consultation_failures == 2
        assert pipeline.escalation_sm.current_tier == CadenceTier.USER_OVERRIDE
        assert rec5.action.action == ActionType.WAIT

        # Subsequent steps must remain locked in USER_OVERRIDE
        for _ in range(5):
            rec = pipeline.step(user_goal="Offline test", screen_frame=frame, grounded_elements=elements)
            assert pipeline.escalation_sm.current_tier == CadenceTier.USER_OVERRIDE
            assert rec.action.action == ActionType.WAIT

