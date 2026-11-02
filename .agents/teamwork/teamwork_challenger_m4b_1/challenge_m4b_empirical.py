r"""
C:\ParasiteAI\.agents\teamwork\teamwork_challenger_m4b_1\challenge_m4b_empirical.py
Empirical Challenger Test Suite for Milestone 4B: 4-Tier Escalation State Machine.

Adversarial Stress Testing:
1. Exact strike transitions: T1->T2 on 2, T3->T4 on 2, T4->USER_OVERRIDE on 3.
2. Exact boundary tests for diff_threshold (0.01999 vs 0.02000).
3. Loop protection counters: 2 advisor failures -> USER_OVERRIDE, 3 escalation cycles -> USER_OVERRIDE.
4. Action modality strike exemptions: passive actions (WAIT, DONE), CLI actions (returncode 0 vs != 0).
5. Strike leakage prevention: local_strikes, guided_strikes, copilot_strikes isolation.
6. Hardware interrupt immediate preemption from every tier.
7. End-to-end DualMindPipeline integration and LivingPlan state synchronization.
8. Randomized invariant fuzzing (1000 trials).
9. Pydantic v2 schema serialization / deserialization roundtrip.
"""

from __future__ import annotations

import random
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
# 1. Exact Strike Transitions & Strict Threshold Boundaries
# ===========================================================================

class TestExactStrikeTransitions:
    """Empirically stress-tests strike counting and exact threshold transitions."""

    def test_tier_1_to_tier_2_exact_boundary(self):
        sm = EscalationStateMachine()
        assert sm.current_tier == CadenceTier.TIER_1_LOCAL
        assert sm.local_strikes == 0

        # Attempt 1: Interactive failure (diff below 0.02)
        tier = sm.on_action_result(success=True, screen_diff=0.019999, action_type=ActionType.CLICK)
        assert tier == CadenceTier.TIER_1_LOCAL
        assert sm.local_strikes == 1
        assert sm.current_strikes == 1

        # Near miss: diff of exactly 0.020000 MUST reset strike to 0
        tier = sm.on_action_result(success=True, screen_diff=0.020000, action_type=ActionType.CLICK)
        assert tier == CadenceTier.TIER_1_LOCAL
        assert sm.local_strikes == 0
        assert sm.current_strikes == 0

        # Re-accumulate strike 1
        tier = sm.on_action_result(success=False, screen_diff=0.05, action_type=ActionType.CLICK)
        assert sm.local_strikes == 1
        assert sm.current_tier == CadenceTier.TIER_1_LOCAL

        # Accumulate strike 2 -> MUST transition to TIER_2_CONSULT
        tier = sm.on_action_result(success=True, screen_diff=0.015, action_type=ActionType.CLICK)
        assert tier == CadenceTier.TIER_2_CONSULT
        assert sm.current_tier == CadenceTier.TIER_2_CONSULT
        assert sm.local_strikes == 2

    def test_tier_3_to_tier_4_exact_boundary(self):
        sm = EscalationStateMachine(current_tier=CadenceTier.TIER_3_GUIDED)
        assert sm.guided_strikes == 0

        # Guided Strike 1: failure
        tier = sm.on_action_result(success=True, screen_diff=0.01999, action_type=ActionType.CLICK)
        assert tier == CadenceTier.TIER_3_GUIDED
        assert sm.guided_strikes == 1
        assert sm.current_strikes == 1

        # Near miss: diff of 0.021000 resets guided_strikes to 0
        tier = sm.on_action_result(success=True, screen_diff=0.021000, action_type=ActionType.CLICK)
        assert tier == CadenceTier.TIER_3_GUIDED
        assert sm.guided_strikes == 0

        # Guided Strike 1 again
        sm.on_action_result(success=False, screen_diff=0.0, action_type=ActionType.CLICK)
        assert sm.guided_strikes == 1

        # Guided Strike 2 -> MUST advance to TIER_4_CO_PILOT and record cycle 1
        tier = sm.on_action_result(success=True, screen_diff=0.005, action_type=ActionType.CLICK)
        assert tier == CadenceTier.TIER_4_CO_PILOT
        assert sm.current_tier == CadenceTier.TIER_4_CO_PILOT
        assert sm.guided_strikes == 2
        assert sm.copilot_strikes == 0
        assert sm.total_escalation_cycles == 1

    def test_tier_4_to_user_override_exact_boundary(self):
        sm = EscalationStateMachine(current_tier=CadenceTier.TIER_4_CO_PILOT)
        assert sm.copilot_strikes == 0

        # Co-Pilot Strike 1
        tier = sm.on_action_result(success=False, screen_diff=0.0, action_type=ActionType.CLICK)
        assert tier == CadenceTier.TIER_4_CO_PILOT
        assert sm.copilot_strikes == 1
        assert sm.current_strikes == 1

        # Co-Pilot Strike 2
        tier = sm.on_action_result(success=True, screen_diff=0.01, action_type=ActionType.CLICK)
        assert tier == CadenceTier.TIER_4_CO_PILOT
        assert sm.copilot_strikes == 2
        assert sm.current_strikes == 2

        # Co-Pilot Strike 3 -> MUST transition to USER_OVERRIDE
        tier = sm.on_action_result(success=False, screen_diff=0.0, action_type=ActionType.CLICK)
        assert tier == CadenceTier.USER_OVERRIDE
        assert sm.current_tier == CadenceTier.USER_OVERRIDE
        assert sm.copilot_strikes == 3

    def test_copilot_micro_action_success_recovery(self):
        sm = EscalationStateMachine(
            current_tier=CadenceTier.TIER_4_CO_PILOT,
            copilot_strikes=2,
            guided_strikes=2,
        )
        # Micro-action succeeds with 4% diff
        tier = sm.on_action_result(success=True, screen_diff=0.04, action_type=ActionType.CLICK)
        assert tier == CadenceTier.TIER_3_GUIDED
        assert sm.current_tier == CadenceTier.TIER_3_GUIDED
        assert sm.copilot_strikes == 0
        assert sm.guided_strikes == 0


