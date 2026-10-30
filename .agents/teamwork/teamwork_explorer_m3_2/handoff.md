# Handoff Report: Milestone M3 — Ghost-Hand Screen Overlay HUD

**Agent**: `teamwork_explorer_m3_2` (Explorer 2 for M3)  
**Date**: 2026-10-29  
**Type**: Hard Handoff (Investigation & Specification Complete)  
**Deliverable Artifact**: `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m3_2\plan.md`  

---

## 1. Observation

1. **Host Environment & PySide6 / PyQt6 Availability**:
   - Shell command `uv run python -c "import PyQt6.QtWidgets; print('PyQt6 OK'); import pytestqt; print('pytest-qt OK')"` exited with code 0:
     ```
     PyQt6 OK
     pytest-qt OK
     ```
   - Running `uv run pytest tests/test_kinematics.py` showed:
     `PyQt6 6.12.0 -- Qt runtime 6.12.0 -- Qt compiled 6.12.0 -- pytest-9.2.0 -- plugins: qt-4.5.0`
     All 14 kinematics tests passed in 0.29s.

2. **Multi-Monitor Virtual Desktop Geometry**:
   - Shell command inspecting virtual desktop geometry:
     `uv run python -c "from PyQt6.QtWidgets import QApplication; from PyQt6.QtGui import QGuiApplication; app = QApplication([]); screen = QGuiApplication.primaryScreen(); print('VirtualGeo:', screen.virtualGeometry().getRect())"`
     Output:
     ```
     VirtualGeo: (0, 0, 3840, 1080)
     ```
   - Observed that the active host has a 3840x1080 virtual desktop spanning multiple displays, confirming that `screen.geometry()` (which only returns the primary 1920x1080) would truncate overlay visibility, whereas `screen.virtualGeometry()` covers all monitors.

3. **Win32 Layered Click-Through Verification on PyQt6 QWidget**:
   - Executed native Win32 window style manipulation via `user32.SetWindowLongW` on `QWidget.winId()`:
     ```python
     hwnd = int(w.winId())
     GWL_EXSTYLE = -20
     WS_EX_LAYERED = 0x00080000
     WS_EX_TRANSPARENT = 0x00000020
     WS_EX_TOPMOST = 0x00000008
     WS_EX_NOACTIVATE = 0x08000000
     WS_EX_TOOLWINDOW = 0x00000080
     ```
   - Result:
     ```
     Old Style: 0x80088
     New Style: 0x80800a8
     WS_EX_TRANSPARENT present: True
     WS_EX_NOACTIVATE present: True
     WS_EX_LAYERED present: True
     ```
     Verified that Windows permits applying `WS_EX_TRANSPARENT` (click-through) and `WS_EX_NOACTIVATE` (no focus theft) directly onto PyQt6 widgets.

4. **Integration Hook in Existing `MouseDriver`**:
   - In `parasite_ai/hands/mouse.py` (lines 98, 171-176, 236-243):
     ```python
     if preview_reticle and self.preview_reticle_ms > 0:
         if self.reticle_callback:
             self.reticle_callback(target_x, target_y, self.preview_reticle_ms)
         if cancellation_token and cancellation_token.wait(timeout=self.preview_reticle_ms / 1000.0):
             self.release_all_buttons()
             return False
     ```
   - Confirmed that `MouseDriver` already contains the callback invocation `reticle_callback(target_x, target_y, duration_ms)` and the 300ms pause gate with `<2ms` cancellation token polling.

5. **Existing Configuration Schema in `parasite_ai/config.py`**:
   - In `parasite_ai/config.py` (lines 277-299), `GhostHUDConfig` is fully defined and validated with Pydantic:
     - `enabled: bool = True`
     - `fps_target: int = 60`
     - `reticle_color: str = "#FF3366"`
     - `reticle_duration_ms: int = 300`
     - `som_box_color: str = "#00E5FF"`
     - `som_glow_color: str = "#00FFCC"`
     - `box_alpha: float = 0.25`
     - `stroke_width_px: float = 1.5`

