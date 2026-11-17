"""
tests/test_tool_aware_reasoning.py - Automated Unit & Integration Tests for Tool-Aware Reasoning (VERIF-4).

Tests:
1. Canvas and native drawing context routing (Priority Rule 1: PHYSICAL_GUI, confidence 0.95).
2. Application launch verbs routing to UniversalAppResolver (Priority Rule 2: PHYSICAL_GUI, confidence 0.92).
3. Deterministic code, test, and file operations (Priority Rule 3: LOCAL_DEVELOPER_TOOL, confidence 0.95).
4. Strategic advisor cognitive deadlock heuristics (STRATEGIC_ADVISOR, confidence 0.90).
5. Default desktop interactions fallback (PHYSICAL_GUI, confidence 0.75).
6. DualMindPipeline integration: tool_route attribution in LivingPlan steps and evaluate_goal_affordance().
"""

from __future__ import annotations

import pytest

from parasite_ai.mind.affordance import (
    ActionAffordance,
    AffordanceAssessment,
    AffordanceEvaluator,
)
from parasite_ai.mind.dual_mind import DualMindPipeline
from parasite_ai.mind.plan import StepIntent


class TestToolAwareAffordanceEvaluator:
    """Tests for AffordanceEvaluator heuristic routing rules."""

    # -----------------------------------------------------------------------
    # Priority Rule 1: Graphical Canvas & Native Drawing Context
    # -----------------------------------------------------------------------

    @pytest.mark.parametrize(
        "goal,active_window",
        [
            ("Draw a blue circle on canvas", ""),
            ("Sketch a diagram in Paint", ""),
            ("Use Photoshop to crop picture", ""),
            ("Draw a red line with the brush tool", ""),
            ("GIMP photo touchup", ""),
            ("Save drawing to canvas", "Canvas Editor"),
            ("Create file new_sketch.png", "Untitled - Paint"),  # Rule 1 overrides code keyword "create file"
            ("Refactor diagram", "Adobe Photoshop 2024"),         # Rule 1 overrides code keyword "refactor"
        ],
    )
    def test_canvas_and_drawing_routes_to_physical_gui(self, goal: str, active_window: str):
        assessment = AffordanceEvaluator.evaluate(goal, active_window)
        assert assessment.affordance == ActionAffordance.PHYSICAL_GUI
        assert assessment.confidence == 0.95
        assert "graphical/canvas" in assessment.justification.lower()
        assert assessment.suggested_command is None

    # -----------------------------------------------------------------------
    # Priority Rule 2: Application Launch Verbs
    # -----------------------------------------------------------------------

    @pytest.mark.parametrize(
        "goal,expected_target",
        [
            ("Open Notepad", "notepad"),
            ("launch calculator", "calculator"),
            ("Start Spotify", "spotify"),
            ("switch to Discord", "discord"),
            ("bring up Task Manager", "task manager"),
            ("open C:\\Windows\\System32\\calc.exe", "c:\\windows\\system32\\calc.exe"),
        ],
    )
    def test_app_launch_verbs_route_to_physical_gui(self, goal: str, expected_target: str):
        assessment = AffordanceEvaluator.evaluate(goal, "")
        assert assessment.affordance == ActionAffordance.PHYSICAL_GUI
        assert assessment.confidence == 0.92
        assert "universalappresolver" in assessment.justification.lower()
        assert expected_target in assessment.justification.lower()
        assert assessment.suggested_command is None

    @pytest.mark.parametrize(
        "terminal_goal",
        [
            "open terminal",
            "launch powershell",
            "start cmd",
            "start bash",
            "bring up command prompt",
        ],
    )
    def test_terminal_launch_verbs_excluded_from_rule_2(self, terminal_goal: str):
        """Launching raw shell binaries does not trigger Priority Rule 2 UniversalAppResolver launch."""
        assessment = AffordanceEvaluator.evaluate(terminal_goal, "")
        # Should not have Rule 2's 0.92 confidence or mention UniversalAppResolver
        assert assessment.confidence != 0.92
        assert "universalappresolver" not in assessment.justification.lower()

    # -----------------------------------------------------------------------
    # Priority Rule 3: Deterministic Code, Test & File Operations
    # -----------------------------------------------------------------------

    @pytest.mark.parametrize(
        "goal,expected_cmd",
        [
            ("refactor database connection pool", None),
            ("run test suite for authentication", None),
            ("run pytest on tests/test_login.py", "pytest"),
            ("git commit -m 'feat: add telemetry'", "git commit"),
            ("create file settings.json", None),
            ("batch replace old_api with new_api in all files", None),
            ("git push origin feature/gui", "git push"),
            ("check git status before committing", "git status"),
        ],
    )
    def test_code_and_test_operations_route_to_local_developer_tool(
        self, goal: str, expected_cmd: str | None
    ):
        assessment = AffordanceEvaluator.evaluate(goal, "")
        assert assessment.affordance == ActionAffordance.LOCAL_DEVELOPER_TOOL
        assert assessment.confidence == 0.95
        assert "cliexecutionsandbox" in assessment.justification.lower()
        if expected_cmd:
            assert assessment.suggested_command == expected_cmd

    # -----------------------------------------------------------------------
    # Strategic Advisor Heuristics
    # -----------------------------------------------------------------------

    @pytest.mark.parametrize(
        "goal",
        [
            "consult advisor on UI layout",
            "deadlock in multi-window flow",
            "unresponsive screen need advice",
            "help me decide overall strategy",
        ],
    )
    def test_cognitive_deadlock_routes_to_strategic_advisor(self, goal: str):
        assessment = AffordanceEvaluator.evaluate(goal, "")
        assert assessment.affordance == ActionAffordance.STRATEGIC_ADVISOR
        assert assessment.confidence == 0.90
        assert "advisor" in assessment.justification.lower()

    # -----------------------------------------------------------------------
    # Default Desktop Interaction Fallback
    # -----------------------------------------------------------------------

    @pytest.mark.parametrize(
        "goal",
        [
            "click the submit button",
            "scroll down the settings view",
            "select the third option in dropdown",
            "type user password into field",
            "maximize the active window",
        ],
    )
    def test_general_gui_goals_default_to_physical_gui(self, goal: str):
        assessment = AffordanceEvaluator.evaluate(goal, "")
        assert assessment.affordance == ActionAffordance.PHYSICAL_GUI
        assert assessment.confidence == 0.75
        assert "standard desktop operation" in assessment.justification.lower()
        assert assessment.suggested_command is None


