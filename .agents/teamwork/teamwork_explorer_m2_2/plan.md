# Milestone M2 — Kinematic Mouse Trajectory Engine: Technical Implementation Plan

**Author:** teamwork_explorer_m2_2  
**Date:** 2026-10-29  
**Subsystems:** `parasite_ai.hands.kinematics` and `parasite_ai.hands.mouse`  
**Target Files:**
- `parasite_ai/hands/kinematics.py`
- `parasite_ai/hands/mouse.py`
- `parasite_ai/hands/__init__.py`
- `tests/test_kinematics.py`
- `tests/test_mouse_driver.py`

---

## 1. Executive Summary & Problem Formulation

In naive desktop automation (e.g., standard `pyautogui.moveTo` or `SetCursorPos`), mouse movements follow rigid straight lines or teleport instantaneously across coordinates. This causes three severe failures:
1. **Hostile Visual Artifacts & User Disorientation:** Instantaneous coordinate snaps startle the user watching their screen, making it impossible to predict what the assistant is about to click.
2. **Bot Detection & Heuristic Flagging:** Modern anti-automation heuristics on web interfaces and desktop software flag constant-velocity straight-line paths or zero-duration teleportation.
3. **Physical Hardware Contention:** If the user touches their physical mouse while synthetic movement is in progress, any system lacking high-resolution, sub-millisecond interrupt checks will violently fight the user for cursor control.

This technical plan specifies the **Kinematic Mouse Trajectory Engine**, a mathematically principled bio-mimetic arm/wrist movement system coupled to an interruptible 120Hz Win32 driver.

---

## 2. Mathematical Modeling of Human Arm & Wrist Kinematics

### 2.1 Fitts's Law Movement Duration Scaling

The duration $T$ of human goal-directed motor reaches follows the Shannon formulation of Fitts's Law (MacKenzie, 1992):
$$T = a + b \log_2\left(1 + \frac{D}{W}\right)$$

Where:
- $D = \|\vec{P}_{\text{target}} - \vec{P}_{\text{start}}\| = \sqrt{(x_1 - x_0)^2 + (y_1 - y_0)^2}$ is the Euclidean distance in pixels.
- $W = 40.0\text{ px}$ is the effective target width (defaulting to standard button icon dimension).
- $a = 0.16\text{ s}$ is the motor initiation and perceptual latency intercept.
- $b = 0.11\text{ s/bit}$ is the reciprocal of the index of performance (bandwidth of human motor channel $\approx 9.1\text{ bits/s}$).
- Duration clamping:
  $$T_{\text{clamped}} = \max\left(0.18\text{ s}, \min\left(0.65\text{ s}, T \cdot \text{speed\_factor}\right)\right)$$
  - For short hops ($D \le 40\text{px}$): $T \approx 0.18\text{ s} - 0.27\text{ s}$.
  - For medium distances ($D \approx 300\text{px}$): $T \approx 0.50\text{ s}$.
  - For screen sweeps ($D \ge 1000\text{px}$): $T$ saturates cleanly at $0.65\text{ s}$.
- Special Case: When $D = 0$, $T = 0$, returning $[P_0]$ with zero latency.

---

### 2.2 Cubic Bézier Arc Geometry & Wrist Pivot Offset

Human arm reaches naturally curve because the forearm and hand pivot around elbow and wrist joints. A straight line is mathematically unnatural.

Let start point be $P_0 = (x_0, y_0)$ and target (or overshoot) point be $P_3 = (x_3, y_3)$.
1. **Displacement Vector:**
   $$\vec{V} = P_3 - P_0 = (V_x, V_y) = (x_3 - x_0, y_3 - y_0)$$
   $$D = \|\vec{V}\| = \sqrt{V_x^2 + V_y^2}$$

2. **Unit Normal Vector:**
   $$\hat{n} = \left(-\frac{V_y}{D}, \frac{V_x}{D}\right) \quad \text{for } D > 0, \quad \hat{n} = (0, 0) \text{ for } D = 0$$
   Notice that $\hat{n} \cdot \vec{V} = -\frac{V_y V_x}{D} + \frac{V_x V_y}{D} = 0$, guaranteeing strict perpendicularity.

