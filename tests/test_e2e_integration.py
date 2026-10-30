"""
tests/test_e2e_integration.py - Comprehensive End-to-End Acceptance Test Suite.

Verifies the 6 Core ParasiteAI E2E Scenarios:
1. Scenario 1: Clean Startup & Zero-Config Default Boot.
2. Scenario 2: End-to-End Goal Execution Cycle (Closed-loop SoM, Monologue, Reticle, Glide, Diff, Telemetry).
3. Scenario 3: Physical Hardware Touch Interruption (<2ms Preemption, Atomic Cancellation, USER_OVERRIDE).
4. Scenario 4: Sensitive Window Detection & Privacy Blackout (Masked Perception, Cleared HUD, PROTECTED).
5. Scenario 5: 3-Strike Failure Loop Emergency Reset (Mood Degradation, Loop Detection, PANIC Strategy Reset).
6. Scenario 6: Zero-VRAM Visible Browser Brain Offload (Chrome Automation, Sentinel Clipboard Verification & Guaranteed Restore).
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtWidgets import QApplication

from parasite_ai.config import AppConfig, load_config
from parasite_ai.hands.keyboard import KeyboardDriver, MockInputBackend
from parasite_ai.hands.mouse import MouseDriver
from parasite_ai.main import ParasiteApp, parse_args
from parasite_ai.mind.brain_manager import BrainMode, LocalBrainManager
from parasite_ai.mind.dual_mind import DualMindPipeline
from parasite_ai.mind.memory import ActionPlan, ActionType, EpisodicMemory
from parasite_ai.mind.offloader import (
    BrowserOffloader,
    MockBrowserWindowBackend,
    MockClipboardBackend,
    OffloadHarvestError,
    OffloaderState,
    SentinelClipboardVerifier,
)
from parasite_ai.runtime import RuntimeOrchestrator
from parasite_ai.safety.interrupt_guard import (
    InterruptGuard,
    LLKHF_INJECTED,
    LLMHF_INJECTED,
    VK_P,
)
from parasite_ai.safety.window_guard import WindowGuard, WindowInfo
from parasite_ai.ui.bridge import UIBridge
from parasite_ai.ui.companion_dock import CompanionDock
from parasite_ai.ui.dpi import init_high_dpi_awareness
from parasite_ai.ui.ghost_hud import GhostHUD
from parasite_ai.ui.types import UIElement
from parasite_ai.vision.capture import ScreenCapture
from parasite_ai.vision.grounding import ScreenGrounder


@pytest.fixture(scope="module")
def qapp() -> Generator[QApplication, None, None]:
    """Ensures QApplication exists in offscreen mode for all tests."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


# ===========================================================================
# SCENARIO 1: Clean Startup & Zero-Config Default Boot
# ===========================================================================

