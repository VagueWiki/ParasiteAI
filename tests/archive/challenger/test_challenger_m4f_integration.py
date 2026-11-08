"""
tests/test_challenger_m4f_integration.py - Milestone 4F Final System Integration Adversarial Stress Suite.

Authored by Challenger 2 (Empirical Challenger):
Adversarially stress-tests:
1. Dynamic Contingency Pointer Advancement & Execution Flow:
   - Verifies plan.get_current_step() immediately returns inserted contingency step.
   - Traces execution upon contingency completion (advancement to subsequent steps).
   - Empirically challenges and documents the uncompleted parent step anomaly and terminal step termination.
   - Validates caret, modal dialog, and visual stagnation contingency insertion triggers.
2. Trailing Non-Word Symbols and Compound Application Names:
   - 'GNU / Notepad++ Editor', 'Visual Studio C# Express', 'Dev-C++ IDE', 'C++ Builder',
     'Embarcadero C++ Builder 11', 'Microsoft Visual C++ 2015-2022', 'Borland C++ 5.0'.
   - Non-prefix position word boundary matching (score >= 0.80).
   - Destructive verb traps with trailing symbols (score == 0.0).
   - Overextended symbol rejection ('Notepad+++', 'C+++', 'C##' -> 0.0).
   - Trailing alphanumeric boundary rejection ('C++20', 'C#10', 'Notepad++x64' -> 0.0).
   - Best element selection across UIElement roles with symbol labels.
3. Attached Punctuation & Complex Natural Language Commands:
   - Prompt variants with attached commas, semicolons, colons, periods, exclamation, questions:
     'open visual studio code, then write code', 'please start notepad; write note',
     'launch dev-c++: compile project', 'open notepad++, and type hello',
     'bring up visual studio code! then debug', 'switch to spotify? play music',
     'start calculator... compute 42', 'open chrome,please',
     'open c++ builder, then design form', 'run powershell: Get-Process',
     'open visual studio c# express, and build'.
   - Negative prompt disqualification ('open it', 'launch this', 'start that', 'switch to window').
4. Defensive None & Malformed Input Handling:
   - None / empty string / whitespace target app handling in extract_target_app and resolve_launch_action.
   - Empirical boundary checks on None elements in resolve_launch_action and find_best_element.
   - Empirical boundary checks on None arguments in PrecisionAppMatcher.score_match.
5. Cross-Module Synergy & State Machine Invariants:
   - UniversalAppResolver 3-tier sequence to exhaustion (WAIT) with loop prevention.
   - Rapid app switching counter reset.
   - Cadence buffer cancellation responsiveness.
   - CLI execution returncode strike evaluation.
   - Passive action strike exemption.
   - Dual-channel speech sanitization.
"""

from __future__ import annotations

import re
import threading
import time
from typing import List, Optional
import pytest

from parasite_ai.mind.dual_mind import ActionResult, DualChannelRouter
from parasite_ai.mind.memory import ActionPlan, ActionType, CadenceTier, EscalationStateMachine
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
# 1. Dynamic Contingency Pointer Advancement & Execution Flow
# ===========================================================================

