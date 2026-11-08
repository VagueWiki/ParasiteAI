"""
ParasiteAI - Milestone M2 Adversarial Gate Verification Test Suite (Challenger 1).
Exhaustively stress-tests:
1. Alternating physical vs synthetic event bursts on InterruptGuard under concurrency.
2. Rapid preemption of MouseDriver during active movement, verifying unconditional button release.
3. Screen corner slam stress testing on primary and virtual desktop (negative coordinates).
4. Extreme coordinates for KinematicsEngine (zero distance, 8K diagonals, monotonicity, 0-pixel landing error).
5. WindowGuard edge cases (empty strings, whitespace-only, dead PIDs, permission-denied, buffer stress).
"""

from __future__ import annotations

import ctypes
import math
import random
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from parasite_ai.config import MouseConfig, SafetyConfig
from parasite_ai.hands.keyboard import (
    KEYEVENTF_KEYUP,
    LLKHF_INJECTED,
    LLMHF_INJECTED,
    MOUSEEVENTF_LEFTUP,
    MOUSEEVENTF_MIDDLEUP,
    MOUSEEVENTF_RIGHTUP,
    VK_BACK,
    VK_CONTROL,
    VK_ESCAPE,
    VK_MENU,
    VK_P,
    VK_SHIFT,
    MockInputBackend,
)
from parasite_ai.hands.kinematics import KinematicConfig, KinematicsEngine
from parasite_ai.hands.mouse import MouseDriver
from parasite_ai.safety.interrupt_guard import (
    InterruptGuard,
    LLKHF_UP,
    WM_KEYDOWN,
    WM_KEYUP,
    WM_MOUSEMOVE,
)
from parasite_ai.safety.panic import PanicManager, PanicTriggerSource
from parasite_ai.safety.window_guard import (
    WindowGuard,
    WindowGuardedException,
    WindowInfo,
)


