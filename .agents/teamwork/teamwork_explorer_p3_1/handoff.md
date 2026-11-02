# Handoff Report: Phase 3A Localized ROI Diffing Exploration

**Author:** Explorer Agent (`teamwork_explorer_p3_1`)  
**Mission:** Requirement R1 (Phase 3A: Localized ROI Diffing)  
**Target Project:** ParasiteAI (`C:\ParasiteAI`)  
**Target Codebase Paths:**
- `parasite_ai/mind/dual_mind.py`
- `parasite_ai/ui/types.py`
- `parasite_ai/vision/capture.py`
- `parasite_ai/vision/foveated.py`
- `parasite_ai/mind/memory.py`
- `tests/test_dual_mind.py`
- `tests/test_challenger_m4_2.py`

---

## 1. Observation

### 1.1 Existing Test Suite Status
The full test suite was executed via `pytest`:
- **Command:** `Set-Location C:\ParasiteAI; & "C:\ParasiteAI\.venv\Scripts\python.exe" -m pytest`
- **Result:** `797 passed in 130.10s (0:02:10)` (Exit code 0, 100% green, zero regressions).

### 1.2 Current Visual Verification Architecture in `DualMindPipeline.step()`
In `C:\ParasiteAI\parasite_ai\mind\dual_mind.py` (lines 855–871):
```python
        # 6. Settling & Screen Diff
        post_frame = current_frame
        if action_res.success and action_plan.action in INTERACTIVE_ACTION_TYPES and not action_res.interrupted:
            time.sleep(0.05)
            if self.capturer:
                try:
                    post_frame = self.capturer.capture_screen()
                except Exception:
                    pass

        post_hash = compute_dhash(post_frame) if post_frame is not None else None
        screen_diff = (
            compute_pixel_diff(current_frame, post_frame)
            if (current_frame is not None and post_frame is not None)
            else 0.0
        )
```
- `current_frame` is captured at line 701: `current_frame = self.capturer.capture_screen()`.
- `post_frame` is captured at line 861: `post_frame = self.capturer.capture_screen()`.
- Both `current_frame` and `post_frame` are full-desktop numpy RGB arrays of shape `(1080, 3840, 3)` (or synthetic arrays in tests).
- `compute_pixel_diff(current_frame, post_frame)` computes the fractional pixel difference over the **entire virtual desktop**:
  `changed_pixels / total_pixels`.
- In `C:\ParasiteAI\parasite_ai\mind\memory.py` (lines 232–238):
  ```python
            if parsed_action.action in INTERACTIVE_ACTION_TYPES:
                # Interactive action strike if physical execution failed OR screen did not change
                if not success or screen_diff < self.screen_diff_threshold:
                    is_strike = True
                    self._consecutive_strikes += 1
                else:
                    self._consecutive_strikes = 0
  ```
  `self.screen_diff_threshold` defaults to `0.02` (2%).

### 1.3 Target Resolution and Bounding Box Representations
- In `C:\ParasiteAI\parasite_ai\ui\types.py` (lines 60–96):
  ```python
  class UIElement(BaseModel):
      id: int
      role: str = "Button"
      label: str = ""
      x: int
      y: int
      width: int
      height: int
      center_x: int
      center_y: int
      ...
      @computed_field
      @property
      def bbox(self) -> Tuple[int, int, int, int]:
          return (self.x, self.y, self.width, self.height)
  ```
  `UIElement` currently lacks a `.pad()` method and a structured `BoundingBox` class.
- In `C:\ParasiteAI\parasite_ai\mind\dual_mind.py` (lines 873–883):
  `target_info` is constructed from `matched = next((e for e in elements if e.id == action_plan.target_id), None)` and stores `matched.bbox`.
- In `C:\ParasiteAI\parasite_ai\vision\capture.py` (lines 18–36):
  `get_virtual_screen_bounds()` dynamically retrieves `(vx, vy, vw, vh)` via Win32 `GetSystemMetrics(SM_XVIRTUALSCREEN .. SM_CYVIRTUALSCREEN)`, returning `(0, 0, 3840, 1080)` on the empirical dual-monitor workstation.

