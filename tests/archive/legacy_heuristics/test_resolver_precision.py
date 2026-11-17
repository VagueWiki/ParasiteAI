"""
tests/test_resolver_precision.py - Comprehensive Unit & Integration Tests for VERIF-11.

Covers:
1. PrecisionAppMatcher:
   - Exact matching priority (1.0)
   - Destructive verb disqualification (0.0 for exit, close, quit, delete, etc.)
   - Prefix boundary matching (0.95 for target + ' ', ' -', ':')
   - Word boundary regex matching (0.80..0.90 with positional ratio)
   - Substring rejection (0.0 for 'art' in 'SmartScreen', 'cat' in 'catalog', 'edit' in 'credit')
   - Best element selection across preferred UI roles and score thresholding
2. UniversalAppResolver 3-Tier State Machine:
   - Tier 1: Visible element match -> ActionType.CLICK and state reset
   - Tier 2: Windows Start Search chord (Win -> Type target_app -> Enter)
   - Tier 3: Windows Run dialog fallback (Win+R -> Type target_app -> Enter)
   - Exhaustion: Both tiers attempted -> ActionType.WAIT with diagnostic reasoning (no infinite loop)
   - State reset upon switching target application
   - Non-blocking preemption check against cancellation_token
3. verify_step_completion across all 8 StepIntent semantic categories:
   - LAUNCH_OR_ACTIVATE, NAVIGATE, INPUT_DATA, SELECT_OPTION,
   - VERIFY_STATE, DISMISS_DIALOG, CONSULT_ADVISOR, CONCLUDE
4. Automated contingency step insertion:
   - Missing caret focus -> click-to-focus contingency
   - 0% diff visual stagnation -> re-ground contingency
   - Blocking modal dialog -> dismiss dialog contingency
"""

from __future__ import annotations

import re
import threading
from typing import List, Optional
import pytest

from parasite_ai.mind.dual_mind import ActionResult
from parasite_ai.mind.memory import ActionPlan, ActionType
from parasite_ai.mind.plan import (
    LivingPlan,
    PlanStep,
    StepIntent,
    StepStatus,
    check_and_insert_contingencies,
    verify_step_completion,
)
from parasite_ai.mind.resolver import PrecisionAppMatcher, UniversalAppResolver
from parasite_ai.safety.window_guard import WindowInfo
from parasite_ai.ui.types import UIElement


# ===========================================================================
# 1. PrecisionAppMatcher Unit Tests
# ===========================================================================