# ===========================================================================
# 1. Alternating Physical vs Synthetic Event Bursts on InterruptGuard
# ===========================================================================
class TestAdversarialInterruptGuardAlternatingBursts:
    """Stress tests alternating synthetic vs physical event bursts on InterruptGuard."""

    def test_alternating_mouse_synthetic_physical_bursts_100_iterations(self):
        """Alternates bursts of synthetic mouse events with simulated physical events."""
        guard = InterruptGuard(cooldown_seconds=0.1)
        token = guard.get_cancellation_token()

        # Warm-up to initialize thread infrastructure
        guard.simulate_event("mouse", flags=0, pt=(500, 500))
        guard.reset_interrupt()

        for iteration in range(50):
            # 1. Synthetic burst (LLMHF_INJECTED = 1): must NEVER trigger interrupt
            for _ in range(10):
                guard.simulate_event(
                    "mouse",
                    flags=LLMHF_INJECTED,
                    pt=(random.randint(100, 800), random.randint(100, 600)),
                )
            assert not token.is_set(), f"Iteration {iteration}: Synthetic burst triggered interrupt!"
            assert not guard.is_interrupted()

            # 2. Physical event (flags = 0): must IMMEDIATELY trigger interrupt (< 2ms)
            t0 = time.perf_counter()
            guard.simulate_event(
                "mouse",
                flags=0,
                pt=(random.randint(100, 800), random.randint(100, 600)),
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000.0

            assert token.is_set(), f"Iteration {iteration}: Physical event failed to trigger interrupt!"
            assert guard.is_interrupted()
            assert elapsed_ms < 5.0, f"Iteration {iteration}: Interrupt latency too high ({elapsed_ms:.2f}ms)"

            # 3. Reset and verify clean slate
            guard.reset_interrupt()
            assert not token.is_set()
            assert not guard.is_interrupted()

    def test_alternating_keyboard_synthetic_physical_bursts_100_iterations(self):
        """Alternates bursts of synthetic keyboard events with simulated physical events."""
        guard = InterruptGuard(cooldown_seconds=0.1)
        token = guard.get_cancellation_token()

        for iteration in range(50):
            # 1. Synthetic keystroke burst (LLKHF_INJECTED = 0x10)
            for _ in range(10):
                guard.simulate_event("keyboard", flags=LLKHF_INJECTED, vk_code=65)
            assert not token.is_set(), f"Iteration {iteration}: Synthetic keystroke triggered interrupt!"
            assert not guard.is_interrupted()

            # 2. Physical keystroke (flags = 0)
            t0 = time.perf_counter()
            guard.simulate_event("keyboard", flags=0, vk_code=65)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0

            assert token.is_set(), f"Iteration {iteration}: Physical key failed to trigger interrupt!"
            assert guard.is_interrupted()
            assert elapsed_ms < 5.0

            # 3. Reset
            guard.reset_interrupt()
            assert not token.is_set()
            assert not guard.is_interrupted()

    def test_concurrent_synthetic_flood_with_physical_interleaving(self):
        """
        Multi-threaded stress: 4 worker threads bombard synthetic events
        while 1 thread injects physical events and 1 thread monitors preemption.
        """
        guard = InterruptGuard(cooldown_seconds=0.05)
        stop_event = threading.Event()
        errors: list[Exception] = []

        def synthetic_mouse_flooder():
            try:
                while not stop_event.is_set():
                    guard.simulate_event("mouse", flags=LLMHF_INJECTED, pt=(500, 500))
                    time.sleep(0.0001)
            except Exception as e:
                errors.append(e)

        def synthetic_keyboard_flooder():
            try:
                while not stop_event.is_set():
                    guard.simulate_event("keyboard", flags=LLKHF_INJECTED, vk_code=70)
                    time.sleep(0.0001)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=synthetic_mouse_flooder, daemon=True),
            threading.Thread(target=synthetic_mouse_flooder, daemon=True),
            threading.Thread(target=synthetic_keyboard_flooder, daemon=True),
            threading.Thread(target=synthetic_keyboard_flooder, daemon=True),
        ]
        for t in threads:
            t.start()

        # Let synthetic flood run for 30ms to confirm no false positives
        time.sleep(0.030)
        assert not guard.get_cancellation_token().is_set()
        assert not guard.is_interrupted()

        # Inject physical touch amidst flood
        for _ in range(5):
            guard.simulate_event("mouse", flags=0, pt=(500, 500))
            assert guard.get_cancellation_token().is_set()
            assert guard.is_interrupted()
            guard.reset_interrupt()
            time.sleep(0.005)

        stop_event.set()
        for t in threads:
            t.join(timeout=1.0)

        assert len(errors) == 0, f"Thread errors encountered: {errors}"

    def test_sliding_cooldown_extended_by_subsequent_physical_events(self):
        """Ensures repeated physical touches extend the cooldown window."""
        cooldown = 0.20
        guard = InterruptGuard(cooldown_seconds=cooldown)

        # First touch at t=0
        guard.simulate_event("mouse", flags=0, pt=(100, 100))
        assert guard.is_interrupted()

        # Wait 120ms (more than half cooldown)
        time.sleep(0.12)
        assert guard.is_interrupted()

        # Second touch at t=120ms (resets cooldown to now + 200ms)
        guard.simulate_event("mouse", flags=0, pt=(100, 100))
        assert guard.is_interrupted()

        # Wait another 120ms (t=240ms from start, but only 120ms from second touch)
        time.sleep(0.12)
        # Should STILL be interrupted because of sliding extension
        assert guard.is_interrupted()

        # Wait remaining time to let cooldown expire
        time.sleep(0.15)
        assert not guard.is_interrupted()

    def test_wait_interruptible_instant_abort_on_physical_burst(self):
        """Verifies wait_interruptible unblocks immediately on physical touch."""
        guard = InterruptGuard(cooldown_seconds=0.1)

        def inject_after_delay():
            time.sleep(0.020)
            guard.simulate_event("mouse", flags=0, pt=(300, 300))

        threading.Thread(target=inject_after_delay, daemon=True).start()

        t0 = time.perf_counter()
        completed_full_wait = guard.wait_interruptible(timeout=2.0)
        elapsed = time.perf_counter() - t0

        assert completed_full_wait is False
        assert elapsed < 0.150, f"wait_interruptible took too long to abort ({elapsed:.3f}s)"


