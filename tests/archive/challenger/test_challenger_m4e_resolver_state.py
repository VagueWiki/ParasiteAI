"""
tests/test_challenger_m4e_resolver_state.py - Adversarial Stress Suite for Milestone 4E.

Authored by Challenger 2 (Empirical Challenger):
Adversarially stress-tests:
1. UniversalAppResolver State Transitions & Loop Prevention:
   - Exhaustion progression across Tier 1, Tier 2 (Win chord -> Type), Tier 3 (Win+R chord -> Type),
     and Tier 4 Exhaustion (ActionType.WAIT with diagnostic replan reasoning).
   - Long-run loop prevention: 50+ consecutive calls never cycle back to Win or Win+R.
   - External UI interception: Start search box or Run dialog already present.
   - Rapid target application switching and attempt counter resets.
   - Target name formatting, whitespace normalization, empty strings.
   - Non-blocking cadence wait responsiveness with cancellation token (<20ms abort).
2. verify_step_completion across all 8 StepIntent Types:
   - LAUNCH_OR_ACTIVATE, NAVIGATE, INPUT_DATA, SELECT_OPTION,
   - VERIFY_STATE, DISMISS_DIALOG, CONSULT_ADVISOR, CONCLUDE.
   - Threshold boundaries, CLI return codes, hardware interrupts, and target mismatches.
3. Automated Contingency Step Insertion:
   - Caret contingency injection on missing caret focus during INPUT_DATA.
   - Visual stagnation contingency on screen_diff < 0.001 for interactive intents.
   - Non-interactive intents exempt from stagnation contingency.
   - Modal dialog contingency injection on blocking UI elements.
   - LivingPlan replan_count tracking and step order validation.
4. PrecisionAppMatcher Adversarial Boundaries:
   - Negative verb filtering, boundary regex, non-boundary substring disqualification.
"""

from __future__ import annotations

import threading
import time
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
# 1. UniversalAppResolver State Transitions & Exhaustion Progression
# ===========================================================================

