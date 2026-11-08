"""
tests/test_phase4_final_integration.py - Phase 4 Polish & End-to-End Edge-Case Integration Test Suite.

Validates the Polish & Edge-Case Remediations:
  1. Trailing non-word character boundary matching in PrecisionAppMatcher.score_match
     (e.g., 'notepad++', 'c++', 'c#') in non-prefix positions.
  2. Attached punctuation delimiter parsing in UniversalAppResolver.extract_target_app
     (e.g., 'open visual studio code, then write code').
  3. Defensive None/empty checks in UniversalAppResolver.resolve_launch_action.
  4. LivingPlan dynamic contingency pointer advancement to prerequisite contingency step.
  5. End-to-end integration across Phase 4 components.
"""

import threading
import pytest

from parasite_ai.mind.resolver import PrecisionAppMatcher, UniversalAppResolver
from parasite_ai.mind.plan import (
    LivingPlan,
    PlanStep,
    StepIntent,
    StepStatus,
    check_and_insert_contingencies,
)
from parasite_ai.mind.memory import ActionPlan, ActionType, CadenceTier
from parasite_ai.ui.types import UIElement


# ===========================================================================
# 1. PrecisionAppMatcher Polish: Trailing Non-Word Character Boundaries
# ===========================================================================

class TestPrecisionAppMatcherTrailingNonWord:
    """Verifies that non-word trailing characters (notepad++, c++, c#) match correctly in non-prefix positions."""

    def test_notepad_plus_plus_non_prefix_position(self):
        """'notepad++' in non-prefix positions (e.g. 'GNU / Notepad++ Editor') must score >= 0.80 and not 0.0."""
        score = PrecisionAppMatcher.score_match("GNU / Notepad++ Editor", "notepad++")
        assert score >= 0.80, f"Expected score >= 0.80, got {score}"

    def test_c_plus_plus_non_prefix_position(self):
        """'c++' in non-prefix positions (e.g. 'Modern C++ Compiler') must score >= 0.80 and not 0.0."""
        score = PrecisionAppMatcher.score_match("Modern C++ Compiler", "c++")
        assert score >= 0.80, f"Expected score >= 0.80, got {score}"

    def test_c_sharp_non_prefix_position(self):
        """'c#' in non-prefix positions (e.g. 'Microsoft C# IDE') must score >= 0.80 and not 0.0."""
        score = PrecisionAppMatcher.score_match("Microsoft C# IDE", "c#")
        assert score >= 0.80, f"Expected score >= 0.80, got {score}"

    def test_exact_matches_still_return_one(self):
        assert PrecisionAppMatcher.score_match("Notepad++", "notepad++") == 1.0
        assert PrecisionAppMatcher.score_match("C++", "c++") == 1.0
        assert PrecisionAppMatcher.score_match("C#", "c#") == 1.0

    def test_prefix_matches_still_return_ninety_five(self):
        assert PrecisionAppMatcher.score_match("Notepad++ - Editor", "notepad++") == 0.95
        assert PrecisionAppMatcher.score_match("C++ - Language Spec", "c++") == 0.95

    def test_negative_verb_filter_applies_to_trailing_symbols(self):
        """Destructive verbs disqualify elements even if target matches."""
        assert PrecisionAppMatcher.score_match("Exit Notepad++", "notepad++") == 0.0
        assert PrecisionAppMatcher.score_match("Uninstall Notepad++", "notepad++") == 0.0
        assert PrecisionAppMatcher.score_match("Close C++ Project", "c++") == 0.0

    def test_rejection_of_overextended_symbols(self):
        """'notepad++' must not falsely match 'notepad+++'."""
        assert PrecisionAppMatcher.score_match("Notepad+++ Editor", "notepad++") == 0.0

    def test_word_boundary_rejection_for_symbol_followed_by_alphanumeric(self):
        """'c++' must not match 'c++20' where symbol is followed by word character."""
        assert PrecisionAppMatcher.score_match("C++20 Draft", "c++") == 0.0

    def test_find_best_element_with_trailing_symbols(self):
        elements = [
            UIElement.from_bbox(1, (10, 10, 100, 30), label="SmartScreen", role="Button"),
            UIElement.from_bbox(2, (10, 50, 100, 30), label="Exit Notepad++", role="Button"),
            UIElement.from_bbox(3, (10, 90, 100, 30), label="Community Notepad++ v8.5", role="Button"),
        ]
        best = PrecisionAppMatcher.find_best_element("notepad++", elements)
        assert best is not None
        elem, score = best
        assert elem.id == 3
        assert score >= 0.80