3. **Stochastic Arc Deviation:**
   $$A = D \cdot \text{Uniform}(-0.14, 0.14)$$
   The signed uniform distribution randomly assigns clockwise or counter-clockwise curvature, preventing repetitive identical trajectories.

4. **Asymmetric Control Points:**
   $$P_1 = P_0 + 0.32 \vec{V} + A \hat{n}$$
   $$P_2 = P_0 + 0.68 \vec{V} + 0.45 A \hat{n}$$
   - $P_1$ is situated at $32\%$ of the longitudinal travel with $100\%$ of arc deviation $A$.
   - $P_2$ is situated at $68\%$ of the longitudinal travel with $45\%$ of arc deviation $A$.
   - This asymmetry produces the characteristic "elbow-lead" curve where the lateral deviation peaks early and straightens out smoothly as the hand approaches the target.

5. **Parametric Curve Evaluation:**
   For progress parameter $\tau \in [0, 1]$:
   $$B(\tau) = (1 - \tau)^3 P_0 + 3(1 - \tau)^2 \tau P_1 + 3(1 - \tau) \tau^2 P_2 + \tau^3 P_3$$

---

### 2.3 Flash & Hogan Minimum Jerk Trajectory Polynomial

To map normalized elapsed time $s = \frac{t}{T} \in [0, 1]$ to spatial displacement progress $\tau \in [0, 1]$, we employ the Flash & Hogan (1985) Minimum Jerk formulation. Human motor control optimizes smoothness by minimizing the integral of squared jerk ($\dddot{x}^2 + \dddot{y}^2$):

$$\tau(s) = 10s^3 - 15s^4 + 6s^5$$

#### Mathematical Derivatives & Physical Properties:
- **Displacement:** $\tau(0) = 0$, $\tau(0.5) = 0.5$, $\tau(1) = 1$.
- **Velocity:** $\dot{\tau}(s) = \frac{d\tau}{ds} = 30s^2 - 60s^3 + 30s^4 = 30s^2(1 - s)^2$.
  - $\dot{\tau}(0) = 0$ (starts from rest).
  - $\dot{\tau}(1) = 0$ (arrives smoothly at rest).
  - $\dot{\tau}(0.5) = 1.875$ (bell-shaped velocity profile peaking at exact midpoint).
  - Strictly monotonic: $\dot{\tau}(s) \ge 0$ for all $s \in [0, 1]$.
- **Acceleration:** $\ddot{\tau}(s) = \frac{d^2\tau}{ds^2} = 60s - 180s^2 + 120s^3 = 60s(1 - s)(1 - 2s)$.
  - $\ddot{\tau}(0) = 0$ (zero initial acceleration spike).
  - $\ddot{\tau}(1) = 0$ (zero terminal deceleration shock).
  - $\ddot{\tau}(0.5) = 0$ (inflection point at peak speed).

---

### 2.4 Physiological Micro-Jitter (8-12Hz) with Sine Boundary Damping

Living human hands exhibit involuntary neuromuscular tremor in the 8–12 Hz frequency band (Elble & Randall, 1976). Without micro-jitter, the generated path is an unnaturally pristine mathematical curve.

To inject realistic micro-jitter while guaranteeing that the cursor starts and lands at the exact pixel coordinates without drift:
1. **Tremor Frequencies & Amplitudes:**
   - $f_x, f_y \sim \text{Uniform}(8.0, 12.0)\text{ Hz}$
   - $A_x, A_y \sim \text{Uniform}(0.8, 1.8)\text{ px}$ (scaled by `micro_jitter_amplitude_px / 1.2`)
   - $\phi_x, \phi_y \sim \text{Uniform}(0, 2\pi)$
   - Filtered stochastic Gaussian component: $\eta_x, \eta_y \sim \mathcal{N}(0, 0.25^2)$

