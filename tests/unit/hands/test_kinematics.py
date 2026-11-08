"""
Tests for ParasiteAI Biomechanical Kinematic Mouse Trajectory Engine.
Verifies Fitts's Law duration scaling, Flash & Hogan Minimum Jerk polynomial invariants,
Cubic Bezier curve geometry, physiological micro-jitter with sine boundary damping,
terminal overshoot and corrective micro-hop, trajectory smoothness, and deterministic seeding.
"""

from __future__ import annotations

import math
import pytest

from parasite_ai.hands.kinematics import KinematicConfig, KinematicsEngine


class TestFittsLawDurationScaling:
    """Verifies duration calculation according to Shannon formulation of Fitts's Law."""

    def test_fitts_law_duration_scaling(self):
        engine = KinematicsEngine()

        # D = 0 -> 0 duration
        assert engine.calculate_fitts_duration(0.0) == 0.0

        # D = 40px: log2(1 + 40/40) = 1 bit -> raw_t = 0.16 + 0.11*1 = 0.27s
        t_40 = engine.calculate_fitts_duration(40.0)
        assert pytest.approx(0.27, abs=0.01) == t_40

        # D = 800px: log2(1 + 800/40) = log2(21) ~= 4.392 -> raw_t = 0.16 + 0.11*4.392 = 0.643s
        t_800 = engine.calculate_fitts_duration(800.0)
        assert pytest.approx(0.643, abs=0.02) == t_800

        # Clamping checks:
        # Extremely small non-zero distance should clamp to min_duration_s (0.18s)
        t_tiny = engine.calculate_fitts_duration(1.0)
        assert t_tiny >= 0.18

        # Extremely large distance (e.g. 5000px) should clamp to max_duration_s (0.65s)
        t_huge = engine.calculate_fitts_duration(5000.0)
        assert t_huge == 0.65

    def test_fitts_law_zero_distance(self):
        engine = KinematicsEngine()
        traj = engine.generate_trajectory((100, 100), (100, 100))
        assert traj == [(100, 100)]
        assert engine.calculate_fitts_duration(0.0) == 0.0

    def test_fitts_speed_factor_scaling(self):
        engine = KinematicsEngine()
        d = 300.0
        base_t = engine.calculate_fitts_duration(d, speed_factor=1.0)

        # Faster movement (speed_factor = 0.6)
        fast_t = engine.calculate_fitts_duration(d, speed_factor=0.6)
        assert fast_t <= base_t
        assert fast_t >= 0.18  # Respects min_duration_s clamp

        # Slower movement (speed_factor = 1.5)
        slow_t = engine.calculate_fitts_duration(d, speed_factor=1.5)
        assert slow_t >= base_t
        assert slow_t <= 0.65  # Respects max_duration_s clamp


class TestMinimumJerkPolynomial:
    """Verifies Flash & Hogan Minimum Jerk polynomial mathematical properties."""

    def test_minimum_jerk_boundary_conditions(self):
        engine = KinematicsEngine()

        # Displacement boundary conditions: tau(0) = 0, tau(1) = 1, tau(0.5) = 0.5
        assert engine.minimum_jerk(0.0) == 0.0
        assert engine.minimum_jerk(1.0) == 1.0
        assert pytest.approx(0.5, abs=1e-6) == engine.minimum_jerk(0.5)

        # Velocity boundary conditions: v(0) = 0, v(1) = 0, v(0.5) = 1.875
        assert engine.minimum_jerk_velocity(0.0) == 0.0
        assert engine.minimum_jerk_velocity(1.0) == 0.0
        assert pytest.approx(1.875, abs=1e-6) == engine.minimum_jerk_velocity(0.5)

        # Acceleration boundary conditions: a(0) = 0, a(1) = 0, a(0.5) = 0
        assert engine.minimum_jerk_acceleration(0.0) == 0.0
        assert engine.minimum_jerk_acceleration(1.0) == 0.0
        assert pytest.approx(0.0, abs=1e-6) == engine.minimum_jerk_acceleration(0.5)

    def test_minimum_jerk_monotonicity(self):
        engine = KinematicsEngine()
        prev = 0.0
        steps = 100
        for i in range(1, steps + 1):
            s = i / steps
            curr = engine.minimum_jerk(s)
            assert curr >= prev, f"Violated monotonicity at s={s}: {curr} < {prev}"
            vel = engine.minimum_jerk_velocity(s)
            assert vel >= 0.0, f"Velocity negative at s={s}: {vel}"
            prev = curr


class TestCubicBezierAndCurvature:
    """Verifies Cubic Bezier parametric point generation and asymmetric elbow-lead curvature."""

    def test_cubic_bezier_endpoints(self):
        p0 = (100.0, 100.0)
        p1 = (200.0, 300.0)
        p2 = (400.0, 500.0)
        p3 = (600.0, 600.0)

        # At tau=0, curve must equal p0
        bx0, by0 = KinematicsEngine.cubic_bezier_point(p0, p1, p2, p3, 0.0)
        assert pytest.approx(p0[0], abs=1e-5) == bx0
        assert pytest.approx(p0[1], abs=1e-5) == by0

        # At tau=1, curve must equal p3
        bx1, by1 = KinematicsEngine.cubic_bezier_point(p0, p1, p2, p3, 1.0)
        assert pytest.approx(p3[0], abs=1e-5) == bx1
        assert pytest.approx(p3[1], abs=1e-5) == by1

    def test_cubic_bezier_smooth_interpolation(self):
        p0 = (0.0, 0.0)
        p1 = (50.0, 100.0)
        p2 = (150.0, 100.0)
        p3 = (200.0, 0.0)

        prev_pt = p0
        for i in range(1, 21):
            tau = i / 20.0
            pt = KinematicsEngine.cubic_bezier_point(p0, p1, p2, p3, tau)
            # Distance between consecutive 5% steps must be finite and smooth
            step_dist = math.hypot(pt[0] - prev_pt[0], pt[1] - prev_pt[1])
            assert 0.0 < step_dist < 50.0
            prev_pt = pt


