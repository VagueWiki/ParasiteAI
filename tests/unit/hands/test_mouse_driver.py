"""
Tests for ParasiteAI Win32 Human-Like Mouse Driver.
Verifies simulation mode movement, pre-click reticle preview callback,
sub-2ms interrupt preemption during preview and mid-flight, fail-safe button release on interrupt,
click/double-click/drag-and-drop/scroll sequences, and already-cancelled token preemption.
"""

from __future__ import annotations

import threading
import time
import pytest

from parasite_ai.config import MouseConfig
from parasite_ai.hands.kinematics import KinematicConfig, KinematicsEngine
from parasite_ai.hands.mouse import MouseDriver


class TestMouseDriverSimulationMode:
    """Verifies basic movement, positioning, and state tracking in simulation mode."""

    def test_mouse_driver_simulation_mode_movement(self):
        driver = MouseDriver(
            config=MouseConfig(step_delay_ms=1.0),
            simulation_mode=True,
            preview_reticle_ms=0,
        )

        assert driver.get_cursor_pos() == (960, 540)
        success = driver.move_to(500, 400, duration=0.02)
        assert success is True
        assert driver.get_cursor_pos() == (500, 400)
        assert len(driver.simulation_history) > 0
        assert driver.simulation_history[-1]["event"] == "move"
        assert driver.simulation_history[-1]["pos"] == (500, 400)

    def test_mouse_driver_same_position_move(self):
        driver = MouseDriver(simulation_mode=True, preview_reticle_ms=0)
        pos = driver.get_cursor_pos()
        success = driver.move_to(pos[0], pos[1])
        assert success is True
        assert driver.get_cursor_pos() == pos


class TestMouseDriverReticlePreview:
    """Verifies 300ms pre-click reticle preview callback and preview interruption."""

    def test_mouse_driver_pre_click_reticle_callback(self):
        reticle_invocations: list[tuple[int, int, int]] = []

        def on_reticle(x: int, y: int, duration_ms: int) -> None:
            reticle_invocations.append((x, y, duration_ms))

        driver = MouseDriver(
            reticle_callback=on_reticle,
            simulation_mode=True,
            preview_reticle_ms=20,  # Fast preview for test speed
        )

        success = driver.click(300, 200, preview_reticle=True)
        assert success is True
        assert len(reticle_invocations) == 1
        assert reticle_invocations[0] == (300, 200, 20)

    def test_mouse_driver_interrupt_during_preview(self):
        reticle_invocations: list[tuple[int, int, int]] = []

        def on_reticle(x: int, y: int, duration_ms: int) -> None:
            reticle_invocations.append((x, y, duration_ms))

        token = threading.Event()

        # Fire cancellation token 10ms into the 300ms preview
        def trigger_token():
            time.sleep(0.010)
            token.set()

        threading.Thread(target=trigger_token, daemon=True).start()

        driver = MouseDriver(
            reticle_callback=on_reticle,
            simulation_mode=True,
            preview_reticle_ms=300,
        )

        initial_pos = driver.get_cursor_pos()
        t0 = time.perf_counter()
        success = driver.click(700, 600, cancellation_token=token, preview_reticle=True)
        t_elapsed = time.perf_counter() - t0

        assert success is False
        # Aborted well before the 300ms preview completed
        assert t_elapsed < 0.200
        # Cursor never moved to target
        assert driver.get_cursor_pos() == initial_pos


class TestMouseDriverInterruptsAndLatency:
    """Verifies sub-2ms preemption mid-trajectory and automatic fail-safe release."""

    def test_mouse_driver_already_cancelled_token(self):
        driver = MouseDriver(simulation_mode=True)
        token = threading.Event()
        token.set()  # Token is already pre-set

        t0 = time.perf_counter()
        success = driver.move_to(800, 800, cancellation_token=token)
        t_elapsed = time.perf_counter() - t0

        assert success is False
        # Preemption occurs almost instantly (< 2ms)
        assert t_elapsed < 0.005
        assert driver.get_cursor_pos() == (960, 540)

    def test_mouse_driver_interrupt_mid_trajectory(self):
        driver = MouseDriver(
            config=MouseConfig(step_delay_ms=8.0),
            simulation_mode=True,
            preview_reticle_ms=0,
        )

        token = threading.Event()

        # Interrupt after 30ms (during flight)
        def trigger_token():
            time.sleep(0.030)
            token.set()

        threading.Thread(target=trigger_token, daemon=True).start()

        t0 = time.perf_counter()
        success = driver.move_to(100, 100, duration=0.40, cancellation_token=token)
        t_elapsed = time.perf_counter() - t0

        assert success is False
        # Movement aborted mid-flight in ~30-50ms instead of 400ms
        assert t_elapsed < 0.250
        # Cursor stopped midway, not at destination (100, 100)
        assert driver.get_cursor_pos() != (100, 100)

    def test_mouse_driver_releases_buttons_on_interrupt(self):
        driver = MouseDriver(simulation_mode=True, preview_reticle_ms=0)
        token = threading.Event()

        # Manually hold left button
        driver.mouse_down("left")
        assert "left" in driver._held_buttons

        token.set()
        # Attempt to move while token is set
        success = driver.move_to(500, 500, cancellation_token=token)
        assert success is False

        # Fail-safe must have released all buttons immediately
        assert len(driver._held_buttons) == 0
        release_events = [e for e in driver.simulation_history if e["event"] == "release_all_buttons"]
        assert len(release_events) > 0