# ===========================================================================
# 2. UniversalAppResolver Polish: Attached Punctuation Delimiters
# ===========================================================================

class TestUniversalAppResolverAttachedPunctuation:
    """Verifies that natural language parsing handles attached punctuation delimiters cleanly."""

    def test_attached_comma_then_pattern(self):
        """'open visual studio code, then write code' -> 'visual studio code'."""
        result = UniversalAppResolver.extract_target_app("open visual studio code, then write code")
        assert result == "visual studio code"

    def test_attached_comma_without_space_then(self):
        """'open visual studio code,then write code' -> 'visual studio code'."""
        result = UniversalAppResolver.extract_target_app("open visual studio code,then write code")
        assert result == "visual studio code"

    def test_attached_comma_please_pattern(self):
        """'launch notepad, please' -> 'notepad'."""
        result = UniversalAppResolver.extract_target_app("launch notepad, please")
        assert result == "notepad"

    def test_attached_semicolon_pattern(self):
        """'start spotify; play some jazz' -> 'spotify'."""
        result = UniversalAppResolver.extract_target_app("start spotify; play some jazz")
        assert result == "spotify"

    def test_attached_colon_pattern(self):
        """'open up discord: chat with friends' -> 'discord'."""
        result = UniversalAppResolver.extract_target_app("open up discord: chat with friends")
        assert result == "discord"

    def test_attached_period_pattern(self):
        """'run powershell. then check git status' -> 'powershell'."""
        result = UniversalAppResolver.extract_target_app("run powershell. then check git status")
        assert result == "powershell"

    def test_target_with_trailing_symbols_and_attached_comma(self):
        """'open notepad++, and edit file' -> 'notepad++'."""
        result = UniversalAppResolver.extract_target_app("open notepad++, and edit file")
        assert result == "notepad++"

    def test_standard_patterns_unaffected(self):
        assert UniversalAppResolver.extract_target_app("open discord") == "discord"
        assert UniversalAppResolver.extract_target_app("launch visual studio code and create a file") == "visual studio code"
        assert UniversalAppResolver.extract_target_app("switch to notepad") == "notepad"
        assert UniversalAppResolver.extract_target_app("open up obsidian") == "obsidian"


# ===========================================================================
# 3. UniversalAppResolver Defensive None / Empty Check
# ===========================================================================

class TestUniversalAppResolverDefensiveNoneCheck:
    """Verifies defensive checks in resolve_launch_action when target_app is None or empty."""

    def test_target_app_none_returns_wait(self):
        resolver = UniversalAppResolver(cadence_buffer_ms=0)
        plan = resolver.resolve_launch_action(None, [])
        assert plan.action == ActionType.WAIT
        assert plan.wait_ms == 500
        assert "No target application identified" in plan.reasoning

    def test_target_app_empty_string_returns_wait(self):
        resolver = UniversalAppResolver(cadence_buffer_ms=0)
        plan = resolver.resolve_launch_action("", [])
        assert plan.action == ActionType.WAIT
        assert plan.wait_ms == 500

    def test_target_app_whitespace_string_returns_wait(self):
        resolver = UniversalAppResolver(cadence_buffer_ms=0)
        plan = resolver.resolve_launch_action("   \t\n", [])
        assert plan.action == ActionType.WAIT
        assert plan.wait_ms == 500

    def test_valid_target_app_resolves_normally(self):
        resolver = UniversalAppResolver(cadence_buffer_ms=0)
        plan = resolver.resolve_launch_action("notepad", [])
        assert plan.action == ActionType.HOTKEY
        assert plan.keys == ["win"]


# ===========================================================================
# 4. LivingPlan Dynamic Contingency Pointer Advancement
# ===========================================================================