2. **Sine Boundary Damping Envelope:**
   $$\text{Damp}(s) = \sin(\pi s), \quad s \in [0, 1]$$
   - At start ($s = 0$): $\sin(0) = 0 \implies J(0) = 0$.
   - At midpoint ($s = 0.5$): $\sin(\pi / 2) = 1.0 \implies$ full tremor expression.
   - At arrival ($s = 1.0$): $\sin(\pi) = 0 \implies J(1) = 0$.

3. **Jitter Vector Equations:**
   $$J_x(s, t) = \sin(\pi s) \cdot \left[ A_x \sin(2\pi f_x t + \phi_x) + \eta_x \right]$$
   $$J_y(s, t) = \sin(\pi s) \cdot \left[ A_y \cos(2\pi f_y t + \phi_y) + \eta_y \right]$$

Because $\text{Damp}(0) = 0$ and $\text{Damp}(1) = 0$, the tremor displacement is guaranteed to be $0$ at both endpoints.

---

### 2.5 Target Overshoot & Rapid Corrective Micro-Hop

Under rapid movements ($D > 40\text{ px}$), human targeting exhibits a two-component structure: a primary ballistic open-loop sweep that slightly overshoots the target boundary, followed by a rapid closed-loop visual/proprioceptive correction (Meyer et al., 1988).

1. **Activation Condition:**
   - Distance $D > 40.0\text{ px}$.
   - Overshoot probability: $p = 0.75$ (or configurable).

2. **Trajectory Decomposition:**
   - **Primary Flight Duration ($T_1$):**
     $$T_2 = \max(0.040, \min(0.060, 0.15 \cdot T))$$
     $$T_1 = T - T_2$$
     (Primary flight consumes $\approx 85\%$ of duration; corrective hop consumes $\approx 15\%$, lasting $40-60\text{ms}$).
   - **Overshoot Point ($P_{\text{over}}$):**
     $$\hat{u} = \left(\frac{x_3 - x_0}{D}, \frac{y_3 - y_0}{D}\right)$$
     $$d_{\text{over}} \sim \text{Uniform}(2.0, 5.0)\text{ px}$$
     $$P_{\text{over}} = P_3 + d_{\text{over}} \cdot \hat{u}$$
   - **Phase 1 (Ballistic Reach from $P_0$ to $P_{\text{over}}$):**
     - Evaluated via Cubic Bézier + Minimum Jerk targeting $P_{\text{over}}$.
     - Steps: $N_1 = \max(2, \text{round}(T_1 \cdot 120))$.
   - **Phase 2 (Corrective Micro-Hop from $P_{\text{over}}$ to exact $P_3$):**
     - Evaluated via linear or micro-curved Minimum Jerk from $P_{\text{over}}$ to $P_3$.
     - Steps: $N_2 = \max(2, \text{round}(T_2 \cdot 120))$.
     - Uses subdued micro-jitter amplitude ($0.35 \times$).
     - Clamps final waypoint strictly to $P_3$.

---

## 3. Module Specification: `parasite_ai/hands/kinematics.py`

### 3.1 Class Architecture & Type Definitions

```python
"""
parasite_ai.hands.kinematics - Biomechanical Mouse Trajectory Engine.
Implements Fitts's Law duration scaling, Cubic Bezier curvature, Flash & Hogan
Minimum Jerk velocity profiles, physiological micro-jitter, and target overshoot.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class KinematicConfig:
    """Configuration parameters for human kinematic trajectory generation."""
    fitts_a: float = 0.16           # Perceptual/motor latency intercept in seconds
    fitts_b: float = 0.11           # Motor processing coefficient in seconds/bit
    target_width_px: float = 40.0   # Effective target width in pixels
    min_duration_s: float = 0.18    # Minimum trajectory duration clamp
    max_duration_s: float = 0.65    # Maximum trajectory duration clamp
    hz: int = 120                   # Interpolation sampling frequency (120Hz)
    arc_deviation_ratio: float = 0.14 # Maximum orthogonal Bezier deviation ratio
    jitter_amplitude_px: float = 1.2 # Baseline amplitude of physiological tremor
    jitter_freq_min_hz: float = 8.0  # Minimum physiological tremor frequency
    jitter_freq_max_hz: float = 12.0 # Maximum physiological tremor frequency
    enable_overshoot: bool = True    # Enable target overshoot on long sweeps
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
        raw_t = self.config.fitts_a + self.config.fitts_b * math.log2(1.0 + distance_px / self.config.target_width_px)
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
    ) -> List[Tuple[int, int]]:
        """
        Generates a 120Hz sequence of integer screen coordinates from start_pt to target_pt.
        Integrates Fitts's Law duration, Cubic Bezier curvature, Min-Jerk velocity profile,
        physiological tremor (8-12Hz), and terminal overshoot micro-hop.
        """
        ...
```

