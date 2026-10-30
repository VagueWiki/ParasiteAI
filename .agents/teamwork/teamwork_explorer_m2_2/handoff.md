# Handoff Report: Milestone M2 — Kinematic Mouse Trajectory Engine

**Agent ID:** teamwork_explorer_m2_2  
**Recipient:** Orchestrator (`9a16f679-6db4-4849-ba56-0f4856cbbf9b`) / Worker (`teamwork_worker_m1` or designated M2 worker)  
**Date:** 2026-10-29  
**Status:** Hard Handoff (Investigation & Architecture Complete)  
**Artifact Path:** `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m2_2\plan.md`

---

## 1. Observation

Direct observations from inspection tools and empirical test executions on the host environment:

1. **Host Environment & Pytest Suite Baseline:**
   - Command: `uv run pytest`
   - Result: 189 passed in 17.14s. Python version: 3.12.13 (win32).
   - All Milestone M1 tests and adversarial stress tests pass cleanly without errors.

2. **Existing Configuration Contracts (`parasite_ai/config.py`):**
   - Lines 351–389: `MouseConfig` defines:
     - `speed_factor: float = Field(default=1.0, ge=0.1, le=5.0)`
     - `trajectory_type: Literal["cubic_bezier", "min_jerk", "linear"] = Field(default="cubic_bezier")`
     - `overshoot_radius_px: int = Field(default=12, ge=0, le=100)`
     - `micro_jitter_amplitude_px: float = Field(default=1.5, ge=0.0, le=10.0)`
     - `step_delay_ms: int = Field(default=8, ge=1, le=50)` (corresponds to 120Hz: $1000 / 8 \approx 125\text{Hz}$)
     - `preview_reticle_ms: int = Field(default=300, ge=0, le=2000)`
   - Lines 425–432: `HandsConfig` defines `mouse: MouseConfig = Field(default_factory=MouseConfig)`.

3. **Win32 Memory Layout Verification (Host Python 3.12 x64):**
   - Command executed:
     ```python
     ctypes.sizeof(MOUSEINPUT) == 32
     ctypes.sizeof(KEYBDINPUT) == 24
     ctypes.sizeof(HARDWAREINPUT) == 8
     ctypes.sizeof(_INPUT_UNION) == 32
     ctypes.sizeof(INPUT) == 40
     getattr(INPUT, '_u').offset == 8
     ```
   - Result: `INPUT` is exactly 40 bytes on 64-bit Windows, with a mandatory 4-byte padding aligning `_u` at offset 8. Any structure omitting this padding corrupts `SendInput` execution with error `87` (`ERROR_INVALID_PARAMETER`).

4. **Multi-Monitor Display Topology (`user32.GetSystemMetrics`):**
   - Command executed:
     - `SM_CXSCREEN = 1920, SM_CYSCREEN = 1080` (Primary display).
     - `SM_XVIRTUALSCREEN = 0, SM_YVIRTUALSCREEN = 0, SM_CXVIRTUALSCREEN = 3840, SM_CYVIRTUALSCREEN = 1080` (Virtual multi-monitor desktop).
   - Result: Coordinate normalization for `SendInput` must account for `SM_CXVIRTUALSCREEN` and `SM_CYVIRTUALSCREEN` combined with `MOUSEEVENTF_VIRTUALDESK | MOUSEEVENTF_ABSOLUTE` to correctly span multiple monitors.

5. **Empirical Scheduler & Event Latency Benchmarks:**
   - Command executed: 120Hz wait loop benchmark using `ctypes.windll.winmm.timeBeginPeriod(1)` and `threading.Event.wait(0.008333)`.
     - Result: Mean step interval is **9.55 ms** ($\approx 105 - 120\text{Hz}$).
   - Command executed: Cross-thread interrupt unblock latency test.
     - Result: Latencies recorded: `[0.0752, 0.0549, 0.0521, 0.0629, 0.0706]` ms. Maximum measured latency: **0.0752 ms**. This provides a 26x safety margin below the 2.0 ms interrupt budget.

6. **Mathematical Model Validation:**
   - Flash & Hogan Minimum Jerk polynomial $\tau(s) = 10s^3 - 15s^4 + 6s^5$:
     - $s=0.0 \implies \tau=0.0000, \dot{\tau}=0.0000, \ddot{\tau}=0.0000$
     - $s=0.5 \implies \tau=0.5000, \dot{\tau}=1.8750, \ddot{\tau}=0.0000$
     - $s=1.0 \implies \tau=1.0000, \dot{\tau}=0.0000, \ddot{\tau}=0.0000$
   - Physiological Micro-Jitter Boundary Damping $\text{Damp}(s) = \sin(\pi s)$:
     - Evaluated to $0.0$ at $s=0.0$ and $< 10^{-16}$ at $s=1.0$, guaranteeing drift-free arrival at the exact integer target coordinate.
   - Empirical Trajectory Generation from $(100, 100)$ to $(800, 600)$:
     - Trajectory generated 78 waypoints at 120Hz over 0.64s.
     - Max single-step jump: $23.35\text{ px}$. Mean step jump: $11.46\text{ px}$. Start: $(100, 100)$, End: $(800, 600)$. Overshoot: $4.53\text{ px}$ along vector of travel with subsequent corrective deceleration.

---

## 2. Logic Chain