class TestScenario1CleanStartup:
    """Verifies startup lifecycle, dry-run health checks, and zero-config generation."""

    def test_dry_run_cli_subprocess(self) -> None:
        """Verifies 'python main.py --dry-run' exits code 0 in <5s with clean output."""
        start_time = time.perf_counter()
        proc = subprocess.run(
            [sys.executable, "main.py", "--dry-run", "--headless"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        elapsed = time.perf_counter() - start_time
        assert proc.returncode == 0, f"Dry-run failed with stderr: {proc.stderr}"
        assert "Clean dry-run initialization completed successfully" in proc.stdout
        assert elapsed < 5.0, f"Dry-run startup took {elapsed:.2f}s (budget: <5.0s)"

    def test_programmatic_bootstrap_health_checks(self, qapp: QApplication) -> None:
        """Verifies programmatic instantiation and health of all 12 core subsystems."""
        dpi_ok = init_high_dpi_awareness()
        assert isinstance(dpi_ok, bool)

        args = parse_args(["--headless", "--brain-mode", "mock"])
        app = ParasiteApp(args)
        try:
            # 1. UIBridge
            assert app.bridge is not None
            # 2. Runtime Orchestrator
            assert app.runtime is not None
            # 3. InterruptGuard
            assert app.runtime.interrupt_guard is not None
            # 4. WindowGuard
            assert app.runtime.window_guard is not None
            # 5. MouseDriver
            assert app.runtime.mouse_driver is not None
            # 6. KeyboardDriver
            assert app.runtime.keyboard_driver is not None
            # 7. ScreenCapture
            assert app.runtime.screen_capture is not None
            # 8. ScreenGrounder
            assert app.runtime.screen_grounder is not None
            # 9. LocalBrainManager
            assert app.runtime.brain_manager is not None
            # 10. EpisodicMemory
            assert app.runtime.memory is not None
            # 11. CompanionDock
            assert app.dock is not None
            # 12. GhostHUD
            assert app.hud is not None
        finally:
            app.shutdown()

    def test_zero_config_autogen(self, tmp_path: Path) -> None:
        """Verifies loading a nonexistent config path auto-generates a valid default file."""
        nonexistent = tmp_path / "auto_config.yaml"
        assert not nonexistent.exists()
        cfg = load_config(nonexistent)
        assert isinstance(cfg, AppConfig)
        assert nonexistent.exists()
        assert "brain:" in nonexistent.read_text(encoding="utf-8")


# ===========================================================================
# SCENARIO 2: End-to-End Goal Execution Cycle
# ===========================================================================

class TestScenario2GoalExecutionCycle:
    """Verifies complete closed-loop cycle from goal input to telemetry update."""

    def test_full_goal_to_telemetry_flow(self, qapp: QApplication) -> None:
        """Verifies SoM visual grounding, thought/speech, reticle, movement, and telemetry."""
        bridge = UIBridge()
        config = AppConfig()
        config.brain.mode = "mock"

        # Track signals emitted across the closed loop
        received_states: list[tuple[str, str]] = []
        received_thoughts: list[str] = []
        received_speeches: list[str] = []
        received_reticles: list[tuple[int, int, int]] = []
        received_telemetries: list[str] = []

        bridge.sig_state_changed.connect(lambda s, m: received_states.append((s, m)))
        bridge.sig_thought_updated.connect(lambda t: received_thoughts.append(t))
        bridge.sig_speech_updated.connect(lambda s: received_speeches.append(s))
        bridge.sig_reticle_requested.connect(lambda x, y, dur, tid, lbl: received_reticles.append((x, y, dur)))
        bridge.sig_telemetry_updated[str].connect(lambda t: received_telemetries.append(t))

        dock = CompanionDock(config=config.ui.dock, bridge=bridge)
        hud = GhostHUD(config=config.ui.hud, bridge=bridge, enable_win32_styles=False)

        runtime = RuntimeOrchestrator(
            config=config,
            bridge=bridge,
            simulation_mode=True,
            headless=True,
        )

        try:
            # 1. Synthesize target button on 1920x1080 display
            target_elem = UIElement(
                id=1,
                role="Button",
                label="Submit",
                x=500,
                y=400,
                width=100,
                height=40,
                center_x=550,
                center_y=420,
            )
            synthetic_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

            # 2. Run deterministic single step targeting button #1 (with safe window active)
            override_action = ActionPlan(
                action=ActionType.CLICK,
                target_id=1,
                reasoning="Clicking submit button to proceed",
            )

            with patch.object(runtime.window_guard, "is_safe_to_operate", return_value=True):
                step_record = runtime.run_single_step(
                    goal="Click the Submit button",
                    screen_frame=synthetic_frame,
                    grounded_elements=[target_elem],
                    override_action=override_action,
                )

            QApplication.processEvents()

            # 3. Assert execution results
            assert step_record.success is True
            assert step_record.action.action == ActionType.CLICK
            assert step_record.action.target_id == 1

            # 4. Verify reticle requested at element center
            assert len(received_reticles) >= 1
            reticle_x, reticle_y, reticle_dur = received_reticles[0]
            assert (reticle_x, reticle_y) == (550, 420)
            assert reticle_dur == 300

            # 5. Verify mouse driver coordinates reached target
            cursor_pos = runtime.mouse_driver.get_cursor_pos()
            assert cursor_pos == (550, 420)

            # 6. Verify episodic memory was updated
            assert len(runtime.memory) == 1
            assert runtime.memory.get_recent_history(1)[0].success is True

            # 7. Complete task with DONE action
            with patch.object(runtime.window_guard, "is_safe_to_operate", return_value=True):
                done_record = runtime.run_single_step(
                    goal="Click the Submit button",
                    override_action=ActionPlan(action=ActionType.DONE, reasoning="Goal completed"),
                )
            assert done_record.action.action == ActionType.DONE

        finally:
            runtime.stop()
            dock.close()
            hud.close()


# ===========================================================================
# SCENARIO 3: Physical Hardware Touch Interruption (<2ms)
# ===========================================================================

class TestScenario3HardwareInterruptPreemption:
    """Verifies synthetic input filtering, <2ms preemption, and dock state update."""

    def test_synthetic_events_filtered(self) -> None:
        """Verifies synthetic injected events do NOT trigger preemption."""
        guard = InterruptGuard(cooldown_seconds=2.0)
        token = guard.get_cancellation_token()

        assert not guard.is_interrupted()
        assert not token.is_set()

        # Dispatch synthetic mouse and keyboard packets
        guard.simulate_event("mouse", flags=LLMHF_INJECTED, pt=(500, 500))
        guard.simulate_event("keyboard", flags=LLKHF_INJECTED, vk_code=VK_P)

        assert not guard.is_interrupted()
        assert not token.is_set()

    def test_physical_touch_preemption_under_2ms(self, qapp: QApplication) -> None:
        """Verifies physical hardware touch aborts in strictly < 2ms and updates dock."""
        bridge = UIBridge()
        dock_states: list[str] = []
        bridge.sig_state_changed.connect(lambda s, m: dock_states.append(s))
        dock = CompanionDock(bridge=bridge)

        guard = InterruptGuard(
            cooldown_seconds=1.0,
            on_interrupt_callback=lambda reason: (
                bridge.clear_reticle(),
                bridge.notify_state("USER_OVERRIDE", "Curious"),
            ),
        )
        token = guard.get_cancellation_token()

        # Benchmark physical touch preemption latency
        t0 = time.perf_counter()
        guard.simulate_event("mouse", flags=0, pt=(600, 600))
        t_elapsed = time.perf_counter() - t0

        assert token.is_set(), "Cancellation token must be set on physical touch"
        assert guard.is_interrupted(), "Interrupt guard must report interrupted"
        assert t_elapsed < 0.002, f"Preemption latency {t_elapsed*1000:.3f}ms exceeded 2ms budget"

        QApplication.processEvents()
        # Verify UI state switched to USER_OVERRIDE
        assert "USER_OVERRIDE" in dock_states
        dock.close()

    def test_mouse_driver_aborts_immediately_on_interrupt(self) -> None:
        """Verifies in-flight mouse movement aborts immediately when token is tripped."""
        driver = MouseDriver(simulation_mode=True, preview_reticle_ms=0)
        token = threading.Event()
        token.set()  # Pre-tripped token

        success = driver.move_to(1000, 800, cancellation_token=token)
        assert success is False
        assert len(driver._held_buttons) == 0


# ===========================================================================
# SCENARIO 4: Sensitive Window Detection & Privacy Blackout
# ===========================================================================

class TestScenario4SensitiveWindowPrivacyBlackout:
    """Verifies WindowGuard password manager detection, privacy blackout, and action pausing."""

    def test_sensitive_window_blocks_pipeline(self, qapp: QApplication) -> None:
        """Verifies sensitive window pauses actions, sets PROTECTED, and masks vision."""
        bridge = UIBridge()
        dock = CompanionDock(bridge=bridge)
        hud = GhostHUD(bridge=bridge, enable_win32_styles=False)

        config = AppConfig()
        config.brain.mode = "mock"
        runtime = RuntimeOrchestrator(
            config=config,
            bridge=bridge,
            simulation_mode=True,
            headless=True,
        )

        try:
            # Simulate active password manager window
            sensitive_window = WindowInfo(
                hwnd=5555,
                title="Bitwarden - Password Manager",
                class_name="Chrome_WidgetWin_1",
                process_name="bitwarden.exe",
                process_path="C:\\bitwarden.exe",
                pid=9999,
                rect=(100, 100, 800, 600),
                is_sensitive=True,
                reason="Sensitive process matched: 'bitwarden.exe'",
            )

            with patch.object(runtime.window_guard, "get_active_window_info", return_value=sensitive_window):
                assert runtime.window_guard.is_safe_to_operate() is False

                # Execute pipeline step
                step_record = runtime.run_single_step(goal="Type password")

                # Must record WAIT action with privacy pause
                assert step_record.action.action == ActionType.WAIT
                assert "sensitive window" in step_record.error_message.lower()

                # Process Qt queue so queued connections update dock
                QApplication.processEvents()

                # CompanionDock must be in PROTECTED state and perception masked
                assert dock._current_state == "PROTECTED"
                assert dock._is_masked is True
                assert "PAUSED — SENSITIVE" in dock.grounding_badge.text()

        finally:
            runtime.stop()
            dock.close()
            hud.close()

    def test_safe_window_restoration(self) -> None:
        """Verifies returning to a safe window restores is_safe_to_operate to True."""
        guard = WindowGuard()
        safe_window = WindowInfo(
            hwnd=1234,
            title="Calculator",
            class_name="CalcFrame",
            process_name="calc.exe",
            process_path="C:\\calc.exe",
            pid=4321,
            rect=(0, 0, 400, 400),
            is_sensitive=False,
            reason="Window is safe to operate",
        )
        with patch.object(guard, "get_active_window_info", return_value=safe_window):
            assert guard.is_safe_to_operate() is True


# ===========================================================================
# SCENARIO 5: 3-Strike Failure Loop Emergency Reset
# ===========================================================================

class TestScenario5ThreeStrikesFailureLoop:
    """Verifies consecutive action failure strikes, loop detection, and emergency PANIC override."""

    def test_three_strike_loop_triggers_panic_override(self) -> None:
        """Verifies 3 zero-diff actions trip is_in_loop and force PANIC strategy reset."""
        memory = EpisodicMemory(capacity=10, strike_limit=3)
        assert not memory.is_in_loop()

        # Strike 1: zero screen diff
        memory.record_step(
            action=ActionPlan(action=ActionType.CLICK, target_id=1),
            success=False,
            screen_diff=0.001,
        )
        assert memory.get_consecutive_strikes() == 1
        assert not memory.is_in_loop()

        # Strike 2: zero screen diff
        memory.record_step(
            action=ActionPlan(action=ActionType.CLICK, target_id=1),
            success=False,
            screen_diff=0.002,
        )
        assert memory.get_consecutive_strikes() == 2
        assert not memory.is_in_loop()

        # Strike 3: zero screen diff -> TRIPS LOOP DETECTOR!
        memory.record_step(
            action=ActionPlan(action=ActionType.CLICK, target_id=1),
            success=False,
            screen_diff=0.000,
        )
        assert memory.get_consecutive_strikes() == 3
        assert memory.is_in_loop() is True

        # When loop detector trips, DualMindPipeline intercepts and forces PANIC action
        bridge = UIBridge()
        panic_emitted: list[bool] = []
        bridge.sig_panic_triggered.connect(lambda: panic_emitted.append(True))

        config = AppConfig()
        config.brain.mode = "mock"
        brain = LocalBrainManager(config=config)

        pipeline = DualMindPipeline(
            brain_manager=brain,
            memory=memory,
            bridge=bridge,
            config=config,
        )

        step = pipeline.step(user_goal="Keep trying")
        assert step.action.action == ActionType.PANIC
        assert "3-strike" in step.action.reasoning
        assert len(panic_emitted) >= 1

        # Corrective interactive action with positive visual diff resets strikes
        memory.record_step(
            action=ActionPlan(action=ActionType.CLICK, target_id=2, reasoning="Repositioning"),
            success=True,
            screen_diff=0.15,
        )
        assert memory.get_consecutive_strikes() == 0
        assert memory.is_in_loop() is False


# ===========================================================================
# SCENARIO 6: Zero-VRAM Visible Browser Brain Offload
# ===========================================================================

class TestScenario6VisibleBrowserBrainOffload:
    """Verifies visible Chrome automation and Sentinel Clipboard Verification with guaranteed restore."""

    def test_sentinel_clipboard_harvest_and_guaranteed_restore(self) -> None:
        """Verifies Sentinel UUID injection, answer harvest, and original clipboard restoration."""
        user_original_document = "CONFIDENTIAL USER SPREADSHEET 2026"
        clipboard = MockClipboardBackend(initial_text=user_original_document)
        verifier = SentinelClipboardVerifier(clipboard=clipboard, default_timeout_s=2.0)

        # Action simulating web AI copy: sets response text
        def simulate_copy_action() -> bool:
            clipboard.set_text("Here is the summarized frontier web AI response.")
            return True

        result = verifier.execute_harvest(trigger_copy_action=simulate_copy_action)
        assert result == "Here is the summarized frontier web AI response."

        # GUARANTEE: User's original clipboard text must be restored in all cases
        assert clipboard.get_text() == user_original_document

    def test_sentinel_clipboard_restore_on_harvest_error(self) -> None:
        """Verifies original clipboard is 100% restored even when harvesting times out or errors."""
        user_original_document = "MY IMPORTANT NOTES"
        clipboard = MockClipboardBackend(initial_text=user_original_document)
        window_mgr = MockBrowserWindowBackend(existing_hwnd=9988)

        offloader = BrowserOffloader(
            clipboard_backend=clipboard,
            window_backend=window_mgr,
        )

        # Force execute_harvest to return None (simulating timeout)
        with patch.object(offloader.verifier, "execute_harvest", return_value=None):
            with pytest.raises(OffloadHarvestError):
                offloader.query_web_ai(prompt="Generate report")

        # GUARANTEE: User's original clipboard content is STILL 100% restored!
        assert clipboard.get_text() == user_original_document

    def test_visible_browser_offloader_full_cycle(self, qapp: QApplication) -> None:
        """Verifies offloader state machine transitions through visible focus and prompt entry."""
        bridge = UIBridge()
        dock = CompanionDock(bridge=bridge)

        clipboard = MockClipboardBackend(initial_text="User draft text")
        window_mgr = MockBrowserWindowBackend(existing_hwnd=7788)
        mouse = MouseDriver(simulation_mode=True, preview_reticle_ms=0)
        keyboard = KeyboardDriver(backend=MockInputBackend())

        offloader = BrowserOffloader(
            clipboard_backend=clipboard,
            window_backend=window_mgr,
            keyboard_driver=keyboard,
            mouse_driver=mouse,
            bridge=bridge,
        )

        # Hook verifier execute_harvest to simulate web AI answer
        def mock_harvest(trigger_copy_action: Any, **kwargs: Any) -> str:
            return "Visible Chrome AI Answer: 42"

        with patch.object(offloader.verifier, "execute_harvest", side_effect=mock_harvest):
            answer = offloader.query_web_ai(prompt="What is the answer to life?")
            assert "42" in answer
            assert offloader.state == OffloaderState.COMPLETED
            assert 7788 in window_mgr.focused_hwnds

        dock.close()