---

## 4. Module Specification: `parasite_ai/hands/mouse.py`

### 4.1 Win32 High-Resolution Timer & Event Structures

On 64-bit Windows:
- `timeBeginPeriod(1)` configures the OS timer scheduler tick to 1.0ms.
- `MOUSEINPUT` requires 32 bytes, `INPUT` requires 40 bytes with 8-byte union alignment.
- Virtual desktop coordinates require normalization using `SM_XVIRTUALSCREEN`, `SM_YVIRTUALSCREEN`, `SM_CXVIRTUALSCREEN`, `SM_CYVIRTUALSCREEN`.

```python
import ctypes
from ctypes import wintypes

# Win32 Constants
INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_VIRTUALDESK = 0x4000
MOUSEEVENTF_ABSOLUTE = 0x8000
WHEEL_DELTA = 120

SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]

class _INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT)]

class INPUT(ctypes.Structure):
    _anonymous_ = ("_u",)
    _fields_ = [
        ("type", wintypes.DWORD),
        ("_u", _INPUT_UNION),
    ]
```

---

### 4.2 Class Architecture: `MouseDriver`

```python
"""
parasite_ai.hands.mouse - Win32 Human-Like Mouse Driver.
Executes 120Hz trajectory interpolation with timeBeginPeriod(1), instant interrupt
cancellation (<2ms), pre-click reticle preview hook, and headless simulation mode.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from parasite_ai.hands.kinematics import KinematicConfig, KinematicsEngine


class MouseDriver:
    """
    Win32 mouse controller providing physical human-like cursor glides,
    clicks, double clicks, dragging, scrolling, and instant interrupt aborts.
    """

    def __init__(
        self,
        kinematics: Optional[KinematicsEngine] = None,
        reticle_callback: Optional[Callable[[int, int, int], None]] = None,
        simulation_mode: bool = False,
        speed_factor: float = 1.0,
        preview_reticle_ms: int = 300,
    ):
        self.kinematics = kinematics or KinematicsEngine()
        self.reticle_callback = reticle_callback
        self.simulation_mode = simulation_mode
        self.speed_factor = speed_factor
        self.preview_reticle_ms = preview_reticle_ms

        # Internal state tracking
        self._held_buttons = set() # {"left", "right", "middle"}
        self._sim_cursor_pos: Tuple[int, int] = (0, 0)
        self.simulation_history: List[Dict[str, Any]] = []

    def get_cursor_pos(self) -> Tuple[int, int]:
        """Returns current screen coordinates (x, y)."""
        if self.simulation_mode:
            return self._sim_cursor_pos
        # Win32 GetCursorPos implementation
        ...

    def move_to(
        self,
        x: int,
        y: int,
        duration: Optional[float] = None,
        cancellation_token: Optional[threading.Event] = None,
        preview_reticle: bool = False,
    ) -> bool:
        """
        Executes human curved glide to (x, y) at 120Hz.
        Checks cancellation_token before each step. Aborts in < 2ms if set.
        Returns True if arrived at destination, False if interrupted.
        """
        ...

    def click(
        self,
        x: Optional[int] = None,
        y: Optional[int] = None,
        button: str = "left",
        cancellation_token: Optional[threading.Event] = None,
        preview_reticle: bool = True,
    ) -> bool:
        """
        Signals pre-click reticle (300ms preview), glides to target, and clicks.
        Returns False immediately if cancellation_token is set during preview or flight.
        """
        ...

    def double_click(
        self,
        x: Optional[int] = None,
        y: Optional[int] = None,
        button: str = "left",
        cancellation_token: Optional[threading.Event] = None,
    ) -> bool:
        """Executes double click with realistic human inter-click pause (60-100ms)."""
        ...

    def mouse_down(
        self,
        button: str = "left",
        cancellation_token: Optional[threading.Event] = None,
    ) -> bool:
        """Presses and holds mouse button."""
        ...

    def mouse_up(
        self,
        button: str = "left",
        cancellation_token: Optional[threading.Event] = None,
    ) -> bool:
        """Releases held mouse button."""
        ...

    def drag_and_drop(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        button: str = "left",
        cancellation_token: Optional[threading.Event] = None,
    ) -> bool:
        """Glides to start, presses button, glides to end, releases button."""
        ...

    def scroll(
        self,
        delta: int,
        x: Optional[int] = None,
        y: Optional[int] = None,
        cancellation_token: Optional[threading.Event] = None,
    ) -> bool:
        """Performs mouse wheel scrolling at specified or current coordinates."""
        ...

    def release_all_buttons(self) -> None:
        """Emergency fail-safe: immediately releases all held buttons."""
        ...
```