class TestPrecisionAppMatcher:
    """Verifies precision fuzzy scoring, boundary checks, and rejection heuristics."""

    def test_exact_match(self) -> None:
        """Level 1: Exact string match produces 1.0 confidence score."""
        assert PrecisionAppMatcher.score_match("Notepad", "notepad") == 1.0
        assert PrecisionAppMatcher.score_match("calculator", "Calculator") == 1.0
        assert PrecisionAppMatcher.score_match("  Spotify  ", "spotify") == 1.0
        assert PrecisionAppMatcher.score_match("Visual Studio Code", "visual studio code") == 1.0

    def test_empty_or_whitespace_inputs(self) -> None:
        """Empty or blank inputs immediately score 0.0."""
        assert PrecisionAppMatcher.score_match("", "notepad") == 0.0
        assert PrecisionAppMatcher.score_match("Notepad", "") == 0.0
        assert PrecisionAppMatcher.score_match("   ", "   ") == 0.0

    def test_destructive_verb_disqualification(self) -> None:
        """Disqualifies buttons with destructive/exit verbs even if target is contained."""
        target = "notepad"
        destructive_labels = [
            "Exit Notepad",
            "Close Notepad",
            "Quit Notepad",
            "Cancel Notepad",
            "Uninstall Notepad",
            "Delete Notepad",
            "Remove Notepad",
            "Kill Notepad",
            "Close Window",
            "exit-window",
            "Quit Application",
        ]
        for label in destructive_labels:
            score = PrecisionAppMatcher.score_match(label, target)
            assert score == 0.0, f"Expected 0.0 for destructive label '{label}', got {score}"

    def test_prefix_boundary_matching(self) -> None:
        """Level 2: Target as prefix followed by space, hyphen, or colon produces 0.95."""
        target = "notepad"
        assert PrecisionAppMatcher.score_match("Notepad - Document 1", target) == 0.95
        assert PrecisionAppMatcher.score_match("Notepad: Text Editor", target) == 0.95
        assert PrecisionAppMatcher.score_match("Notepad (64-bit)", target) == 0.95
        assert PrecisionAppMatcher.score_match("Notepad App", target) == 0.95

    def test_word_boundary_regex_matching(self) -> None:
        """Level 3: Full word match surrounded by word boundaries produces 0.80..0.90."""
        target = "notepad"
        score_early = PrecisionAppMatcher.score_match("Microsoft Notepad", target)
        assert 0.80 <= score_early <= 0.95
        assert score_early >= 0.80

        # Positional score ratio check: earlier occurrence scores higher
        score_late = PrecisionAppMatcher.score_match("A very long application title containing Notepad", target)
        assert 0.80 <= score_late <= 0.95
        assert score_early > score_late

    def test_substring_rejection(self) -> None:
        """Arbitrary substrings without word boundaries must score 0.0."""
        # Non-boundary collisions specified in VERIF-11
        assert PrecisionAppMatcher.score_match("SmartScreen", "art") == 0.0
        assert PrecisionAppMatcher.score_match("catalog", "cat") == 0.0
        assert PrecisionAppMatcher.score_match("credit", "edit") == 0.0
        assert PrecisionAppMatcher.score_match("swordfish", "word") == 0.0
        assert PrecisionAppMatcher.score_match("keypad", "pad") == 0.0
        assert PrecisionAppMatcher.score_match("StartScreen", "art") == 0.0

    def test_find_best_element_selection(self) -> None:
        """Selects the highest scoring element among candidates and respects threshold."""
        elements = [
            UIElement.from_bbox(1, (10, 10, 50, 50), label="Exit Notepad", role="Button"),
            UIElement.from_bbox(2, (10, 70, 50, 50), label="SmartScreen", role="Button"),
            UIElement.from_bbox(3, (10, 130, 50, 50), label="Microsoft Notepad", role="Button"),
            UIElement.from_bbox(4, (10, 190, 50, 50), label="Notepad", role="Button"),
        ]

        best = PrecisionAppMatcher.find_best_element("notepad", elements, threshold=0.80)
        assert best is not None
        elem, score = best
        assert elem.id == 4
        assert score == 1.0

    def test_find_best_element_filters_by_threshold_and_role(self) -> None:
        """Elements below threshold or with non-preferred roles are excluded."""
        elements = [
            UIElement.from_bbox(1, (10, 10, 50, 50), label="SmartScreen", role="Button"),
            UIElement.from_bbox(2, (10, 70, 50, 50), label="art", role="ScrollBar"),  # non-preferred role
        ]
        assert PrecisionAppMatcher.find_best_element("art", elements, threshold=0.80) is None


# ===========================================================================
# 2. UniversalAppResolver 3-Tier State Machine Tests
# ===========================================================================

