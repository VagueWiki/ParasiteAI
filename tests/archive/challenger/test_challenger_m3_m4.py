"""
Adversarial and Empirical Stress Test Harness for Milestones M3 & M4 (R4 & R5).
Written by Challenger 2 (teamwork_challenger).
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from typing import Any, List, Tuple
from unittest.mock import MagicMock

import pytest

from parasite_ai.config import SafetyConfig
from parasite_ai.safety.panic import (
    PanicManager,
    PanicTriggerSource,
    LLMHF_INJECTED,
)
from parasite_ai.mind.plan import (
    LivingPlan,
    PlanStep,
    StepIntent,
    StepStatus,
    extract_strategic_blueprint_json,
    parse_gemini_consultation_response,
    format_gemini_consultation_prompt,
)


class MockInputBackend:
    """Mock input backend tracking dispatches and screen metrics."""
    def __init__(self, screen_metrics=(1920, 1080, 0, 0, 1920, 1080)):
        self.screen_metrics = screen_metrics
        self.events: List[Any] = []
        self.release_called = False

    def get_screen_metrics(self) -> Tuple[int, int, int, int, int, int]:
        return self.screen_metrics

    def emergency_hardware_release(self) -> None:
        self.release_called = True


# ===========================================================================
# 1. R4 Stress Testing: Mouse Flood, Corner Oscillations, Multi-Monitor
# ===========================================================================

class TestR4MouseCornerFloodAndDebounceChallenge:
    """Empirical stress challenge for PanicManager.check_mouse_position."""

    def test_flood_5000_synthetic_injected_packets_never_panic(self):
        """Synthetic injected packets (flags=LLMHF_INJECTED) must NEVER trigger panic."""
        backend = MockInputBackend(screen_metrics=(1920, 1080, 0, 0, 1920, 1080))
        callback = MagicMock()
        panic = PanicManager(backend=backend, on_panic_callback=callback)

        corners = [(0, 0), (1919, 0), (0, 1079), (1919, 1079)]
        for i in range(5000):
            cx, cy = corners[i % 4]
            fired = panic.check_mouse_position(cx, cy, flags=LLMHF_INJECTED)
            assert fired is False, f"Synthetic packet {i} triggered panic!"

        assert callback.call_count == 0
        assert panic.is_panic() is False
        assert panic.get_panic_reason() is None

    def test_flood_5000_physical_packets_in_corner_triggers_strictly_once(self, monkeypatch):
        """5000 high-frequency physical packets in corner zone within 1.0s must trigger ONLY 1 panic."""
        backend = MockInputBackend(screen_metrics=(1920, 1080, 0, 0, 1920, 1080))
        callback = MagicMock()
        panic = PanicManager(backend=backend, on_panic_callback=callback)

        simulated_time = 100.0
        monkeypatch.setattr(time, "monotonic", lambda: simulated_time)

        panics_fired = 0
        # 5000 packets dispatched over 0.5s (10,000 packets/sec flood)
        for i in range(5000):
            simulated_time = 100.0 + (i * 0.0001)  # reaches 100.4999s (< 1.0s)
            # Jitter within delta=4 around corner (0, 0)
            x, y = i % 4, (i // 4) % 4
            fired = panic.check_mouse_position(x, y, flags=0)
            if fired:
                panics_fired += 1

        assert panics_fired == 1, f"Expected strictly 1 panic trigger, got {panics_fired}"
        assert callback.call_count == 1
        assert panic.is_panic() is True
        assert panic.get_panic_reason() == PanicTriggerSource.CORNER_SLAM

    def test_high_frequency_boundary_oscillations_across_threshold(self, monkeypatch):
        """
        Oscillate cursor across the delta=4 threshold 5,000 times within 1.0s.
        Must strictly trigger on the first entry, and debounce all subsequent re-entries
        until cooldown >= 1.0s has elapsed.
        """
        backend = MockInputBackend(screen_metrics=(1920, 1080, 0, 0, 1920, 1080))
        callback = MagicMock()
        panic = PanicManager(backend=backend, on_panic_callback=callback)

        simulated_time = 100.0
        monkeypatch.setattr(time, "monotonic", lambda: simulated_time)

        panics_fired = 0
        # Oscillate between (4,4) [in corner] and (5,5) [out of corner]
        for i in range(5000):
            simulated_time = 100.0 + (i * 0.00015)  # 0.0s to 0.75s (< 1.0s)
            if i % 2 == 0:
                # In corner
                fired = panic.check_mouse_position(4, 4, flags=0)
            else:
                # Out of corner
                fired = panic.check_mouse_position(5, 5, flags=0)
            if fired:
                panics_fired += 1

        # Across 2,500 entries into corner, ONLY the first entry at t=100.0 must fire
        assert panics_fired == 1
        assert callback.call_count == 1

        # Now advance time past the 1.0s cooldown: t = 101.05s
        simulated_time = 101.05
        # Cursor enters corner again
        fired_after_cooldown = panic.check_mouse_position(4, 4, flags=0)
        assert fired_after_cooldown is True
        assert callback.call_count == 2

        # Another 2,000 oscillations between 101.05s and 101.85s (< 1.0s since 101.05)
        for i in range(2000):
            simulated_time = 101.05 + (i * 0.0004)
            if i % 2 == 0:
                fired = panic.check_mouse_position(4, 4, flags=0)
            else:
                fired = panic.check_mouse_position(5, 5, flags=0)
            if fired:
                panics_fired += 1

        # No additional panics should have fired
        assert callback.call_count == 2

    def test_multi_monitor_and_negative_virtual_coordinates(self):
        """Multi-monitor setups with negative coordinates must accurately detect all virtual corners."""
        # Dual-monitor: Primary 1920x1080 at (0, 0), Secondary 1920x1080 at (-1920, 0)
        # Virtual desktop: vx = -1920, vy = 0, vcx = 3840, vcy = 1080
        backend = MockInputBackend(screen_metrics=(1920, 1080, -1920, 0, 3840, 1080))
        callback = MagicMock()
        panic = PanicManager(backend=backend, on_panic_callback=callback)

        # Corners:
        # 1. Virtual Far Top-Left (-1920, 0)
        panic.reset_panic()
        assert panic.check_mouse_position(-1920, 0, flags=0) is True
        assert panic.is_panic() is True

        # 2. Virtual Far Bottom-Left (-1920, 1079)
        panic.reset_panic()
        assert panic.check_mouse_position(-1920, 1079, flags=0) is True

        # 3. Virtual Far Top-Right (1919, 0)
        panic.reset_panic()
        assert panic.check_mouse_position(1919, 0, flags=0) is True

        # 4. Virtual Far Bottom-Right (1919, 1079)
        panic.reset_panic()
        assert panic.check_mouse_position(1919, 1079, flags=0) is True

        # 5. Non-corners in secondary monitor should NOT trigger
        panic.reset_panic()
        assert panic.check_mouse_position(-960, 540, flags=0) is False
        assert panic.check_mouse_position(-1900, 100, flags=0) is False
        assert panic.is_panic() is False

    def test_triple_monitor_complex_topology_and_near_corner_boundary(self):
        """Triple monitor with vertical offset (vx=0, vy=-1080, vcx=3840, vcy=2160)."""
        backend = MockInputBackend(screen_metrics=(1920, 1080, 0, -1080, 3840, 2160))
        panic = PanicManager(backend=backend)

        # Virtual top-left is (0, -1080)
        panic.reset_panic()
        assert panic.check_mouse_position(0, -1080, flags=0) is True

        # Just outside delta: (6, -1080) -> delta=4
        panic.reset_panic()
        assert panic.check_mouse_position(6, -1080, flags=0) is False


# ===========================================================================
# 2. R4 Stress Testing: Deadlock and Exception Immunity on Ctrl+Alt+K Kill
# ===========================================================================

class TestR4CtrlAltKDeadlockAndExceptionImmunityChallenge:
    """Empirical challenge for PanicManager.trigger_panic(CTRL_ALT_K_KILL)."""

    def test_ctrl_alt_k_bypasses_hung_or_deadlocked_callbacks(self, monkeypatch):
        """
        When callbacks raise exceptions or deadlock, trigger_panic(CTRL_ALT_K_KILL)
        MUST execute hard_kill_all_processes() immediately and exit without blocking.
        """
        mock_popen = MagicMock()
        mock_exit = MagicMock()
        monkeypatch.setattr(subprocess, "Popen", mock_popen)
        monkeypatch.setattr(os, "_exit", mock_exit)

        backend = MockInputBackend()
        panic = PanicManager(backend=backend)
        panic.allow_process_exit = True

        hang_event = threading.Event()

        def hanging_callback(reason: str):
            # Simulates a hung/deadlocked UI thread or modal dialog
            hang_event.wait(timeout=10.0)

        def exploding_callback(reason: str):
            raise RuntimeError("Fatal callback error")

        panic.register_callback(hanging_callback)
        panic.register_callback(exploding_callback)

        start_time = time.monotonic()
        panic.trigger_panic(PanicTriggerSource.CTRL_ALT_K_KILL)
        duration = time.monotonic() - start_time

        # Must execute within < 50ms without waiting for hang_event or crashing on exploding_callback
        assert duration < 0.2, f"Execution blocked: took {duration}s"

        # Verify taskkill invocation
        mock_popen.assert_called_once()
        cmd = mock_popen.call_args[0][0]
        assert cmd[:4] == ["taskkill", "/F", "/T", "/PID"]
        assert cmd[4] == str(os.getpid())

        # Verify immediate os._exit(1)
        mock_exit.assert_called_once_with(1)

    def test_hard_kill_resilient_to_failing_hardware_release_and_subprocess(self, monkeypatch):
        """Even if hardware release or subprocess raise unexpected exceptions, os._exit(1) is guaranteed."""
        mock_exit = MagicMock()
        monkeypatch.setattr(os, "_exit", mock_exit)

        # Force emergency_hardware_release and Popen to raise exceptions
        class FailingBackend:
            def emergency_hardware_release(self):
                raise RuntimeError("Hardware bus error")

        def failing_popen(*args, **kwargs):
            raise OSError("Subprocess creation failed")

        monkeypatch.setattr(subprocess, "Popen", failing_popen)

        panic = PanicManager(backend=FailingBackend())
        panic.hard_kill_all_processes()

        # os._exit(1) must still be reached and called with 1
        mock_exit.assert_called_once_with(1)

    def test_ctrl_alt_k_when_exit_not_allowed_catches_all_callback_exceptions(self):
        """When allow_process_exit is False, callback exceptions do not bubble up or halt other callbacks."""
        backend = MockInputBackend()
        panic = PanicManager(backend=backend)
        panic.allow_process_exit = False

        called: List[str] = []

        def cb1(reason: str):
            called.append("cb1")
            raise ValueError("cb1 failed")

        def cb2(reason: str):
            called.append("cb2")
            raise ZeroDivisionError("cb2 division by zero")

        def cb3(reason: str):
            called.append("cb3")

        panic.register_callback(cb1)
        panic.register_callback(cb2)
        panic.register_callback(cb3)

        # Must not raise
        panic.trigger_panic(PanicTriggerSource.CTRL_ALT_K_KILL)

        # All callbacks attempted despite exceptions
        assert called == ["cb1", "cb2", "cb3"]
        assert panic.is_panic() is True


# ===========================================================================
# 3. R5 Stress Testing: LivingPlan Mutations, Dynamic Contingencies & Lifecycle
# ===========================================================================

class TestR5LivingPlanMutationsChallenge:
    """Empirical challenge for dynamic LivingPlan mutations and lifecycle."""

    def test_multilevel_dynamic_contingency_step_injection(self):
        """
        Tests multi-level contingency injection:
        Base plan: Step 1 -> Step 2 -> Step 3.
        While executing Step 2, inject contingency Step 201.
        While executing Step 201, inject nested contingency Step 202.
        Verify correct in-order execution across all levels and completion.
        """
        step1 = PlanStep(step_id=1, intent=StepIntent.LAUNCH_OR_ACTIVATE, description="Open App", success_criteria="App open")
        step2 = PlanStep(step_id=2, intent=StepIntent.NAVIGATE, description="Go to Settings", success_criteria="Settings open")
        step3 = PlanStep(step_id=3, intent=StepIntent.CONCLUDE, description="Finish task", success_criteria="Task done")

        plan = LivingPlan(user_goal="Configure system", steps=[step1, step2, step3], current_step_id=1)

        # Step 1: Open App -> completed
        next_step = plan.advance_step()
        assert next_step.step_id == 2
        assert plan.steps[0].status == StepStatus.COMPLETED
        assert plan.steps[1].status == StepStatus.IN_PROGRESS

        # Step 2: Blocked by modal -> Inject Contingency 201
        step201 = PlanStep(
            step_id=201,
            intent=StepIntent.DISMISS_DIALOG,
            description="Dismiss modal",
            success_criteria="Modal closed",
            status=StepStatus.PENDING,
        )
        plan.insert_contingency_step(step201)
        assert plan.replan_count == 1
        assert [s.step_id for s in plan.steps] == [1, 2, 201, 3]

        # Step 2 completes -> Advance to Step 201
        next_step = plan.advance_step()
        assert next_step.step_id == 201
        assert plan.current_step_id == 201
        assert plan.get_current_step().status == StepStatus.IN_PROGRESS

        # Nested Contingency: Step 201 triggers another sub-contingency Step 202
        step202 = PlanStep(
            step_id=202,
            intent=StepIntent.VERIFY_STATE,
            description="Verify modal gone",
            success_criteria="Clean screen",
            status=StepStatus.PENDING,
        )
        plan.insert_contingency_step(step202)
        assert plan.replan_count == 2
        assert [s.step_id for s in plan.steps] == [1, 2, 201, 202, 3]

        # Step 201 completes -> Advance to Step 202
        next_step = plan.advance_step()
        assert next_step.step_id == 202
        assert plan.current_step_id == 202

        # Step 202 completes -> Resume original Step 3
        next_step = plan.advance_step()
        assert next_step.step_id == 3
        assert plan.current_step_id == 3

        # Step 3 completes -> Plan finished
        next_step = plan.advance_step()
        assert next_step is None
        assert plan.is_completed() is True
        assert all(s.status == StepStatus.COMPLETED for s in plan.steps)

    def test_out_of_order_completion_and_skipping(self):
        """Steps completed or skipped out of sequential order must be handled cleanly."""
        steps = [
            PlanStep(step_id=1, intent=StepIntent.LAUNCH_OR_ACTIVATE, description="S1", success_criteria="C1"),
            PlanStep(step_id=2, intent=StepIntent.NAVIGATE, description="S2", success_criteria="C2"),
            PlanStep(step_id=3, intent=StepIntent.INPUT_DATA, description="S3", success_criteria="C3"),
            PlanStep(step_id=4, intent=StepIntent.CONCLUDE, description="S4", success_criteria="C4"),
        ]
        plan = LivingPlan(user_goal="Test out of order", steps=steps, current_step_id=1)

        # Mark step 2 as SKIPPED and step 3 as already COMPLETED
        plan.steps[1].status = StepStatus.SKIPPED
        plan.steps[2].status = StepStatus.COMPLETED

        # Advance from Step 1: should skip 2 & 3 and land on Step 4
        next_step = plan.advance_step()
        assert next_step.step_id == 4
        assert plan.current_step_id == 4

        # Complete Step 4
        next_step = plan.advance_step()
        assert next_step is None
        assert plan.is_completed() is True

    def test_failed_step_contingency_recording_and_completion_blocker(self):
        """Failed steps record reasons and strictly block is_completed()."""
        steps = [
            PlanStep(step_id=1, intent=StepIntent.LAUNCH_OR_ACTIVATE, description="S1", success_criteria="C1"),
            PlanStep(step_id=2, intent=StepIntent.NAVIGATE, description="S2", success_criteria="C2"),
        ]
        plan = LivingPlan(user_goal="Test failure", steps=steps, current_step_id=1)

        plan.advance_step()  # Step 1 -> COMPLETED, Step 2 -> IN_PROGRESS
        plan.mark_step_failed(step_id=2, reason="Element obscured by unknown window")

        assert plan.steps[1].status == StepStatus.FAILED
        assert "Element obscured by unknown window" in plan.steps[1].contingency
        assert plan.is_completed() is False

        # Prompt context reflects active failed step with (FAILED)
        context = plan.to_prompt_context()
        assert "(FAILED)" in context
        assert "[→] Step 2: NAVIGATE" in context
        assert "[✓] Step 1: LAUNCH_OR_ACTIVATE" in context

        # When current_step_id points elsewhere, non-active failed step renders [✗]
        plan.current_step_id = 999
        context_inactive = plan.to_prompt_context()
        assert "[✗] Step 2: NAVIGATE" in context_inactive

    def test_deep_pydantic_serialization_roundtrip(self):
        """Complex living plan with 50 steps, multiple statuses and contingencies roundtrips losslessly."""
        steps = []
        for i in range(1, 51):
            steps.append(
                PlanStep(
                    step_id=i,
                    intent=StepIntent.NAVIGATE if i % 2 == 0 else StepIntent.INPUT_DATA,
                    description=f"Action directive {i}",
                    target_description=f"UI element {i}",
                    success_criteria=f"Verifiable state {i}",
                    rationale=f"Rationale {i}",
                    status=StepStatus.COMPLETED if i < 20 else StepStatus.PENDING,
                    contingency=f"Contingency plan {i}" if i % 5 == 0 else None,
                )
            )

        plan = LivingPlan(
            user_goal="Perform massive enterprise workflow",
            overall_strategy="Divide and conquer across 50 steps",
            steps=steps,
            current_step_id=20,
            replan_count=7,
            consulted_gemini=True,
        )

        json_repr = plan.model_dump_json()
        restored = LivingPlan.model_validate_json(json_repr)

        assert restored.user_goal == plan.user_goal
        assert restored.overall_strategy == plan.overall_strategy
        assert restored.current_step_id == plan.current_step_id
        assert restored.replan_count == plan.replan_count
        assert restored.consulted_gemini is True
        assert len(restored.steps) == 50
        assert restored.steps[19].step_id == 20
        assert restored.steps[19].intent == StepIntent.NAVIGATE
        assert restored.steps[4].contingency == "Contingency plan 5"


# ===========================================================================
# 4. R5 Stress Testing: Adversarial LLM JSON Parsing & Sanitization
# ===========================================================================

class TestR5AdversarialLLMJSONParserChallenge:
    """Stress tests extract_strategic_blueprint_json & parse_gemini_consultation_response."""

    def test_markdown_backticks_inside_json_string_literals(self):
        """Backticks inside JSON strings must not corrupt markdown fence extraction."""
        adversarial_text = """Here is your plan:
```json
{
  "rationale": "Locate and click the `Submit` button in the `Main Form`",
  "recommended_strategy": [
    {
      "step_id": 1,
      "intent": "NAVIGATE",
      "description": "Click the `Submit` button",
      "target_description": "Button with text `Submit`",
      "success_criteria": "`Status: Submitted` text visible"
    }
  ]
}
```
Good luck!
"""
        plan = parse_gemini_consultation_response(adversarial_text, user_goal="Submit form")
        assert len(plan.steps) == 1
        assert "`Submit`" in plan.steps[0].description
        assert "`Status: Submitted`" in plan.steps[0].success_criteria

    def test_nested_curly_braces_and_escaped_quotes_inside_strings(self):
        """Curly braces `{}` inside JSON string literals must not break balanced-brace parsing."""
        raw_text = """Let me assist:
{
  "rationale": "Payload contains nested JSON-like {test: 123} structures",
  "recommended_strategy": [
    {
      "step_id": 1,
      "intent": "INPUT_DATA",
      "description": "Type {\\\"user\\\": {\\\"name\\\": \\\"Alice\\\"}} into JSON input field",
      "success_criteria": "Display shows {valid: true}"
    }
  ]
}
Hope that works!"""

        extracted = extract_strategic_blueprint_json(raw_text)
        assert extracted is not None
        plan = parse_gemini_consultation_response(raw_text, user_goal="Inject JSON")
        assert len(plan.steps) == 1
        assert "Alice" in plan.steps[0].description

    def test_truncated_json_raises_clean_value_error(self):
        """Truncated JSON fragments must raise clean ValueError without uncaught exceptions."""
        truncated_candidates = [
            '{"rationale": "Plan cut off mid-way',
            '{"recommended_strategy": [{"step_id": 1, "intent": "NA',
            '```json\n{"rationale": "Truncated", "recommended_strategy": [',
            '{"steps": [{"step_id": 1, "description": "partial"',
            '{',
            '{"recommended_strategy":',
        ]
        for candidate in truncated_candidates:
            with pytest.raises(ValueError) as excinfo:
                parse_gemini_consultation_response(candidate, user_goal="Test")
            assert "Failed to extract strategic blueprint" in str(excinfo.value)

    def test_missing_fields_and_unexpected_types_resilience(self):
        """Sparse or type-distorted steps must be normalized gracefully."""
        adversarial_json = {
            "rationale": None,
            "recommended_strategy": [
                {},  # completely empty step dict
                {"step_id": "not_an_int", "intent": None, "description": ""},
                {"step_id": -99, "intent": 12345, "success_criteria": ""},
                "Not even a dictionary (string item in list)",
                None,
                {"step_id": 4, "intent": "UNKNOWN_ACTION", "description": "Valid action"},
            ],
        }
        raw_text = json.dumps(adversarial_json)
        plan = parse_gemini_consultation_response(raw_text, user_goal="Sparse input test")

        # Non-dict items skipped; dict items parsed with sane defaults
        assert len(plan.steps) == 4
        assert plan.steps[0].step_id == 1
        assert plan.steps[0].intent == StepIntent.NAVIGATE
        assert plan.steps[1].step_id == 2
        assert plan.steps[2].step_id == 3
        assert plan.steps[3].step_id == 4
        assert plan.steps[3].intent == StepIntent.NAVIGATE  # fallback for unknown action

    def test_trailing_commas_in_arrays_and_objects(self):
        """Sanitizer handles trailing commas before closing braces and brackets."""
        text_with_trailing_commas = """
        {
            "rationale": "Plan with sloppy syntax",
            "recommended_strategy": [
                {
                    "step_id": 1,
                    "intent": "LAUNCH_OR_ACTIVATE",
                    "description": "Start app",
                    "success_criteria": "App started",
                },
            ],
        }
        """
        plan = parse_gemini_consultation_response(text_with_trailing_commas, user_goal="Trailing comma test")
        assert len(plan.steps) == 1
        assert plan.steps[0].intent == StepIntent.LAUNCH_OR_ACTIVATE

    def test_html_xml_enclosure_and_emoji_chatter(self):
        """LLM output wrapped in XML tags, HTML elements, and heavy emoji chatter."""
        adversarial_text = """
        <thought>
        The user wants to open Firefox and search for cat memes. 🐱
        Let's construct a robust living plan!
        </thought>
        <response>
        🤖 **Greetings Human!** Here is the master plan for your mission! 🚀✨

        ```json
        {
            "overall_strategy": "Search cat memes in browser 🐾",
            "steps": [
                {
                    "step_id": 1,
                    "intent": "OPEN",
                    "description": "<b>Launch</b> Firefox browser 🦊",
                    "success_criteria": "Firefox window is active"
                },
                {
                    "step_id": 2,
                    "intent": "TYPE",
                    "description": "Type 'cute kittens' into search bar ⌨️",
                    "success_criteria": "Search results loaded"
                }
            ]
        }
        ```

        Enjoy the cats! Let me know if you need anything else! 💖🎉
        </response>
        """
        plan = parse_gemini_consultation_response(adversarial_text, user_goal="Find cats")
        assert len(plan.steps) == 2
        assert plan.steps[0].intent == StepIntent.LAUNCH_OR_ACTIVATE  # "OPEN" -> LAUNCH_OR_ACTIVATE
        assert plan.steps[1].intent == StepIntent.INPUT_DATA  # "TYPE" -> INPUT_DATA
        assert "Firefox" in plan.steps[0].description
        assert "kittens" in plan.steps[1].description

    def test_multiple_json_blocks_prefers_strategic_blueprint(self):
        """When an LLM produces metadata JSON before the blueprint JSON, extractor finds the blueprint."""
        text = """