# ===========================================================================
# 2. Loop Protection & Oscillation Cap Verification
# ===========================================================================

class TestLoopProtectionCounters:
    """Empirically stress-tests infinite loop termination conditions."""

    def test_advisor_failure_cap_exactly_two_attempts(self):
        sm = EscalationStateMachine(max_consultation_failures=2)

        # Trigger Tier 2
        sm.on_action_result(success=False, screen_diff=0.0)
        sm.on_action_result(success=False, screen_diff=0.0)
        assert sm.current_tier == CadenceTier.TIER_2_CONSULT

        # Advisor Failure 1
        sm.on_consultation_failure()
        assert sm.current_tier == CadenceTier.TIER_1_LOCAL
        assert sm.consultation_failures == 1
        assert sm.local_strikes == 0

        # Trigger Tier 2 again
        sm.on_action_result(success=False, screen_diff=0.0)
        sm.on_action_result(success=False, screen_diff=0.0)
        assert sm.current_tier == CadenceTier.TIER_2_CONSULT

        # Advisor Failure 2 -> Cap reached -> Immediate USER_OVERRIDE
        sm.on_consultation_failure()
        assert sm.current_tier == CadenceTier.USER_OVERRIDE
        assert sm.consultation_failures == 2

    def test_advisor_consultation_success_resets_failure_counter(self):
        sm = EscalationStateMachine(max_consultation_failures=2)

        # Fail once
        sm.current_tier = CadenceTier.TIER_2_CONSULT
        sm.on_consultation_failure()
        assert sm.consultation_failures == 1
        assert sm.current_tier == CadenceTier.TIER_1_LOCAL

        # Return to Tier 2
        sm.current_tier = CadenceTier.TIER_2_CONSULT
        # This time consultation succeeds
        sm.on_consultation_success()
        assert sm.current_tier == CadenceTier.TIER_3_GUIDED
        assert sm.consultation_failures == 0
        assert sm.local_strikes == 0

    def test_escalation_cycle_cap_exactly_three_oscillations(self):
        sm = EscalationStateMachine(max_escalation_cycles=3)
        sm.current_tier = CadenceTier.TIER_3_GUIDED

        # --- Cycle 1 ---
        sm.on_action_result(success=False, screen_diff=0.0)
        sm.on_action_result(success=False, screen_diff=0.0)
        assert sm.current_tier == CadenceTier.TIER_4_CO_PILOT
        assert sm.total_escalation_cycles == 1
        # Co-pilot recovers
        sm.on_action_result(success=True, screen_diff=0.05)
        assert sm.current_tier == CadenceTier.TIER_3_GUIDED
        assert sm.total_escalation_cycles == 1  # Invariant: cycle count NOT reset

        # --- Cycle 2 ---
        sm.on_action_result(success=False, screen_diff=0.0)
        sm.on_action_result(success=False, screen_diff=0.0)
        assert sm.current_tier == CadenceTier.TIER_4_CO_PILOT
        assert sm.total_escalation_cycles == 2
        # Co-pilot recovers
        sm.on_action_result(success=True, screen_diff=0.05)
        assert sm.current_tier == CadenceTier.TIER_3_GUIDED
        assert sm.total_escalation_cycles == 2

        # --- Cycle 3 (Final) ---
        sm.on_action_result(success=False, screen_diff=0.0)
        assert sm.current_tier == CadenceTier.TIER_3_GUIDED
        assert sm.guided_strikes == 1

        # Second failure in Cycle 3 -> MUST transition directly to USER_OVERRIDE (bypassing T4!)
        tier = sm.on_action_result(success=False, screen_diff=0.0)
        assert tier == CadenceTier.USER_OVERRIDE
        assert sm.current_tier == CadenceTier.USER_OVERRIDE
        assert sm.total_escalation_cycles == 3

    def test_stress_infinite_ping_pong_loop_mathematically_impossible(self):
        """Stress tests that no sequence of micro-successes can bypass the cycle cap."""
        sm = EscalationStateMachine(max_escalation_cycles=3)
        sm.current_tier = CadenceTier.TIER_3_GUIDED

        actions_executed = 0
        while sm.current_tier != CadenceTier.USER_OVERRIDE and actions_executed < 100:
            actions_executed += 1
            if sm.current_tier == CadenceTier.TIER_3_GUIDED:
                # Always fail in Tier 3
                sm.on_action_result(success=False, screen_diff=0.0)
            elif sm.current_tier == CadenceTier.TIER_4_CO_PILOT:
                # Always succeed in Tier 4 to attempt an infinite loop
                sm.on_action_result(success=True, screen_diff=0.10)

        # Invariant: Must terminate at USER_OVERRIDE in finite steps
        assert sm.current_tier == CadenceTier.USER_OVERRIDE
        assert sm.total_escalation_cycles == 3
        # In fact, exactly 2 failures * 3 cycles = 6 failures in T3 + 2 successes in T4 = 8 actions total
        assert actions_executed == 8