class TestResolverStateTransitionsAndLoopPrevention:
    """Adversarially verifies attempt counters, tier transitions, and exhaustion loop prevention."""

    def test_strict_5call_exhaustion_sequence_with_no_som_match(self) -> None:
        """
        Adversarial progression check:
        When no SOM elements match:
          Call 1: Hotkey ["win"] (Start chord)
          Call 2: Type f"{app}\\n" (Submit search, _start_search_attempts=1)
          Call 3: Hotkey ["win", "r"] (Run dialog fallback chord)
          Call 4: Type f"{app}\\n" (Submit run dialog, _run_dialog_attempts=1)
          Call 5: ActionType.WAIT (Exhaustion — cleanly escalates to replan, NEVER loops back)
        """
        resolver = UniversalAppResolver(cadence_buffer_ms=0)
        target = "uninstalled_heavy_app"
        empty_elements: List[UIElement] = []

        # Call 1: Start Search chord
        c1 = resolver.resolve_launch_action(target, empty_elements)
        assert c1.action == ActionType.HOTKEY
        assert c1.keys == ["win"]
        assert resolver._search_opened is True
        assert resolver._start_search_attempts == 0

        # Call 2: Submit search
        c2 = resolver.resolve_launch_action(target, empty_elements)
        assert c2.action == ActionType.TYPE
        assert c2.text == f"{target}\n"
        assert c2.submit is True
        assert resolver._search_opened is False
        assert resolver._start_search_attempts == 1

        # Call 3: Run dialog chord fallback
        c3 = resolver.resolve_launch_action(target, empty_elements)
        assert c3.action == ActionType.HOTKEY
        assert c3.keys == ["win", "r"]
        assert resolver._run_opened is True
        assert resolver._run_dialog_attempts == 0

        # Call 4: Submit run dialog
        c4 = resolver.resolve_launch_action(target, empty_elements)
        assert c4.action == ActionType.TYPE
        assert c4.text == f"{target}\n"
        assert c4.submit is True
        assert resolver._run_opened is False
        assert resolver._run_dialog_attempts == 1

        # Call 5: Exhaustion
        c5 = resolver.resolve_launch_action(target, empty_elements)
        assert c5.action == ActionType.WAIT
        assert "exhausted" in (c5.reasoning or "").lower()
        assert "replan" in (c5.reasoning or "").lower()

    def test_long_run_loop_prevention_remains_in_wait_state(self) -> None:
        """
        Stress test: Calling resolve_launch_action 50 times consecutively
        must NEVER cycle back to Win or Win+R once exhausted.
        """
        resolver = UniversalAppResolver(cadence_buffer_ms=0)
        target = "phantom_process"
        empty_elements: List[UIElement] = []

        # Advance to exhaustion (calls 1 to 4)
        for _ in range(4):
            resolver.resolve_launch_action(target, empty_elements)

        # Calls 5 through 50 must all return ActionType.WAIT
        for call_idx in range(5, 51):
            plan = resolver.resolve_launch_action(target, empty_elements)
            assert plan.action == ActionType.WAIT, (
                f"Call {call_idx} violated exhaustion state by emitting {plan.action} instead of WAIT!"
            )
            assert resolver._start_search_attempts >= 1
            assert resolver._run_dialog_attempts >= 1

    def test_rapid_target_app_switching_resets_attempt_counters(self) -> None:
        """
        Stress test: Rapidly alternating between target applications mid-tier
        must immediately reset attempt counters and tier states on each switch.
        """
        resolver = UniversalAppResolver(cadence_buffer_ms=0)
        empty_elements: List[UIElement] = []

        # Step 1: Start launching App A (reaches Tier 2 Step A)
        p1 = resolver.resolve_launch_action("notepad", empty_elements)
        assert p1.action == ActionType.HOTKEY
        assert p1.keys == ["win"]
        assert resolver._search_opened is True
        assert resolver._target_app == "notepad"

        # Step 2: Immediate switch to App B before completing Tier 2 for App A
        p2 = resolver.resolve_launch_action("calculator", empty_elements)
        assert p2.action == ActionType.HOTKEY
        assert p2.keys == ["win"]
        assert resolver._search_opened is True
        assert resolver._target_app == "calculator"
        assert resolver._start_search_attempts == 0
        assert resolver._run_dialog_attempts == 0

        # Step 3: Advance App B to Tier 3 Step A (Win+R)
        resolver.resolve_launch_action("calculator", empty_elements)  # Type calc
        p3 = resolver.resolve_launch_action("calculator", empty_elements)  # Win+R
        assert p3.action == ActionType.HOTKEY
        assert p3.keys == ["win", "r"]
        assert resolver._run_opened is True

        # Step 4: Rapidly switch to App C -> must cleanly reset to Tier 2 Step A
        p4 = resolver.resolve_launch_action("spotify", empty_elements)
        assert p4.action == ActionType.HOTKEY
        assert p4.keys == ["win"]
        assert resolver._target_app == "spotify"
        assert resolver._start_search_attempts == 0
        assert resolver._run_dialog_attempts == 0
        assert resolver._run_opened is False

    def test_target_app_casing_and_whitespace_idempotence(self) -> None:
        """Verifies that casing and whitespace differences do not trigger spurious state resets."""
        resolver = UniversalAppResolver(cadence_buffer_ms=0)
        empty_elements: List[UIElement] = []

        # Call with lowercase
        p1 = resolver.resolve_launch_action("notepad", empty_elements)
        assert p1.action == ActionType.HOTKEY
        assert resolver._search_opened is True

        # Call with mixed case and whitespace for same app -> must NOT reset state!
        p2 = resolver.resolve_launch_action("   NotePad \n  ", empty_elements)
        assert p2.action == ActionType.TYPE
        assert p2.text == "   NotePad \n  \n"
        assert resolver._start_search_attempts == 1

    def test_empty_or_whitespace_target_app_returns_wait(self) -> None:
        """Empty or whitespace-only target apps safely yield WAIT without crashing."""
        resolver = UniversalAppResolver(cadence_buffer_ms=0)
        for empty_val in ["", "   ", "\t\n"]:
            plan = resolver.resolve_launch_action(empty_val, [])
            assert plan.action == ActionType.WAIT
            assert "No target application" in (plan.reasoning or "")

    def test_run_dialog_already_open_on_screen(self) -> None:
        """Detects already-open Run dialog edit box and directly submits target without Win+R chord."""
        resolver = UniversalAppResolver(cadence_buffer_ms=0)
        run_element = UIElement.from_bbox(55, (100, 200, 250, 30), label="Type the name of a program", role="Edit")

        action = resolver.resolve_launch_action("cmd.exe", [run_element])
        assert action.action == ActionType.CLICK_AND_TYPE
        assert action.target_id == 55
        assert action.text == "cmd.exe"
        assert action.submit is True
        assert resolver._run_dialog_attempts == 1

        # Next call with empty elements transitions to Tier 2 (since start search was not attempted)
        next_action = resolver.resolve_launch_action("cmd.exe", [])
        assert next_action.action == ActionType.HOTKEY
        assert next_action.keys == ["win"]

    def test_start_search_box_already_open_on_screen(self) -> None:
        """Detects already-open Start Search box and directly types target without Win chord."""
        resolver = UniversalAppResolver(cadence_buffer_ms=0)
        search_element = UIElement.from_bbox(77, (50, 900, 300, 40), label="Search box", role="Edit")

        action = resolver.resolve_launch_action("terminal", [search_element])
        assert action.action == ActionType.CLICK_AND_TYPE
        assert action.target_id == 77
        assert "terminal" in action.text
        assert action.submit is True
        assert resolver._start_search_attempts == 1

        # Next call with empty elements transitions directly to Tier 3 (Win+R)
        next_action = resolver.resolve_launch_action("terminal", [])
        assert next_action.action == ActionType.HOTKEY
        assert next_action.keys == ["win", "r"]

    def test_som_match_interrupts_in_flight_tier_and_resets(self) -> None:
        """If a matching SOM element appears during Tier 2 or Tier 3, it clicks it and resets state."""
        resolver = UniversalAppResolver(cadence_buffer_ms=0)
        empty: List[UIElement] = []

        # Advance to Tier 3 Win+R
        resolver.resolve_launch_action("paint", empty)  # Win
        resolver.resolve_launch_action("paint", empty)  # Type
        resolver.resolve_launch_action("paint", empty)  # Win+R

        assert resolver._run_opened is True

        # Now Paint icon appears on desktop or taskbar!
        paint_elem = UIElement.from_bbox(88, (300, 400, 60, 60), label="Paint", role="Button")
        action = resolver.resolve_launch_action("paint", [paint_elem])

        assert action.action == ActionType.CLICK
        assert action.target_id == 88
        assert resolver._start_search_attempts == 0
        assert resolver._run_dialog_attempts == 0
        assert resolver._run_opened is False
        assert resolver._search_opened is False