class TestLivingPlanContingencyPointerAdvancement:
    """Verifies that check_and_insert_contingencies advances current_step_id to the inserted contingency."""

    def test_caret_contingency_advances_active_pointer(self):
        """When missing caret focus triggers a contingency, current_step_id must point to that contingency."""
        plan = LivingPlan(
            user_goal="Type credentials",
            steps=[
                PlanStep(
                    step_id=1,
                    intent=StepIntent.INPUT_DATA,
                    description="Type username into input field",
                    target_description="Username Input",
                    success_criteria="Username typed",
                    status=StepStatus.IN_PROGRESS,
                ),
                PlanStep(
                    step_id=2,
                    intent=StepIntent.INPUT_DATA,
                    description="Type password",
                    target_description="Password Input",
                    success_criteria="Password typed",
                ),
            ],
            current_step_id=1,
        )

        step = plan.get_current_step()
        assert step is not None

        contingency = check_and_insert_contingencies(plan, step, screen_diff=0.0, caret_active=False)
        assert contingency is not None
        assert contingency.intent == StepIntent.NAVIGATE
        assert "caret" in contingency.description.lower()

        # Invariant: plan.current_step_id must now point to the contingency step
        assert plan.current_step_id == contingency.step_id
        active_step = plan.get_current_step()
        assert active_step is not None
        assert active_step.step_id == contingency.step_id
        assert "caret" in active_step.description.lower()

    def test_stagnation_contingency_advances_active_pointer(self):
        """When 0% diff visual stagnation triggers a contingency, current_step_id must point to that contingency."""
        plan = LivingPlan(
            user_goal="Click button",
            steps=[
                PlanStep(
                    step_id=1,
                    intent=StepIntent.SELECT_OPTION,
                    description="Click Submit",
                    target_description="Submit Button",
                    success_criteria="Form submitted",
                    status=StepStatus.IN_PROGRESS,
                )
            ],
            current_step_id=1,
        )

        step = plan.get_current_step()
        assert step is not None

        contingency = check_and_insert_contingencies(plan, step, screen_diff=0.0001, caret_active=True)
        assert contingency is not None
        assert contingency.intent == StepIntent.NAVIGATE
        assert plan.current_step_id == contingency.step_id
        assert plan.get_current_step().step_id == contingency.step_id

    def test_modal_dialog_contingency_advances_active_pointer(self):
        """When a blocking modal dialog triggers a contingency, current_step_id must point to that contingency."""
        plan = LivingPlan(
            user_goal="Export report",
            steps=[
                PlanStep(
                    step_id=1,
                    intent=StepIntent.NAVIGATE,
                    description="Click Export",
                    target_description="Export Button",
                    success_criteria="File saved",
                    status=StepStatus.IN_PROGRESS,
                )
            ],
            current_step_id=1,
        )

        step = plan.get_current_step()
        assert step is not None

        dialog = UIElement.from_bbox(99, (300, 200, 400, 250), label="Save Confirmation Prompt", role="Window")
        contingency = check_and_insert_contingencies(
            plan, step, screen_diff=0.0, caret_active=True, blocking_dialog=dialog
        )
        assert contingency is not None
        assert contingency.intent == StepIntent.DISMISS_DIALOG
        assert plan.current_step_id == contingency.step_id
        assert plan.get_current_step().step_id == contingency.step_id


# ===========================================================================
# 5. Full End-to-End Synergy Test
# ===========================================================================

class TestPhase4EndToEndSynergy:
    """Verifies that all Phase 4 modules collaborate seamlessly without regression."""

    def test_resolver_three_tier_with_trailing_symbols(self):
        """Resolver gracefully walks Tier 1 -> Tier 2 -> Tier 3 for targets like 'Notepad++'."""
        resolver = UniversalAppResolver(cadence_buffer_ms=0)
        target = "notepad++"

        # Tier 1 fails (no visible elements) -> triggers Tier 2 Start Search chord
        action_t2_1 = resolver.resolve_launch_action(target, [])
        assert action_t2_1.action == ActionType.HOTKEY
        assert action_t2_1.keys == ["win"]

        # Next call simulates active Start Search box typing
        action_t2_2 = resolver.resolve_launch_action(target, [])
        assert action_t2_2.action == ActionType.TYPE
        assert "notepad++\n" in action_t2_2.text

        # Next call transitions to Tier 3 Run Dialog fallback (Win+R)
        action_t3_1 = resolver.resolve_launch_action(target, [])
        assert action_t3_1.action == ActionType.HOTKEY
        assert action_t3_1.keys == ["win", "r"]

        # Next call types into Run dialog
        action_t3_2 = resolver.resolve_launch_action(target, [])
        assert action_t3_2.action == ActionType.TYPE
        assert "notepad++\n" in action_t3_2.text

        # Next call exhausts and emits WAIT without infinite loop
        action_exhaust = resolver.resolve_launch_action(target, [])
        assert action_exhaust.action == ActionType.WAIT
        assert "exhausted" in action_exhaust.reasoning.lower()