# ===========================================================================
# 3. Action Modality Strike Exemptions & Boundary Matrix
# ===========================================================================

class TestActionModalityMatrix:
    """Stress tests action-aware strike evaluation across all action modalities."""

    @pytest.mark.parametrize("tier", [CadenceTier.TIER_1_LOCAL, CadenceTier.TIER_3_GUIDED])
    def test_cli_returncode_zero_bypasses_visual_diff(self, tier: CadenceTier):
        sm = EscalationStateMachine(current_tier=tier)
        # Incur 1 strike first
        sm.on_action_result(success=False, screen_diff=0.0, action_type=ActionType.CLICK)
        assert sm.current_strikes == 1

        # CLI command succeeds with returncode 0 and 0.0 visual diff
        res = sm.on_action_result(
            success=True,
            screen_diff=0.0,
            action_type=ActionType.RUN_CLI_COMMAND,
            cli_returncode=0,
        )
        assert res == tier
        # Invariant: Strike counter MUST be reset to 0
        assert sm.current_strikes == 0

    @pytest.mark.parametrize("bad_rc", [1, 2, 127, 255, -1])
    def test_cli_non_zero_returncode_incurs_strike(self, bad_rc: int):
        sm = EscalationStateMachine(current_tier=CadenceTier.TIER_1_LOCAL)
        res = sm.on_action_result(
            success=True,
            screen_diff=0.0,
            action_type=ActionType.RUN_CLI_COMMAND,
            cli_returncode=bad_rc,
        )
        assert res == CadenceTier.TIER_1_LOCAL
        assert sm.local_strikes == 1

    def test_cli_execution_failure_with_rc_zero_incurs_strike(self):
        """Even if rc=0, if physical subprocess timed out or failed (success=False), incur strike."""
        sm = EscalationStateMachine(current_tier=CadenceTier.TIER_1_LOCAL)
        res = sm.on_action_result(
            success=False,
            screen_diff=0.0,
            action_type=ActionType.RUN_CLI_COMMAND,
            cli_returncode=0,
        )
        assert res == CadenceTier.TIER_1_LOCAL
        assert sm.local_strikes == 1

    @pytest.mark.parametrize("passive_type", [ActionType.WAIT, ActionType.DONE])
    def test_passive_action_zero_diff_does_not_increment_or_reset_strikes(self, passive_type: ActionType):
        sm = EscalationStateMachine(current_tier=CadenceTier.TIER_1_LOCAL)
        # Establish 1 strike
        sm.on_action_result(success=False, screen_diff=0.0, action_type=ActionType.CLICK)
        assert sm.local_strikes == 1

        # Execute passive action with 0.0 diff
        res = sm.on_action_result(
            success=True,
            screen_diff=0.0,
            action_type=passive_type,
            is_interactive=False,
        )
        assert res == CadenceTier.TIER_1_LOCAL
        # Invariant: Strike counter must remain completely untouched (still 1)
        assert sm.local_strikes == 1

    def test_passive_action_failure_incurs_strike(self):
        sm = EscalationStateMachine(current_tier=CadenceTier.TIER_1_LOCAL)
        res = sm.on_action_result(
            success=False,
            screen_diff=0.0,
            action_type=ActionType.WAIT,
            is_interactive=False,
        )
        assert res == CadenceTier.TIER_1_LOCAL
        assert sm.local_strikes == 1

    def test_explicit_is_interactive_false_exempts_visual_diff(self):
        sm = EscalationStateMachine(current_tier=CadenceTier.TIER_1_LOCAL)
        sm.on_action_result(success=False, screen_diff=0.0, action_type=ActionType.CLICK)
        assert sm.local_strikes == 1

        # Non-visual clipboard HOTKEY (e.g. Ctrl+C)
        res = sm.on_action_result(
            success=True,
            screen_diff=0.0,
            action_type=ActionType.HOTKEY,
            is_interactive=False,
        )
        assert res == CadenceTier.TIER_1_LOCAL
        assert sm.local_strikes == 1

    def test_interactive_action_diff_below_threshold_incurs_strike(self):
        sm = EscalationStateMachine(current_tier=CadenceTier.TIER_1_LOCAL)
        # 1.9999% diff with threshold 0.02
        res = sm.on_action_result(
            success=True,
            screen_diff=0.019999,
            action_type=ActionType.CLICK,
            diff_threshold=0.02,
        )
        assert sm.local_strikes == 1