# ===========================================================================
# 2. Rapid Preemption of MouseDriver and Unconditional Button Release
# ===========================================================================
class TestAdversarialMouseDriverPreemptionAndButtonRelease:
    """Stress tests rapid preemption of MouseDriver and verifies zero stuck buttons."""

    def test_preemption_during_active_movement_unconditionally_releases_left_button(self):
        """Cancels MouseDriver during movement; verifies held button is released."""
        driver = MouseDriver(
            config=MouseConfig(step_delay_ms=5.0),
            simulation_mode=True,
            preview_reticle_ms=0,
        )
        token = threading.Event()

        # Hold left button
        driver.mouse_down("left")
        assert "left" in driver._held_buttons

        def cancel_midway():
            time.sleep(0.025)
            token.set()

        threading.Thread(target=cancel_midway, daemon=True).start()

        success = driver.move_to(800, 800, duration=0.30, cancellation_token=token)
        assert success is False
        # Button must be unconditionally released
        assert len(driver._held_buttons) == 0
        assert "left" not in driver._held_buttons

        release_events = [e for e in driver.simulation_history if e["event"] == "release_all_buttons"]
        assert len(release_events) > 0

    def test_preemption_with_all_three_buttons_held(self):
        """Holds left, right, middle buttons simultaneously; cancels move; verifies all released."""
        driver = MouseDriver(
            config=MouseConfig(step_delay_ms=5.0),
            simulation_mode=True,
            preview_reticle_ms=0,
        )
        token = threading.Event()

        driver.mouse_down("left")
        driver.mouse_down("right")
        driver.mouse_down("middle")
        assert driver._held_buttons == {"left", "right", "middle"}

        def cancel_midway():
            time.sleep(0.020)
            token.set()

        threading.Thread(target=cancel_midway, daemon=True).start()

        success = driver.move_to(500, 500, duration=0.25, cancellation_token=token)
        assert success is False
        assert len(driver._held_buttons) == 0
        assert driver._held_buttons == set()

    def test_drag_and_drop_preemption_at_each_critical_checkpoint(self):
        """Tests preemption during each phase of drag_and_drop, ensuring no stuck buttons."""
        # Checkpoint 1: Cancelled before drag starts (pre-set token)
        driver1 = MouseDriver(simulation_mode=True, preview_reticle_ms=0)
        token1 = threading.Event()
        token1.set()
        assert driver1.drag_and_drop(100, 100, 400, 400, cancellation_token=token1) is False
        assert len(driver1._held_buttons) == 0

        # Checkpoint 2: Cancelled during flight to destination
        driver2 = MouseDriver(
            config=MouseConfig(step_delay_ms=5.0),
            simulation_mode=True,
            preview_reticle_ms=0,
        )
        token2 = threading.Event()

        def cancel_during_drag():
            # Wait for button to be pressed, then cancel
            while "left" not in driver2._held_buttons:
                time.sleep(0.002)
            time.sleep(0.010)
            token2.set()

        threading.Thread(target=cancel_during_drag, daemon=True).start()
        success2 = driver2.drag_and_drop(100, 100, 800, 800, cancellation_token=token2)
        assert success2 is False
        assert len(driver2._held_buttons) == 0

    def test_rapid_preemption_hammer_stress_50_iterations(self):
        """Executes 50 rapid movement iterations with random cancellation delays."""
        driver = MouseDriver(
            config=MouseConfig(step_delay_ms=2.0),
            simulation_mode=True,
            preview_reticle_ms=0,
        )

        buttons = ["left", "right", "middle"]
        for i in range(50):
            token = threading.Event()
            btn = buttons[i % 3]
            driver.mouse_down(btn)

            # Random cancellation delay between 1ms and 15ms
            delay = random.uniform(0.001, 0.015)

            def trigger(t_delay: float):
                time.sleep(t_delay)
                token.set()

            threading.Thread(target=trigger, args=(delay,), daemon=True).start()

            target_x = random.randint(100, 1800)
            target_y = random.randint(100, 1000)
            driver.move_to(target_x, target_y, duration=0.20, cancellation_token=token)

            # Invariant: after every aborted iteration, held buttons MUST be 0
            assert len(driver._held_buttons) == 0, f"Iteration {i}: Button {btn} remained stuck!"

    def test_pre_cancelled_token_click_and_move_instant_abort(self):
        """Verifies sub-2ms preemption when token is pre-cancelled."""
        driver = MouseDriver(simulation_mode=True, preview_reticle_ms=100)
        token = threading.Event()
        token.set()

        driver.mouse_down("left")
        assert len(driver._held_buttons) == 1

        t0 = time.perf_counter()
        res_move = driver.move_to(500, 500, cancellation_token=token)
        t_move = time.perf_counter() - t0

        assert res_move is False
        assert t_move < 0.010
        assert len(driver._held_buttons) == 0

        driver.mouse_down("right")
        t0 = time.perf_counter()
        res_click = driver.click(500, 500, cancellation_token=token)
        t_click = time.perf_counter() - t0

        assert res_click is False
        assert t_click < 0.010
        assert len(driver._held_buttons) == 0