### 1.4 Pre-existing Adversarial Test Interaction
In `C:\ParasiteAI\tests\test_challenger_m4_2.py` (lines 678–724):
```python
        elements = [UIElement.from_bbox(1, (50, 50, 50, 50), label="TargetBtn")]
        base_frame = np.full((100, 100, 3), 100, dtype=np.uint8)
        ...
        # Step 3: real visual diff (delta = 100 > 15 across 20% of frame -> 0.20 diff >= 0.02) -> RESETS TO 0
        real_change_frame = base_frame.copy()
        real_change_frame[0:20, :, :] = 200
        pipeline.capturer.capture_screen.return_value = real_change_frame

        rec3 = pipeline.step(
            user_goal="Click button",
            screen_frame=base_frame,
            grounded_elements=elements,
        )
        assert rec3.is_strike is False
```
In this test written during Milestone 4:
- The target element `TargetBtn` is at `(50, 50, 50, 50)`.
- If padded by 20px, its ROI spans `y in [30, 100]` and `x in [30, 100]`.
- The test author injected changes at `real_change_frame[0:20, :, :] = 200` (rows 0 to 19), which is **outside** the target's padded ROI.
- Under full desktop diffing, this changed 20% of the dummy 100x100 frame, resetting strikes. Under localized ROI diffing scoped strictly to the target button, rows 0:20 are outside the ROI, yielding 0.0 diff unless line 712 also updates pixels within the target button or a fallback/compatibility measure is applied.

---

## 2. Logic Chain

1. **Defect in Full-Desktop Diffing:**
   - On a `3840×1080` screen ($4,147,200$ pixels), a standard button of size $100\times 40$ ($4,000$ pixels) represents $\frac{4,000}{4,147,200} = 0.096\%$ of the desktop. Even if 100% of the button's pixels change upon click, the full-desktop difference ratio is $0.00096$, which is far below the $0.02$ ($2.0\%$) strike threshold in `EpisodicMemory`. This triggers a false failure strike.
   - Conversely, if the button does not respond at all, but a background notification pops up in the system tray or a video plays on Monitor 2 altering $100,000$ pixels ($2.4\%$), full-desktop diffing registers a false positive success.

2. **Resolution via Padded ROI:**
   - Scoping verification to `target_bbox.pad(20px)`:
     For a $100\times 40$ button, padding by 20px yields an ROI of $140\times 80 = 11,200$ pixels.
     If the button state changes ($4,000$ pixels), the localized diff ratio is $\frac{4,000}{11,200} = 35.7\%$, easily clearing the $2.0\%$ threshold.
     Simultaneously, changes in the system tray or desktop background fall completely outside the $140\times 80$ crop and contribute $0.0\%$ to the diff, eliminating false positives.

3. **Multi-Monitor Boundary Invariants:**
   - Clamping must query `get_virtual_screen_bounds()` (`vx, vy, vw, vh = 0, 0, 3840, 1080`).
   - Slicing must clamp against both virtual screen dimensions and the actual passed `frame.shape` (`fh, fw`), ensuring zero `IndexError` or negative slice bounds when synthetic test frames (e.g. $100\times 100$) are provided.

4. **Action Hierarchy & Global Fallback:**
   - **Targeted Actions (`CLICK`, `DOUBLE_CLICK`, `RIGHT_CLICK`, `CLICK_AND_TYPE`, `TYPE` with target):**
     Resolve target element via `action_plan.target_id` or explicit `coordinates`. Crop both `current_frame` and `post_frame` to `target_bbox.pad(20px)`.
   - **Ungrounded Point Actions (`coordinates` without `target_id`):**
     Pad the target point $(x, y)$ by 20px into a $40\times 40$ bounding box `(x-20, y-20, 40, 40)` clamped to bounds.
   - **Global Actions (`HOTKEY` chords like `Win`, `Win+R`, `Alt+Tab`, or actions without target):**
     Fall back cleanly to full-desktop diffing (`compute_pixel_diff(current_frame, post_frame)`), as global actions inherently alter disparate screen regions (Start menu, Run dialog, window activation).
   - **Non-Interactive Actions (`WAIT`, `DONE`, `PANIC`):**
     Skip post-action capture; set `screen_diff = 0.0`.

---

## 3. Caveats

1. **Existing Test Suite Compatibility (`test_challenger_m4_2.py`):**
   - In `tests/test_challenger_m4_2.py::TestDualMindPipelineIntegrationAdversarial::test_noise_frame_diff_causes_strike_while_real_diff_resets`, line 712 modified rows `[0:20, :, :]` of a synthetic $100\times 100$ frame while specifying `TargetBtn` at `(50, 50, 50, 50)`.
   - Under localized ROI diffing, changes to rows 0–19 do not touch the button's padded ROI `[30:100, 30:100]`.
   - **Recommendation:** When implementing Phase 3A, update line 712 of `test_challenger_m4_2.py` to also change pixels inside `TargetBtn` (e.g., `real_change_frame[50:70, 50:70, :] = 200`), perfectly preserving the test's intent ("real diff > 15 resets strikes") under localized ROI diffing.
2. **Read-Only Explorer Constraint:**
   - As an explorer agent, no source code or test files were modified during this investigation.
3. **Perceptual dHash Calculation:**
   - Computing `dHash` on the localized ROI crop matches the behavior of `FoveatedVisionEngine` in `foveated.py`. If no target ROI is present, `dHash` is calculated on the full frame.

---

## 4. Conclusion & Recommended Implementation Strategy