# ===========================================================================
# 2. Non-blocking Cadence Buffer Wait & Cancellation Responsiveness
# ===========================================================================

class TestCadenceBufferCancellationResponsiveness:
    """Verifies that cancellation tokens interrupt cadence sleeps in <20ms."""

    def test_pre_set_cancellation_token_unblocks_under_5ms(self) -> None:
        """A pre-set cancellation token returns immediately (<5ms) despite 2000ms cadence buffer."""
        token = threading.Event()
        token.set()

        resolver = UniversalAppResolver(cadence_buffer_ms=2000.0)
        resolver._search_opened = True

        t0 = time.perf_counter()
        action = resolver.resolve_launch_action("notepad", [], cancellation_token=token)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        assert action.action == ActionType.TYPE
        assert elapsed_ms < 5.0, f"Expected <5ms unblock with pre-set token, got {elapsed_ms:.2f}ms"

    def test_concurrent_background_cancellation_unblocks_under_25ms(self) -> None:
        """A cancellation token set concurrently by a background thread breaks out in <25ms."""
        token = threading.Event()
        resolver = UniversalAppResolver(cadence_buffer_ms=1000.0)
        resolver._search_opened = True

        # Fire cancellation at 10ms
        timer = threading.Timer(0.010, token.set)
        timer.start()

        t0 = time.perf_counter()
        action = resolver.resolve_launch_action("notepad", [], cancellation_token=token)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        timer.join()

        assert action.action == ActionType.TYPE
        assert elapsed_ms < 25.0, f"Expected <25ms concurrent unblock, got {elapsed_ms:.2f}ms"

    def test_unset_cancellation_token_waits_full_duration(self) -> None:
        """When token is unset, wait executes for specified cadence buffer (e.g. 50ms)."""
        token = threading.Event()
        resolver = UniversalAppResolver(cadence_buffer_ms=50.0)
        resolver._search_opened = True

        t0 = time.perf_counter()
        action = resolver.resolve_launch_action("notepad", [], cancellation_token=token)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        assert action.action == ActionType.TYPE
        assert elapsed_ms >= 45.0, f"Expected >=45ms wait with unset token, got {elapsed_ms:.2f}ms"