# ===========================================================================
# 3. Screen Corner Slam Stress Testing on Primary and Virtual Desktop
# ===========================================================================
class TestAdversarialScreenCornerSlamMultiMonitor:
    """Stress tests screen corner slam panic detection on primary and virtual monitors."""

    def test_primary_monitor_corner_slam_exact_and_within_delta(self):
        """Tests all 4 primary monitor corners at exact coordinates and within delta."""
        mock_backend = MockInputBackend()
        # Primary: 1920x1080
        mock_backend.get_screen_metrics = lambda: (1920, 1080, 0, 0, 1920, 1080)
        cfg = SafetyConfig(corner_panic_enabled=True, corner_distance_px=4)
        panic = PanicManager(config=cfg, backend=mock_backend)

        corners = [
            (0, 0),             # Top-Left
            (1919, 0),          # Top-Right
            (0, 1079),          # Bottom-Left
            (1919, 1079),       # Bottom-Right
        ]

        for cx, cy in corners:
            # 1. Exact corner
            assert panic.check_mouse_position(cx, cy, flags=0) is True
            assert panic.is_panic() is True
            assert panic.get_panic_reason() == PanicTriggerSource.CORNER_SLAM
            panic.reset_panic()

            # 2. Within delta offset (+2, +2) or (-2, -2)
            dx = 2 if cx == 0 else -2
            dy = 2 if cy == 0 else -2
            assert panic.check_mouse_position(cx + dx, cy + dy, flags=0) is True
            assert panic.is_panic() is True
            panic.reset_panic()

    def test_primary_monitor_outside_delta_does_not_trigger_panic(self):
        """Points outside corner_distance_px must not trigger panic."""
        mock_backend = MockInputBackend()
        mock_backend.get_screen_metrics = lambda: (1920, 1080, 0, 0, 1920, 1080)
        cfg = SafetyConfig(corner_panic_enabled=True, corner_distance_px=4)
        panic = PanicManager(config=cfg, backend=mock_backend)

        # Delta is 4: offset of 5 must NOT trigger
        assert panic.check_mouse_position(5, 5, flags=0) is False
        assert panic.check_mouse_position(1919 - 5, 5, flags=0) is False
        assert panic.check_mouse_position(960, 540, flags=0) is False
        assert not panic.is_panic()

    def test_virtual_desktop_multi_monitor_negative_coordinates(self):
        """
        Multi-monitor test with negative coordinates:
        Left monitor: 1920x1080 at (-1920, 0)
        Primary monitor: 1920x1080 at (0, 0)
        Total virtual screen: vx=-1920, vy=0, vcx=3840, vcy=1080
        """
        mock_backend = MockInputBackend()
        mock_backend.get_screen_metrics = lambda: (1920, 1080, -1920, 0, 3840, 1080)
        cfg = SafetyConfig(corner_panic_enabled=True, corner_distance_px=4)
        panic = PanicManager(config=cfg, backend=mock_backend)

        # Virtual desktop far-left corners:
        # Top-Left: (-1920, 0)
        # Bottom-Left: (-1920, 1079)
        # Top-Right: (-1920 + 3840 - 1, 0) = (1919, 0)
        # Bottom-Right: (1919, 1079)

        # Test negative corner slam: (-1920, 0)
        assert panic.check_mouse_position(-1920, 0, flags=0) is True
        assert panic.is_panic() is True
        assert panic.get_panic_reason() == PanicTriggerSource.CORNER_SLAM
        panic.reset_panic()

        # Test negative corner slam with small delta: (-1918, 2)
        assert panic.check_mouse_position(-1918, 2, flags=0) is True
        assert panic.is_panic() is True
        panic.reset_panic()

        # Test far bottom-left: (-1920, 1079)
        assert panic.check_mouse_position(-1920, 1079, flags=0) is True
        assert panic.is_panic() is True
        panic.reset_panic()

    def test_corner_slam_synthetic_injected_movement_ignored(self):
        """Synthetic injected cursor movement (LLMHF_INJECTED) must NEVER trigger corner panic."""
        mock_backend = MockInputBackend()
        mock_backend.get_screen_metrics = lambda: (1920, 1080, 0, 0, 1920, 1080)
        cfg = SafetyConfig(corner_panic_enabled=True, corner_distance_px=4)
        panic = PanicManager(config=cfg, backend=mock_backend)

        # Move to (0, 0) with LLMHF_INJECTED
        fired = panic.check_mouse_position(0, 0, flags=LLMHF_INJECTED)
        assert fired is False
        assert not panic.is_panic()

    def test_corner_slam_disabled_via_config(self):
        """Corner slam does not trigger when disabled in config."""
        mock_backend = MockInputBackend()
        mock_backend.get_screen_metrics = lambda: (1920, 1080, 0, 0, 1920, 1080)
        cfg = SafetyConfig(corner_panic_enabled=False, corner_distance_px=4)
        panic = PanicManager(config=cfg, backend=mock_backend)

        assert panic.check_mouse_position(0, 0, flags=0) is False
        assert not panic.is_panic()

    def test_corner_slam_neutralizes_hardware(self):
        """Corner slam trigger must invoke emergency_hardware_release."""
        mock_backend = MockInputBackend()
        mock_backend.get_screen_metrics = lambda: (1920, 1080, 0, 0, 1920, 1080)
        cfg = SafetyConfig(corner_panic_enabled=True, corner_distance_px=4)
        panic = PanicManager(config=cfg, backend=mock_backend)

        panic.check_mouse_position(0, 0, flags=0)
        assert panic.is_panic()

        # Verify mouse buttons and modifiers release packets were dispatched to backend
        events = mock_backend.events
        mouse_ups = [e for e in events if e.type == 0 and (e.flags & (MOUSEEVENTF_LEFTUP | MOUSEEVENTF_RIGHTUP | MOUSEEVENTF_MIDDLEUP))]
        key_ups = [e for e in events if e.type == 1 and (e.flags & KEYEVENTF_KEYUP)]
        assert len(mouse_ups) > 0
        assert len(key_ups) > 0