Here is my status:
```json
{"status": 200, "tokens_used": 450}
```
And here is the actual strategic execution blueprint:
```json
{
  "rationale": "Actual plan",
  "recommended_strategy": [
    {"step_id": 1, "intent": "NAVIGATE", "description": "Proceed", "success_criteria": "Done"}
  ]
}
```
"""
        extracted = extract_strategic_blueprint_json(text)
        assert extracted is not None
        assert "recommended_strategy" in extracted
        assert extracted["rationale"] == "Actual plan"

    def test_completely_empty_or_non_json_inputs(self):
        """Completely non-JSON inputs raise descriptive ValueError."""
        non_json_inputs = [
            "",
            "   ",
            "\n\t\r\n",
            "Sorry, as an AI language model, I cannot formulate plans for desktop interaction.",
            "{\"key\": \"value without any strategic blueprint terms\"}",
        ]
        for text in non_json_inputs:
            with pytest.raises(ValueError):
                parse_gemini_consultation_response(text, user_goal="Test")

    def test_consultation_prompt_formatter_robustness(self):
        """Prompt formatter safely sanitizes extreme inputs (null bytes, newlines, empty strings)."""
        prompt = format_gemini_consultation_prompt(
            goal="Test\x00Goal\nWith Newlines",
            active_window_title="",
            process_name="",
            open_apps_summary="",
            visual_scene_summary="",
            dilemma_description="",
        )
        assert "Test\x00Goal\nWith Newlines" in prompt
        assert "Active Window: Desktop (explorer.exe)" in prompt
        assert "Visible Applications: None" in prompt


# ===========================================================================
# 5. Extreme Concurrency & Boundary Invalidation Stress Tests
# ===========================================================================

class TestExtremeConcurrencyAndBoundaryChallenges:
    """Extreme multi-threaded concurrency and boundary fuzzing."""

    def test_concurrent_multi_threaded_mouse_flood(self):
        """10 threads concurrently dispatching 500 mouse packets each (5,000 total) at (0, 0)."""
        backend = MockInputBackend(screen_metrics=(1920, 1080, 0, 0, 1920, 1080))
        callback = MagicMock()
        panic = PanicManager(backend=backend, on_panic_callback=callback)

        panics_fired = []
        lock = threading.Lock()

        def flood_worker():
            local_fired = 0
            for i in range(500):
                fired = panic.check_mouse_position(i % 3, (i + 1) % 3, flags=0)
                if fired:
                    local_fired += 1
            with lock:
                panics_fired.append(local_fired)

        threads = [threading.Thread(target=flood_worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Due to 1.0s debounce, strictly 1 panic across all 10 concurrent threads
        total_fired = sum(panics_fired)
        assert total_fired == 1, f"Expected 1 panic across all threads, got {total_fired}"
        assert callback.call_count == 1
        assert panic.is_panic() is True

    def test_concurrent_multi_threaded_ctrl_alt_k_kill(self, monkeypatch):
        """10 threads concurrently invoking trigger_panic(CTRL_ALT_K_KILL)."""
        mock_popen = MagicMock()
        mock_exit = MagicMock()
        monkeypatch.setattr(subprocess, "Popen", mock_popen)
        monkeypatch.setattr(os, "_exit", mock_exit)

        backend = MockInputBackend()
        panic = PanicManager(backend=backend)
        panic.allow_process_exit = True

        threads = [
            threading.Thread(target=panic.trigger_panic, args=(PanicTriggerSource.CTRL_ALT_K_KILL,))
            for _ in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Multiple concurrent kill requests all execute safely without deadlock
        assert mock_exit.called
        assert mock_popen.called
        assert panic.is_panic() is True

    def test_extreme_coordinate_and_flag_boundaries(self):
        """Fuzz check_mouse_position with 32-bit integer limits and maximum flags."""
        backend = MockInputBackend()
        panic = PanicManager(backend=backend)

        # 32-bit integer limits
        assert panic.check_mouse_position(2147483647, 2147483647, flags=0) is False
        assert panic.check_mouse_position(-2147483648, -2147483648, flags=0) is False

        # Max uint32 flags (has LLMHF_INJECTED bit set) -> MUST be ignored
        assert panic.check_mouse_position(0, 0, flags=0xFFFFFFFF) is False
        assert panic.is_panic() is False

    def test_nested_quad_backtick_markdown_blocks(self):
        """LLM nesting code inside quad backticks ````markdown ... ````."""
        text = """````markdown