1. **From Acceptance Criteria R3 & Survey 2 to Mathematical Architecture:**
   - R3 requires non-linear human movement avoiding straight lines, instant jumps, and rigid velocities.
   - Survey 2 established that human reaching is governed by three biological laws: Fitts's Law (duration scaling), Minimum Jerk ( Flash & Hogan velocity profile), and physiological neuromuscular tremor (8–12Hz).
   - Therefore, a multi-stage pipeline is mathematically necessary:
     - Fitts's Law computes movement duration $T = a + b \log_2(1 + D/W)$ clamped to $[0.18, 0.65]\text{s}$.
     - Asymmetric Cubic Bézier curve ($P_1 = P_0 + 0.32\vec{V} + A\hat{n}$, $P_2 = P_0 + 0.68\vec{V} + 0.45A\hat{n}$) generates natural wrist/elbow curvature.
     - Flash & Hogan polynomial maps normalized time to displacement, enforcing zero initial and final velocity and acceleration.
     - Sine-damped micro-jitter adds tremor while mathematically preserving exact endpoints ($\sin(0) = \sin(\pi) = 0$).
     - For $D > 40\text{px}$, decomposing the path into a primary ballistic sweep ($85\% T$) with $2-5\text{px}$ overshoot and a secondary corrective micro-hop ($15\% T$, $40-60\text{ms}$) reflects human closed-loop motor control.

2. **From Latency Budget to Win32 Driver Architecture:**
   - Requirement demands `< 2ms` abort upon physical hardware touch.
   - Windows default timers tick at $15.625\text{ms}$, and standard `time.sleep` blocks asynchronously without early wakeup.
   - Enabling `timeBeginPeriod(1)` reduces kernel scheduler resolution to $1.0\text{ms}$.
   - Using `cancellation_token.wait(timeout=step_interval)` uses OS `WaitForSingleObject`. When `cancellation_token.set()` is invoked by the hook thread on physical touch, the OS instantly wakes the thread in $\approx 0.075\text{ms}$, allowing the loop to break, release any held buttons, and abort before the next coordinate is injected.

3. **From Ghost-Hand HUD to Reticle Hook:**
   - R2 and R3 demand a 300ms pre-click reticle preview.
   - Integrating `reticle_callback(x, y, 300)` before moving or clicking and waiting with `cancellation_token.wait(timeout=0.300)` ensures that if the user touches their mouse during the preview, the action aborts before any cursor movement occurs.

4. **From CI/CD Testability to Simulation Mode:**
   - Tests in automated environments (`uv run pytest`) must not move the tester's physical cursor across the screen.
   - Implementing `simulation_mode=True` allows the driver to track virtual cursor positions and log emitted events into an audit log (`simulation_history`), enabling deterministic, fast, headless unit tests.

---

## 3. Caveats

1. **Hardware Hook Interoperability:**
   - `MouseDriver` relies on a `cancellation_token` (`threading.Event`) provided by `InterruptGuard`. In unit testing of `mouse.py`, an independent `threading.Event` is used to simulate cancellation. Full integration with low-level hooks (`WH_MOUSE_LL`) will occur when `InterruptGuard` is instantiated.
2. **Multi-Monitor DPI Scaling:**
   - Windows DPI scaling settings can cause physical pixel coordinates to diverge from logical desktop coordinates if the application process is DPI-unaware. In Milestone M5, `ctypes.windll.shcore.SetProcessDpiAwareness(2)` (Per-Monitor v2) must be called at application startup.
3. **No Direct Production Code Written:**
   - Per explorer role constraints, all code specifications, classes, algorithms, and test suites are provided as design specifications in `plan.md` and this report without modifying the production source tree.

---

## 4. Conclusion

The kinematic and mouse driver specifications are complete, mathematically verified, empirically benchmarked, and ready for immediate implementation by the Worker:
1. `parasite_ai/hands/kinematics.py`: `KinematicConfig` and `KinematicsEngine` providing Fitts's Law duration, Cubic Bézier curvature, Flash & Hogan minimum jerk easing, 8–12Hz micro-jitter with sine boundary damping, and target overshoot.
2. `parasite_ai/hands/mouse.py`: `MouseDriver` providing 120Hz high-resolution scheduler integration (`timeBeginPeriod(1)`), instant interrupt abort (< 2ms), pre-click reticle preview (300ms), Win32 `SendInput` actions, fail-safe button release, and headless simulation mode.
3. Complete test specifications defined in `tests/test_kinematics.py` (10 tests) and `tests/test_mouse_driver.py` (10 tests).

---

## 5. Verification Method

Once implemented by the Worker, the subsystem can be independently verified using the following commands and assertions:

1. **Execute Kinematics and Mouse Driver Test Suites:**
   ```powershell
   uv run pytest tests/test_kinematics.py tests/test_mouse_driver.py -v
   ```
   - Invalidation condition: Any test failure, single-step coordinate jump $> 30\text{px}$, endpoint mismatch $\ne P_3$, or interrupt abort latency $\ge 2.0\text{ms}$.

2. **Execute Full Suite Regression:**
   ```powershell
   uv run pytest
   ```
   - Invalidation condition: Any regression in the existing 189 passing tests.

3. **Verify Memory Structure Alignment:**
   ```powershell
   uv run python -c "import ctypes; from parasite_ai.hands.mouse import INPUT; assert ctypes.sizeof(INPUT) == 40"
   ```
   - Invalidation condition: `ctypes.sizeof(INPUT) != 40`.