# ===========================================================================
# 3. verify_step_completion across all 8 StepIntent Types
# ===========================================================================

class TestStepVerificationAcrossAll8Intents:
    """Stress tests verify_step_completion across all 8 StepIntent categories."""

    @pytest.fixture
    def active_notepad_window(self) -> WindowInfo:
        return WindowInfo(
            hwnd=1001,
            title="Untitled - Notepad",
            class_name="Notepad",
            process_name="notepad.exe",
            process_path="C:\\Windows\\notepad.exe",
            pid=2002,
            rect=(0, 0, 1920, 1080),
            is_sensitive=False,
            reason="",
        )

    # --- 1. LAUNCH_OR_ACTIVATE ---
    def test_verify_launch_or_activate_window_and_process_matching(self, active_notepad_window: WindowInfo) -> None:
        step = PlanStep(
            step_id=1,
            intent=StepIntent.LAUNCH_OR_ACTIVATE,
            description="Launch Notepad",
            target_description="notepad",
            success_criteria="Notepad window active",
        )
        action = ActionPlan(action=ActionType.HOTKEY, keys=["win"])
        success_result = ActionResult(success=True)

        # Match title
        assert verify_step_completion(step, action, success_result, screen_diff=0.0, current_window=active_notepad_window) is True

        # Match process name
        step.target_description = "notepad.exe"
        assert verify_step_completion(step, action, success_result, screen_diff=0.0, current_window=active_notepad_window) is True

        # Dynamic fallback extraction from step.description when target_description is None
        step.target_description = None
        step.description = "open up notepad and create a file"
        assert verify_step_completion(step, action, success_result, screen_diff=0.0, current_window=active_notepad_window) is True

    def test_verify_launch_or_activate_cli_and_diff_threshold(self) -> None:
        step = PlanStep(
            step_id=1,
            intent=StepIntent.LAUNCH_OR_ACTIVATE,
            description="Launch process via CLI",
            success_criteria="Process launched",
        )
        cli_action = ActionPlan(action=ActionType.RUN_CLI_COMMAND)
        assert verify_step_completion(step, cli_action, ActionResult(success=True, returncode=0)) is True
        assert verify_step_completion(step, cli_action, ActionResult(success=True, returncode=1)) is False

        # Visual diff threshold (0.02)
        gui_action = ActionPlan(action=ActionType.CLICK)
        assert verify_step_completion(step, gui_action, ActionResult(success=True), screen_diff=0.020) is True
        assert verify_step_completion(step, gui_action, ActionResult(success=True), screen_diff=0.019) is False

    # --- 2. NAVIGATE ---
    def test_verify_navigate_thresholds(self) -> None:
        step = PlanStep(
            step_id=2,
            intent=StepIntent.NAVIGATE,
            description="Click navigation item",
            success_criteria="Page transitions",
        )
        action = ActionPlan(action=ActionType.CLICK)
        assert verify_step_completion(step, action, ActionResult(success=True), screen_diff=0.020) is True
        assert verify_step_completion(step, action, ActionResult(success=True), screen_diff=0.019) is False

        # CLI action under navigate
        cli_action = ActionPlan(action=ActionType.RUN_CLI_COMMAND)
        assert verify_step_completion(step, cli_action, ActionResult(success=True, returncode=0)) is True
        assert verify_step_completion(step, cli_action, ActionResult(success=True, returncode=127)) is False

    # --- 3. INPUT_DATA ---
    def test_verify_input_data_thresholds(self) -> None:
        step = PlanStep(
            step_id=3,
            intent=StepIntent.INPUT_DATA,
            description="Type text into editor",
            success_criteria="Text visible",
        )
        action = ActionPlan(action=ActionType.TYPE, text="test")
        assert verify_step_completion(step, action, ActionResult(success=True), screen_diff=0.005) is True
        assert verify_step_completion(step, action, ActionResult(success=True), screen_diff=0.004) is False
        assert verify_step_completion(step, action, ActionResult(success=True), screen_diff=0.0) is False

    # --- 4. SELECT_OPTION ---
    def test_verify_select_option_thresholds(self) -> None:
        step = PlanStep(
            step_id=4,
            intent=StepIntent.SELECT_OPTION,
            description="Select dropdown option",
            success_criteria="Option selected",
        )
        action = ActionPlan(action=ActionType.CLICK)
        assert verify_step_completion(step, action, ActionResult(success=True), screen_diff=0.005) is True
        assert verify_step_completion(step, action, ActionResult(success=True), screen_diff=0.004) is False

    # --- 5. VERIFY_STATE ---
    def test_verify_verify_state_window_and_passive_assertion(self, active_notepad_window: WindowInfo) -> None:
        step = PlanStep(
            step_id=5,
            intent=StepIntent.VERIFY_STATE,
            description="Verify Notepad window active",
            target_description="notepad",
            success_criteria="Notepad is active window",
        )
        action = ActionPlan(action=ActionType.WAIT)
        assert verify_step_completion(step, action, ActionResult(success=True), current_window=active_notepad_window) is True
        assert verify_step_completion(step, action, ActionResult(success=False), current_window=active_notepad_window) is False

    # --- 6. DISMISS_DIALOG ---
    def test_verify_dismiss_dialog_by_diff_and_title(self) -> None:
        step = PlanStep(
            step_id=6,
            intent=StepIntent.DISMISS_DIALOG,
            description="Dismiss Save confirmation",
            success_criteria="Dialog closed",
        )
        action = ActionPlan(action=ActionType.CLICK)

        # Diff >= 0.01 succeeds
        assert verify_step_completion(step, action, ActionResult(success=True), screen_diff=0.010) is True

        # Dialog keyword absence in active window
        clean_window = WindowInfo(
            hwnd=501, title="Main Application Dashboard", class_name="AppClass",
            process_name="app.exe", process_path="C:\\app.exe", pid=1,
            rect=(0, 0, 100, 100), is_sensitive=False, reason="",
        )
        assert verify_step_completion(step, action, ActionResult(success=True), screen_diff=0.0, current_window=clean_window) is True

    # --- 7. CONSULT_ADVISOR ---
    def test_verify_consult_advisor(self) -> None:
        step = PlanStep(
            step_id=7,
            intent=StepIntent.CONSULT_ADVISOR,
            description="Consult strategic Gemini",
            success_criteria="Living plan blueprint generated",
        )
        action = ActionPlan(action=ActionType.WAIT)
        assert verify_step_completion(step, action, ActionResult(success=True)) is True
        assert verify_step_completion(step, action, ActionResult(success=False)) is False

    # --- 8. CONCLUDE ---
    def test_verify_conclude_conditions(self) -> None:
        step = PlanStep(
            step_id=8,
            intent=StepIntent.CONCLUDE,
            description="Complete overall goal",
            success_criteria="Task finished",
        )
        # ActionType.DONE
        assert verify_step_completion(step, ActionPlan(action=ActionType.DONE), ActionResult(success=True)) is True
        # Reasoning containing 'complete'
        assert verify_step_completion(step, ActionPlan(action=ActionType.WAIT, reasoning="Workflow complete"), ActionResult(success=True)) is True
        # Failed action cannot conclude
        assert verify_step_completion(step, ActionPlan(action=ActionType.DONE), ActionResult(success=False)) is False

    # --- Global Invariants & Interruption ---
    def test_hardware_interrupt_or_panic_always_fails_verification(self) -> None:
        """Physical touch interruption or PANIC action unconditionally fails step verification."""
        for intent in StepIntent:
            step = PlanStep(step_id=1, intent=intent, description="Action", success_criteria="Done")
            normal_action = ActionPlan(action=ActionType.CLICK)
            panic_action = ActionPlan(action=ActionType.PANIC)

            # Touch preemption
            interrupted_res = ActionResult(success=False, interrupted=True, error="Interrupted by touch")
            assert verify_step_completion(step, normal_action, interrupted_res, screen_diff=0.10) is False

            # Panic action
            assert verify_step_completion(step, panic_action, ActionResult(success=True), screen_diff=0.10) is False


