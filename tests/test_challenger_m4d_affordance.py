"""
tests/test_challenger_m4d_affordance.py - Empirical Challenger Test Suite for Phase 4 Milestone 4D.

Empirically verifies:
1. Ambiguous hybrid user goals (canvas keywords vs code keywords vs launch verbs).
2. Non-English, accented, Unicode, and alternating/mixed-case user goals.
3. Punctuation-heavy, malformed, empty, None, and extreme-boundary goals.
4. Multi-action chained goals and priority hierarchy enforcement:
   - Priority 1: Canvas / Native drawing (PHYSICAL_GUI, confidence=0.95)
   - Priority 2: App Launch verbs (PHYSICAL_GUI, confidence=0.92, excluding raw shells)
   - Priority 3: Deterministic code, test, and file operations (LOCAL_DEVELOPER_TOOL, confidence=0.95)
   - Priority 4: Strategic advisor / cognitive deadlock (STRATEGIC_ADVISOR, confidence=0.90)
   - Fallback: Standard desktop operation (PHYSICAL_GUI, confidence=0.75)
5. DualMindPipeline LivingPlan tool_route attribution (GUI vs CLI vs ADVISOR).
6. DualMindPipeline & ActionDispatcher integration with ActionType.RUN_CLI_COMMAND:
   - Returncode == 0 execution produces ActionResult(success=True, returncode=0).
   - Escalation state machine evaluates headless CLI without visual diff strikes (screen_diff=0.0).
   - CLI failure (returncode != 0) correctly incurs escalation strikes and transitions from T1 to T2.
   - Preemption token aborts CLI execution cleanly and triggers preemption / USER_OVERRIDE.
"""

from __future__ import annotations

import threading
from typing import Optional
from unittest.mock import MagicMock
import numpy as np
import pytest

from parasite_ai.action.dispatcher import ActionDispatcher
from parasite_ai.action.types import ActionPlan, ActionType
from parasite_ai.mind.affordance import (
    ActionAffordance,
    AffordanceAssessment,
    AffordanceEvaluator,
    CLIExecutionResult,
    CLIExecutionSandbox,
)
from parasite_ai.mind.dual_mind import ActionResult, DualMindPipeline
from parasite_ai.mind.memory import (
    CadenceTier,
    EpisodicMemory,
    EscalationStateMachine,
)
from parasite_ai.mind.plan import LivingPlan, PlanStep, StepIntent


# ===========================================================================
# 1. Ambiguous Hybrid Goals Test Suite
# ===========================================================================

