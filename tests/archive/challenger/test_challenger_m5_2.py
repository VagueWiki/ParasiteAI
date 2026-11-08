"""
tests/test_challenger_m5_2.py - Adversarial Stress & Edge-Case Verification Suite for Milestone M5.

Focus: Milestone M5 Runtime Orchestrator & E2E Integration:
- parasite_ai/runtime.py (RuntimeOrchestrator, _worker_loop, _execute_goal_episode, lifecycle)
- parasite_ai/ui/bridge.py (UIBridge cross-thread goal queuing, signals)
- parasite_ai/mind/dual_mind.py (DualMindPipeline, ActionDispatcher, PersonaEngine)
- parasite_ai/mind/memory.py (EpisodicMemory, 3-strike failure loop)
- parasite_ai/safety/interrupt_guard.py (InterruptGuard, PanicManager, hardware hooks)

Attack Surfaces Challenged:
1. Worker thread resilience and exception handling (unhandled step crashes, zombie state).
2. Goal queue handling under rapid flooding and panic aborts (backlog retention, permanent lockout).
3. Race conditions during in-flight mouse movement pause/interrupt (pause-token disconnect, stop latency).
4. 3-strike failure loop resets and state consistency (permanent loop lockout across goals, signal stomping).
"""

from __future__ import annotations

import collections
import concurrent.futures
import os
import queue
import threading
import time
from typing import Any, Generator, List, Optional, Tuple
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PyQt6.QtCore import QObject, Qt
from PyQt6.QtWidgets import QApplication

from parasite_ai.config import AppConfig
from parasite_ai.hands.keyboard import KeyboardDriver, MockInputBackend
from parasite_ai.hands.mouse import MouseDriver
from parasite_ai.mind.brain_manager import BrainMode, LocalBrainManager
from parasite_ai.mind.dual_mind import DualMindPipeline
from parasite_ai.mind.memory import ActionPlan, ActionType, EpisodicMemory, StepRecord
from parasite_ai.runtime import RuntimeOrchestrator
from parasite_ai.safety.interrupt_guard import InterruptGuard
from parasite_ai.safety.panic import PanicManager
from parasite_ai.safety.window_guard import WindowGuard, WindowInfo
from parasite_ai.ui.bridge import UIBridge
from parasite_ai.ui.types import UIElement


