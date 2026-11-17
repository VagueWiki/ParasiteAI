"""
tests/test_living_plan.py - Comprehensive Unit Tests for LivingPlan & PlanStep Models.

Validates:
- StepIntent & StepStatus enum taxonomies
- PlanStep schema validation & constraint enforcement
- LivingPlan state transitions, step advancement, and contingency injection
- LivingPlan completion checks and LLM prompt context formatting
"""

import pytest
from pydantic import ValidationError

from parasite_ai.mind.plan import (
    LivingPlan,
    PlanStep,
    StepIntent,
    StepStatus,
)


class TestStepTaxonomies:
    """Verifies StepIntent and StepStatus enum behaviors."""

    def test_step_intent_all_values(self):
        expected_intents = {
            "LAUNCH_OR_ACTIVATE",
            "NAVIGATE",
            "INPUT_DATA",
            "SELECT_OPTION",
            "VERIFY_STATE",
            "DISMISS_DIALOG",
            "CONSULT_ADVISOR",
            "CONCLUDE",
        }
        actual_intents = {intent.value for intent in StepIntent}
        assert actual_intents == expected_intents
        for intent in StepIntent:
            assert isinstance(intent, str)
            assert intent == intent.value

    def test_step_status_all_values(self):
        expected_statuses = {
            "PENDING",
            "IN_PROGRESS",
            "COMPLETED",
            "SKIPPED",
            "FAILED",
        }
        actual_statuses = {status.value for status in StepStatus}
        assert actual_statuses == expected_statuses
        for status in StepStatus:
            assert isinstance(status, str)
            assert status == status.value


class TestPlanStepValidation:
    """Verifies PlanStep schema validation and serialization."""

    def test_plan_step_minimal_valid(self):
        step = PlanStep(
            step_id=1,
            intent=StepIntent.NAVIGATE,
            description="Click on the search box",
            success_criteria="Search box has cursor focus",
        )
        assert step.step_id == 1
        assert step.intent == StepIntent.NAVIGATE
        assert step.description == "Click on the search box"
        assert step.success_criteria == "Search box has cursor focus"
        assert step.target_description is None
        assert step.rationale == ""
        assert step.status == StepStatus.PENDING
        assert step.contingency is None

    def test_plan_step_full_valid(self):
        step = PlanStep(
            step_id=2,
            intent=StepIntent.INPUT_DATA,
            description="Type user query",
            target_description="Search box text element",
            success_criteria="Text 'hello' appears in search box",
            rationale="Query is required before submitting",
            status=StepStatus.IN_PROGRESS,
            contingency="If search box disappears, click refresh",
        )
        assert step.step_id == 2
        assert step.intent == StepIntent.INPUT_DATA
        assert step.target_description == "Search box text element"
        assert step.rationale == "Query is required before submitting"
        assert step.status == StepStatus.IN_PROGRESS
        assert step.contingency == "If search box disappears, click refresh"

    def test_plan_step_coerces_string_intent_and_status(self):
        step = PlanStep(
            step_id=1,
            intent="LAUNCH_OR_ACTIVATE",
            description="Open app",
            success_criteria="App visible",
            status="COMPLETED",
        )
        assert step.intent == StepIntent.LAUNCH_OR_ACTIVATE
        assert step.status == StepStatus.COMPLETED

    def test_plan_step_invalid_step_id(self):
        with pytest.raises(ValidationError):
            PlanStep(
                step_id=0,  # ge=1 violated
                intent=StepIntent.NAVIGATE,
                description="Invalid",
                success_criteria="None",
            )

        with pytest.raises(ValidationError):
            PlanStep(
                step_id=-5,
                intent=StepIntent.NAVIGATE,
                description="Negative",
                success_criteria="None",
            )

    def test_plan_step_invalid_intent(self):
        with pytest.raises(ValidationError):
            PlanStep(
                step_id=1,
                intent="DO_MAGIC_TRICK",
                description="Invalid intent",
                success_criteria="None",
            )

    def test_plan_step_serialization_roundtrip(self):
        step = PlanStep(
            step_id=3,
            intent=StepIntent.VERIFY_STATE,
            description="Check download completed",
            target_description="Download progress bar",
            success_criteria="Progress bar shows 100%",
            rationale="Ensure file exists",
            status=StepStatus.COMPLETED,
            contingency="Retry download if failed",
        )
        dumped = step.model_dump()
        reconstructed = PlanStep.model_validate(dumped)
        assert reconstructed == step
        assert reconstructed.model_dump_json() == step.model_dump_json()