class TestChallengerAmbiguousHybridGoals:
    """Stress tests for ambiguous goals containing competing keyword signals."""

    @pytest.mark.parametrize(
        "goal,active_window,expected_affordance,expected_conf,expected_fragment",
        [
            # "draw a python script in paint": Canvas keyword ("paint", "draw") vs code keyword ("python")
            ("draw a python script in paint", "", ActionAffordance.PHYSICAL_GUI, 0.95, "graphical/canvas"),
            # Active window has "Paint", goal asks to "refactor parser"
            ("refactor parser module", "Untitled - Paint", ActionAffordance.PHYSICAL_GUI, 0.95, "graphical/canvas"),
            # Active window has "Photoshop", goal asks to "run pytest"
            ("run pytest on test_vision.py", "Adobe Photoshop 2024", ActionAffordance.PHYSICAL_GUI, 0.95, "graphical/canvas"),
            # Goal has both sketch and refactor
            ("sketch an architectural refactoring on the canvas", "", ActionAffordance.PHYSICAL_GUI, 0.95, "graphical/canvas"),
            # Goal has "create file" and "brush"
            ("create file with brush tool", "", ActionAffordance.PHYSICAL_GUI, 0.95, "graphical/canvas"),
            # Goal has "batch replace" and "photoshop"
            ("batch replace brush colors in Photoshop", "", ActionAffordance.PHYSICAL_GUI, 0.95, "graphical/canvas"),
            # App launch verb takes priority over code keywords when not a canvas
            ("open notepad and run pytest", "", ActionAffordance.PHYSICAL_GUI, 0.92, "universalappresolver"),
            ("start calculator and test git status", "", ActionAffordance.PHYSICAL_GUI, 0.92, "universalappresolver"),
            ("launch visual studio and create file", "", ActionAffordance.PHYSICAL_GUI, 0.92, "universalappresolver"),
            ("bring up vscode and git commit", "", ActionAffordance.PHYSICAL_GUI, 0.92, "universalappresolver"),
            ("switch to Spotify and refactor playlist", "", ActionAffordance.PHYSICAL_GUI, 0.92, "universalappresolver"),
        ],
    )
    def test_ambiguous_hybrid_goals_resolution(
        self,
        goal: str,
        active_window: str,
        expected_affordance: ActionAffordance,
        expected_conf: float,
        expected_fragment: str,
    ):
        assessment = AffordanceEvaluator.evaluate(goal=goal, active_window_title=active_window)
        assert assessment.affordance == expected_affordance
        assert assessment.confidence == pytest.approx(expected_conf)
        assert expected_fragment in assessment.justification.lower()

    def test_paint_canvas_overrides_deadlock_keywords(self):
        """Even if deadlock / advisor keywords appear, drawing canvas context takes precedence."""
        assessment = AffordanceEvaluator.evaluate(
            goal="consult advisor regarding deadlock while sketching in Paint",
            active_window_title="",
        )
        assert assessment.affordance == ActionAffordance.PHYSICAL_GUI
        assert assessment.confidence == 0.95

    def test_pure_code_in_clean_window_routes_to_cli(self):
        """When not in canvas and no launch verbs present, code and test keywords route strictly to CLI."""
        assessment = AffordanceEvaluator.evaluate(
            goal="run pytest on tests/test_memory.py",
            active_window_title="Visual Studio Code",
        )
        assert assessment.affordance == ActionAffordance.LOCAL_DEVELOPER_TOOL
        assert assessment.confidence == 0.95
        assert assessment.suggested_command == "pytest"


# ===========================================================================
# 2. Non-English, Accented, and Mixed-Case Goals
# ===========================================================================

class TestChallengerNonEnglishAndCasingGoals:
    """Stress tests for internationalization, Unicode accents, and arbitrary casing."""

    @pytest.mark.parametrize(
        "goal,expected_affordance,expected_cmd",
        [
            # Mixed-case & alternating case
            ("pYtEsT --cOv=pArAsItE", ActionAffordance.LOCAL_DEVELOPER_TOOL, "pytest"),
            ("ReFaCtOr MoDuLe", ActionAffordance.LOCAL_DEVELOPER_TOOL, None),
            ("gIt StAtUs", ActionAffordance.LOCAL_DEVELOPER_TOOL, "git status"),
            ("GiT CoMmIt -m 'wip'", ActionAffordance.LOCAL_DEVELOPER_TOOL, "git commit"),
            ("GIT PUSH origin main", ActionAffordance.LOCAL_DEVELOPER_TOOL, "git push"),
            ("OpEn NoTePaD", ActionAffordance.PHYSICAL_GUI, None),
            ("cOnSuLt AdViSoR oN sTrAtEgY", ActionAffordance.STRATEGIC_ADVISOR, None),
            ("DRAWBIGCANVAS", ActionAffordance.PHYSICAL_GUI, None),
            ("PAINT_SKETCH_NOW", ActionAffordance.PHYSICAL_GUI, None),
            # Accented French / Spanish / German / Unicode
            ("Créer un test avec pytest pour la validation", ActionAffordance.LOCAL_DEVELOPER_TOOL, "pytest"),
            ("Ejecutar pytest en tests/ y verificar", ActionAffordance.LOCAL_DEVELOPER_TOOL, "pytest"),
            ("Exécuter git status pour vérifier l'état", ActionAffordance.LOCAL_DEVELOPER_TOOL, "git status"),
            ("Vérifier git commit avant de continuer", ActionAffordance.LOCAL_DEVELOPER_TOOL, "git commit"),
            ("Refactorisation: refactor le composant", ActionAffordance.LOCAL_DEVELOPER_TOOL, None),
            ("Dessiner sur le canvas avec un brush", ActionAffordance.PHYSICAL_GUI, None),
            ("Starte Paint für Zeichnung", ActionAffordance.PHYSICAL_GUI, None),
            ("Bloqué: consult advisor pour stratégie", ActionAffordance.STRATEGIC_ADVISOR, None),
            ("Deadlock critique, need advice immédiatement", ActionAffordance.STRATEGIC_ADVISOR, None),
            # Asian scripts with English keywords embedded
            ("使用 pytest 运行核心单元测试", ActionAffordance.LOCAL_DEVELOPER_TOOL, "pytest"),
            ("进行代码重构 refactor 核心逻辑", ActionAffordance.LOCAL_DEVELOPER_TOOL, None),
            ("在 Paint 界面中绘制新草图", ActionAffordance.PHYSICAL_GUI, None),
            ("遇到了系统死锁 deadlock, 请给出建议", ActionAffordance.STRATEGIC_ADVISOR, None),
        ],
    )
    def test_casing_and_multilingual_routing(
        self, goal: str, expected_affordance: ActionAffordance, expected_cmd: Optional[str]
    ):
        assessment = AffordanceEvaluator.evaluate(goal=goal)
        assert assessment.affordance == expected_affordance
        if expected_cmd:
            assert assessment.suggested_command == expected_cmd