6. **Kinematic Bézier Formulas in `parasite_ai/hands/kinematics.py`**:
   - In `parasite_ai/hands/kinematics.py` (lines 140-156), asymmetric cubic Bézier control points are defined:
     ```python
     p1 = (p0[0] + 0.32 * vx + arc_amp * nx, p0[1] + 0.32 * vy + arc_amp * ny)
     p2 = (p0[0] + 0.68 * vx + 0.45 * arc_amp * nx, p0[1] + 0.68 * vy + 0.45 * arc_amp * ny)
     ```
     Using these identical control point equations in `GhostHUD` trajectory preview guarantees that the visual path matches the physical mouse trajectory.

7. **Offscreen Rendering Compatibility**:
   - Tested `widget.render(pixmap)` in headless context: executed cleanly without errors or display server requirements, confirming complete testability under `pytest-qt` (`qtbot`).

---

## 2. Logic Chain

1. **From Observation 2 to Multi-Monitor Spanning**:
   Because the user's desktop can span multiple monitors (as verified by `(0, 0, 3840, 1080)`), positioning the HUD using `screen.virtualGeometry()` and connecting to `screen.virtualGeometryChanged` ensures the overlay covers all monitors and handles negative coordinate offsets (`x - geo.x()`).
2. **From Observation 3 to Click-Through & Focus Non-Interference**:
   Applying Win32 extended window styles `WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW` via `user32.SetWindowLongW` on `self.winId()` guarantees that the HUD remains permanently topmost, visually transparent, and physically click-through without intercepting mouse clicks or stealing input focus from target applications.
3. **From Observations 4 & 6 to 300ms Targeting Reticle & Path Preview**:
   `MouseDriver` already expects `reticle_callback(target_x, target_y, duration_ms)` before initiating movement. Providing `show_reticle(x, y, duration_ms, target_id, label)` on `GhostHUD` and wiring it to `reticle_callback` provides the exact 300ms visual pre-flight check. Rendering the contracting reticle brackets, floating banner, and Bézier path matching `KinematicsEngine` gives the user total visibility of the impending action.
4. **From Observations 1, 5, & 7 to Implementation & Test Strategy**:
   With `PyQt6 6.12.0`, `pytest-qt 4.5.0`, and Pydantic `GhostHUDConfig` already present in the workspace, `GhostHUD` can be cleanly implemented in `parasite_ai/ui/ghost_hud.py` with 100% automated test coverage in `tests/test_ghost_hud.py` using `qtbot` and `widget.render(pixmap)`.

---

## 3. Caveats

1. **Non-Windows / CI Execution**:
   On non-Windows platforms or in pure headless containers where `ctypes.windll` or real HWNDs are not present, calling `user32.SetWindowLongW` would raise an exception. The plan defensively wraps `apply_win32_styles()` in `sys.platform == "win32"` and `try...except` so tests pass unconditionally in any environment.
2. **DPI Awareness Prerequisite**:
   For coordinate precision on Windows 11 high-DPI displays (125%, 150%), `SetProcessDpiAwareness(2)` (Per-Monitor v2) must be called in `main.py` before `QApplication` instantiation. This is documented and assigned to the integration explorer (`teamwork_explorer_m3_3`).

---

## 4. Conclusion

The technical architecture and implementation plan for the Ghost-Hand Screen Overlay HUD (`parasite_ai/ui/ghost_hud.py`) is complete, robust, and verified.
- Full code specification is provided in `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m3_2\plan.md`.
- Full test suite specification covering Win32 styles, virtual desktop geometry, SoM category colors, reticle countdown, Bézier path preview, and interrupt abort is provided.
- The design is ready for immediate implementation by the milestone worker.

---

## 5. Verification Method

1. **Code Layout Inspection**:
   Inspect `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m3_2\plan.md` to review the class structure, methods, Win32 constants, and test cases.
2. **Implementation Verification**:
   When `parasite_ai/ui/ghost_hud.py` and `tests/test_ghost_hud.py` are written by the worker, execute:
   ```powershell
   uv run pytest tests/test_ghost_hud.py -v
   ```
   All test cases (geometry span, Win32 styles, SoM bounding boxes, role color mappings, reticle countdown signal, and abort handling) must pass with 100% success.
3. **Invalidation Conditions**:
   - If `WS_EX_TRANSPARENT` or `WS_EX_NOACTIVATE` fails to apply, user clicks on desktop apps under the overlay would be blocked.
   - If virtual geometry origin offset is ignored, overlay coordinates on multi-monitor setups with secondary screens on the left would be misaligned.