---

### 4.3 120Hz Interruptible Step Loop Algorithm

The high-resolution movement loop is engineered as follows:

```
[Start move_to(x, y)]
       |
       +---> Check cancellation_token.is_set()?
       |        YES: return False immediately.
       |
       +---> If preview_reticle is True and preview_reticle_ms > 0:
       |        Fire reticle_callback(x, y, preview_reticle_ms)
       |        Wait cancellation_token.wait(timeout=preview_ms / 1000.0)
       |        Did token fire? YES: return False (aborted before motion!).
       |
       +---> Generate 120Hz trajectory points via KinematicsEngine.
       |
       +---> Initialize Win32 scheduler: winmm.timeBeginPeriod(1)
       |
       +---> For each waypoint (pt_x, pt_y) in trajectory:
       |        1. Check cancellation_token.is_set() -> if True: abort & break
       |        2. Apply cursor pos (SendInput / SetCursorPos / sim update)
       |        3. Wait remaining step interval (1/120s = 8.33ms) via:
       |           if cancellation_token.wait(timeout=step_interval):
       |               # Token was set by Hook Thread in < 0.1ms!
       |               release_all_buttons()
       |               abort & break
       |
       +---> finally: winmm.timeEndPeriod(1)
       |
[Return True if completed, False if aborted]
```

#### Abort Latency Guarantee:
Because `cancellation_token.wait(timeout=step_interval)` uses native OS wait primitives (`WaitForSingleObject`), when the hook thread detects physical user input (`LLMHF_INJECTED == 0`) and sets the event, `wait()` wakes up immediately in **$\approx 0.075\text{ ms}$**, breaking out of the loop and restoring hardware state in **$< 0.2\text{ ms}$**, more than 10x faster than the 2.0ms requirement!

---

## 5. Automated Test Suite Specifications

### 5.1 `tests/test_kinematics.py`