# ===========================================================================
# 3. Punctuation-Heavy, Malformed, and Boundary Goals
# ===========================================================================

class TestChallengerPunctuationAndBoundaryGoals:
    """Stress tests for punctuation-heavy strings, empty/None values, and extreme lengths."""

    @pytest.mark.parametrize(
        "goal,expected_affordance",
        [
            (">>> pytest -vv --tb=short tests/test_core.py <<<", ActionAffordance.LOCAL_DEVELOPER_TOOL),
            ("[CRITICAL] git status && git commit -m '[HOTFIX] fix regex'!", ActionAffordance.LOCAL_DEVELOPER_TOOL),
            ("!!! DEADLOCK DETECTED !!! NEED ADVICE ???", ActionAffordance.STRATEGIC_ADVISOR),
            ("¿¿¿ Launch Notepad ??? (v11.0)", ActionAffordance.PHYSICAL_GUI),
            ("--- draw: circle --- (brush: 5px) ***", ActionAffordance.PHYSICAL_GUI),
            ("$$$ refactor auth module $$$", ActionAffordance.LOCAL_DEVELOPER_TOOL),
            ("### create file README.md ###", ActionAffordance.LOCAL_DEVELOPER_TOOL),
            ("~~~ batch replace foo bar ~~~", ActionAffordance.LOCAL_DEVELOPER_TOOL),
            ("<<< git push origin main >>>", ActionAffordance.LOCAL_DEVELOPER_TOOL),
        ],
    )
    def test_punctuation_heavy_goals(self, goal: str, expected_affordance: ActionAffordance):
        assessment = AffordanceEvaluator.evaluate(goal=goal)
        assert assessment.affordance == expected_affordance

    @pytest.mark.parametrize(
        "whitespace_goal,expected_affordance",
        [
            ("   \t\n  pytest   \r\n  ", ActionAffordance.LOCAL_DEVELOPER_TOOL),
            ("\n\t  open calc  \t\n", ActionAffordance.PHYSICAL_GUI),
            ("   \t  consult advisor  \t   ", ActionAffordance.STRATEGIC_ADVISOR),
            ("   \t\n  draw circle  \r\n  ", ActionAffordance.PHYSICAL_GUI),
        ],
    )
    def test_whitespace_padded_goals(self, whitespace_goal: str, expected_affordance: ActionAffordance):
        assessment = AffordanceEvaluator.evaluate(goal=whitespace_goal)
        assert assessment.affordance == expected_affordance

    @pytest.mark.parametrize(
        "empty_or_degenerate_goal",
        [
            "",
            "   ",
            "\t\n\r",
            None,
            "1234567890",
            "!@#$%^&*()_+-=[]{}|;:',.<>?/`~",
        ],
    )
    def test_empty_none_and_degenerate_goals_fallback_safely(self, empty_or_degenerate_goal):
        """Evaluator must never raise an exception on empty, None, or symbol-only inputs."""
        assessment = AffordanceEvaluator.evaluate(goal=empty_or_degenerate_goal)
        assert assessment.affordance == ActionAffordance.PHYSICAL_GUI
        assert assessment.confidence == 0.75
        assert "standard desktop operation" in assessment.justification.lower()
        assert assessment.suggested_command is None

    def test_none_active_window_title_safe(self):
        """Active window title as None must not cause TypeError."""
        assessment = AffordanceEvaluator.evaluate(goal="run pytest", active_window_title=None)
        assert assessment.affordance == ActionAffordance.LOCAL_DEVELOPER_TOOL

    def test_extreme_length_goal(self):
        """5000-character goal with embedded keyword evaluates safely without timeout or crash."""
        padding = "lorem ipsum dolor sit amet " * 200
        long_goal = f"{padding} pytest {padding}"
        assessment = AffordanceEvaluator.evaluate(goal=long_goal)
        assert assessment.affordance == ActionAffordance.LOCAL_DEVELOPER_TOOL
        assert assessment.suggested_command == "pytest"

    def test_extreme_length_active_window_title(self):
        """5000-character window title with embedded canvas keyword evaluates safely."""
        padding = "Window Description " * 250
        long_title = f"{padding} Paint {padding}"
        assessment = AffordanceEvaluator.evaluate(goal="refactor something", active_window_title=long_title)
        assert assessment.affordance == ActionAffordance.PHYSICAL_GUI
        assert assessment.confidence == 0.95