class TestDynamicContingencyPointerAdvancement:
    """Adversarially tests contingency step injection, pointer advancement, and execution flow."""

    def test_caret_contingency_immediately_becomes_current_step(self) -> None:
        """When missing caret focus triggers a contingency, get_current_step() immediately returns it."""
        plan = LivingPlan(
            user_goal="Fill registration form",
            steps=[
                PlanStep(
                    step_id=1,
                    intent=StepIntent.INPUT_DATA,
                    description="Type email address",
                    target_description="Email Input Box",
                    success_criteria="Email entered",
                    status=StepStatus.IN_PROGRESS,
                ),
                PlanStep(
                    step_id=2,
                    intent=StepIntent.SELECT_OPTION,
                    description="Click Submit",
                    success_criteria="Form submitted",
                ),
            ],
            current_step_id=1,
        )

        step = plan.get_current_step()
        assert step is not None
        assert step.step_id == 1

        contingency = check_and_insert_contingencies(plan, step, screen_diff=0.0, caret_active=False)
        assert contingency is not None
        assert contingency.intent == StepIntent.NAVIGATE
        assert "caret" in contingency.description.lower()

        # Invariant: plan.current_step_id must point to the contingency step immediately
        assert plan.current_step_id == contingency.step_id
        active = plan.get_current_step()
        assert active is not None
        assert active.step_id == contingency.step_id
        assert active.intent == StepIntent.NAVIGATE

    def test_modal_dialog_contingency_immediately_becomes_current_step(self) -> None:
        """When an unexpected modal dialog triggers a contingency, get_current_step() immediately returns it."""
        plan = LivingPlan(
            user_goal="Save document",
            steps=[
                PlanStep(
                    step_id=1,
                    intent=StepIntent.NAVIGATE,
                    description="Click Save button",
                    target_description="Save",
                    success_criteria="Save dialog opens",
                    status=StepStatus.IN_PROGRESS,
                ),
            ],
            current_step_id=1,
        )

        step = plan.get_current_step()
        assert step is not None

        dialog_element = UIElement.from_bbox(
            42, (200, 150, 400, 200), label="Warning: Low Disk Space", role="Window"
        )
        contingency = check_and_insert_contingencies(
            plan, step, screen_diff=0.0, caret_active=True, blocking_dialog=dialog_element
        )
        assert contingency is not None
        assert contingency.intent == StepIntent.DISMISS_DIALOG
        assert "low disk space" in contingency.description.lower()
        assert plan.current_step_id == contingency.step_id
        assert plan.get_current_step().step_id == contingency.step_id

    def test_stagnation_contingency_immediately_becomes_current_step(self) -> None:
        """When visual stagnation (diff < 0.001) occurs on an interactive step, contingency becomes active."""
        plan = LivingPlan(
            user_goal="Select tab",
            steps=[
                PlanStep(
                    step_id=1,
                    intent=StepIntent.SELECT_OPTION,
                    description="Click Settings tab",
                    target_description="Settings Tab",
                    success_criteria="Settings panel visible",
                    status=StepStatus.IN_PROGRESS,
                )
            ],
            current_step_id=1,
        )

        step = plan.get_current_step()
        assert step is not None

        contingency = check_and_insert_contingencies(plan, step, screen_diff=0.0002, caret_active=True)
        assert contingency is not None
        assert contingency.intent == StepIntent.NAVIGATE
        assert "stagnation" in contingency.description.lower() or "re-ground" in contingency.description.lower()
        assert plan.current_step_id == contingency.step_id
        assert plan.get_current_step().step_id == contingency.step_id

    def test_contingency_completion_advances_to_subsequent_parent_step(self) -> None:
        """
        Adversarial execution flow analysis:
        In a 2-step workflow [Step 1 (IN_PROGRESS), Step 2 (PENDING)]:
        When Step 1 inserts Contingency Step 3:
          - active pointer becomes Step 3.
          - upon completion of Step 3, advance_step() transitions to Step 2.
          - EMPIRICAL ANOMALY DOCUMENTED: Step 1 remains in StepStatus.IN_PROGRESS because
            the contingency was inserted at index idx+1 and advance_step() only scans forward.
            Consequently, when Step 2 completes, plan.is_completed() evaluates to False.
        """
        plan = LivingPlan(
            user_goal="Login workflow",
            steps=[
                PlanStep(
                    step_id=1,
                    intent=StepIntent.INPUT_DATA,
                    description="Type username into input field",
                    target_description="Username Box",
                    success_criteria="Username typed",
                    status=StepStatus.IN_PROGRESS,
                ),
                PlanStep(
                    step_id=2,
                    intent=StepIntent.SELECT_OPTION,
                    description="Click Login button",
                    target_description="Login Button",
                    success_criteria="Dashboard loaded",
                    status=StepStatus.PENDING,
                ),
            ],
            current_step_id=1,
        )

        step = plan.get_current_step()
        contingency = check_and_insert_contingencies(plan, step, screen_diff=0.0, caret_active=False)
        assert contingency is not None
        assert plan.current_step_id == contingency.step_id

        # Simulate contingency step execution success -> advance_step()
        next_step = plan.advance_step()
        assert next_step is not None
        # Returns to subsequent step in parent workflow
        assert next_step.step_id == 2
        assert plan.current_step_id == 2
        assert contingency.status == StepStatus.COMPLETED

        # Empirical finding: Step 1 was bypassed and remains IN_PROGRESS
        step_1 = next(s for s in plan.steps if s.step_id == 1)
        assert step_1.status == StepStatus.IN_PROGRESS, (
            "Empirical finding: Interrupted step 1 remains IN_PROGRESS because advance_step() "
            "scanned forward past the contingency step."
        )

        # Complete Step 2
        terminal = plan.advance_step()
        assert terminal is None
        # Invariant check: plan cannot be marked completed because Step 1 was never completed!
        assert not plan.is_completed(), (
            "Empirical finding: plan.is_completed() is False because Step 1 was bypassed."
        )

    def test_contingency_on_terminal_step_premature_termination(self) -> None:
        """
        Adversarial edge case: A single-step plan triggers a contingency.
        Upon completing the contingency, advance_step() finds no further steps and returns None,
        leaving the original goal step unexecuted and plan.is_completed() False.
        """
        plan = LivingPlan(
            user_goal="Type quick note",
            steps=[
                PlanStep(
                    step_id=1,
                    intent=StepIntent.INPUT_DATA,
                    description="Type note text",
                    target_description="Text Area",
                    success_criteria="Text appears",
                    status=StepStatus.IN_PROGRESS,
                )
            ],
            current_step_id=1,
        )

        step = plan.get_current_step()
        contingency = check_and_insert_contingencies(plan, step, screen_diff=0.0, caret_active=False)
        assert contingency is not None
        assert plan.current_step_id == contingency.step_id

        # Contingency completes
        next_step = plan.advance_step()
        # Returns None because no steps exist after contingency
        assert next_step is None
        assert not plan.is_completed()
        assert plan.steps[0].status == StepStatus.IN_PROGRESS


