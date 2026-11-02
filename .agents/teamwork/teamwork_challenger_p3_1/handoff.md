# Empirical Challenger Report: Phase 3A Localized ROI Diffing

**Author:** Empirical Challenger Agent (`teamwork_challenger_p3_1`)  
**Mission:** Stress-test Requirement R1 (Phase 3A: Localized ROI Diffing)  
**Target Workspace:** `C:\ParasiteAI`  
**Date:** 2026-10-31  
**Empirical Verdict:** **APPROVE**

---

## 1. Observation

### 1.1 Implementation Architecture Verified
- `parasite_ai/ui/types.py` (lines 61–128):
  - `BoundingBox` provides `.pad(padding_px=20, bounds=None)` and `.crop_frame(frame, bounds=None)` with strict virtual desktop clamping against `get_virtual_screen_bounds()` (`3840x1080 @ 100% DPI`).
  - `UIElement.target_bbox` and `UIElement.pad()` delegate cleanly to `BoundingBox`.
- `parasite_ai/mind/dual_mind.py` (lines 287–332):
  - `extract_action_target_roi` resolves target ROIs across target IDs, element coordinates, ungrounded coordinates (producing a 40x40 padded box), active window rects for TYPE/SCROLL, and returns `None` for global actions (`HOTKEY`, `WAIT`, `DONE`, `PANIC`).
- `parasite_ai/mind/dual_mind.py` (lines 1016–1064):
  - Step 6 scopes screen difference verification to localized ROI crops (`roi_pre` and `roi_post`) when resolved, falling back to full desktop diffing when `target_roi` is `None` or out-of-frame.

### 1.2 Base Test Execution
- Command:
  ```powershell
  Set-Location C:\ParasiteAI; & "C:\ParasiteAI\.venv\Scripts\python.exe" -m pytest tests/test_phase3_execution_loop.py -v
  ```
- Output:
  ```
  ============================= 32 passed in 2.13s ==============================
  ```
  All 32 tests in `tests/test_phase3_execution_loop.py` pass cleanly.

### 1.3 Challenger Empirical Stress Harness Execution
Created and executed `tests/test_phase3_challenger_stress.py` containing 9 adversarial stress tests covering all mandated verification areas:
- Command:
  ```powershell
  Set-Location C:\ParasiteAI; & "C:\ParasiteAI\.venv\Scripts\python.exe" -m pytest tests/test_phase3_challenger_stress.py -v
  ```
- Output:
  ```
  tests/test_phase3_challenger_stress.py::TestExtremeBoundaryConditions::test_partially_offscreen_left_top_element PASSED [ 11%]
  tests/test_phase3_challenger_stress.py::TestExtremeBoundaryConditions::test_completely_offscreen_element_safely_degenerates PASSED [ 22%]
  tests/test_phase3_challenger_stress.py::TestExtremeBoundaryConditions::test_dual_monitor_seam_crossing_element PASSED [ 33%]
  tests/test_phase3_challenger_stress.py::TestExtremeBoundaryConditions::test_extreme_bottom_right_virtual_desktop_element PASSED [ 44%]
  tests/test_phase3_challenger_stress.py::TestExtremeBoundaryConditions::test_zero_width_or_zero_height_elements PASSED [ 55%]
  tests/test_phase3_challenger_stress.py::TestPeripheralNoiseRejection::test_peripheral_tray_noise_yields_zero_diff_and_strike PASSED [ 66%]
  tests/test_phase3_challenger_stress.py::TestPeripheralNoiseRejection::test_changes_inside_target_roi_exceed_threshold_and_reset_strikes PASSED [ 77%]
  tests/test_phase3_challenger_stress.py::TestFallbackBehavior::test_ungrounded_point_clicks_create_centered_40x40_padded_roi PASSED [ 88%]
  tests/test_phase3_challenger_stress.py::TestFallbackBehavior::test_global_actions_cleanly_fallback_to_full_desktop_diffing PASSED [100%]
  ============================== 9 passed in 2.30s ==============================
  ```

### 1.4 Full Regression Suite Execution
- Command:
  ```powershell
  Set-Location C:\ParasiteAI; & "C:\ParasiteAI\.venv\Scripts\python.exe" -m pytest
  ```
- Output:
  ```
  ======================= 838 passed in 140.18s (0:02:20) =======================
  ```
  100% green across all 838 tests (including 32 Phase 3 tests and 9 Challenger stress tests), with zero regressions.

---

## 2. Logic Chain

### 2.1 Extreme Boundary Conditions
1. **Partially Off-Screen Geometry:**
   - Input: `BoundingBox(x=-10, y=0, width=50, height=50).pad(20px, bounds=(0, 0, 3840, 1080))`.
   - Math: `new_x = max(0, -30) = 0`, `new_y = max(0, -20) = 0`, `new_right = min(3840, 60) = 60`, `new_bottom = min(1080, 70) = 70`.
   - Output: `(x=0, y=0, width=60, height=70)`. Crop on `(1080, 3840, 3)` frame produces valid `(70, 60, 3)` array without indexing errors.