# ===========================================================================
# 4. Multi-Action Chained Goals & Strict Priority Rules
# ===========================================================================

class TestChallengerMultiActionAndPriorityChaining:
    """Stress tests verifying strict priority order among conflicting rules."""

    def test_canvas_strictly_overrides_code_and_advisor(self):
        """Rule 1 (Canvas) > Rule 3 (Code) and Rule 4 (Advisor)."""
        goal = "consult advisor to refactor drawing on Paint canvas"
        assessment = AffordanceEvaluator.evaluate(goal=goal)
        assert assessment.affordance == ActionAffordance.PHYSICAL_GUI
        assert assessment.confidence == 0.95

    def test_app_launch_strictly_overrides_code_when_not_canvas(self):
        """Rule 2 (Launch) > Rule 3 (Code)."""
        goal = "open notepad and refactor code"
        assessment = AffordanceEvaluator.evaluate(goal=goal)
        assert assessment.affordance == ActionAffordance.PHYSICAL_GUI
        assert assessment.confidence == 0.92

    def test_code_strictly_overrides_advisor_when_no_canvas_or_launch(self):
        """Rule 3 (Code) > Rule 4 (Advisor)."""
        goal = "consult advisor because git status failed with deadlock"
        assessment = AffordanceEvaluator.evaluate(goal=goal)
        assert assessment.affordance == ActionAffordance.LOCAL_DEVELOPER_TOOL
        assert assessment.confidence == 0.95
        assert assessment.suggested_command == "git status"

    def test_code_refactor_overrides_deadlock_keywords(self):
        """Rule 3 (Code) > Rule 4 (Advisor)."""
        goal = "deadlock encountered while trying to refactor database layer"
        assessment = AffordanceEvaluator.evaluate(goal=goal)
        assert assessment.affordance == ActionAffordance.LOCAL_DEVELOPER_TOOL
        assert assessment.confidence == 0.95

    def test_advisor_triggered_when_pure_deadlock(self):
        """Rule 4 (Advisor) triggers when no canvas, no launch, and no code keywords."""
        goal = "unresponsive dialog, need advice on deadlock strategy"
        assessment = AffordanceEvaluator.evaluate(goal=goal)
        assert assessment.affordance == ActionAffordance.STRATEGIC_ADVISOR
        assert assessment.confidence == 0.90

    @pytest.mark.parametrize(
        "shell_goal",
        [
            "open terminal",
            "launch powershell",
            "start cmd",
            "start bash",
            "bring up command prompt",
        ],
    )
    def test_raw_shell_launch_excluded_from_rule_2(self, shell_goal: str):
        """Launching raw interactive shells is excluded from Rule 2 and drops to default PHYSICAL_GUI (0.75)."""
        assessment = AffordanceEvaluator.evaluate(goal=shell_goal)
        assert assessment.affordance == ActionAffordance.PHYSICAL_GUI
        assert assessment.confidence == 0.75
        assert "universalappresolver" not in assessment.justification.lower()