class TestUniversalAppResolverStateMachine:
    """Verifies deterministic 3-tier fallback progression and exhaustion."""

    def test_tier1_match_emits_click_and_resets_state(self) -> None:
        resolver = UniversalAppResolver()
        elements = [
            UIElement.from_bbox(101, (200, 300, 80, 80), label="Calculator", role="Button"),
        ]

        action = resolver.resolve_launch_action("calculator", elements)
        assert action.action == ActionType.CLICK
        assert action.target_id == 101
        assert action.coordinates == (240, 340)
        assert resolver._start_search_attempts == 0
        assert resolver._run_dialog_attempts == 0
        assert resolver._search_opened is False
        assert resolver._run_opened is False

    def test_3tier_full_progression_to_exhaustion(self) -> None:
        """
        Tests complete transition:
        Tier 2 Step A (Win) -> Step B (Type) ->
        Tier 3 Step A (Win+R) -> Step B (Type) ->
        Exhaustion (WAIT, no looping).
        """
        resolver = UniversalAppResolver(cadence_buffer_ms=0)
        empty_elements: List[UIElement] = []
        target = "custom_tool"

        # Tier 2 - Step A: Trigger Win key
        plan1 = resolver.resolve_launch_action(target, empty_elements)
        assert plan1.action == ActionType.HOTKEY
        assert plan1.keys == ["win"]
        assert resolver._search_opened is True
        assert resolver._start_search_attempts == 0

        # Tier 2 - Step B: Type target name into active Start Search
        plan2 = resolver.resolve_launch_action(target, empty_elements)
        assert plan2.action == ActionType.TYPE
        assert plan2.text == f"{target}\n"
        assert plan2.submit is True
        assert resolver._search_opened is False
        assert resolver._start_search_attempts == 1

        # Tier 3 - Step A: Trigger Win+R chord fallback
        plan3 = resolver.resolve_launch_action(target, empty_elements)
        assert plan3.action == ActionType.HOTKEY
        assert plan3.keys == ["win", "r"]
        assert resolver._run_opened is True
        assert resolver._run_dialog_attempts == 0

        # Tier 3 - Step B: Type target name into active Run dialog
        plan4 = resolver.resolve_launch_action(target, empty_elements)
        assert plan4.action == ActionType.TYPE
        assert plan4.text == f"{target}\n"
        assert plan4.submit is True
        assert resolver._run_opened is False
        assert resolver._run_dialog_attempts == 1

        # Exhaustion: Both tiers have been attempted
        plan5 = resolver.resolve_launch_action(target, empty_elements)
        assert plan5.action == ActionType.WAIT
        assert "Resolution exhausted" in (plan5.reasoning or "")
        assert "replan" in (plan5.reasoning or "").lower()

        # Call again: must remain in WAIT state without re-triggering Win or Win+R
        plan6 = resolver.resolve_launch_action(target, empty_elements)
        assert plan6.action == ActionType.WAIT

    def test_new_target_app_resets_state_counters(self) -> None:
        resolver = UniversalAppResolver(cadence_buffer_ms=0)
        empty_elements: List[UIElement] = []

        # Exhaust first app
        for _ in range(5):
            resolver.resolve_launch_action("app_one", empty_elements)
        assert resolver._start_search_attempts == 1
        assert resolver._run_dialog_attempts == 1

        # Now launch a new app -> state must reset to 0
        plan = resolver.resolve_launch_action("app_two", empty_elements)
        assert plan.action == ActionType.HOTKEY
        assert plan.keys == ["win"]
        assert resolver._start_search_attempts == 0
        assert resolver._run_dialog_attempts == 0
        assert resolver._search_opened is True

    def test_cancellation_token_preemption(self) -> None:
        """Cadence buffer wait unblocks immediately (<20ms) when cancellation token is set."""
        token = threading.Event()
        token.set()  # Human hardware touch detected!

        resolver = UniversalAppResolver(cadence_buffer_ms=1000.0)
        resolver._search_opened = True

        import time
        start = time.perf_counter()
        action = resolver.resolve_launch_action("notepad", [], cancellation_token=token)
        latency_ms = (time.perf_counter() - start) * 1000.0

        assert action.action == ActionType.TYPE
        assert latency_ms < 20.0  # Unblocked immediately by token.wait() instead of sleeping 1000ms


# ===========================================================================
# 3. LivingPlan Step Verification across 8 StepIntents
# ===========================================================================

