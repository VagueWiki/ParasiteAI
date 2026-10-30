# Milestone M3 Code Review & Adversarial Stress Report (Reviewer 2)

**Agent**: `teamwork_reviewer_m3_2`  
**Roles**: Reviewer, Adversarial Critic  
**Working Directory**: `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_reviewer_m3_2\`  
**Milestone**: Milestone M3 — Desktop Companion Dock & Ghost-Hand Overlay  
**Handoff Type**: Hard (Gate Evaluation Complete)  
**Date**: 2026-10-29  

---

## Review Summary

**Verdict**: **APPROVE**  
**Integrity Attestation**: **PASSED** (Zero integrity violations; genuine implementation without dummy facades, test result hardcoding, or bypassed functionality).  
**Overall Risk Assessment**: **LOW**

---

## 1. Observation

1. **Win32 Layered Window Style Helper (`parasite_ai/ui/win32_styles.py`)**:
   - Lines 18-37: Win32 constants `GWL_EXSTYLE (-20)`, `WS_EX_LAYERED (0x00080000)`, `WS_EX_TRANSPARENT (0x00000020)`, `WS_EX_TOPMOST (0x00000008)`, `WS_EX_NOACTIVATE (0x08000000)`, and `WS_EX_TOOLWINDOW (0x00000080)` combined into `REQUIRED_HUD_EX_STYLES`.
   - Lines 48-61: Platform check `sys.platform != "win32"` and headless CI guard `user32.IsWindow(hwnd)` preventing `ERROR_INVALID_WINDOW_HANDLE (1400)` under offscreen QPA.
   - Lines 63-76: Preserves existing styles via bitwise OR (`current_style | REQUIRED_HUD_EX_STYLES`) and enforces topmost z-order via `SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_FRAMECHANGED)`.

2. **High-DPI Awareness Bootstrapper (`parasite_ai/ui/dpi.py`)**:
   - Lines 26-44: Tier 1 Per-Monitor v2 bootstrap via `user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))`. Idempotently handles `ERROR_ACCESS_DENIED (5)`.
   - Lines 46-58: Tier 2 Per-Monitor fallback via `shcore.SetProcessDpiAwareness(2)`. Handles `S_OK (0)` and `E_ACCESSDENIED (0x80070005)`.
   - Lines 60-67: Tier 3 Vista fallback via `user32.SetProcessDPIAware()`.

3. **Ghost-Hand HUD Overlay (`parasite_ai/ui/ghost_hud.py`)**:
   - Lines 162-180: Window flags configured with `FramelessWindowHint | WindowStaysOnTopHint | Tool`, translucent background, and transparent for mouse events (`WA_TransparentForMouseEvents`, `WA_ShowWithoutActivating`). Spans `screen.virtualGeometry()` and connects to `screen.virtualGeometryChanged`.
   - Lines 298-338: `_normalize_target` normalizes both dictionary representations and `UIElement` models, mapping roles (`button`, `edit`, `ocr`, `hyperlink`) to distinct color palettes in `ROLE_COLOR_MAP`.
   - Lines 362-408: Set-of-Mark drawing renders rounded bounding boxes with semi-transparent fill (`box_alpha`), dark slate pill badges (`#111827`, 90% opacity), 14-character truncated labels with ellipses, and desktop boundary clamping for top and right screen edges.
   - Lines 409-464: 300ms pre-click reticle draws dynamic curved Bézier trajectory preview matching `KinematicsEngine` with asymmetric elbow-lead control points (`0.32 * dx + arc_amp * nx`, `0.68 * dx + 0.45 * arc_amp * nx`) and traveling pulse orb evaluated via Bernstein degree-3 polynomial.
   - Lines 465-511: Targeting reticle animates 4 corner brackets contracting from 32px to 16px radius, pulsing outer halo, center crosshair ticks, and center dot.
   - Lines 512-547: Aiming banner displays `Aiming: [#ID] Label (remaining_ms)` flipping below the target if near the top edge.
   - Lines 245-258: `abort_reticle()` halts animation timer and clears state immediately upon panic or physical input interrupt.

4. **Test Suite Execution Results**:
   - Targeted command:
     ```powershell
     uv run pytest tests/test_ghost_hud.py tests/test_dpi.py -v
     ```
     Verbatim result: `20 passed in 0.68s`
   - Full regression test command:
     ```powershell
     uv run pytest -v
     ```
     Verbatim result: `365 passed in 22.38s` (Zero failures, zero errors, zero regressions).

---

## 2. Logic Chain

1. **Verification of Win32 Style Configuration & CI Safety**:
   - *Observation 1*: `win32_styles.py` combines `WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW` and guards execution with `user32.IsWindow(hwnd)`.
   - *Logic*: `WS_EX_TRANSPARENT` satisfies R2 by making the overlay click-through so user actions fall through to underlying windows. `WS_EX_NOACTIVATE` guarantees the overlay never steals input focus. The `user32.IsWindow(hwnd)` check ensures that running under `QT_QPA_PLATFORM=offscreen` during automated CI tests degrades gracefully without raising Win32 error 1400. This is confirmed by unit tests `test_win32_extended_window_styles_mocked` and `test_win32_extended_styles_invalid_window_handled`.