# ===========================================================================
# 4. Strike Leakage Prevention Tests
# ===========================================================================

class TestStrikeLeakagePrevention:
    """Verifies strict isolation between local, guided, and copilot strike counters."""

    def test_consultation_success_clears_local_strikes(self):
        sm = EscalationStateMachine()
        # Accumulate 2 local strikes -> TIER_2_CONSULT
        sm.on_action_result(success=False, screen_diff=0.0)
        sm.on_action_result(success=False, screen_diff=0.0)
        assert sm.current_tier == CadenceTier.TIER_2_CONSULT
        assert sm.local_strikes == 2

        # Invariant: Consultation success MUST zero out local_strikes
        sm.on_consultation_success()
        assert sm.current_tier == CadenceTier.TIER_3_GUIDED
        assert sm.local_strikes == 0
        assert sm.guided_strikes == 0
        assert sm.current_strikes == 0

    def test_consultation_failure_attempt_one_clears_local_strikes(self):
        sm = EscalationStateMachine()
        sm.on_action_result(success=False, screen_diff=0.0)
        sm.on_action_result(success=False, screen_diff=0.0)
        assert sm.current_tier == CadenceTier.TIER_2_CONSULT
        assert sm.local_strikes == 2

        # Failure attempt 1 -> falls back to Tier 1
        sm.on_consultation_failure()
        assert sm.current_tier == CadenceTier.TIER_1_LOCAL
        # Invariant: local_strikes MUST be reset to 0 for a fresh 2-attempt budget
        assert sm.local_strikes == 0
        assert sm.consultation_failures == 1

    def test_t4_micro_recovery_clears_guided_and_copilot_strikes(self):
        sm = EscalationStateMachine(
            current_tier=CadenceTier.TIER_4_CO_PILOT,
            copilot_strikes=2,
            guided_strikes=2,
            local_strikes=0,
        )
        # Micro action succeeds
        sm.on_action_result(success=True, screen_diff=0.05, action_type=ActionType.CLICK)
        assert sm.current_tier == CadenceTier.TIER_3_GUIDED
        assert sm.copilot_strikes == 0
        assert sm.guided_strikes == 0
        assert sm.local_strikes == 0


# ===========================================================================
# 5. Hardware Interrupt & Preemption from Every Tier
# ===========================================================================