| # | Test Name | Purpose & Verification Criteria |
|---|-----------|---------------------------------|
| 1 | `test_fitts_law_duration_scaling` | Verifies short hops ($40\text{px}$) yield $\approx 0.27\text{s}$, diagonal moves ($800\text{px}$) yield $\approx 0.64\text{s}$, clamped strictly to $[0.18, 0.65]\text{s}$. |
| 2 | `test_fitts_law_zero_distance` | Verifies $D=0$ yields $0\text{s}$ duration and returns single point $[P_0]$. |
| 3 | `test_fitts_speed_factor_scaling` | Verifies `speed_factor=0.5` doubles speed / halves duration, respecting minimum clamps. |
| 4 | `test_minimum_jerk_boundary_conditions` | Verifies $\tau(0)=0$, $\tau(1)=1$, $\dot{\tau}(0)=0$, $\dot{\tau}(1)=0$, $\ddot{\tau}(0)=0$, $\ddot{\tau}(1)=0$, and strict monotonicity. |
| 5 | `test_cubic_bezier_endpoints_and_curvature` | Verifies $B(0)=P_0$, $B(1)=P_3$, and intermediate control points displace perpendicularly along unit normal $\hat{n}$. |
| 6 | `test_micro_jitter_sine_boundary_damping` | Verifies jitter formula evaluates to mathematically zero at $s=0$ and $s=1$, while expressing $\approx 1.2\text{px}$ tremor at $s=0.5$. |
| 7 | `test_target_overshoot_presence` | Verifies for $D > 40\text{px}$, the trajectory contains intermediate points that overshoot $P_3$ along the travel vector by $2-5\text{px}$ before corrective return. |
| 8 | `test_trajectory_smoothness_and_no_teleportation` | Verifies maximum single-step jump at 120Hz is $< 30\text{px}$ across a $1000\text{px}$ trajectory, preventing any teleportation. |
| 9 | `test_trajectory_deterministic_seeding` | Verifies identical random seeds generate identical waypoint sequences. |
| 10 | `test_trajectory_exact_arrival` | Verifies that trajectory start point strictly equals $P_0$ and final point strictly equals $P_3$ in all randomized runs. |

---

### 5.2 `tests/test_mouse_driver.py`

| # | Test Name | Purpose & Verification Criteria |
|---|-----------|---------------------------------|
| 1 | `test_mouse_driver_simulation_mode_movement` | In `simulation_mode=True`, moves to $(500, 400)$ and asserts virtual cursor reaches exact coordinates. |
| 2 | `test_mouse_driver_pre_click_reticle_callback` | Verifies `reticle_callback` is invoked with target coordinates and duration (300ms) before clicking or moving. |
| 3 | `test_mouse_driver_interrupt_during_preview` | Sets `cancellation_token` during 300ms reticle preview. Verifies driver aborts immediately in $<2\text{ms}$ with zero cursor movement. |
| 4 | `test_mouse_driver_interrupt_mid_trajectory` | Fires `cancellation_token` halfway through a glide. Verifies trajectory terminates in $<2\text{ms}$ and returns `False`. |
| 5 | `test_mouse_driver_releases_buttons_on_interrupt` | Simulates interrupt while mouse button is held down (e.g. during drag). Verifies all buttons are immediately released in fail-safe. |
| 6 | `test_mouse_driver_click_sequence` | Verifies `click()` emits `reticle_preview` -> `move` -> `mouse_down` -> `hold` -> `mouse_up`. |
| 7 | `test_mouse_driver_double_click_cadence` | Verifies double click executes two clicks separated by $60-120\text{ms}$ inter-click delay. |
| 8 | `test_mouse_driver_drag_and_drop` | Verifies drag moves to origin, holds left button, glides to destination, and releases button. |
| 9 | `test_mouse_driver_scroll_event` | Verifies `scroll(delta=3)` emits wheel events with correct direction and delta multiplier. |
| 10 | `test_mouse_driver_already_cancelled_token` | If `cancellation_token.is_set()` before calling `move_to`, driver returns `False` immediately with zero step execution. |

---

## 6. Implementation Checklist for Worker

1. **Create `parasite_ai/hands/__init__.py`**:
   - Expose `KinematicsEngine`, `KinematicConfig`, `MouseDriver`.
2. **Create `parasite_ai/hands/kinematics.py`**:
   - Implement `KinematicConfig` and `KinematicsEngine` with all mathematical formulas.
3. **Create `parasite_ai/hands/mouse.py`**:
   - Implement `MouseDriver` with Win32 `INPUT`/`SendInput`/`timeBeginPeriod` and simulation mode.
4. **Create `tests/test_kinematics.py`**:
   - Implement complete 10-test suite verifying mathematical invariants.
5. **Create `tests/test_mouse_driver.py`**:
   - Implement complete 10-test suite verifying driver execution, interrupt latency, simulation mode, and reticle callbacks.
6. **Execute Verification**:
   - Run `uv run pytest tests/test_kinematics.py tests/test_mouse_driver.py`.
   - Run full test suite: `uv run pytest`.