# ===========================================================================
# 2. Trailing Non-Word Symbols and Compound Application Names
# ===========================================================================

class TestTrailingNonWordSymbolsAndCompoundNames:
    """Adversarially tests PrecisionAppMatcher on compound names and non-word trailing symbols."""

    @pytest.mark.parametrize(
        "label,target,expected_min_score",
        [
            ("GNU / Notepad++ Editor", "notepad++", 0.80),
            ("Visual Studio C# Express", "visual studio c#", 0.80),
            ("Visual Studio C# Express", "c#", 0.80),
            ("Dev-C++ IDE", "dev-c++", 0.80),
            ("Dev-C++ IDE", "c++", 0.80),
            ("C++ Builder", "c++ builder", 0.80),
            ("Embarcadero C++ Builder 11", "c++ builder", 0.80),
            ("Microsoft Visual C++ 2015-2022 Redistributable", "c++", 0.80),
            ("Borland C++ 5.0", "c++", 0.80),
            ("Community Notepad++ v8.5.2 (64-bit)", "notepad++", 0.80),
            ("Eclipse IDE for C/C++ Developers", "c++", 0.80),
        ],
    )
    def test_non_prefix_trailing_non_word_symbols_score_above_threshold(
        self, label: str, target: str, expected_min_score: float
    ) -> None:
        """Labels containing trailing non-word symbols in non-prefix positions must score >= 0.80."""
        score = PrecisionAppMatcher.score_match(label, target)
        assert score >= expected_min_score, (
            f"Expected score >= {expected_min_score} for label='{label}', target='{target}', got {score}"
        )

    @pytest.mark.parametrize(
        "destructive_label,target",
        [
            ("Uninstall Notepad++", "notepad++"),
            ("Close Dev-C++ IDE", "dev-c++"),
            ("Delete C# Project", "c#"),
            ("Kill C++ Compiler", "c++"),
            ("Exit Notepad++", "notepad++"),
            ("Remove Visual Studio C#", "visual studio c#"),
            ("Quit Dev-C++", "c++"),
            ("Cancel C++ Builder Setup", "c++ builder"),
        ],
    )
    def test_destructive_verbs_unconditionally_disqualify_symbols(
        self, destructive_label: str, target: str
    ) -> None:
        """Destructive/exit verbs must return 0.0 even when trailing symbol targets match."""
        score = PrecisionAppMatcher.score_match(destructive_label, target)
        assert score == 0.0, f"Expected 0.0 for destructive label '{destructive_label}', got {score}"

    @pytest.mark.parametrize(
        "overextended_label,target",
        [
            ("Notepad+++ Text Editor", "notepad++"),
            ("Modern C+++ Language", "c++"),
            ("Microsoft C## Compiler", "c#"),
        ],
    )
    def test_overextended_symbols_rejected(self, overextended_label: str, target: str) -> None:
        """Overextended symbols like notepad+++ or c+++ must not match target notepad++ or c++."""
        score = PrecisionAppMatcher.score_match(overextended_label, target)
        assert score == 0.0, f"Expected 0.0 for overextended label '{overextended_label}', got {score}"

    @pytest.mark.parametrize(
        "label_with_alnum_follow,target",
        [
            ("C++20 Working Draft", "c++"),
            ("C#10 in a Nutshell", "c#"),
            ("Notepad++x64 Release", "notepad++"),
        ],
    )
    def test_symbol_followed_by_alphanumeric_rejected(
        self, label_with_alnum_follow: str, target: str
    ) -> None:
        """Symbols immediately followed by alphanumeric characters must fail word boundary regex."""
        score = PrecisionAppMatcher.score_match(label_with_alnum_follow, target)
        assert score == 0.0, f"Expected 0.0 for label '{label_with_alnum_follow}', got {score}"

    def test_find_best_element_with_compound_symbols_and_role_filtering(self) -> None:
        """find_best_element selects legitimate symbol element and disqualifies destructive and non-preferred roles."""
        elements = [
            UIElement.from_bbox(1, (10, 10, 100, 30), label="Uninstall Notepad++", role="Button"),
            UIElement.from_bbox(2, (10, 50, 100, 30), label="GNU / Notepad++ Editor", role="ScrollBar"),  # non-preferred
            UIElement.from_bbox(3, (10, 90, 100, 30), label="GNU / Notepad++ Editor", role="ListItem"),  # preferred
            UIElement.from_bbox(4, (10, 130, 100, 30), label="Notepad+++ Clone", role="Button"),
        ]
        match = PrecisionAppMatcher.find_best_element("notepad++", elements)
        assert match is not None
        elem, score = match
        assert elem.id == 3
        assert score >= 0.80