2. **Multi-Monitor Seam Crossing (1920 Boundary):**
   - Input: `BoundingBox(x=1910, y=500, width=50, height=50)`.
   - Math: Padded x-span is `[1890, 1980]`. `1890 < 1920` (Monitor 1) and `1980 > 1920` (Monitor 2).
   - Output: Crop on `(1080, 3840, 3)` spans both monitors seamlessly; columns 0..29 contain Monitor 1 pixels, columns 30..89 contain Monitor 2 pixels. Neither monitor clips or zeroes the box.
3. **Extreme Bottom-Right Clamping:**
   - Input: `BoundingBox(x=3830, y=1070, width=50, height=50)`.
   - Math: `new_x = 3810`, `new_y = 1050`, `new_right = min(3840, 3900) = 3840`, `new_bottom = min(1080, 1140) = 1080`.
   - Output: `(x=3810, y=1050, width=30, height=30)`. Slicing `[1050:1080, 3810:3840]` yields exact `(30, 30, 3)` crop without index overflow.
4. **Degenerate Geometries:**
   - Input: Point `BoundingBox(x=500, y=400, width=0, height=0).pad(20px)`.
   - Output: `(480, 380, 40, 40)`. Padded width and height are `max(0, 520 - 480) = 40`. Handles single-axis zeros (0x50, 50x0) uniformly.

### 2.2 Peripheral Noise Rejection & Strike Tracking
1. **Noise Rejection (System Tray vs Monitor 1 Target):**
   - Full-desktop frame is `3840x1080`. Target element at `(200, 200, 50, 50)` on Monitor 1.
   - 3600 pixels altered in system tray at `(1040:1080, 3750:3840)` on Monitor 2.
   - Because visual verification crops strictly to target ROI `(180:270, 180:270)`, the tray change contributes zero pixels to the target difference.
   - Result: `screen_diff == 0.0 < 0.02`, triggering an episodic strike (`rec.is_strike is True`, `consecutive_strikes == 1`). Peripheral noise does not mask a failed action.
2. **Target Change Detection & Strike Reset:**
   - Preloaded 2 consecutive strikes into episodic memory.
   - Visual change strictly inside target element `(210:240, 210:240)` produces `screen_diff > 0.02`.
   - Result: `rec.is_strike is False`, resetting `consecutive_strikes` to 0.

### 2.3 Fallback Mechanics
1. **Ungrounded Point Clicks:**
   - `extract_action_target_roi` handles `coordinates=(600, 400)` without matched element by synthesizing `BoundingBox(600, 400, 0, 0).pad(20px)`.
   - Produces a symmetric 40x40 ROI centered on `(600, 400)` (`[580, 380, 40, 40]`).
2. **Global Actions Fallback:**
   - `extract_action_target_roi` returns `None` for `HOTKEY`, `WAIT`, `DONE`, `PANIC`.
   - `DualMindPipeline.step()` cleanly catches `target_roi is None` and evaluates `compute_pixel_diff(current_frame, post_frame)`.
   - No exceptions are raised; full desktop diffing applies.

---

## 3. Caveats

- **No Caveats.**
  - All stress assertions passed unconditionally across all 4 mandatory areas.
  - Review-only discipline was maintained; no implementation code was modified.
  - All 829 existing regression tests remain intact.

---

## 4. Conclusion

**Verdict: APPROVE.**

The implementation of Requirement R1 (Phase 3A: Localized ROI Diffing) in `parasite_ai/ui/types.py` and `parasite_ai/mind/dual_mind.py` is empirically robust, correctly handles dual-monitor boundary clamping (3840x1080 @ 100% DPI), eliminates peripheral false positives from system tray updates, correctly tracks episodic strikes, and falls back gracefully for ungrounded clicks and global actions.

---

## 5. Verification Method

### 5.1 Commands
```powershell
# 1. Execute Phase 3 unit test suite
Set-Location C:\ParasiteAI; & "C:\ParasiteAI\.venv\Scripts\python.exe" -m pytest tests/test_phase3_execution_loop.py -v

# 2. Execute Challenger empirical stress harness
Set-Location C:\ParasiteAI; & "C:\ParasiteAI\.venv\Scripts\python.exe" -m pytest tests/test_phase3_challenger_stress.py -v
```

### 5.2 Invalidation Conditions
- Any bounding box padding operation on Monitor 2 ($x \ge 1920$) returning negative or clipped coordinates.
- System tray visual updates masking button click failures on Monitor 1.
- Crashes when clicking ungrounded points or dispatching global hotkeys.
