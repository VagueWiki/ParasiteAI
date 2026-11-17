"""
tests/unit/hands/test_human_mouse_kinematics.py - Stint P4.1 Unit Tests.

Verifies HumanCurve two-phase velocity ballistics, asymmetric sprint + terminal homing,
motor commitment hesitation (25-60ms) with sub-2ms cancellation preemption,
and stochastic click dwell hold duration (45ms +/- 10ms).
"""

from __future__ import annotations

import math
import threading
import time
import pytest

from parasite_ai.config import MouseConfig
from parasite_ai.hands.kinematics import KinematicConfig, KinematicsEngine
from parasite_ai.hands.mouse import MouseDriver


class TestHumanCurveTwoPhaseBallistics:
    """Verifies HumanCurve asymmetric Fitts's Law two-phase velocity profile."""

    def test_two_phase_velocity_profile_asymmetry(self) -> None:
        engine = KinematicsEngine(config=KinematicConfig(use_two_phase_ballistics=True))

        # Exact boundary conditions
        assert engine.two_phase_progress(0.0) == 0.0
        assert engine.two_phase_progress(1.0) == 1.0
        assert engine.two_phase_velocity(0.0) == 0.0
        assert engine.two_phase_velocity(1.0) == 0.0

        # Monotonicity and early acceleration peak (~35-42% of duration)
        steps = 100
        velocities = []
        prev = 0.0
        for i in range(1, steps + 1):
            s = i / steps
            prog = engine.two_phase_progress(s)
            assert prog >= prev
            prev = prog
            velocities.append((s, engine.two_phase_velocity(s)))

        peak_s, peak_v = max(velocities, key=lambda item: item[1])
        assert 0.30 <= peak_s <= 0.45, f"Expected early ballistic peak near 0.37, got s={peak_s}"
        assert peak_v > 1.875  # Faster ballistic sprint than symmetric min-jerk

        # Ballistic sprint covers ~80-85% of distance by s=0.60, leaving smooth homing tail
        prog_60 = engine.two_phase_progress(0.60)
        assert 0.78 <= prog_60 <= 0.90, f"Expected ~80-85% distance by s=0.60, got {prog_60:.3f}"

    def test_two_phase_trajectory_smoothness_and_bounds(self) -> None:
        engine = KinematicsEngine(
            config=KinematicConfig(use_two_phase_ballistics=True, enable_overshoot=True),
            seed=42,
        )
        p0 = (100, 100)
        p_target = (1100, 100)
        bounds = (0, 0, 1919, 1079)

        traj = engine.generate_trajectory(p0, p_target, bounds=bounds)
        assert traj[0] == p0
        assert traj[-1] == p_target
        assert len(traj) > 30

        max_step = max(
            math.hypot(traj[i][0] - traj[i - 1][0], traj[i][1] - traj[i - 1][1])
            for i in range(1, len(traj))
        )
        assert max_step < 35.0, f"Single-step jump {max_step:.2f}px exceeded smoothness budget"

        for x, y in traj:
            assert 0 <= x <= 1919
            assert 0 <= y <= 1079


class TestBiologicalMotorHesitationAndDwell:
    """Verifies pre-click motor hesitation (25-60ms), preemption, and stochastic dwell."""

    def test_motor_hesitation_pause_recorded_and_bounded(self) -> None:
        cfg = MouseConfig(
            step_delay_ms=1,
            preview_reticle_ms=0,
            enable_motor_hesitation=True,
            motor_hesitation_min_ms=25,
            motor_hesitation_max_ms=60,
        )
        driver = MouseDriver(config=cfg, simulation_mode=True, seed=7)

        ok = driver.click(500, 500, preview_reticle=False)
        assert ok is True

        hesitations = [e for e in driver.simulation_history if e["event"] == "motor_hesitation"]
        assert len(hesitations) == 1
        assert 25.0 <= hesitations[0]["duration_ms"] <= 60.0

        # Motor hesitation must occur AFTER move and BEFORE mouse_down
        events = [e["event"] for e in driver.simulation_history]
        assert events.index("motor_hesitation") < events.index("mouse_down")

    def test_motor_hesitation_sub_2ms_cancellation_preemption(self) -> None:
        cfg = MouseConfig(
            step_delay_ms=1,
            preview_reticle_ms=0,
            enable_motor_hesitation=True,
            motor_hesitation_min_ms=180,
            motor_hesitation_max_ms=200,
        )
        driver = MouseDriver(config=cfg, simulation_mode=True, seed=9)
        token = threading.Event()

        # Cancel 15ms after starting click from current position (no travel)
        cur_x, cur_y = driver.get_cursor_pos()

        def trigger_cancel() -> None:
            time.sleep(0.015)
            token.set()

        threading.Thread(target=trigger_cancel, daemon=True).start()

        t0 = time.perf_counter()
        ok = driver.click(cur_x, cur_y, cancellation_token=token, preview_reticle=False)
        elapsed = time.perf_counter() - t0

        assert ok is False
        assert elapsed < 0.080, f"Preemption during motor hesitation took too long: {elapsed:.3f}s"
        down_events = [e for e in driver.simulation_history if e["event"] == "mouse_down"]
        assert len(down_events) == 0, "mouse_down must NOT fire when cancelled during hesitation"

    def test_stochastic_dwell_duration_distribution(self) -> None:
        cfg = MouseConfig(
            step_delay_ms=1,
            preview_reticle_ms=0,
            enable_motor_hesitation=False,
            dwell_mean_ms=45,
            dwell_std_ms=10,
        )
        driver = MouseDriver(config=cfg, simulation_mode=True, seed=123)
        cur_x, cur_y = driver.get_cursor_pos()

        for _ in range(10):
            assert driver.click(cur_x, cur_y, preview_reticle=False) is True

        dwells = [e["duration_ms"] for e in driver.simulation_history if e["event"] == "dwell"]
        assert len(dwells) == 10
        assert all(20.0 <= d <= 85.0 for d in dwells)
        assert len(set(dwells)) > 1, "Dwell duration should vary stochastically around 45ms"

    def test_mouse_config_propagates_to_kinematics(self) -> None:
        cfg = MouseConfig(
            use_two_phase_ballistics=False,
            motor_hesitation_min_ms=30,
            motor_hesitation_max_ms=55,
            dwell_mean_ms=50,
            dwell_std_ms=8,
        )
        driver = MouseDriver(config=cfg, simulation_mode=True)
        assert driver.kinematics.config.use_two_phase_ballistics is False
        assert driver.kinematics.config.motor_hesitation_min_s == pytest.approx(0.030)
        assert driver.kinematics.config.motor_hesitation_max_s == pytest.approx(0.055)
        assert driver.kinematics.config.dwell_mean_s == pytest.approx(0.050)
        assert driver.kinematics.config.dwell_std_s == pytest.approx(0.008)