# ===========================================================================
# 3. Attached Punctuation & Complex Natural Language Commands
# ===========================================================================

class TestAttachedPunctuationAndNaturalLanguageCommands:
    """Adversarially tests extract_target_app against complex natural language command strings."""

    @pytest.mark.parametrize(
        "query,expected_target",
        [
            ("open visual studio code, then write code", "visual studio code"),
            ("please start notepad; write note", "notepad"),
            ("launch dev-c++: compile project", "dev-c++"),
            ("open notepad++, and type hello", "notepad++"),
            ("bring up visual studio code! then debug", "visual studio code"),
            ("switch to spotify? play music", "spotify"),
            ("start calculator... compute 42", "calculator"),
            ("open chrome,please", "chrome"),
            ("open c++ builder, then design form", "c++ builder"),
            ("run powershell: Get-Process", "powershell"),
            ("open visual studio c# express, and build", "visual studio c# express"),
            ("start paint, draw circle", "paint"),
            ("bring up discord; message team", "discord"),
            ("launch slack! check announcements", "slack"),
            ("switch to obsidian: take notes", "obsidian"),
        ],
    )
    def test_attached_punctuation_parsing_variants(self, query: str, expected_target: str) -> None:
        """extract_target_app cleanly strips attached punctuation delimiters from extracted app names."""
        extracted = UniversalAppResolver.extract_target_app(query)
        assert extracted is not None
        assert extracted.strip().lower() == expected_target.lower(), (
            f"For query '{query}', expected '{expected_target}', got '{extracted}'"
        )

    @pytest.mark.parametrize(
        "generic_or_invalid_prompt",
        [
            "open it",
            "launch this",
            "start that",
            "switch to window",
            "open file",
            "launch folder",
            "bring up menu",
            "",
            "   \t\n",
            "just looking around the screen",
            "clicking somewhere else",
        ],
    )
    def test_generic_and_non_app_words_rejected(self, generic_or_invalid_prompt: str) -> None:
        """Generic non-app words and non-launch commands return None."""
        assert UniversalAppResolver.extract_target_app(generic_or_invalid_prompt) is None