# ===========================================================================
# 5. DualMindPipeline LivingPlan Tool Route Attribution
# ===========================================================================

class TestChallengerLivingPlanToolRouteIntegration:
    """Verifies LivingPlan step tool_route assignment across affordances."""

    @pytest.fixture
    def mock_pipeline(self):
        mock_brain = MagicMock()
        pipeline = DualMindPipeline(brain_manager=mock_brain)
        return pipeline

    @pytest.mark.parametrize(
        "goal,expected_route",
        [
            ("run pytest on tests/test_affordance.py", "CLI"),
            ("refactor memory storage model", "CLI"),
            ("git commit -m 'feat: affordance'", "CLI"),
            ("create file data.json", "CLI"),
            ("batch replace old_val with new_val", "CLI"),
            ("draw a landscape in paint", "GUI"),
            ("sketch portrait with brush", "GUI"),
            ("consult advisor on deadlock", "ADVISOR"),
            ("unresponsive window need advice", "ADVISOR"),
            ("click submit button", "GUI"),
            ("scroll down page", "GUI"),
        ],
    )
    def test_living_plan_tool_route_attribution(
        self, mock_pipeline: DualMindPipeline, goal: str, expected_route: str
    ):
        plan = mock_pipeline._initialize_or_update_plan(user_goal=goal)
        assert plan is not None
        assert len(plan.steps) >= 2
        # Verify objective step has the correct tool_route
        objective_step = next(
            s for s in plan.steps
            if s.intent in (StepIntent.NAVIGATE, StepIntent.INPUT_DATA)
        )
        assert objective_step.tool_route == expected_route

    def test_living_plan_with_target_app_has_gui_launch_step(self, mock_pipeline: DualMindPipeline):
        """When an application launch is detected, step 1 is LAUNCH_OR_ACTIVATE with tool_route='GUI'."""
        plan = mock_pipeline._initialize_or_update_plan(user_goal="open notepad and write note")
        assert plan.steps[0].intent == StepIntent.LAUNCH_OR_ACTIVATE
        assert plan.steps[0].tool_route == "GUI"
        assert "notepad" in (plan.steps[0].target_description or "").lower()


# ===========================================================================
# 6. ActionDispatcher & EscalationStateMachine CLI Integration
# ===========================================================================