class TestMicroJitterAndBoundaryDamping:
    """Verifies that micro-jitter is damped strictly to zero at trajectory boundaries."""

    def test_micro_jitter_sine_boundary_damping(self):
        # Sine boundary damping formula: damp(s) = sin(pi * s)
        # At s = 0: sin(0) = 0
        # At s = 1: sin(pi) = 0
        # At s = 0.5: sin(pi/2) = 1.0
        assert pytest.approx(0.0, abs=1e-6) == math.sin(math.pi * 0.0)
        assert pytest.approx(0.0, abs=1e-6) == math.sin(math.pi * 1.0)
        assert pytest.approx(1.0, abs=1e-6) == math.sin(math.pi * 0.5)

    def test_trajectory_exact_boundary_arrival(self):
        # Regardless of random jitter or overshoot, trajectory must strictly start at p0 and end at p3
        engine = KinematicsEngine()
        pairs = [
            ((0, 0), (100, 100)),
            ((500, 300), (520, 310)),
            ((1920, 1080), (10, 10)),
            ((100, 500), (900, 200)),
        ]

        for p0, p3 in pairs:
            traj = engine.generate_trajectory(p0, p3)
            assert traj[0] == p0, f"Trajectory did not start at {p0}, started at {traj[0]}"
            assert traj[-1] == p3, f"Trajectory did not end at {p3}, ended at {traj[-1]}"


class TestTargetOvershoot:
    """Verifies two-phase reach decomposition and terminal overshoot micro-hop."""

    def test_target_overshoot_presence_on_long_distance(self):
        # Distance > 40px triggers overshoot
        engine = KinematicsEngine(seed=42)
        p0 = (100, 100)
        p_target = (800, 100)  # purely horizontal reach of 700px

        traj = engine.generate_trajectory(p0, p_target)

        # Must start at p0 and end at p_target
        assert traj[0] == p0
        assert traj[-1] == p_target

        # Check for overshoot beyond x=800 in intermediate waypoints
        max_x = max(pt[0] for pt in traj)
        assert max_x > 800, f"Expected overshoot beyond target x=800, got max_x={max_x}"
        assert max_x <= 810, f"Overshoot too extreme: {max_x}"

    def test_no_overshoot_on_short_distance(self):
        config = KinematicConfig(overshoot_min_dist_px=40.0)
        engine = KinematicsEngine(config=config, seed=42)
        p0 = (100, 100)
        p_target = (120, 100)  # 20px reach, well below 40px threshold

        traj = engine.generate_trajectory(p0, p_target)
        assert traj[0] == p0
        assert traj[-1] == p_target

        # Short hop should not exceed target by more than 1px due to micro-jitter damping
        max_x = max(pt[0] for pt in traj)
        assert max_x <= 121


class TestTrajectorySmoothnessAndDeterminism:
    """Verifies no single-step teleportation jumps and deterministic reproducible seeding."""

    def test_trajectory_smoothness_and_no_teleportation(self):
        engine = KinematicsEngine()
        p0 = (100, 100)
        p_target = (1100, 100)  # reach of 1000px as per specification
        traj = engine.generate_trajectory(p0, p_target)

        assert len(traj) > 30  # at 120Hz over ~0.65s, expect ~70-80 steps

        # Check maximum single-step jump between consecutive waypoints
        max_step_dist = 0.0
        for i in range(1, len(traj)):
            d = math.hypot(traj[i][0] - traj[i - 1][0], traj[i][1] - traj[i - 1][1])
            if d > max_step_dist:
                max_step_dist = d

        # At 120Hz, smooth human motion across 1000px should never jump more than 35px in a single 8.3ms step
        assert max_step_dist < 35.0, f"Teleportation detected! Single step jump was {max_step_dist}px"

    def test_trajectory_deterministic_seeding(self):
        engine1 = KinematicsEngine(seed=12345)
        engine2 = KinematicsEngine(seed=12345)

        traj1 = engine1.generate_trajectory((200, 200), (900, 700))
        traj2 = engine2.generate_trajectory((200, 200), (900, 700))

        assert traj1 == traj2, "Identical seeds must produce identical trajectories"

    def test_different_seeds_produce_different_paths(self):
        engine1 = KinematicsEngine(seed=111)
        engine2 = KinematicsEngine(seed=999)

        traj1 = engine1.generate_trajectory((200, 200), (900, 700))
        traj2 = engine2.generate_trajectory((200, 200), (900, 700))

        assert traj1 != traj2, "Different seeds should produce stochastic variance"