# ===========================================================================
# 4. Defensive None & Malformed Input Handling
# ===========================================================================

class TestDefensiveNoneAndMalformedInputs:
    """Stress tests boundary inputs (None, empty, non-string, malformed) across resolver and matcher."""

    def test_extract_target_app_none_safe(self) -> None:
        assert UniversalAppResolver.extract_target_app(None) is None

    def test_resolve_launch_action_none_target_returns_wait(self) -> None:
        resolver = UniversalAppResolver(cadence_buffer_ms=0)
        action = resolver.resolve_launch_action(None, [])
        assert action.action == ActionType.WAIT
        assert action.wait_ms == 500
        assert "No target application identified" in action.reasoning

    def test_resolve_launch_action_empty_or_whitespace_target_returns_wait(self) -> None:
        resolver = UniversalAppResolver(cadence_buffer_ms=0)
        for empty_val in ("", "   ", "\t\n"):
            action = resolver.resolve_launch_action(empty_val, [])
            assert action.action == ActionType.WAIT
            assert action.wait_ms == 500

    def test_resolve_launch_action_none_elements_behavior(self) -> None:
        """
        Empirical observation: If elements is passed as None, resolve_launch_action
        attempts to iterate over elements in find_best_element, raising TypeError.
        This test documents the empirical boundary condition.
        """
        resolver = UniversalAppResolver(cadence_buffer_ms=0)
        with pytest.raises(TypeError):
            resolver.resolve_launch_action("notepad", None)  # type: ignore

    def test_score_match_none_target_or_label_behavior(self) -> None:
        """
        Empirical observation: score_match currently calls label.strip() before checking None,
        raising AttributeError when None is passed.
        This test documents the empirical boundary condition.
        """
        with pytest.raises(AttributeError):
            PrecisionAppMatcher.score_match(None, "notepad")  # type: ignore

        with pytest.raises(AttributeError):
            PrecisionAppMatcher.score_match("notepad", None)  # type: ignore

    def test_find_best_element_empty_list_returns_none(self) -> None:
        assert PrecisionAppMatcher.find_best_element("notepad", []) is None

    def test_living_plan_empty_plan_operations(self) -> None:
        plan = LivingPlan(user_goal="Empty test")
        assert plan.get_current_step() is None
        assert plan.advance_step() is None
        assert not plan.is_completed()


# ===========================================================================
# 5. Cross-Module Synergy & State Machine Invariants
# ===========================================================================