class TestHardwareInterruptPreemption:
    """Verifies instant preemption to USER_OVERRIDE from all states."""

    @pytest.mark.parametrize("starting_tier", [
        CadenceTier.TIER_1_LOCAL,
        CadenceTier.TIER_2_CONSULT,
        CadenceTier.TIER_3_GUIDED,
        CadenceTier.TIER_4_CO_PILOT,
        CadenceTier.USER_OVERRIDE,
    ])
    def test_hardware_interrupt_immediately_sets_user_override(self, starting_tier: CadenceTier):
        sm = EscalationStateMachine(current_tier=starting_tier)
        sm.on_hardware_interrupt()
        assert sm.current_tier == CadenceTier.USER_OVERRIDE

    def test_actions_locked_after_user_override(self):
        sm = EscalationStateMachine(current_tier=CadenceTier.USER_OVERRIDE)
        for diff in [0.0, 0.05, 0.50, 1.0]:
            for success in [True, False]:
                res = sm.on_action_result(success=success, screen_diff=diff)
                assert res == CadenceTier.USER_OVERRIDE
                assert sm.current_tier == CadenceTier.USER_OVERRIDE

    def test_manual_reset_returns_to_clean_tier_1(self):
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
        assert sm.current_strikes == 0


# ===========================================================================
# 6. End-to-End DualMindPipeline Integration Empirical Tests
# ===========================================================================

class TestDualMindPipelineIntegrationEmpirical:
    """Empirical testing of pipeline execution and LivingPlan synchronization."""

    def test_pipeline_full_lifecycle_progression(self):
        mock_brain = MagicMock()
        mock_brain.generate_thought.return_value = "Thinking..."
        mock_brain.generate_action.return_value = {"action": "CLICK", "target_id": 1}

        mock_mouse = MagicMock()
        mock_mouse.click.return_value = True

        mock_offloader = MagicMock()
        mock_offloader.query_web_ai.return_value = """{
            "rationale": "Advisor plan",
            "steps": [
                {"step_id": 1, "intent": "LAUNCH_OR_ACTIVATE", "description": "Launch App", "success_criteria": "App opened"}
            ]
        }"""

        pipeline = DualMindPipeline(
            brain_manager=mock_brain,
            mouse_driver=mock_mouse,
            offloader=mock_offloader,
        )

        elements = [UIElement.from_bbox(1, (10, 10, 50, 30), label="Target", role="Button")]
        frame = np.zeros((100, 100, 3), dtype=np.uint8)

        # 1. Step 1 in T1: Failure 1
        rec1 = pipeline.step(user_goal="Test", screen_frame=frame, grounded_elements=elements)
        assert pipeline.escalation_sm.current_tier == CadenceTier.TIER_1_LOCAL
        assert pipeline.escalation_sm.local_strikes == 1
        assert pipeline.active_plan.escalation_tier == CadenceTier.TIER_1_LOCAL
        assert pipeline.active_plan.tier_strikes == 1

        # 2. Step 2 in T1: Failure 2 -> Escalates to TIER_2_CONSULT
        rec2 = pipeline.step(user_goal="Test", screen_frame=frame, grounded_elements=elements)
        assert pipeline.escalation_sm.current_tier == CadenceTier.TIER_2_CONSULT
        assert pipeline.escalation_sm.local_strikes == 2
        assert pipeline.active_plan.escalation_tier == CadenceTier.TIER_2_CONSULT
        # In TIER_2_CONSULT, current_strikes represents consultation_failures (starts at 0)
        assert pipeline.active_plan.tier_strikes == pipeline.escalation_sm.current_strikes
        assert pipeline.escalation_sm.current_strikes == 0

        # 3. Step 3: Enters Tier 2 -> queries offloader -> parses blueprint -> enters TIER_3_GUIDED
        rec3 = pipeline.step(user_goal="Test", screen_frame=frame, grounded_elements=elements)
        assert rec3.success is True
        assert pipeline.escalation_sm.current_tier == CadenceTier.TIER_3_GUIDED
        assert pipeline.escalation_sm.local_strikes == 0
        assert pipeline.escalation_sm.guided_strikes == 0
        assert pipeline.active_plan.escalation_tier == CadenceTier.TIER_3_GUIDED
        assert pipeline.active_plan.tier_strikes == 0

    def test_pipeline_cli_action_execution_modalities(self):
        mock_brain = MagicMock()
        mock_brain.generate_thought.return_value = "Run command"
        pipeline = DualMindPipeline(brain_manager=mock_brain)

        # 1. CLI command with returncode == 0
        cli_action_ok = ActionPlan(action=ActionType.RUN_CLI_COMMAND, cli_command="echo hello")
        with patch.object(pipeline.action_dispatcher, "dispatch") as mock_dispatch:
            mock_dispatch.return_value = ActionResult(success=True, returncode=0, action_executed=cli_action_ok)
            rec = pipeline.step(user_goal="Echo", override_action=cli_action_ok)
            assert rec.success is True
            assert pipeline.escalation_sm.local_strikes == 0

        # 2. CLI command with returncode == 1 -> incurs strike
        cli_action_fail = ActionPlan(action=ActionType.RUN_CLI_COMMAND, cli_command="exit 1")
        with patch.object(pipeline.action_dispatcher, "dispatch") as mock_dispatch:
            mock_dispatch.return_value = ActionResult(success=True, returncode=1, action_executed=cli_action_fail)
            rec = pipeline.step(user_goal="Fail", override_action=cli_action_fail)
            assert pipeline.escalation_sm.local_strikes == 1