class TestDualMindPipelineAffordanceIntegration:
    """Tests for DualMindPipeline integration with AffordanceEvaluator and LivingPlan."""

    def test_pipeline_exposes_affordance_evaluator(self):
        from unittest.mock import MagicMock
        pipeline = DualMindPipeline(brain_manager=MagicMock())
        assert hasattr(pipeline, "affordance_evaluator")
        assert isinstance(pipeline.affordance_evaluator, AffordanceEvaluator)

    def test_pipeline_evaluate_goal_affordance(self):
        from unittest.mock import MagicMock
        pipeline = DualMindPipeline(brain_manager=MagicMock())
        assessment = pipeline.evaluate_goal_affordance("run pytest on tests/")
        assert assessment.affordance == ActionAffordance.LOCAL_DEVELOPER_TOOL
        assert assessment.confidence == 0.95

    def test_living_plan_assigns_cli_tool_route_for_developer_tasks(self):
        from unittest.mock import MagicMock
        pipeline = DualMindPipeline(brain_manager=MagicMock())
        plan = pipeline._initialize_or_update_plan("refactor authentication module and run test")
        assert len(plan.steps) >= 2
        objective_step = next(s for s in plan.steps if s.intent in (StepIntent.NAVIGATE, StepIntent.INPUT_DATA))
        assert objective_step.tool_route == "CLI"

    def test_living_plan_assigns_gui_tool_route_for_canvas_tasks(self):
        from unittest.mock import MagicMock
        pipeline = DualMindPipeline(brain_manager=MagicMock())
        plan = pipeline._initialize_or_update_plan("draw a tree in Paint")
        assert len(plan.steps) >= 2
        objective_step = next(s for s in plan.steps if s.intent in (StepIntent.NAVIGATE, StepIntent.INPUT_DATA))
        assert objective_step.tool_route == "GUI"

    def test_living_plan_assigns_advisor_tool_route_for_deadlock(self):
        from unittest.mock import MagicMock
        pipeline = DualMindPipeline(brain_manager=MagicMock())
        plan = pipeline._initialize_or_update_plan("consult advisor for deadlock")
        assert len(plan.steps) >= 2
        objective_step = next(s for s in plan.steps if s.intent in (StepIntent.NAVIGATE, StepIntent.INPUT_DATA))
        assert objective_step.tool_route == "ADVISOR"