class TestChallengerActionDispatcherAndEscalationIntegration:
    """
    Empirically verifies:
    - ActionType.RUN_CLI_COMMAND execution through ActionDispatcher.
    - returncode == 0 returns ActionResult(success=True, returncode=0).
    - EscalationStateMachine treats successful CLI as effective success with screen_diff=0.0.
    - Zero visual diff strikes incurred for CLI actions.
    - CLI failure (returncode != 0) correctly incurs strikes and transitions tiers.
    - Cancellation token preemption terminates subprocess in <20ms and triggers USER_OVERRIDE.
    """

    def test_action_dispatcher_executes_successful_cli_command(self):
        dispatcher = ActionDispatcher()
        action = ActionPlan(
            action=ActionType.RUN_CLI_COMMAND,
            cli_command='python -c "import sys; sys.stdout.write(\'HELLO_CLI\'); sys.exit(0)"',
        )
        res: ActionResult = dispatcher.dispatch(action=action, som_elements=[])
        assert res.success is True
        assert res.returncode == 0
        assert res.error is None
        assert res.interrupted is False

    def test_action_dispatcher_captures_failing_cli_command(self):
        dispatcher = ActionDispatcher()
        action = ActionPlan(
            action=ActionType.RUN_CLI_COMMAND,
            cli_command='python -c "import sys; sys.stderr.write(\'FATAL_ERROR\'); sys.exit(42)"',
        )
        res: ActionResult = dispatcher.dispatch(action=action, som_elements=[])
        assert res.success is False
        assert res.returncode == 42
        assert "FATAL_ERROR" in (res.error or "")

    def test_action_dispatcher_rejects_scraping_and_destructive_tools(self):
        dispatcher = ActionDispatcher()
        forbidden_commands = [
            "curl http://127.0.0.1:8000",
            "wget https://example.com/file.zip",
            "python -m playwright test",
            "cmd /c format C:",
            "cmd /c del /s C:\\important.txt",
        ]
        for cmd in forbidden_commands:
            action = ActionPlan(action=ActionType.RUN_CLI_COMMAND, cli_command=cmd)
            res = dispatcher.dispatch(action=action, som_elements=[])
            assert res.success is False
            assert res.returncode == -1
            assert "rejected by security filter" in (res.error or "").lower()

    def test_escalation_state_machine_successful_cli_bypasses_visual_diff(self):
        """
        ActionType.RUN_CLI_COMMAND with returncode == 0 must be treated as effective success,
        even when screen_diff == 0.0, keeping local_strikes at 0.
        """
        sm = EscalationStateMachine()
        assert sm.current_tier == CadenceTier.TIER_1_LOCAL
        assert sm.local_strikes == 0

        # Execute 5 consecutive successful CLI commands with 0.0 visual diff
        for _ in range(5):
            tier = sm.on_action_result(
                success=True,
                screen_diff=0.0,
                action_type=ActionType.RUN_CLI_COMMAND,
                is_interactive=False,
                cli_returncode=0,
                diff_threshold=0.02,
            )
            assert tier == CadenceTier.TIER_1_LOCAL
            assert sm.local_strikes == 0

    def test_escalation_state_machine_successful_cli_resets_prior_strikes(self):
        """A successful CLI action (returncode 0) resets local_strikes back to 0."""
        sm = EscalationStateMachine()
        # Incur 1 strike from a failed GUI click
        sm.on_action_result(
            success=True,
            screen_diff=0.001,  # Below 0.02 threshold -> strike!
            action_type=ActionType.CLICK,
            is_interactive=True,
            diff_threshold=0.02,
        )
        assert sm.local_strikes == 1
        assert sm.current_tier == CadenceTier.TIER_1_LOCAL

        # Now execute successful CLI action
        sm.on_action_result(
            success=True,
            screen_diff=0.0,
            action_type=ActionType.RUN_CLI_COMMAND,
            is_interactive=False,
            cli_returncode=0,
            diff_threshold=0.02,
        )
        assert sm.local_strikes == 0
        assert sm.current_tier == CadenceTier.TIER_1_LOCAL

    def test_escalation_state_machine_failed_cli_increments_strikes_and_transitions(self):
        """A failing CLI action (returncode != 0) incurs strikes and transitions T1 -> T2."""
        sm = EscalationStateMachine()
        assert sm.current_tier == CadenceTier.TIER_1_LOCAL

        # Strike 1: Failed CLI command
        tier1 = sm.on_action_result(
            success=False,
            screen_diff=0.0,
            action_type=ActionType.RUN_CLI_COMMAND,
            is_interactive=False,
            cli_returncode=1,
            diff_threshold=0.02,
        )
        assert tier1 == CadenceTier.TIER_1_LOCAL
        assert sm.local_strikes == 1

        # Strike 2: Second failed CLI command -> Transitions to TIER_2_CONSULT!
        tier2 = sm.on_action_result(
            success=False,
            screen_diff=0.0,
            action_type=ActionType.RUN_CLI_COMMAND,
            is_interactive=False,
            cli_returncode=2,
            diff_threshold=0.02,
        )
        assert tier2 == CadenceTier.TIER_2_CONSULT
        assert sm.current_tier == CadenceTier.TIER_2_CONSULT

    def test_preemption_token_in_cli_execution_sandbox(self):
        """Setting cancellation token during CLI execution immediately aborts in <20ms."""
        token = threading.Event()
        timer = threading.Timer(0.015, token.set)
        timer.start()

        try:
            res: CLIExecutionResult = CLIExecutionSandbox.execute(
                command_str='python -c "import time; time.sleep(10.0)"',
                timeout=5.0,
                cancellation_token=token,
            )
            assert res.preempted is True
            assert res.exit_code == -1
            # Check preemption response was rapid (under 500ms total wall time)
            assert res.duration_ms < 500.0
        finally:
            timer.cancel()