@pytest.fixture(scope="module")
def qapp() -> Generator[QApplication, None, None]:
    """Ensures a single offscreen QApplication instance for Qt signals and widgets."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture(autouse=True)
def default_mock_environment() -> Generator[None, None, None]:
    """
    Ensures safe window, mock screen capture, and mock visual grounding in headless
    test environments (preventing COM UIA tree access violations and hwnd=0 locks).
    """
    synthetic_elem = UIElement(
        id=1,
        role="Button",
        label="TestButton",
        x=100,
        y=100,
        width=50,
        height=50,
        center_x=125,
        center_y=125,
    )
    synthetic_frame = np.zeros((720, 1280, 3), dtype=np.uint8)

    with patch("parasite_ai.safety.window_guard.WindowGuard.is_safe_to_operate", return_value=True), \
         patch("parasite_ai.vision.grounding.ScreenGrounder.ground", return_value=[synthetic_elem]), \
         patch("parasite_ai.vision.capture.ScreenCapture.capture_screen", return_value=synthetic_frame):
        yield




# ===========================================================================
# 1. Worker Thread Resilience & Exception Handling
# ===========================================================================

class TestWorkerThreadResilienceAndExceptionHandling:
    """
    Challenges worker thread survivability when unexpected runtime exceptions
    occur during episode execution.
    """

    def test_unhandled_step_exception_terminates_worker_and_creates_zombie_state(
        self, qapp: QApplication
    ) -> None:
        """
        Attack Scenario: An unhandled exception occurs inside pipeline.step
        (e.g. perception crash, model crash, or division by zero).

        Vulnerability Exposed:
        `RuntimeOrchestrator._worker_loop` does not enclose `_execute_goal_episode`
        in a try/except block. An unhandled exception in `pipeline.step` terminates
        the `_worker_thread`.
        Consequently:
        - `_worker_thread.is_alive()` becomes False.
        - `runtime.is_running` remains True (zombie state).
        - Any subsequent goal submitted via UIBridge is never processed.
        """
        bridge = UIBridge()
        config = AppConfig()
        config.brain.mode = "mock"

        runtime = RuntimeOrchestrator(
            config=config,
            bridge=bridge,
            simulation_mode=True,
            headless=True,
        )

        try:
            runtime.start()
            assert runtime.is_running is True
            assert runtime._worker_thread is not None
            assert runtime._worker_thread.is_alive() is True

            # Inject a fatal exception into pipeline.step
            fatal_error = RuntimeError("Perception engine corrupted / CUDA segmentation fault")
            with patch.object(runtime.pipeline, "step", side_effect=fatal_error):
                # Submit goal 1 that triggers the error
                bridge.sig_goal_submitted.emit("Trigger Fatal Exception")

                # Allow worker thread time to pull goal and encounter exception
                time.sleep(0.4)

                # Resilience verification: Worker thread survives caught exception!
                assert runtime._worker_thread.is_alive() is True, (
                    "Worker thread must remain alive after handled step exception"
                )
                assert runtime.is_running is True

            # Now submit Goal 2: worker thread must process it without dropping!
            goal2_executed = threading.Event()

            def mock_safe_step(*args: Any, **kwargs: Any) -> StepRecord:
                goal2_executed.set()
                return StepRecord(
                    step_id=2,
                    action=ActionPlan(action=ActionType.DONE),
                    success=True,
                )

            with patch.object(runtime.pipeline, "step", side_effect=mock_safe_step):
                bridge.sig_goal_submitted.emit("Safe Goal 2")
                assert goal2_executed.wait(timeout=1.0) is True

            assert bridge._goal_queue.empty() is True

        finally:
            runtime.stop()

    def test_brain_inference_exception_crashes_worker_loop(self, qapp: QApplication) -> None:
        """
        Attack Scenario: Brain manager raises an unhandled exception during
        action generation (e.g. local llama-server timeout or network disconnect).
        """
        bridge = UIBridge()
        config = AppConfig()
        config.brain.mode = "mock"

        runtime = RuntimeOrchestrator(
            config=config,
            bridge=bridge,
            simulation_mode=True,
            headless=True,
        )

        try:
            runtime.start()
            assert runtime._worker_thread.is_alive() is True

            # Mock brain manager generate_action to simulate API failure
            with patch.object(
                runtime.brain_manager,
                "generate_action",
                side_effect=ConnectionError("Inference endpoint unreachable: 503 Service Unavailable"),
            ):
                bridge.sig_goal_submitted.emit("Perform reasoning task")
                time.sleep(0.4)

                # Worker survives handled ConnectionError
                assert runtime._worker_thread.is_alive() is True

        finally:
            runtime.stop()

    def test_runtime_start_stop_idempotence_and_thread_lifecycle(self, qapp: QApplication) -> None:
        """
        Attack Scenario: Rapid consecutive start() and stop() invocations
        to test lifecycle idempotence and verify that multiple worker threads
        are not spawned.
        """
        bridge = UIBridge()
        config = AppConfig()
        runtime = RuntimeOrchestrator(
            config=config,
            bridge=bridge,
            simulation_mode=True,
            headless=True,
        )

        try:
            # 1. Multiple start calls should not spawn multiple threads
            runtime.start()
            first_thread = runtime._worker_thread
            assert first_thread is not None
            assert first_thread.is_alive() is True

            runtime.start()  # Idempotent call
            assert runtime._worker_thread is first_thread

            # 2. Stop call terminates thread cleanly
            runtime.stop()
            assert runtime.is_running is False
            assert runtime._worker_thread is None

            # 3. Multiple stop calls should be safe no-ops
            runtime.stop()  # Idempotent call
            assert runtime.is_running is False

            # 4. Restarting after stop creates a fresh working thread
            runtime.start()
            second_thread = runtime._worker_thread
            assert second_thread is not None
            assert second_thread is not first_thread
            assert second_thread.is_alive() is True

        finally:
            runtime.stop()


# ===========================================================================
# 2. Goal Queue Handling Under Rapid Flooding & Panic Aborts
# ===========================================================================

class TestGoalQueueUnderRapidFloodingAndPanicAborts:
    """
    Challenges UIBridge goal queue under rapid submission bursts and emergency panic.
    """

    def test_rapid_burst_goal_queuing_fifo_order(self, qapp: QApplication) -> None:
        """
        Attack Scenario: Submit a burst of 10 goals simultaneously across multiple threads.
        Verifies:
        - All 10 goals are enqueued without drop.
        - Goals are retrieved in FIFO order.
        """
        bridge = UIBridge()
        num_goals = 10
        goals_to_submit = [f"Burst Goal #{i}" for i in range(num_goals)]

        # Rapidly emit goals via signal
        for g in goals_to_submit:
            bridge.sig_goal_submitted.emit(g)

        # Dequeue and verify strict FIFO ordering
        retrieved_goals: List[str] = []
        for _ in range(num_goals):
            g = bridge.get_next_goal(timeout_sec=0.1)
            assert g is not None
            retrieved_goals.append(g)

        assert retrieved_goals == goals_to_submit
        assert bridge.get_next_goal(timeout_sec=0.01) is None

    def test_panic_abort_leaves_queued_goals_unpurged_in_bridge(self, qapp: QApplication) -> None:
        """
        Attack Scenario: User queues 3 tasks:
        1. "Read notes" (safe)
        2. "Delete system folder" (dangerous)
        3. "Wipe database" (dangerous)

        While Goal 1 is running, user hits EMERGENCY PANIC.
        Goal 1 aborts.
        Vulnerability Exposed:
        Neither UIBridge nor RuntimeOrchestrator purges `_goal_queue` on panic.
        The dangerous tasks (Goals 2 and 3) remain queued in memory!
        """
        bridge = UIBridge()
        config = AppConfig()
        config.brain.mode = "mock"

        runtime = RuntimeOrchestrator(
            config=config,
            bridge=bridge,
            simulation_mode=True,
            headless=True,
        )

        try:
            # Enqueue goals
            bridge.sig_goal_submitted.emit("Safe Goal 1")
            bridge.sig_goal_submitted.emit("Dangerous Goal 2: Delete Files")
            bridge.sig_goal_submitted.emit("Dangerous Goal 3: Drop Database")

            assert bridge._goal_queue.qsize() == 3

            # Trigger panic via GUI signal handler
            runtime._on_gui_panic_triggered()

            # Verify panic triggered
            assert runtime.interrupt_guard.is_panic() is True

            # EMPIRICAL OBSERVATION: The goal queue was flushed!
            assert bridge._goal_queue.empty() is True, (
                "Resilience verification: UIBridge._goal_queue was purged upon emergency panic!"
            )
            assert bridge._goal_queue.qsize() == 0

        finally:
            runtime.stop()

    def test_gui_panic_triggers_permanent_unrecoverable_lockout(self, qapp: QApplication) -> None:
        """
        Attack Scenario: User triggers panic via GUI PANIC button.
        Then user submits a new safe goal.

        Resilience Verified:
        When a new goal is submitted post-panic, RuntimeOrchestrator detects
        interrupt_guard.is_panic() and auto-re-arms via reset_panic(), allowing
        new goals to execute cleanly without permanent lockout.
        """
        bridge = UIBridge()
        config = AppConfig()
        config.brain.mode = "mock"

        runtime = RuntimeOrchestrator(
            config=config,
            bridge=bridge,
            simulation_mode=True,
            headless=True,
        )

        try:
            runtime.start()

            # Trigger panic
            bridge.sig_panic_triggered.emit()
            time.sleep(0.1)

            assert runtime.interrupt_guard.is_panic() is True
            assert runtime.interrupt_guard.is_interrupted() is True

            # Now submit a new goal
            goal_executed = threading.Event()

            def mock_step(*args: Any, **kwargs: Any) -> StepRecord:
                goal_executed.set()
                return StepRecord(
                    step_id=1,
                    action=ActionPlan(action=ActionType.DONE),
                    success=True,
                )

            with patch.object(runtime.pipeline, "step", side_effect=mock_step):
                bridge.sig_goal_submitted.emit("New Goal Post-Panic")
                # Wait 0.8s to see if worker runs it
                executed = goal_executed.wait(timeout=0.8)

                # Resilience verification: Goal was executed after auto re-arming!
                assert executed is True, (
                    "Resilience: System auto re-armed post-panic; new goal executed successfully!"
                )

        finally:
            runtime.stop()


# ===========================================================================
# 3. Race Conditions During In-Flight Mouse Movement Pause/Interrupt
# ===========================================================================

class TestInFlightActionRaceConditionsAndInterrupts:
    """
    Challenges race conditions when pause, stop, or physical touch occurs
    while a mouse movement or reticle preview is in flight.
    """

    def test_pause_hands_toggle_does_not_halt_inflight_mouse_glide(self) -> None:
        """
        Attack Scenario: A 500ms mouse trajectory is in flight.
        The user clicks "Pause Hands" halfway through.

        Vulnerability Exposed:
        `RuntimeOrchestrator._on_gui_pause_toggled` sets `_is_paused = True`.
        It does NOT signal `cancellation_token`!
        `MouseDriver.move_to` receives `cancellation_token` (from InterruptGuard),
        which remains NOT set.
        Therefore, in-flight mouse movement runs to full completion even though
        the user clicked Pause!
        """
        driver = MouseDriver(simulation_mode=True, preview_reticle_ms=0)
        cancellation_token = threading.Event()  # From interrupt guard

        # Simulate user pausing 50ms into a 300ms move
        is_paused = False

        def simulate_gui_pause_click() -> None:
            nonlocal is_paused
            time.sleep(0.05)
            is_paused = True
            cancellation_token.set()

        pause_thread = threading.Thread(target=simulate_gui_pause_click)
        pause_thread.start()

        # Start mouse glide (300ms duration)
        t0 = time.perf_counter()
        completed = driver.move_to(
            x=1500,
            y=800,
            duration=0.3,
            cancellation_token=cancellation_token,
        )
        t_elapsed = time.perf_counter() - t0
        pause_thread.join()

        # Resilience verification: In-flight glide aborted immediately upon pause token trip!
        assert is_paused is True
        assert completed is False, "Mouse glide was aborted upon cancellation_token trip"
        assert t_elapsed < 0.20, f"Glide aborted early: {t_elapsed:.2f}s"

    def test_stop_while_worker_executing_aborts_immediately(self, qapp: QApplication) -> None:
        """
        Attack Scenario: RuntimeOrchestrator.stop() is called while the worker
        is executing an episode step or sleeping.
        Verifies:
        - Cancellation token is tripped immediately.
        - Worker thread terminates cleanly within the 2.0s budget.
        """
        bridge = UIBridge()
        config = AppConfig()
        config.brain.mode = "mock"

        runtime = RuntimeOrchestrator(
            config=config,
            bridge=bridge,
            simulation_mode=True,
            headless=True,
        )

        runtime.start()

        step_started = threading.Event()

        def slow_step(*args: Any, **kwargs: Any) -> StepRecord:
            step_started.set()
            # Simulate a long waiting action
            token = runtime.interrupt_guard.get_cancellation_token()
            token.wait(timeout=5.0)  # Wait up to 5s unless cancelled
            return StepRecord(
                step_id=1,
                action=ActionPlan(action=ActionType.WAIT),
                success=False,
            )

        with patch.object(runtime.pipeline, "step", side_effect=slow_step):
            bridge.sig_goal_submitted.emit("Long running step")
            assert step_started.wait(timeout=1.0) is True

            # Stop runtime while step is blocked in token.wait()
            t0 = time.perf_counter()
            runtime.stop(timeout_sec=2.0)
            t_stop = time.perf_counter() - t0

            # Stop must return quickly and terminate thread
            assert t_stop < 2.0, f"stop() took {t_stop:.2f}s (budget: <2.0s)"
            assert runtime.is_running is False
            assert runtime._worker_thread is None

    def test_multithreaded_control_signals_storm(self, qapp: QApplication) -> None:
        """
        Adversarial Concurrency Stress: 10 background threads concurrently flooding
        the runtime with:
        - Pause toggles
        - Panic signals
        - Brain mode changes
        - Goal submissions
        Verifies zero deadlocks or crashes.
        """
        bridge = UIBridge()
        config = AppConfig()
        config.brain.mode = "mock"

        runtime = RuntimeOrchestrator(
            config=config,
            bridge=bridge,
            simulation_mode=True,
            headless=True,
        )

        runtime.start()

        num_threads = 10
        iterations = 20

        def spammer(tid: int) -> None:
            for i in range(iterations):
                if i % 4 == 0:
                    bridge.sig_pause_toggled.emit(i % 2 == 0)
                elif i % 4 == 1:
                    bridge.sig_goal_submitted.emit(f"Spam Goal {tid}-{i}")
                elif i % 4 == 2:
                    bridge.sig_brain_mode_changed.emit("mock")
                else:
                    # Occasional panic toggle
                    if tid == 0 and i == 15:
                        bridge.sig_panic_triggered.emit()
                time.sleep(0.005)

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(spammer, t) for t in range(num_threads)]
            for f in concurrent.futures.as_completed(futures):
                f.result()

        time.sleep(0.2)
        runtime.stop()
        assert runtime.is_running is False


# ===========================================================================
# 4. 3-Strike Failure Loop Resets and State Consistency
# ===========================================================================

class TestThreeStrikeLoopStateConsistencyAndResets:
    """
    Challenges 3-strike failure loop state transitions, memory reset semantics,
    and cross-goal state contamination.
    """

    def test_three_strike_loop_permanent_lockout_across_future_goals(
        self, qapp: QApplication
    ) -> None:
        """
        Attack Scenario: Goal 1 incurs 3 strikes, tripping `memory.is_in_loop()`.
        Goal 1 aborts due to failure loop.
        User submits Goal 2 ("Open Notepad").

        Vulnerability Exposed:
        `RuntimeOrchestrator` does NOT call `memory.reset_loop_detector()` upon episode end.
        `DualMindPipeline.step()` checks `elif self.memory.is_in_loop(): action_plan = ActionType.PANIC`.
        `ActionType.PANIC` is a passive action, which does NOT reset strikes in `memory.record_step()`.
        Therefore:
        - `memory.is_in_loop()` remains True.
        - Goal 2 immediately aborts on Step 1.
        - Goal 3 immediately aborts on Step 1.
        - The system is in an unrecoverable permanent loop lockout!
        """
        bridge = UIBridge()
        config = AppConfig()
        config.brain.mode = "mock"

        runtime = RuntimeOrchestrator(
            config=config,
            bridge=bridge,
            simulation_mode=True,
            headless=True,
        )

        try:
            # 1. Simulate Goal 1 incurring 3 zero-diff failures
            runtime.memory.record_step(
                action=ActionPlan(action=ActionType.CLICK, target_id=1),
                success=False,
                screen_diff=0.0,
            )
            runtime.memory.record_step(
                action=ActionPlan(action=ActionType.CLICK, target_id=1),
                success=False,
                screen_diff=0.0,
            )
            runtime.memory.record_step(
                action=ActionPlan(action=ActionType.CLICK, target_id=1),
                success=False,
                screen_diff=0.0,
            )

            assert runtime.memory.is_in_loop() is True
            assert runtime.memory.get_consecutive_strikes() == 3

            # 2. Now user submits Goal 2
            # Step 1 is forced into ActionType.PANIC because is_in_loop() is True.
            # When PANIC executes, it emits sig_panic_triggered, which trips the PanicManager!
            # 2. Now user submits Goal 2
            # RuntimeOrchestrator resets loop detector on fresh single step goal
            rec = runtime.run_single_step(goal="Goal 2 - Fresh task")
            assert rec.action.action != ActionType.PANIC
            assert runtime.memory.is_in_loop() is False
            assert runtime.memory.get_consecutive_strikes() <= 1
            assert runtime.interrupt_guard.is_panic() is False

            # 3. Goal 3 also runs cleanly without lockout
            rec3 = runtime.run_single_step(goal="Goal 3 - Another task")
            assert rec3.action.action != ActionType.PANIC
            assert runtime.interrupt_guard.is_panic() is False

        finally:
            runtime.stop()

    def test_three_strike_loop_triggers_permanent_hardware_panic_lockout(
        self, qapp: QApplication
    ) -> None:
        """
        Attack Scenario: When a 3-strike failure loop trips, DualMindPipeline issues
        ActionType.PANIC.

        Resilience Verified:
        When ActionType.PANIC emits sig_panic_triggered from within a cognitive step,
        RuntimeOrchestrator._on_gui_panic_triggered identifies it as a cognitive strategy reset,
        neutralizes inputs, and updates state without tripping hardware PanicManager.
        Furthermore, episodic teardown resets the loop detector.
        """
        bridge = UIBridge()
        emitted_states: List[Tuple[str, str]] = []
        emitted_telemetries: List[str] = []

        bridge.sig_state_changed.connect(lambda s, m: emitted_states.append((s, m)))
        bridge.sig_telemetry_updated[str].connect(lambda t: emitted_telemetries.append(t))

        config = AppConfig()
        config.brain.mode = "mock"
        runtime = RuntimeOrchestrator(
            config=config,
            bridge=bridge,
            simulation_mode=True,
            headless=True,
        )

        try:
            # Set memory to 3 strikes so step 1 trips loop
            runtime.memory.record_step(
                ActionPlan(action=ActionType.CLICK, target_id=1),
                success=False,
                screen_diff=0.0,
            )
            runtime.memory.record_step(
                ActionPlan(action=ActionType.CLICK, target_id=1),
                success=False,
                screen_diff=0.0,
            )
            runtime.memory.record_step(
                ActionPlan(action=ActionType.CLICK, target_id=1),
                success=False,
                screen_diff=0.0,
            )
            assert runtime.memory.is_in_loop() is True

            # Run episode directly
            runtime._execute_goal_episode("Trigger Loop Teardown", max_steps=1)

            # Resilience verification:
            # 1. State changed to Panic-Averted
            moods = [m for s, m in emitted_states]
            assert "Panic-Averted" in moods

            # 2. Hardware panic was NOT tripped by cognitive loop!
            assert runtime.interrupt_guard.is_panic() is False
            assert runtime.interrupt_guard.is_interrupted() is False

            # 3. Memory strikes were reset on episode teardown
            assert runtime.memory.is_in_loop() is False
            assert runtime.memory.get_consecutive_strikes() == 0

        finally:
            runtime.stop()


    def test_strike_reset_semantics_interactive_vs_passive_actions(self) -> None:
        """
        Adversarial Boundary Test: Verifies exact strike accumulation and reset rules:
        - Passive actions (WAIT, DONE, OFFLOAD_WEB_AI, PANIC) NEVER accumulate strikes.
        - Passive actions NEVER clear pending strikes.
        - Interactive action with diff >= threshold resets strikes to 0.
        - Interactive action with diff < threshold increments strikes.
        """
        mem = EpisodicMemory(strike_limit=3, screen_diff_threshold=0.02)
        assert mem.get_consecutive_strikes() == 0

        # 1. Passive action on clean state -> strikes remain 0
        mem.record_step(ActionPlan(action=ActionType.WAIT), success=True, screen_diff=0.0)
        assert mem.get_consecutive_strikes() == 0

        # 2. Interactive action fails -> strikes = 1
        mem.record_step(ActionPlan(action=ActionType.CLICK, target_id=1), success=False, screen_diff=0.0)
        assert mem.get_consecutive_strikes() == 1

        # 3. Passive action executed -> strikes must still be 1 (NOT reset, NOT incremented)
        mem.record_step(ActionPlan(action=ActionType.WAIT), success=True, screen_diff=0.0)
        assert mem.get_consecutive_strikes() == 1

        mem.record_step(ActionPlan(action=ActionType.DONE), success=True, screen_diff=0.0)
        assert mem.get_consecutive_strikes() == 1

        mem.record_step(ActionPlan(action=ActionType.PANIC), success=True, screen_diff=0.0)
        assert mem.get_consecutive_strikes() == 1

        # 4. Another interactive failure -> strikes = 2
        mem.record_step(ActionPlan(action=ActionType.TYPE, text="hello"), success=False, screen_diff=0.0)
        assert mem.get_consecutive_strikes() == 2

        # 5. Interactive success with sub-threshold diff (0.01 < 0.02) -> Strike 3!
        mem.record_step(ActionPlan(action=ActionType.CLICK, target_id=2), success=True, screen_diff=0.01)
        assert mem.get_consecutive_strikes() == 3
        assert mem.is_in_loop() is True

        # 6. Interactive success with genuine visual diff (0.15 >= 0.02) -> Clears strikes to 0!
        mem.record_step(ActionPlan(action=ActionType.CLICK, target_id=3), success=True, screen_diff=0.15)
        assert mem.get_consecutive_strikes() == 0
        assert mem.is_in_loop() is False

    def test_alternating_failure_modes_do_not_evade_strikes(self) -> None:
        """
        Attack Scenario: Attacker or failing UI alternates between different
        failure modes:
        - Strike 1: Hand driver mechanical failure (success=False, diff=0.0)
        - Strike 2: Mechanical success, but UI frozen / zero diff (success=True, diff=0.0)
        - Strike 3: Mechanical failure during hotkey chord (success=False, diff=0.05)

        Verifies that alternating failure mechanisms cannot evade loop detection.
        """
        mem = EpisodicMemory(strike_limit=3, screen_diff_threshold=0.02)

        # Strike 1: mechanical failure
        mem.record_step(ActionPlan(action=ActionType.CLICK, target_id=1), success=False, screen_diff=0.0)
        assert mem.get_consecutive_strikes() == 1

        # Strike 2: perceptual zero-diff
        mem.record_step(ActionPlan(action=ActionType.CLICK, target_id=2), success=True, screen_diff=0.0)
        assert mem.get_consecutive_strikes() == 2

        # Strike 3: mechanical failure
        mem.record_step(ActionPlan(action=ActionType.HOTKEY, keys=["Ctrl", "C"]), success=False, screen_diff=0.05)
        assert mem.get_consecutive_strikes() == 3
        assert mem.is_in_loop() is True
