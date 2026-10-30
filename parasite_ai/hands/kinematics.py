"""
ParasiteAI - Biomechanical Kinematic Mouse Trajectory Engine.
Implements Fitts's Law duration scaling, Cubic Bezier curvature, Flash & Hogan
Minimum Jerk velocity profiles, physiological micro-jitter, and target overshoot.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class KinematicConfig:
    """Configuration parameters for human kinematic trajectory generation."""
    fitts_a: float = 0.16             # Perceptual/motor latency intercept in seconds
    fitts_b: float = 0.11             # Motor processing coefficient in seconds/bit
    target_width_px: float = 40.0     # Effective target width in pixels
    min_duration_s: float = 0.18      # Minimum trajectory duration clamp
    max_duration_s: float = 0.65      # Maximum trajectory duration clamp
    hz: int = 120                     # Interpolation sampling frequency (120Hz)
    arc_deviation_ratio: float = 0.14 # Maximum orthogonal Bezier deviation ratio
    jitter_amplitude_px: float = 1.2  # Baseline amplitude of physiological tremor
    jitter_freq_min_hz: float = 8.0    # Minimum physiological tremor frequency
    jitter_freq_max_hz: float = 12.0   # Maximum physiological tremor frequency
    enable_overshoot: bool = True      # Enable target overshoot on long sweeps
    overshoot_min_dist_px: float = 40.0 # Distance threshold to trigger overshoot
    overshoot_distance_min: float = 2.0 # Minimum overshoot past target in pixels
    overshoot_distance_max: float = 5.0 # Maximum overshoot past target in pixels
    corrective_hop_min_s: float = 0.040 # Minimum corrective hop duration (40ms)
    corrective_hop_max_s: float = 0.060 # Maximum corrective hop duration (60ms)


class KinematicsEngine:
    """Generates human-like cursor trajectories combining biomechanical principles."""

    def __init__(self, config: Optional[KinematicConfig] = None, seed: Optional[int] = None):
        self.config = config or KinematicConfig()
        self._rng = random.Random(seed)

    def calculate_fitts_duration(self, distance_px: float, speed_factor: float = 1.0) -> float:
        """
        Calculates movement duration according to Fitts's Law:
        T = a + b * log2(1 + D / W), clamped between min_duration and max_duration.
        """
        if distance_px <= 0.0:
            return 0.0
        raw_t = self.config.fitts_a + self.config.fitts_b * math.log2(
            1.0 + distance_px / self.config.target_width_px
        )
        scaled_t = raw_t * speed_factor
        return max(self.config.min_duration_s, min(self.config.max_duration_s, scaled_t))

    @staticmethod
    def minimum_jerk(s: float) -> float:
        """
        Flash & Hogan Minimum Jerk polynomial: tau(s) = 10s^3 - 15s^4 + 6s^5
        Guarantees zero velocity and acceleration at s=0 and s=1.
        """
        s_clamped = max(0.0, min(1.0, s))
        return s_clamped**3 * (10.0 + s_clamped * (-15.0 + 6.0 * s_clamped))

    @staticmethod
    def minimum_jerk_velocity(s: float) -> float:
        """First derivative of minimum jerk polynomial: d(tau)/ds = 30s^2(1-s)^2."""
        s_clamped = max(0.0, min(1.0, s))
        return 30.0 * (s_clamped**2) * ((1.0 - s_clamped)**2)

    @staticmethod
    def minimum_jerk_acceleration(s: float) -> float:
        """Second derivative of minimum jerk polynomial: d2(tau)/ds2 = 60s(1-s)(1-2s)."""
        s_clamped = max(0.0, min(1.0, s))
        return 60.0 * s_clamped * (1.0 - s_clamped) * (1.0 - 2.0 * s_clamped)

    @staticmethod
    def cubic_bezier_point(
        p0: Tuple[float, float],
        p1: Tuple[float, float],
        p2: Tuple[float, float],
        p3: Tuple[float, float],
        tau: float,
    ) -> Tuple[float, float]:
        """Evaluates parametric Cubic Bezier curve at parameter tau in [0, 1]."""
        u = 1.0 - tau
        tt = tau * tau
        uu = u * u
        u3 = uu * u
        t3 = tt * tau
        bx = u3 * p0[0] + 3.0 * uu * tau * p1[0] + 3.0 * u * tt * p2[0] + t3 * p3[0]
        by = u3 * p0[1] + 3.0 * uu * tau * p1[1] + 3.0 * u * tt * p2[1] + t3 * p3[1]
        return (bx, by)

    def generate_trajectory(
        self,
        start_pt: Tuple[int, int],
        target_pt: Tuple[int, int],
        duration: Optional[float] = None,
        speed_factor: float = 1.0,
        bounds: Optional[Tuple[int, int, int, int]] = None,
    ) -> List[Tuple[int, int]]:
        """
        Generates a 120Hz sequence of integer screen coordinates from start_pt to target_pt.
        Integrates Fitts's Law duration, Cubic Bezier curvature, Min-Jerk velocity profile,
        physiological tremor (8-12Hz) with sine boundary damping, and terminal overshoot micro-hop.
        Optionally clamps all waypoints to bounds (min_x, min_y, max_x, max_y).
        """
        if start_pt == target_pt:
            return [start_pt]

        dx = target_pt[0] - start_pt[0]
        dy = target_pt[1] - start_pt[1]
        dist = math.hypot(dx, dy)

        if dist < 1.0:
            return [start_pt, target_pt]

        total_duration = duration if duration is not None else self.calculate_fitts_duration(dist, speed_factor)

        # Check if overshoot is warranted
        if self.config.enable_overshoot and dist >= self.config.overshoot_min_dist_px:
            waypoints = self._generate_overshoot_trajectory(start_pt, target_pt, dist, total_duration, bounds=bounds)
        else:
            waypoints = self._generate_single_phase_trajectory(start_pt, target_pt, dist, total_duration)

        if bounds is not None:
            min_x, min_y, max_x, max_y = bounds
            waypoints = [
                (max(min_x, min(pt[0], max_x)), max(min_y, min(pt[1], max_y)))
                for pt in waypoints
            ]
            waypoints[0] = start_pt
            waypoints[-1] = target_pt

        return waypoints

    def _generate_single_phase_trajectory(
        self,
        p0: Tuple[int, int],
        p3: Tuple[int, int],
        dist: float,
        duration: float,
        jitter_scale: float = 1.0,
    ) -> List[Tuple[int, int]]:
        """Generates a single continuous ballistic phase with Cubic Bezier and micro-jitter."""
        steps = max(2, round(duration * self.config.hz))

        if dist < 1e-6:
            return [p0] * steps

        vx = p3[0] - p0[0]
        vy = p3[1] - p0[1]

        # Orthogonal unit normal: (-vy/dist, vx/dist)
        nx = -vy / dist
        ny = vx / dist

        # Stochastic arc deviation
        arc_amp = dist * self._rng.uniform(
            -self.config.arc_deviation_ratio, self.config.arc_deviation_ratio
        )

        # Asymmetric control points (elbow-lead curvature)
        p1 = (
            p0[0] + 0.32 * vx + arc_amp * nx,
            p0[1] + 0.32 * vy + arc_amp * ny,
        )
        p2 = (
            p0[0] + 0.68 * vx + 0.45 * arc_amp * nx,
            p0[1] + 0.68 * vy + 0.45 * arc_amp * ny,
        )

        # Tremor synthesis parameters
        fx = self._rng.uniform(self.config.jitter_freq_min_hz, self.config.jitter_freq_max_hz)
        fy = self._rng.uniform(self.config.jitter_freq_min_hz, self.config.jitter_freq_max_hz)
        phi_x = self._rng.uniform(0.0, 2.0 * math.pi)
        phi_y = self._rng.uniform(0.0, 2.0 * math.pi)
        amp_x = self.config.jitter_amplitude_px * jitter_scale * self._rng.uniform(0.7, 1.3)
        amp_y = self.config.jitter_amplitude_px * jitter_scale * self._rng.uniform(0.7, 1.3)

        waypoints: List[Tuple[int, int]] = []

        for i in range(steps):
            s = i / (steps - 1)
            t = s * duration

            # Spatial progress via Flash & Hogan Minimum Jerk
            tau = self.minimum_jerk(s)

            # Cubic Bezier spatial coordinates
            bx, by = self.cubic_bezier_point(
                (float(p0[0]), float(p0[1])),
                p1,
                p2,
                (float(p3[0]), float(p3[1])),
                tau,
            )

            # Physiological micro-jitter with sine boundary damping (guarantees damp=0 at s=0, 1)
            damp = math.sin(math.pi * s)
            jx = damp * (amp_x * math.sin(2.0 * math.pi * fx * t + phi_x) + self._rng.gauss(0.0, 0.2))
            jy = damp * (amp_y * math.cos(2.0 * math.pi * fy * t + phi_y) + self._rng.gauss(0.0, 0.2))

            pt = (round(bx + jx), round(by + jy))
            waypoints.append(pt)

        # Force exact boundary conditions
        waypoints[0] = p0
        waypoints[-1] = p3
        return waypoints

    def _generate_overshoot_trajectory(
        self,
        p0: Tuple[int, int],
        p_target: Tuple[int, int],
        dist: float,
        total_duration: float,
        bounds: Optional[Tuple[int, int, int, int]] = None,
    ) -> List[Tuple[int, int]]:
        """
        Decomposes reach into:
        Phase 1: Primary ballistic sweep to overshoot point (85% duration).
        Phase 2: Corrective micro-hop from overshoot point to exact target (15% duration, 40-60ms).
        """
        t2 = max(
            self.config.corrective_hop_min_s,
            min(self.config.corrective_hop_max_s, 0.15 * total_duration),
        )
        t1 = max(0.05, total_duration - t2)

        # Overshoot point along travel vector
        ux = (p_target[0] - p0[0]) / dist
        uy = (p_target[1] - p0[1]) / dist
        d_over = self._rng.uniform(
            self.config.overshoot_distance_min, self.config.overshoot_distance_max
        )

        p_over = (
            round(p_target[0] + d_over * ux),
            round(p_target[1] + d_over * uy),
        )

        if bounds is not None:
            min_x, min_y, max_x, max_y = bounds
            p_over = (
                max(min_x, min(p_over[0], max_x)),
                max(min_y, min(p_over[1], max_y)),
            )

        d_corr = math.hypot(p_target[0] - p_over[0], p_target[1] - p_over[1])
        if d_corr < 1.0:
            # Clamping prevented overshoot past target; smoothly fallback to single continuous phase
            return self._generate_single_phase_trajectory(p0, p_target, dist, total_duration)

        # Phase 1: Ballistic sweep to p_over
        phase1 = self._generate_single_phase_trajectory(p0, p_over, dist + d_over, t1, jitter_scale=1.0)

        # Phase 2: Corrective hop from p_over to p_target (subdued jitter)
        phase2 = self._generate_single_phase_trajectory(p_over, p_target, d_corr, t2, jitter_scale=0.35)

        # Stitch phases avoiding duplicate waypoint
        combined = phase1 + phase2[1:]
        combined[0] = p0
        combined[-1] = p_target
        return combined