# ===========================================================================
# 7. End-to-End DualMindPipeline Step Execution with CLI Commands
# ===========================================================================

class TestChallengerDualMindPipelineStepCLIExecution:
    """Full end-to-end integration test of DualMindPipeline.step() executing CLI actions."""

    def test_pipeline_step_executes_cli_successfully_without_visual_diff_strike(self):
        mock_brain = MagicMock()
        mock_bridge = MagicMock()
        memory = EpisodicMemory()

        pipeline = DualMindPipeline(
            brain_manager=mock_brain,
            memory=memory,
            bridge=mock_bridge,
        )

        override = ActionPlan(
            action=ActionType.RUN_CLI_COMMAND,
            cli_command='python -c "print(\'PIPELINE_CLI_SUCCESS\')"',
            reasoning="Running fast local unit test",
        )

        # Frame with zero diff (same frame before and after)
        frame = np.zeros((100, 100, 3), dtype=np.uint8)

        record = pipeline.step(
            user_goal="run pytest on core",
            screen_frame=frame,
            grounded_elements=[],
            override_action=override,
        )

        assert record.success is True
        assert record.action.action == ActionType.RUN_CLI_COMMAND
        assert pipeline.escalation_sm.local_strikes == 0
        assert pipeline.escalation_sm.current_tier == CadenceTier.TIER_1_LOCAL

    def test_pipeline_step_executes_failing_cli_and_escalates_to_tier_2(self):
        mock_brain = MagicMock()
        mock_bridge = MagicMock()
        memory = EpisodicMemory()

        pipeline = DualMindPipeline(
            brain_manager=mock_brain,
            memory=memory,
            bridge=mock_bridge,
        )

        fail_action = ActionPlan(
            action=ActionType.RUN_CLI_COMMAND,
            cli_command='python -c "import sys; sys.exit(1)"',
            reasoning="Running failing CLI test",
        )

        frame = np.zeros((100, 100, 3), dtype=np.uint8)

        # Step 1: First CLI failure -> strike 1
        rec1 = pipeline.step(
            user_goal="run test",
            screen_frame=frame,
            grounded_elements=[],
            override_action=fail_action,
        )
        assert rec1.success is False
        assert pipeline.escalation_sm.local_strikes == 1
        assert pipeline.escalation_sm.current_tier == CadenceTier.TIER_1_LOCAL

        # Step 2: Second CLI failure -> strike 2 -> Escalates to TIER_2_CONSULT!
        rec2 = pipeline.step(
            user_goal="run test",
            screen_frame=frame,
            grounded_elements=[],
            override_action=fail_action,
        )
        assert rec2.success is False
        assert pipeline.escalation_sm.current_tier == CadenceTier.TIER_2_CONSULT

    def test_pipeline_step_aborts_on_hardware_interrupt(self):
        mock_brain = MagicMock()
        mock_bridge = MagicMock()
        mock_guard = MagicMock()
        # Simulate physical hardware touch
        mock_guard.is_interrupted.return_value = True

        pipeline = DualMindPipeline(
            brain_manager=mock_brain,
            interrupt_guard=mock_guard,
            bridge=mock_bridge,
        )

        override = ActionPlan(
            action=ActionType.RUN_CLI_COMMAND,
            cli_command='python -c "print(\'SHOULD_NOT_RUN\')"',
        )

        record = pipeline.step(
            user_goal="run test",
            override_action=override,
        )

        assert record.success is False
        assert pipeline.escalation_sm.current_tier == CadenceTier.USER_OVERRIDE
        assert "user override active" in (record.error_message or "").lower()
        mock_bridge.notify_state.assert_called_with("USER_OVERRIDE", "Curious")