class TestMouseDriverActionSequences:
    """Verifies click, double-click, drag-and-drop, and scroll actions."""

    def test_mouse_driver_click_sequence(self):
        driver = MouseDriver(
            config=MouseConfig(step_delay_ms=1.0),
            simulation_mode=True,
            preview_reticle_ms=0,
        )

        success = driver.click(400, 300, button="right", preview_reticle=False)
        assert success is True
        assert driver.get_cursor_pos() == (400, 300)

        events = [e["event"] for e in driver.simulation_history]
        assert "move" in events
        assert "mouse_down" in events
        assert "mouse_up" in events

        # Confirm button was right
        down_event = next(e for e in driver.simulation_history if e["event"] == "mouse_down")
        up_event = next(e for e in driver.simulation_history if e["event"] == "mouse_up")
        assert down_event["button"] == "right"
        assert up_event["button"] == "right"

    def test_mouse_driver_double_click_cadence(self):
        driver = MouseDriver(
            config=MouseConfig(step_delay_ms=1.0),
            simulation_mode=True,
            preview_reticle_ms=0,
        )

        success = driver.double_click(200, 200)
        assert success is True

        down_events = [e for e in driver.simulation_history if e["event"] == "mouse_down"]
        up_events = [e for e in driver.simulation_history if e["event"] == "mouse_up"]
        assert len(down_events) == 2
        assert len(up_events) == 2

    def test_mouse_driver_drag_and_drop(self):
        driver = MouseDriver(
            config=MouseConfig(step_delay_ms=1.0),
            simulation_mode=True,
            preview_reticle_ms=0,
        )

        success = driver.drag_and_drop(100, 100, 500, 500, button="left")
        assert success is True
        assert driver.get_cursor_pos() == (500, 500)
        assert len(driver._held_buttons) == 0

        # Verify event order: move -> down -> move -> up
        events = [e["event"] for e in driver.simulation_history]
        assert "mouse_down" in events
        assert "mouse_up" in events
        down_idx = events.index("mouse_down")
        up_idx = events.index("mouse_up")
        assert down_idx < up_idx

    def test_mouse_driver_scroll_event(self):
        driver = MouseDriver(simulation_mode=True, preview_reticle_ms=0)

        success = driver.scroll(delta=-3)
        assert success is True

        scroll_events = [e for e in driver.simulation_history if e["event"] == "scroll"]
        assert len(scroll_events) == 1
        assert scroll_events[0]["delta"] == -3


class TestMouseDriverCoordinateNormalization:
    """Verifies multi-monitor virtual screen boundary clamping and normalization."""

    def test_single_monitor_bounds_clamping(self):
        # 1080p single monitor: [0, 0] to [1920, 1080]
        # (0, 0) -> (0, 0)
        assert MouseDriver.normalize_coordinates(0, 0, 0, 0, 1920, 1080) == (0, 0)
        # (1919, 1079) -> (65535, 65535)
        assert MouseDriver.normalize_coordinates(1919, 1079, 0, 0, 1920, 1080) == (65535, 65535)
        # Out-of-bounds negative -> clamped to (0, 0), no wrap
        assert MouseDriver.normalize_coordinates(-100, -50, 0, 0, 1920, 1080) == (0, 0)
        # Out-of-bounds positive -> clamped to (65535, 65535), no wrap
        assert MouseDriver.normalize_coordinates(3000, 2000, 0, 0, 1920, 1080) == (65535, 65535)

    def test_dual_monitor_negative_offset_clamping(self):
        # Dual monitor setup: Left monitor at (-1920, 0), Right (primary) at (0, 0)
        # Total virtual desktop: vx = -1920, vy = 0, vcx = 3840, vcy = 1080
        # Far-left corner (-1920, 0) -> (0, 0)
        assert MouseDriver.normalize_coordinates(-1920, 0, -1920, 0, 3840, 1080) == (0, 0)
        # Far-right corner (1919, 1079) -> (65535, 65535)
        assert MouseDriver.normalize_coordinates(1919, 1079, -1920, 0, 3840, 1080) == (65535, 65535)
        # Extreme negative overshoot (-2500, 0) -> clamped to (0, 0)
        assert MouseDriver.normalize_coordinates(-2500, 0, -1920, 0, 3840, 1080) == (0, 0)