2. **Verification of High-DPI Awareness**:
   - *Observation 2*: `dpi.py` follows Microsoft's 3-tier precedence hierarchy and catches access-denied errors.
   - *Logic*: Per-Monitor v2 ensures 1:1 pixel coordinate parity between physical desktop pixels, Win32 UI Automation coordinates, and Qt overlay geometries across mixed-DPI multi-monitor configurations. Idempotency guarantees that multiple calls (or calls after Qt initializes its internal DPI scaling) do not crash the host process. This is confirmed by 6 test cases in `tests/test_dpi.py`.

3. **Verification of Set-of-Mark & Reticle Animation**:
   - *Observation 3*: `ghost_hud.py` implements coordinate translation `_to_local`, edge clamping, role-based color themes, and a 300ms countdown with Bézier trajectory calculation identical to `KinematicsEngine`.
   - *Logic*: Set-of-Mark numbered boxes and pill badges provide immediate visual grounding for LLM actions. The contracting brackets and Bézier dashed path with active pulse orb visually prepare the user for mouse clicks. The `abort_reticle` slot guarantees instant preemption when low-level hardware hooks detect human touch (<2ms interrupt).

4. **Verification of Integrity**:
   - *Observations 1, 2, 3, 4*: The implementation contains genuine mathematical calculations, dynamic QPainter drawing, real ctypes system calls, and full test coverage without hardcoded dummy returns or skipped operations.
   - *Logic*: The codebase passes all integrity checks.

---

## 3. Adversarial Challenges & Stress Tests

### Challenge 1: Multi-Monitor Coordinate Offsets with Negative Origins
- **Hypothesis**: In multi-monitor topologies where secondary screens are positioned to the left or above the primary monitor, global desktop coordinates are negative. If the HUD assumes `(0, 0)` is top-left, drawing will be clipped or displaced.
- **Investigation**: In `GhostHUD`, `self.setGeometry(screen.virtualGeometry())` spans the entire virtual bounding box. `_to_local(x, y)` evaluates `QPoint(x - geo.x(), y - geo.y())`. For example, with `geo.x() = -1920` and target `x = -1500`, local coordinate is `-1500 - (-1920) = +420`. Local coordinates are strictly non-negative relative to the widget canvas.
- **Result**: PASS.

### Challenge 2: Division-by-Zero in Degenerate Distance Trajectories
- **Hypothesis**: If the cursor is already at or near the target location (`dist -> 0`), computing orthogonal unit vectors `nx = -dy / dist, ny = dx / dist` could raise `ZeroDivisionError` or produce graphic artifacts.
- **Investigation**: Lines 432-434 in `ghost_hud.py` explicitly test `if dist < 15.0: return`, safely skipping the path preview while allowing reticle brackets and the aiming banner to render normally.
- **Result**: PASS.

### Challenge 3: Hardware Interrupt During Active Reticle Countdown
- **Hypothesis**: If a human touches the mouse hardware during the 300ms reticle countdown, the reticle might continue animating or fire a completion click signal anyway.
- **Investigation**: `abort_reticle()` immediately calls `_anim_timer.stop()`, clears `_reticle_active = False`, emits `sig_reticle_aborted`, and updates the canvas. The timer tick callback checks `if not self._reticle_active: return`, preventing stale completion signals.
- **Result**: PASS.

### Challenge 4: High-DPI Re-initialization & Process Conflict
- **Hypothesis**: Calling DPI initialization when Windows has already locked the process DPI awareness context (e.g. by Qt or Windows manifest) could raise unhandled Win32 exceptions.
- **Investigation**: `dpi.py` explicitly checks `GetLastError() == 5` (`ERROR_ACCESS_DENIED`) and `hr == 0x80070005` (`E_ACCESSDENIED`), returning `True` idempotently.
- **Result**: PASS.

---

## 4. Caveats

- **Dynamic Monitor Topology Changes**: When a physical monitor is attached or disconnected, `GhostHUD` automatically updates via `screen.virtualGeometryChanged`. If this occurs mid-frame during an active reticle animation, the current trajectory preview finishes on the updated geometry on the next tick.
- **Offscreen QPA in Headless CI**: Under offscreen Qt platforms (`QT_QPA_PLATFORM=offscreen`), native Win32 window handles do not exist. As designed, `apply_click_through_styles` safely returns `False` via the `IsWindow` check while Qt widget painting and logic are tested via `render(pixmap)`.

---

## 5. Conclusion

The implementation of `GhostHUD`, `win32_styles.py`, `dpi.py`, and their corresponding test suites is robust, clean, well-architected, and fully compliant with Milestone M3 and project requirements.

**Final Gate Verdict**: **APPROVE**

---

## 6. Verification Method

To independently verify this evaluation, execute:

1. **Run Scoped UI & DPI Test Suites**:
   ```powershell
   uv run pytest tests/test_ghost_hud.py tests/test_dpi.py -v
   ```
   *Expected*: 20 passed in < 1s.

2. **Run Full Project Test Suite**:
   ```powershell
   uv run pytest -v
   ```
   *Expected*: 365 passed in ~22s with 0 failures.

3. **Verify UI Package Imports & Exports**:
   ```powershell
   uv run python -c "import parasite_ai.ui as ui; assert 'GhostHUD' in ui.__all__; assert 'apply_click_through_styles' in ui.__all__; print('Exports verified successfully!')"
   ```
   *Expected*: "Exports verified successfully!"