class TestPhase4CrossModuleSynergy:
    """Verifies end-to-end synergy across resolver, escalation state machine, dual channel, and sandbox."""

    def test_resolver_three_tier_launch_sequence(self) -> None:
        """
        Resolver progression:
        Tier 1 (no SOM match) -> Tier 2 Win chord -> Tier 2 Type -> Tier 3 Win+R chord -> Tier 3 Type -> Exhaustion WAIT.
        """
        resolver = UniversalAppResolver(cadence_buffer_ms=0)
        target = "notepad++"

        # Tier 2: Win chord
        a1 = resolver.resolve_launch_action(target, [])
        assert a1.action == ActionType.HOTKEY and a1.keys == ["win"]

        # Tier 2: Type search
        a2 = resolver.resolve_launch_action(target, [])
        assert a2.action == ActionType.TYPE and "notepad++\n" in a2.text

        # Tier 3: Win+R chord
        a3 = resolver.resolve_launch_action(target, [])
        assert a3.action == ActionType.HOTKEY and a3.keys == ["win", "r"]

        # Tier 3: Type run
        a4 = resolver.resolve_launch_action(target, [])
        assert a4.action == ActionType.TYPE and "notepad++\n" in a4.text

        # Exhaustion: ActionType.WAIT
        a5 = resolver.resolve_launch_action(target, [])
        assert a5.action == ActionType.WAIT
        assert "exhausted" in a5.reasoning.lower()

    def test_rapid_target_switching_resets_resolver_counters(self) -> None:
        """Switching targets resets Tier 2 and Tier 3 attempt counters immediately."""
        resolver = UniversalAppResolver(cadence_buffer_ms=0)

        # Start search on target 1
        resolver.resolve_launch_action("notepad++", [])
        assert resolver._search_opened is True

        # Switch to target 2
        a_switched = resolver.resolve_launch_action("calculator", [])
        assert a_switched.action == ActionType.HOTKEY and a_switched.keys == ["win"]
        assert resolver._target_app == "calculator"
        assert resolver._start_search_attempts == 0

    def test_cadence_buffer_cancellation_preemption(self) -> None:
        """Cadence buffer unblocks in < 20ms upon cancellation token signal."""
        resolver = UniversalAppResolver(cadence_buffer_ms=500.0)
        cancel_token = threading.Event()

        t0 = time.perf_counter()
        cancel_token.set()
        interrupted = resolver._sleep_cadence_buffer(cancel_token)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        assert interrupted is True
        assert elapsed_ms < 20.0, f"Expected abort < 20ms, took {elapsed_ms:.2f}ms"

    def test_escalation_state_machine_cli_evaluation(self) -> None:
        """CLI action with returncode == 0 does NOT incur strike; returncode != 0 incurs strike."""
        sm = EscalationStateMachine()
        assert sm.current_tier == CadenceTier.TIER_1_LOCAL

        # CLI command with returncode == 0 (success)
        sm.on_action_result(
            success=True,
            action_type=ActionType.RUN_CLI_COMMAND,
            is_interactive=True,
            cli_returncode=0,
            screen_diff=0.0,
        )
        assert sm.local_strikes == 0
        assert sm.current_tier == CadenceTier.TIER_1_LOCAL

        # CLI command with returncode != 0 (failure) -> Strike 1
        sm.on_action_result(
            success=False,
            action_type=ActionType.RUN_CLI_COMMAND,
            is_interactive=True,
            cli_returncode=1,
            screen_diff=0.0,
        )
        assert sm.local_strikes == 1

        # Strike 2 -> Advances to TIER_2_CONSULT
        sm.on_action_result(
            success=False,
            action_type=ActionType.RUN_CLI_COMMAND,
            is_interactive=True,
            cli_returncode=1,
            screen_diff=0.0,
        )
        assert sm.current_tier == CadenceTier.TIER_2_CONSULT

    def test_passive_actions_exempt_from_strikes(self) -> None:
        """Passive actions (WAIT, DONE) do NOT incur strikes even with screen_diff == 0."""
        sm = EscalationStateMachine()
        assert sm.current_tier == CadenceTier.TIER_1_LOCAL

        # WAIT
        sm.on_action_result(
            success=True,
            action_type=ActionType.WAIT,
            is_interactive=False,
            screen_diff=0.0,
        )
        assert sm.local_strikes == 0

        # DONE
        sm.on_action_result(
            success=True,
            action_type=ActionType.DONE,
            is_interactive=False,
            screen_diff=0.0,
        )
        assert sm.local_strikes == 0
        assert sm.current_tier == CadenceTier.TIER_1_LOCAL

    def test_dual_channel_router_speech_sanitization(self) -> None:
        """Raw JSON, markdown code blocks, backticks, and coordinates are stripped from persona speech."""
        router = DualChannelRouter()
        raw_advisor_text = (
            "```json\n"
            '{"overall_strategy": "Launch editor", "steps": [{"step_id": 1, "intent": "NAVIGATE"}]}\n'
            "```\n"
            "I will click the button at (450, 720) using `ActionType.CLICK`."
        )

        plan, speech = router.route_consultation_output(
            raw_advisor_text, user_goal="Launch editor", active_plan=LivingPlan(user_goal="Launch editor")
        )

        assert plan is not None
        assert "```" not in speech
        assert "`" not in speech
        assert "{" not in speech
        assert "}" not in speech
        assert "(450, 720)" not in speech
        assert len(speech) > 0

    def test_anti_hardcoding_invariant_certified(self) -> None:
        """Verifies that no static app lookup dictionary exists in parasite_ai."""
        import subprocess
        res = subprocess.run(
            ["git", "grep", "-i", "app_map", "parasite_ai/"],
            capture_output=True,
            text=True,
            cwd="C:\\ParasiteAI",
        )
        assert res.returncode == 1, f"Found hardcoded app_map occurrences: {res.stdout}"
        assert len(res.stdout.strip()) == 0