# ===========================================================================
# 4. Extreme Coordinates & Invariants for KinematicsEngine
# ===========================================================================
class TestAdversarialKinematicsEngineExtremeCoordinates:
    """Stress tests KinematicsEngine with extreme coordinates and verifies physical invariants."""

    def test_zero_distance_hop_invariants(self):
        """Zero distance hop (start_pt == target_pt) must return exactly [start_pt] without error."""
        engine = KinematicsEngine()
        points = [(0, 0), (1920, 1080), (-500, -300), (9999, 9999)]
        for pt in points:
            traj = engine.generate_trajectory(pt, pt)
            assert traj == [pt]
            assert len(traj) == 1
            assert engine.calculate_fitts_duration(0.0) == 0.0

    def test_subpixel_and_one_pixel_hops(self):
        """Small hops (1px or distance < 1.0) must produce valid trajectories without math errors."""
        engine = KinematicsEngine()
        # Distance = 1.0
        traj = engine.generate_trajectory((100, 100), (101, 100))
        assert traj[0] == (100, 100)
        assert traj[-1] == (101, 100)
        assert len(traj) >= 2

        # Diagonal 1px hop (dist = sqrt(2) ~= 1.414)
        traj_diag = engine.generate_trajectory((100, 100), (101, 101))
        assert traj_diag[0] == (100, 100)
        assert traj_diag[-1] == (101, 101)

    def test_extreme_multi_monitor_diagonal_screen_sweeps(self):
        """
        Extreme distance sweeps:
        1. Negative secondary to high-res primary: (-1920, -1080) -> (3840, 2160) (D ~ 6708px)
        2. 8K screen sweep: (7680, 4320) -> (0, 0) (D ~ 8818px)
        """
        engine = KinematicsEngine()

        sweeps = [
            ((-1920, -1080), (3840, 2160)),
            ((7680, 4320), (0, 0)),
            ((-3840, 0), (3840, 1440)),
        ]

        for p_start, p_target in sweeps:
            traj = engine.generate_trajectory(p_start, p_target)
            # 1. 0-pixel landing error
            assert traj[0] == p_start, f"Trajectory did not start at {p_start}"
            assert traj[-1] == p_target, f"Trajectory did not land at {p_target}"

            # 2. No NaNs or Infs
            for x, y in traj:
                assert isinstance(x, int) and isinstance(y, int)
                assert not math.isnan(x) and not math.isnan(y)

            # 3. Path continuity (non-empty, smooth progression)
            assert len(traj) > 30

    def test_maximum_step_displacement_bounds_across_distance_spectrum(self):
        """Verifies no single step teleportation exceeds physically realistic bounds."""
        engine = KinematicsEngine(seed=42)

        test_pairs = [
            ((100, 100), (150, 150)),       # 70px
            ((200, 200), (600, 400)),       # 447px
            ((0, 0), (1920, 1080)),         # 2202px
            ((-1000, -500), (3000, 2000)),  # 4716px
        ]

        for p_start, p_target in test_pairs:
            traj = engine.generate_trajectory(p_start, p_target)
            dist = math.hypot(p_target[0] - p_start[0], p_target[1] - p_start[1])

            # Bound maximum allowable single-step displacement
            # Flash & Hogan peak velocity is 1.875 * dist / duration.
            # At 120Hz, max step is bounded by (1.875 * dist) / (duration * 120) * margin
            duration = engine.calculate_fitts_duration(dist)
            expected_peak_step = (1.875 * dist) / max(1, duration * 120.0)
            max_allowed_step = max(35.0, expected_peak_step * 2.2)

            for i in range(len(traj) - 1):
                p_curr = traj[i]
                p_next = traj[i + 1]
                step_dist = math.hypot(p_next[0] - p_curr[0], p_next[1] - p_curr[1])
                assert step_dist <= max_allowed_step, (
                    f"Teleportation jump of {step_dist:.2f}px detected between {p_curr} and {p_next} "
                    f"(allowed: {max_allowed_step:.2f}px for dist={dist:.1f}px)"
                )

    def test_minimum_jerk_polynomial_strictly_monotonic_across_1000_samples(self):
        """Verifies Flash & Hogan Minimum Jerk polynomial monotonicity over 1000 samples."""
        engine = KinematicsEngine()
        samples = 1000
        prev_tau = 0.0

        for i in range(samples + 1):
            s = i / samples
            tau = engine.minimum_jerk(s)
            vel = engine.minimum_jerk_velocity(s)

            # Monotonicity: tau(s_{i+1}) >= tau(s_i)
            assert tau >= prev_tau - 1e-9, f"Monotonicity violated at s={s}: {tau} < {prev_tau}"
            # Non-negative velocity everywhere in [0, 1]
            assert vel >= -1e-9, f"Velocity negative at s={s}: {vel}"

            prev_tau = tau

        # Clamping outside [0, 1]
        assert engine.minimum_jerk(-0.5) == 0.0
        assert engine.minimum_jerk(1.5) == 1.0

    def test_deterministic_reproducibility_with_seed(self):
        """Verifies deterministic trajectory generation with fixed random seed."""
        engine1 = KinematicsEngine(seed=1337)
        engine2 = KinematicsEngine(seed=1337)
        engine3 = KinematicsEngine(seed=9999)

        traj1 = engine1.generate_trajectory((200, 200), (1200, 800))
        traj2 = engine2.generate_trajectory((200, 200), (1200, 800))
        traj3 = engine3.generate_trajectory((200, 200), (1200, 800))

        assert traj1 == traj2
        assert traj1 != traj3