Here is the plan:
```json
{
  "rationale": "Quad backticks nesting test",
  "recommended_strategy": [
    {"step_id": 1, "intent": "SELECT_OPTION", "description": "Choose option 1", "success_criteria": "Selected"}
  ]
}
```
````"""
        plan = parse_gemini_consultation_response(text, user_goal="Quad backticks")
        assert len(plan.steps) == 1
        assert plan.steps[0].intent == StepIntent.SELECT_OPTION

    def test_unicode_and_multilingual_gemini_response(self):
        """Strategic blueprint containing multi-byte UTF-8 Japanese, Arabic, and escaped unicode."""
        text = """{
  "rationale": "マルチバイトテスト / اختبار متعدد البايتات / \\u0041\\u0042\\u0043",
  "recommended_strategy": [
    {
      "step_id": 1,
      "intent": "INPUT_DATA",
      "description": "名前を入力してください: \\"山田太郎\\"",
      "success_criteria": "画面に「完了」が表示されること"
    }
  ]
}"""
        plan = parse_gemini_consultation_response(text, user_goal="Multilingual")
        assert len(plan.steps) == 1
        assert "マルチバイトテスト" in plan.overall_strategy
        assert "山田太郎" in plan.steps[0].description
        assert "完了" in plan.steps[0].success_criteria

    def test_living_plan_contingency_when_current_step_id_orphan(self):
        """When current_step_id does not exist in steps, insert_contingency_step safely appends."""
        step1 = PlanStep(step_id=1, intent=StepIntent.NAVIGATE, description="S1", success_criteria="C1")
        plan = LivingPlan(user_goal="Orphan test", steps=[step1], current_step_id=999)

        contingency = PlanStep(step_id=500, intent=StepIntent.VERIFY_STATE, description="S500", success_criteria="C500")
        plan.insert_contingency_step(contingency)

        assert plan.replan_count == 1
        assert len(plan.steps) == 2
        assert plan.steps[-1].step_id == 500

    def test_plan_step_schema_validation_invariants(self):
        """PlanStep strictly enforces step_id >= 1 and rejects invalid intent types."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            PlanStep(step_id=0, intent=StepIntent.NAVIGATE, description="Bad id", success_criteria="C")

        with pytest.raises(ValidationError):
            PlanStep(step_id=-10, intent=StepIntent.NAVIGATE, description="Bad id", success_criteria="C")