class TestLivingPlanOperations:
    """Verifies LivingPlan state management, advancement, and mutation."""

    @pytest.fixture
    def sample_plan(self):
        steps = [
            PlanStep(
                step_id=1,
                intent=StepIntent.LAUNCH_OR_ACTIVATE,
                description="Launch Notepad",
                success_criteria="Notepad window appears",
                status=StepStatus.IN_PROGRESS,
            ),
            PlanStep(
                step_id=2,
                intent=StepIntent.INPUT_DATA,
                description="Type introduction text",
                success_criteria="Introduction typed in editor",
                status=StepStatus.PENDING,
            ),
            PlanStep(
                step_id=3,
                intent=StepIntent.CONCLUDE,
                description="Task complete",
                success_criteria="Done",
                status=StepStatus.PENDING,
            ),
        ]
        return LivingPlan(
            user_goal="Open notepad and type intro",
            overall_strategy="Launch editor then write content",
            steps=steps,
            current_step_id=1,
        )

    def test_initial_plan_state(self, sample_plan):
        assert sample_plan.user_goal == "Open notepad and type intro"
        assert sample_plan.overall_strategy == "Launch editor then write content"
        assert len(sample_plan.steps) == 3
        assert sample_plan.current_step_id == 1
        assert sample_plan.replan_count == 0
        assert not sample_plan.consulted_gemini

    def test_get_current_step(self, sample_plan):
        current = sample_plan.get_current_step()
        assert current is not None
        assert current.step_id == 1
        assert current.intent == StepIntent.LAUNCH_OR_ACTIVATE

        sample_plan.current_step_id = 999
        assert sample_plan.get_current_step() is None

    def test_advance_step_sequential(self, sample_plan):
        # Initial step 1 is IN_PROGRESS
        # Advance 1 -> 2
        next_step = sample_plan.advance_step()
        assert next_step is not None
        assert next_step.step_id == 2
        assert next_step.status == StepStatus.IN_PROGRESS
        assert sample_plan.current_step_id == 2
        assert sample_plan.steps[0].status == StepStatus.COMPLETED

        # Advance 2 -> 3
        next_step_2 = sample_plan.advance_step()
        assert next_step_2 is not None
        assert next_step_2.step_id == 3
        assert next_step_2.status == StepStatus.IN_PROGRESS
        assert sample_plan.current_step_id == 3
        assert sample_plan.steps[1].status == StepStatus.COMPLETED

        # Advance 3 -> None (finished)
        next_step_3 = sample_plan.advance_step()
        assert next_step_3 is None
        assert sample_plan.steps[2].status == StepStatus.COMPLETED
        assert sample_plan.is_completed()

    def test_advance_step_empty_plan(self):
        plan = LivingPlan(user_goal="Empty task")
        assert plan.advance_step() is None
        assert not plan.is_completed()

    def test_mark_step_failed_current(self, sample_plan):
        sample_plan.mark_step_failed(reason="Window did not launch")
        current = sample_plan.get_current_step()
        assert current.status == StepStatus.FAILED
        assert "Failure: Window did not launch" in current.contingency
        assert not sample_plan.is_completed()

    def test_mark_step_failed_specific_step(self, sample_plan):
        sample_plan.steps[1].contingency = "Initial contingency"
        sample_plan.mark_step_failed(step_id=2, reason="Timeout waiting for input")
        assert sample_plan.steps[1].status == StepStatus.FAILED
        assert "Initial contingency" in sample_plan.steps[1].contingency
        assert "Timeout waiting for input" in sample_plan.steps[1].contingency

    def test_insert_contingency_step(self, sample_plan):
        # Current step is step 1
        contingency_step = PlanStep(
            step_id=101,
            intent=StepIntent.DISMISS_DIALOG,
            description="Dismiss unexpected update prompt",
            success_criteria="Update prompt closed",
            status=StepStatus.PENDING,
        )

        sample_plan.insert_contingency_step(contingency_step)

        assert sample_plan.replan_count == 1
        assert len(sample_plan.steps) == 4
        # Verify it was inserted immediately after current step (index 1)
        assert sample_plan.steps[1].step_id == 101

        # Advance step should now transition to the contingency step
        next_step = sample_plan.advance_step()
        assert next_step is not None
        assert next_step.step_id == 101
        assert next_step.status == StepStatus.IN_PROGRESS
        assert sample_plan.current_step_id == 101

        # Next advance transitions to original step 2
        after_contingency = sample_plan.advance_step()
        assert after_contingency is not None
        assert after_contingency.step_id == 2
        assert sample_plan.current_step_id == 2

    def test_is_completed(self, sample_plan):
        assert not sample_plan.is_completed()

        sample_plan.steps[0].status = StepStatus.COMPLETED
        sample_plan.steps[1].status = StepStatus.SKIPPED
        sample_plan.steps[2].status = StepStatus.COMPLETED
        assert sample_plan.is_completed()

        # If any step is FAILED, is_completed must be False
        sample_plan.steps[1].status = StepStatus.FAILED
        assert not sample_plan.is_completed()

    def test_to_prompt_context_formatting(self, sample_plan):
        context = sample_plan.to_prompt_context()
        assert "Goal: Open notepad and type intro" in context
        assert "Strategy: Launch editor then write content" in context
        assert "Plan Progress (Active Step: 1):" in context
        assert "[→] Step 1: LAUNCH_OR_ACTIVATE" in context
        assert "[ ] Step 2: INPUT_DATA" in context

        # After step 1 completed, check checkmark
        sample_plan.advance_step()
        updated_context = sample_plan.to_prompt_context()
        assert "[✓] Step 1: LAUNCH_OR_ACTIVATE" in updated_context
        assert "[→] Step 2: INPUT_DATA" in updated_context