# ===========================================================================
# 7. Randomized Invariant Fuzzing (1,000 Iterations)
# ===========================================================================

class TestRandomizedFuzzingInvariants:
    """Stress tests state machine integrity across 1,000 pseudo-random actions."""

    def test_fuzz_1000_actions_invariants_hold(self):
        random.seed(42)
        sm = EscalationStateMachine()
        actions = list(ActionType)

        for i in range(1000):
            # If in USER_OVERRIDE, randomly reset 50% of the time to keep fuzzing
            if sm.current_tier == CadenceTier.USER_OVERRIDE:
                if random.random() < 0.5:
                    sm.reset()
                else:
                    # Verify override invariant persists
                    res = sm.on_action_result(
                        success=random.choice([True, False]),
                        screen_diff=random.uniform(0.0, 1.0),
                    )
                    assert res == CadenceTier.USER_OVERRIDE
                    continue

            # If in TIER_2_CONSULT, simulate advisor query outcome
            if sm.current_tier == CadenceTier.TIER_2_CONSULT:
                if random.random() < 0.7:
                    sm.on_consultation_success()
                else:
                    sm.on_consultation_failure()
                continue

            # Otherwise, evaluate an action result
            act = random.choice(actions)
            is_interactive = act in INTERACTIVE_ACTION_TYPES
            success = random.random() < 0.6
            screen_diff = random.uniform(0.0, 0.1)
            cli_rc = random.choice([0, 1, 2, None]) if act == ActionType.RUN_CLI_COMMAND else None

            # Occasionally simulate a hardware interrupt (5% chance)
            if random.random() < 0.05:
                sm.on_hardware_interrupt()
                assert sm.current_tier == CadenceTier.USER_OVERRIDE
                continue

            tier = sm.on_action_result(
                success=success,
                screen_diff=screen_diff,
                action_type=act,
                is_interactive=is_interactive,
                cli_returncode=cli_rc,
                diff_threshold=0.02,
            )

            # Assert universal invariants
            assert tier in CadenceTier
            assert sm.local_strikes >= 0
            assert sm.guided_strikes >= 0
            assert sm.copilot_strikes >= 0
            assert sm.consultation_failures >= 0
            assert sm.total_escalation_cycles <= sm.max_escalation_cycles
            assert sm.current_strikes >= 0


# ===========================================================================
# 8. Pydantic v2 Schema Roundtrip Serialization
# ===========================================================================

class TestStateSerialization:
    """Verifies that EscalationStateMachine serializes and deserializes cleanly without loss."""

    def test_pydantic_roundtrip_all_states(self):
        for tier in CadenceTier:
            sm = EscalationStateMachine(
                current_tier=tier,
                local_strikes=1,
                guided_strikes=1,
                copilot_strikes=2,
                consultation_failures=1,
                total_escalation_cycles=2,
            )
            raw_json = sm.model_dump_json()
            restored = EscalationStateMachine.model_validate_json(raw_json)
            assert restored.current_tier == sm.current_tier
            assert restored.local_strikes == sm.local_strikes
            assert restored.guided_strikes == sm.guided_strikes
            assert restored.copilot_strikes == sm.copilot_strikes
            assert restored.consultation_failures == sm.consultation_failures
            assert restored.total_escalation_cycles == sm.total_escalation_cycles
            assert restored.current_strikes == sm.current_strikes