### 4.1 Architecture & New Data Contracts

#### A. Define `BoundingBox` Model in `parasite_ai/ui/types.py`
Add `BoundingBox` to `parasite_ai/ui/types.py`:
```python
class BoundingBox(BaseModel):
    """Immutable 2D bounding box with padding, clamping, and array slicing."""
    model_config = ConfigDict(extra="ignore", validate_default=True, frozen=True)

    x: int
    y: int
    width: int
    height: int

    def pad(
        self,
        padding_px: int = 20,
        bounds: Optional[Tuple[int, int, int, int]] = None,
    ) -> BoundingBox:
        """
        Expands the bounding box uniformly by padding_px on all 4 sides,
        clamping coordinates to bounds (min_x, min_y, max_w, max_h).
        Defaults to get_virtual_screen_bounds() if bounds is None.
        """
        if bounds is None:
            from parasite_ai.vision.capture import get_virtual_screen_bounds
            vx, vy, vw, vh = get_virtual_screen_bounds()
        else:
            vx, vy, vw, vh = bounds

        min_x = vx
        min_y = vy
        max_x = vx + vw
        max_y = vy + vh

        new_x = max(min_x, self.x - padding_px)
        new_y = max(min_y, self.y - padding_px)
        new_right = min(max_x, self.x + self.width + padding_px)
        new_bottom = min(max_y, self.y + self.height + padding_px)

        new_w = max(0, new_right - new_x)
        new_h = max(0, new_bottom - new_y)
        return BoundingBox(x=new_x, y=new_y, width=new_w, height=new_h)

    def as_tuple(self) -> Tuple[int, int, int, int]:
        return (self.x, self.y, self.width, self.height)

    def crop_frame(self, frame: Optional[np.ndarray], bounds: Optional[Tuple[int, int, int, int]] = None) -> Optional[np.ndarray]:
        """Extracts localized ROI crop from numpy array clamped to array dimensions."""
        if frame is None or frame.size == 0:
            return None
        fh, fw = frame.shape[:2]
        vx = bounds[0] if bounds else 0
        vy = bounds[1] if bounds else 0

        rel_x1 = max(0, min(self.x - vx, fw))
        rel_y1 = max(0, min(self.y - vy, fh))
        rel_x2 = max(0, min(self.x + self.width - vx, fw))
        rel_y2 = max(0, min(self.y + self.height - vy, fh))

        if rel_y2 <= rel_y1 or rel_x2 <= rel_x1:
            return None
        return frame[rel_y1:rel_y2, rel_x1:rel_x2]
```

Add properties to `UIElement` in `parasite_ai/ui/types.py`:
```python
    @property
    def target_bbox(self) -> BoundingBox:
        return BoundingBox(x=self.x, y=self.y, width=self.width, height=self.height)

    def pad(
        self,
        padding_px: int = 20,
        bounds: Optional[Tuple[int, int, int, int]] = None,
    ) -> BoundingBox:
        return self.target_bbox.pad(padding_px=padding_px, bounds=bounds)
```

#### B. Implement Target ROI Extraction in `parasite_ai/mind/dual_mind.py`
Add helper function in `parasite_ai/mind/dual_mind.py`:
```python
def extract_action_target_roi(
    action: ActionPlan,
    elements: List[UIElement],
    resolved_coords: Optional[Tuple[int, int]] = None,
    active_window_rect: Optional[Tuple[int, int, int, int]] = None,
    padding_px: int = 20,
    bounds: Optional[Tuple[int, int, int, int]] = None,
) -> Optional[BoundingBox]:
    """
    Resolves the target bounding box for localized visual diffing:
    1. By target_id in grounded elements.
    2. By coordinates intersecting any grounded element.
    3. By coordinates fallback to point bounding box (x, y, 0, 0).
    4. By active window rectangle for ungrounded typing/scrolling.
    5. Fallback: None (global action / full desktop diff).
    """
    # 1. Target ID resolution
    if action.target_id is not None:
        matched = next((e for e in elements if e.id == action.target_id), None)
        if matched:
            return matched.pad(padding_px=padding_px, bounds=bounds)

    # 2. Coordinates resolution
    coords = action.coordinates or resolved_coords
    if coords is not None:
        cx, cy = coords
        matched = next((e for e in elements if e.x <= cx <= e.x + e.width and e.y <= cy <= e.y + e.height), None)
        if matched:
            return matched.pad(padding_px=padding_px, bounds=bounds)
        # Point ROI: 40x40 box centered at coordinates
        return BoundingBox(x=cx, y=cy, width=0, height=0).pad(padding_px=padding_px, bounds=bounds)

    # 3. Active window resolution for ungrounded typing/scrolling
    if active_window_rect and action.action in (ActionType.TYPE, ActionType.SCROLL):
        wx, wy, ww, wh = active_window_rect
        if ww > 0 and wh > 0:
            return BoundingBox(x=wx, y=wy, width=ww, height=wh).pad(padding_px=padding_px, bounds=bounds)

    # 4. Global actions or ungrounded chords
    return None
```