class TestLivingPlanStepVerification:
    """Verifies verify_step_completion across all 8 StepIntent categories."""

    @pytest.fixture
    def dummy_window(self) -> WindowInfo:
        return WindowInfo(
            hwnd=12345,
            title="Untitled - Notepad",
            class_name="Notepad",
            process_name="notepad.exe",
            process_path="C:\\Windows\\notepad.exe",
            pid=4321,
            rect=(0, 0, 1920, 1080),
            is_sensitive=False,
            reason="",
        )

    def test_verify_launch_or_activate_by_window(self, dummy_window: WindowInfo) -> None:
        step = PlanStep(
            step_id=1,
            intent=StepIntent.LAUNCH_OR_ACTIVATE,
            description="Launch Notepad",
            target_description="notepad",
            success_criteria="Notepad window appears",
        )
        action = ActionPlan(action=ActionType.HOTKEY, keys=["win"])
        result = ActionResult(success=True)

        # Window title matches target
        assert verify_step_completion(step, action, result, screen_diff=0.0, current_window=dummy_window) is True

        # Process name matches target
        step.target_description = "notepad.exe"
        assert verify_step_completion(step, action, result, screen_diff=0.0, current_window=dummy_window) is True

    def test_verify_launch_or_activate_by_diff(self) -> None:
        step = PlanStep(
            step_id=1,
            intent=StepIntent.LAUNCH_OR_ACTIVATE,
            description="Launch ArbitraryTool",
            target_description="ArbitraryTool",
            success_criteria="Window appears",
        )
        action = ActionPlan(action=ActionType.CLICK)
        result = ActionResult(success=True)

        # Visual diff >= 0.02 confirms launch even if window title unknown
        assert verify_step_completion(step, action, result, screen_diff=0.04, current_window=None) is True
        # Stagnant diff < 0.02 fails
        assert verify_step_completion(step, action, result, screen_diff=0.005, current_window=None) is False

    def test_verify_navigate(self) -> None:
        step = PlanStep(
            step_id=2,
            intent=StepIntent.NAVIGATE,
            description="Click File menu",
            success_criteria="File menu opens",
        )
        action = ActionPlan(action=ActionType.CLICK)
        result = ActionResult(success=True)

        assert verify_step_completion(step, action, result, screen_diff=0.03) is True
        assert verify_step_completion(step, action, result, screen_diff=0.005) is False

    def test_verify_input_data(self) -> None:
        step = PlanStep(
            step_id=3,
            intent=StepIntent.INPUT_DATA,
            description="Type hello",
            success_criteria="Text appears",
        )
        action = ActionPlan(action=ActionType.TYPE, text="hello")
        result = ActionResult(success=True)

        assert verify_step_completion(step, action, result, screen_diff=0.01) is True
        # 0% diff typing indicates missing caret
        assert verify_step_completion(step, action, result, screen_diff=0.0) is False

    def test_verify_select_option(self) -> None:
        step = PlanStep(
            step_id=4,
            intent=StepIntent.SELECT_OPTION,
            description="Select UTF-8 encoding",
            success_criteria="UTF-8 selected",
        )
        action = ActionPlan(action=ActionType.CLICK)
        result = ActionResult(success=True)

        assert verify_step_completion(step, action, result, screen_diff=0.008) is True
        assert verify_step_completion(step, action, result, screen_diff=0.001) is False

    def test_verify_verify_state(self, dummy_window: WindowInfo) -> None:
        step = PlanStep(
            step_id=5,
            intent=StepIntent.VERIFY_STATE,
            description="Check Notepad is active",
            target_description="Notepad",
            success_criteria="Notepad is active",
        )
        action = ActionPlan(action=ActionType.WAIT)
        result = ActionResult(success=True)

        assert verify_step_completion(step, action, result, screen_diff=0.0, current_window=dummy_window) is True

    def test_verify_dismiss_dialog(self) -> None:
        step = PlanStep(
            step_id=6,
            intent=StepIntent.DISMISS_DIALOG,
            description="Dismiss Save Changes prompt",
            success_criteria="Dialog closes",
        )
        action = ActionPlan(action=ActionType.CLICK)
        result = ActionResult(success=True)

        # Succeeded with visual diff
        assert verify_step_completion(step, action, result, screen_diff=0.02) is True

    def test_verify_consult_advisor(self) -> None:
        step = PlanStep(
            step_id=7,
            intent=StepIntent.CONSULT_ADVISOR,
            description="Consult strategic Gemini",
            success_criteria="Blueprint returned",
        )
        action = ActionPlan(action=ActionType.WAIT)
        assert verify_step_completion(step, action, ActionResult(success=True)) is True
        assert verify_step_completion(step, action, ActionResult(success=False)) is False

    def test_verify_conclude(self) -> None:
        step = PlanStep(
            step_id=8,
            intent=StepIntent.CONCLUDE,
            description="Finish task",
            success_criteria="All done",
        )
        action = ActionPlan(action=ActionType.DONE, reasoning="Goal successfully completed")
        assert verify_step_completion(step, action, ActionResult(success=True)) is True
        assert verify_step_completion(step, action, ActionResult(success=False)) is False

    def test_verify_interrupted_action_always_fails(self) -> None:
        step = PlanStep(
            step_id=1,
            intent=StepIntent.NAVIGATE,
            description="Click button",
            success_criteria="Button clicked",
        )
        action = ActionPlan(action=ActionType.CLICK)
        interrupted_res = ActionResult(success=False, interrupted=True, error="Interrupted by touch")
        assert verify_step_completion(step, action, interrupted_res, screen_diff=0.05) is False