# ===========================================================================
# 4. Automated Contingency Insertion Stress Tests
# ===========================================================================

class TestAutomatedContingencyInsertionStress:
    """Stress tests dynamic contingency branch insertion into LivingPlan."""

    def test_missing_caret_contingency_inserts_navigate_click(self) -> None:
        plan = LivingPlan(
            user_goal="Write essay",
            steps=[
                PlanStep(
                    step_id=1,
                    intent=StepIntent.INPUT_DATA,
                    description="Type thesis statement",
                    target_description="Main Document Area",
                    success_criteria="Text appears",
                    status=StepStatus.IN_PROGRESS,
                ),
                PlanStep(
                    step_id=2,
                    intent=StepIntent.CONCLUDE,
                    description="Wrap up",
                    success_criteria="Done",
                ),
            ],
            current_step_id=1,
        )

        step = plan.get_current_step()
        assert step is not None

        # Caret not active during typing
        contingency = check_and_insert_contingencies(plan, step, screen_diff=0.0, caret_active=False)
        assert contingency is not None
        assert contingency.intent == StepIntent.NAVIGATE
        assert "caret" in contingency.description.lower()
        assert contingency.step_id == 3
        # Contingency inserted immediately after step 1
        assert plan.steps[1].step_id == 3
        assert plan.replan_count == 1

    def test_visual_stagnation_contingency_for_interactive_intents(self) -> None:
        """Interactive intents with screen_diff < 0.001 trigger stagnation contingency."""
        interactive_intents = [
            StepIntent.NAVIGATE,
            StepIntent.INPUT_DATA,
            StepIntent.SELECT_OPTION,
            StepIntent.LAUNCH_OR_ACTIVATE,
        ]

        for idx, intent in enumerate(interactive_intents, start=1):
            plan = LivingPlan(
                user_goal="Test stagnation",
                steps=[
                    PlanStep(
                        step_id=1,
                        intent=intent,
                        description=f"Action {intent.value}",
                        target_description="Button X",
                        success_criteria="Response",
                        status=StepStatus.IN_PROGRESS,
                    )
                ],
                current_step_id=1,
            )
            step = plan.get_current_step()
            assert step is not None

            contingency = check_and_insert_contingencies(plan, step, screen_diff=0.0005, caret_active=True)
            assert contingency is not None
            assert contingency.intent == StepIntent.NAVIGATE
            assert "stagnation" in contingency.description.lower() or "re-ground" in contingency.description.lower()
            assert plan.replan_count == 1

    def test_non_interactive_intents_exempt_from_stagnation_contingency(self) -> None:
        """Non-interactive intents (VERIFY_STATE, CONCLUDE, etc.) do NOT insert stagnation contingency on 0% diff."""
        non_interactive = [
            StepIntent.VERIFY_STATE,
            StepIntent.CONSULT_ADVISOR,
            StepIntent.CONCLUDE,
        ]

        for intent in non_interactive:
            plan = LivingPlan(
                user_goal="Passive check",
                steps=[
                    PlanStep(
                        step_id=1,
                        intent=intent,
                        description="Passive action",
                        success_criteria="Confirmed",
                        status=StepStatus.IN_PROGRESS,
                    )
                ],
                current_step_id=1,
            )
            step = plan.get_current_step()
            assert step is not None

            contingency = check_and_insert_contingencies(plan, step, screen_diff=0.0, caret_active=True)
            assert contingency is None
            assert plan.replan_count == 0
            assert len(plan.steps) == 1

    def test_modal_dialog_contingency_takes_highest_precedence(self) -> None:
        """A blocking modal dialog overrides caret or stagnation issues and inserts DISMISS_DIALOG."""
        plan = LivingPlan(
            user_goal="Type form",
            steps=[
                PlanStep(
                    step_id=1,
                    intent=StepIntent.INPUT_DATA,
                    description="Enter SSN",
                    success_criteria="Typed",
                    status=StepStatus.IN_PROGRESS,
                )
            ],
            current_step_id=1,
        )
        step = plan.get_current_step()
        assert step is not None

        dialog = UIElement.from_bbox(99, (200, 200, 400, 300), label="Security Warning Dialog", role="Window")
        # Caret is false AND screen diff is 0, but blocking dialog is present
        contingency = check_and_insert_contingencies(
            plan, step, screen_diff=0.0, caret_active=False, blocking_dialog=dialog
        )
        assert contingency is not None
        assert contingency.intent == StepIntent.DISMISS_DIALOG
        assert "Security Warning Dialog" in contingency.description
        assert plan.replan_count == 1