#### C. Update Step 6 in `DualMindPipeline.step()` in `parasite_ai/mind/dual_mind.py`
Replace lines 855–870 with:
```python
        # 6. Settling & Localized Screen Diff Verification
        post_frame = current_frame
        if action_res.success and action_plan.action in INTERACTIVE_ACTION_TYPES and not action_res.interrupted:
            time.sleep(0.05)
            if self.capturer:
                try:
                    post_frame = self.capturer.capture_screen()
                except Exception:
                    pass

        # Resolve virtual screen bounds and target ROI
        from parasite_ai.vision.capture import get_virtual_screen_bounds
        vbounds = get_virtual_screen_bounds()
        active_rect = None
        if self.window_guard and hasattr(self.window_guard, "get_active_window_info"):
            try:
                winfo = self.window_guard.get_active_window_info()
                if winfo and hasattr(winfo, "rect"):
                    active_rect = winfo.rect
            except Exception:
                pass

        target_roi = extract_action_target_roi(
            action=action_plan,
            elements=elements,
            resolved_coords=action_res.resolved_coordinates,
            active_window_rect=active_rect,
            padding_px=20,
            bounds=vbounds,
        )

        # Localized ROI diffing if target bounding box resolved
        roi_pre = target_roi.crop_frame(current_frame, bounds=vbounds) if target_roi else None
        roi_post = target_roi.crop_frame(post_frame, bounds=vbounds) if target_roi else None

        if roi_pre is not None and roi_post is not None and roi_pre.shape == roi_post.shape and roi_pre.size > 0:
            screen_diff = compute_pixel_diff(roi_pre, roi_post)
            post_hash = compute_dhash(roi_post)
            pre_hash = compute_dhash(roi_pre)
        else:
            # Fallback to full desktop diffing for global actions or ungrounded hotkeys
            screen_diff = (
                compute_pixel_diff(current_frame, post_frame)
                if (current_frame is not None and post_frame is not None)
                else 0.0
            )
            post_hash = compute_dhash(post_frame) if post_frame is not None else None
            pre_hash = compute_dhash(current_frame) if current_frame is not None else None
```

---

## 5. Verification Method

### 5.1 Independent Verification Commands
1. Run existing test suite to ensure zero regressions:
   ```powershell
   Set-Location C:\ParasiteAI; & "C:\ParasiteAI\.venv\Scripts\python.exe" -m pytest
   ```
   **Expected:** All tests pass cleanly (797+ passing).

2. Run `test_dual_mind.py`:
   ```powershell
   Set-Location C:\ParasiteAI; & "C:\ParasiteAI\.venv\Scripts\python.exe" -m pytest tests/test_dual_mind.py
   ```
   **Expected:** All tests pass in $<1.0\text{s}$.

3. Create and execute new unit test suite `tests/test_localized_roi_diff.py`:
   ```powershell
   Set-Location C:\ParasiteAI; & "C:\ParasiteAI\.venv\Scripts\python.exe" -m pytest tests/test_localized_roi_diff.py -v
   ```
   **Test Cases to Implement:**
   - `test_bounding_box_padding_geometry`: Check `(100, 100, 50, 50).pad(20)` yields `(80, 80, 90, 90)`.
   - `test_bounding_box_clamping_virtual_screen_edges`: Verify clamping at `(0, 0)` and `(3840, 1080)`.
   - `test_dual_monitor_seam_preservation`: Verify box crossing $x = 1920$ is not clipped.
   - `test_ui_element_target_bbox_property`: Verify `element.target_bbox.pad(20)` and `element.pad(20)` match.
   - `test_localized_roi_diff_rejects_peripheral_noise`: Modify pixels in system tray region ($x > 3700, y > 1000$); verify target ROI diff remains $0.0$ and incurs a strike.
   - `test_localized_roi_diff_detects_target_change`: Modify pixels strictly inside target button; verify diff $> 0.02$ and strikes reset to 0.
   - `test_point_coordinates_roi_diff`: Click action with `coordinates=(300, 400)` creates a $40\times 40$ ROI.
   - `test_global_hotkey_action_falls_back_to_full_diff`: Hotkey action with no target bbox diffs full screen.
   - `test_degenerate_frame_clamping_safety`: Verify no crashes or `IndexError` when synthetic test frames are smaller than virtual screen.

### 5.2 Invalidation Conditions
- Any coordinate calculation on Monitor 2 ($x \ge 1920$) being clipped to 1920.
- Any regression in the existing 797 tests.
- Visual differences in the system tray or background desktop counting as success for a button click that produced no local visual change.