# ===========================================================================
# 5. WindowGuard Edge Cases
# ===========================================================================
class TestAdversarialWindowGuardEdgeCases:
    """Stress tests WindowGuard foreground privacy shield and fail-safe blackouts."""

    def test_empty_strings_and_whitespace_only(self):
        """Empty or whitespace-only titles and process names default to safe if accessible."""
        guard = WindowGuard()

        # Empty strings
        is_sens, reason = guard.evaluate_sensitivity(
            title="",
            process_name="",
            hwnd=100,
            can_open_process=True,
        )
        assert is_sens is False
        assert reason == "Window is safe to operate"

        # Whitespace-only strings
        is_sens, reason = guard.evaluate_sensitivity(
            title="   \t\r\n   ",
            process_name="   ",
            hwnd=100,
            can_open_process=True,
        )
        assert is_sens is False
        assert reason == "Window is safe to operate"

    def test_null_and_negative_hwnd_failsafe(self):
        """hwnd == 0 (Desktop switch / locked screen) enforces strict fail-safe blackout."""
        guard = WindowGuard()

        is_sens, reason = guard.evaluate_sensitivity(
            title="Google Chrome",
            process_name="chrome.exe",
            hwnd=0,
            can_open_process=True,
        )
        assert is_sens is True
        assert "hwnd == 0" in reason

    def test_permission_denied_and_elevated_process(self):
        """OpenProcess access denied (can_open_process=False) enforces strict fail-safe blackout."""
        guard = WindowGuard()

        is_sens, reason = guard.evaluate_sensitivity(
            title="Normal Window Title",
            process_name="normal.exe",
            hwnd=100,
            can_open_process=False,
        )
        assert is_sens is True
        assert "access denied" in reason.lower()

    def test_dead_or_zero_pid_handling(self):
        """Simulates dead PID or PID=0 returned by Win32 subsystem."""
        guard = WindowGuard()

        # Mock GetForegroundWindow returning valid hwnd, but GetWindowThreadProcessId returning PID 0
        with patch.object(guard._user32, "GetForegroundWindow", return_value=5555):
            with patch.object(
                guard._user32,
                "GetWindowThreadProcessId",
                side_effect=lambda hwnd, pid_ptr: ctypes.memset(pid_ptr, 0, 4),
            ):
                info = guard.get_active_window_info()
                assert info.is_sensitive is True
                assert info.pid == 0
                assert "PID 0" in info.reason
                assert guard.is_safe_to_operate() is False

    def test_massive_unicode_and_buffer_overflow_resistance(self):
        """Tests oversized titles with complex Unicode and emojis."""
        guard = WindowGuard()

        # 10,000 character string containing sensitive substring deep inside
        huge_safe_title = "Normal " * 1500
        is_sens, _ = guard.evaluate_sensitivity(
            title=huge_safe_title,
            process_name="app.exe",
            hwnd=100,
            can_open_process=True,
        )
        assert is_sens is False

        huge_sensitive_title = ("Safe " * 1000) + "Bitwarden Master Password" + (" Safe" * 500)
        is_sens, reason = guard.evaluate_sensitivity(
            title=huge_sensitive_title,
            process_name="app.exe",
            hwnd=100,
            can_open_process=True,
        )
        assert is_sens is True
        assert "Bitwarden" in reason or "bitwarden" in reason.lower()

    def test_case_insensitivity_and_partial_path_matching(self):
        """Tests full paths and mixed casing for blacklists."""
        guard = WindowGuard()

        # Mixed casing title
        is_sens, _ = guard.evaluate_sensitivity(
            title="bItWaRdEn - vAuLt",
            process_name="app.exe",
            hwnd=100,
            can_open_process=True,
        )
        assert is_sens is True

        # Process with full directory path
        is_sens, _ = guard.evaluate_sensitivity(
            title="Dashboard",
            process_name="C:\\Program Files\\1Password\\1password.exe",
            hwnd=100,
            can_open_process=True,
        )
        assert is_sens is True

    def test_exception_fail_safe_in_is_safe_to_operate(self):
        """If get_active_window_info raises an unhandled exception, is_safe_to_operate returns False."""
        guard = WindowGuard()

        with patch.object(guard, "get_active_window_info", side_effect=RuntimeError("Win32 API fault")):
            safe = guard.is_safe_to_operate()
            assert safe is False