# ===========================================================================
# 5. PrecisionAppMatcher Adversarial Boundaries
# ===========================================================================

class TestPrecisionAppMatcherAdversarialBoundaries:
    """Stress tests precision matcher boundaries, destructive verbs, and role filtering."""

    @pytest.mark.parametrize(
        "label,target",
        [
            ("SmartScreen", "art"),
            ("catalog", "cat"),
            ("credit card", "edit"),
            ("swordfish", "word"),
            ("keypad", "pad"),
            ("StartScreen", "art"),
            ("subroutine", "out"),
            ("formulate", "formula"),
        ],
    )
    def test_arbitrary_substring_rejections_score_zero(self, label: str, target: str) -> None:
        """Arbitrary non-boundary substrings must unconditionally score 0.0."""
        assert PrecisionAppMatcher.score_match(label, target) == 0.0

    @pytest.mark.parametrize(
        "destructive_label",
        [
            "Exit Visual Studio",
            "Close Document",
            "Quit App",
            "Cancel Operation",
            "Uninstall Software",
            "Delete Entry",
            "Remove Device",
            "Kill Process",
        ],
    )
    def test_destructive_labels_disqualified(self, destructive_label: str) -> None:
        """Any label containing negative/destructive verbs scores 0.0 for matching."""
        target = "visual studio"
        assert PrecisionAppMatcher.score_match(destructive_label, target) == 0.0

    def test_preferred_role_filtering(self) -> None:
        """Non-preferred roles (e.g. ScrollBar, Separator) are disqualified from best element selection."""
        elements = [
            UIElement.from_bbox(1, (10, 10, 10, 100), label="Notepad", role="ScrollBar"),
            UIElement.from_bbox(2, (10, 110, 100, 2), label="Notepad", role="Separator"),
            UIElement.from_bbox(3, (50, 50, 100, 50), label="Notepad", role="Button"),
        ]

        best = PrecisionAppMatcher.find_best_element("notepad", elements, threshold=0.80)
        assert best is not None
        elem, score = best
        assert elem.id == 3
        assert elem.role == "Button"
        assert score == 1.0