# ===========================================================================
# 4. Automated Contingency Step Insertion Tests
# ===========================================================================

class TestAutomatedContingencyInsertion:
    """Verifies dynamic contingency branch insertion for common execution anomalies."""

    def test_caret_contingency_insertion(self) -> None:
        plan = LivingPlan(
            user_goal="Write note",
            steps=[
                PlanStep(
                    step_id=1,
                    intent=StepIntent.INPUT_DATA,
                    description="Type greeting",
                    target_description="Editor Area",
                    success_criteria="Text entered",
                    status=StepStatus.IN_PROGRESS,
                )
            ],
            current_step_id=1,
        )

        cur = plan.get_current_step()
        assert cur is not None

        # Caret focus unacquired
        contingency = check_and_insert_contingencies(plan, cur, screen_diff=0.0, caret_active=False)
        assert contingency is not None
        assert contingency.intent == StepIntent.NAVIGATE
        assert "caret" in contingency.description.lower()
        assert plan.replan_count == 1
        assert len(plan.steps) == 2
        assert plan.steps[1].step_id == contingency.step_id

    def test_stagnation_contingency_insertion(self) -> None:
        plan = LivingPlan(
            user_goal="Click tab",
            steps=[
                PlanStep(
                    step_id=1,
                    intent=StepIntent.NAVIGATE,
                    description="Click Settings tab",
                    target_description="Settings Tab",
                    success_criteria="Settings panel shown",
                    status=StepStatus.IN_PROGRESS,
                )
            ],
            current_step_id=1,
        )

        cur = plan.get_current_step()
        assert cur is not None

        # 0% diff stagnation
        contingency = check_and_insert_contingencies(plan, cur, screen_diff=0.0, caret_active=True)
        assert contingency is not None
        assert contingency.intent == StepIntent.NAVIGATE
        assert "stagnation" in contingency.description.lower() or "re-ground" in contingency.description.lower()
        assert plan.replan_count == 1

    def test_modal_dialog_contingency_insertion(self) -> None:
        plan = LivingPlan(
            user_goal="Save file",
            steps=[
                PlanStep(
                    step_id=1,
                    intent=StepIntent.NAVIGATE,
                    description="Click Save button",
                    success_criteria="File saved",
                    status=StepStatus.IN_PROGRESS,
                )
            ],
            current_step_id=1,
        )

        cur = plan.get_current_step()
        assert cur is not None

        dialog_element = UIElement.from_bbox(99, (400, 300, 300, 200), label="Confirm Overwrite", role="Window")
        contingency = check_and_insert_contingencies(plan, cur, screen_diff=0.0, blocking_dialog=dialog_element)
        assert contingency is not None
        assert contingency.intent == StepIntent.DISMISS_DIALOG
        assert "Confirm Overwrite" in contingency.description
        assert plan.replan_count == 1
