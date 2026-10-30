# Handoff Report: Milestone M4 Reviewer 1 (Hybrid Screen Grounding & Perception)

## Review Summary

**Verdict**: **APPROVE**  
**Assigned Feature**: Feature 12 — Hybrid Screen Grounding & Perception  
**Assigned Agent**: `teamwork_reviewer_m4_1`  
**Overall Risk Assessment**: LOW  
**Integrity Attestation**: NO INTEGRITY VIOLATIONS DETECTED. Genuine implementation of UIA tree walking, RapidOCR ONNX inference, spatial IoU/containment algorithms, and coordinate transformations without shortcuts, facade mocks, or hardcoded test outputs.

---

## 1. Observation

1. **Implementation Files Inspected**:
   - `parasite_ai/vision/capture.py` (lines 1–148): `ScreenCapture` class providing high-performance screen grab via `mss` (line 68–98), fallback to PIL `ImageGrab` (lines 101–106), and synthetic 1920x1080 numpy frame fallback (line 111). `compute_frame_diff` (lines 17–54) performs 4x downsampling (`arr[::4, ::4]`), casts to `np.int16` to prevent unsigned subtraction underflow, applies noise threshold (`diff > 15`), and returns normalized pixel change ratio in `[0.0, 1.0]`.
   - `parasite_ai/vision/grounding.py` (lines 1–485):
     - Tier 1 UIA Tree Walker (`_walk_uia_tree`, lines 181–295): Uses `uiautomation.WalkControl` with `maxDepth=5` and hard break at 120 elements. Filters out `IsOffscreen` controls, degenerate boxes (`w < 8 or h < 8`), and matches types against `INTERACTIVE_ROLES` dictionary with fallback support for labeled `PaneControl`. Extracts labels with fallback chain `Name -> HelpText -> AutomationId`.
     - Tier 2 Scoped RapidOCR (`_run_scoped_ocr`, lines 296–398): Invoked when `grounding_mode == "ocr_only"`, `force_ocr=True`, or in `hybrid` mode when Tier 1 produces fewer than 6 controls (`self._min_uia_threshold = 6`). Uses active window crop scoping to avoid full-screen latency, translates local OCR bounding boxes back to absolute desktop coordinates via `(offset_x + min_x, offset_y + min_y)`.
     - Tier 3 Spatial Deduplication & Merging (`_deduplicate_and_merge`, lines 399–429): Implements `compute_iou` ($\ge 0.35$) and `compute_containment` ($\ge 0.70$). Enriches missing/generic UIA labels (`"button"`, `"pane"`, `"custom"`, `""`) using contained OCR text and marks source as `"merged"`. Suppresses duplicate OCR bounding boxes.
     - Set-of-Mark 1-Based Indexing & Formatting (`_normalize_elements`, lines 430–468; `format_som_summary`, lines 469–485): Sorts by active window and coordinates (`not e.is_active_window, e.y, e.x`), caps to `max_som_elements` (default 60), and constructs `UIElement` instances with 1-based sequential `id` in `[1..N]`.
   - `parasite_ai/vision/__init__.py` (lines 1–21): Clean public exports of `ScreenCapture`, `ScreenGrounder`, `RawElement`, `compute_iou`, `compute_containment`, `compute_frame_diff`, `INTERACTIVE_ROLES`.
   - `tests/test_grounding.py` (lines 1–328): 13 dedicated unit and integration tests covering initialization defaults, exact IoU math, exact containment math, UIA enumeration, sparse OCR fallback, sufficient UIA skipping OCR, label merging, max elements capping, HWND window filter, headless resilience, SoM summary formatting, frame diff noise thresholding, and UIBridge/GhostHUD interop.

2. **UI Subsystem Contracts Inspected**:
   - `parasite_ai/ui/types.py` (`UIElement`, lines 60–127): Strict Pydantic model with `id: int = Field(ge=1)`, `@computed_field @property def bbox`, `@computed_field @property def center`, and `control_type` property alias returning `self.role` for full specification compliance.
   - `parasite_ai/ui/ghost_hud.py` (`GhostHUD.set_targets`, lines 207–217; `_normalize_target`, lines 301–337): Ingests `UIElement` instances seamlessly, resolving id, role, label, coordinates, and assigning role colors (`ROLE_COLOR_MAP`).
   - `parasite_ai/ui/companion_dock.py` (`CompanionDock.update_perception_preview`, lines 598–628): Accepts frame image and elements list, updates thumbnail and grounding badge text (`f"Grounding: {len(elements)} Targets Active"`), respecting privacy blackout masking.
   - `parasite_ai/ui/bridge.py` (`UIBridge`, lines 87–98): Thread-safe `notify_perception` and `set_hud_targets` signal emitters.

3. **Verbatim Test Results**:
   - `uv run pytest tests/test_grounding.py -v`:
     ```
     ============================= 13 passed in 2.89s ==============================
     ```
   - Full regression suite `uv run pytest`:
     ```
     ============================ 475 passed in 42.02s =============================
     ```
     100% pass across all 475 tests in the repository with 0 failures and 0 regressions.

---

## 2. Logic Chain

1. **Contract Adherence**:
   - `PROJECT.md` Section 3 requires: `ScreenGrounder.ground(window_filter: int = None) -> list[UIElement]` returning indexed interactive elements with `id`, `bbox`, `label`, `control_type`, and `center`.
   - In `grounding.py` line 141, `ground` returns `List[UIElement]`.
   - In `types.py` lines 85–101, `UIElement` defines `@computed_field bbox`, `@computed_field center`, and property `control_type`.
   - Observation 1 & 2 confirm that all fields and properties match the exact contract required by the UI subsystem, GhostHUD, CompanionDock, and UIBridge.

2. **Three-Tier Architecture Verification**:
   - **Tier 1**: `_walk_uia_tree` enforces depth limit 5 (`self._depth_limit = 5`) and element cap of 120 elements (line 223), preventing runaway traversal in deep UI hierarchies.
   - **Tier 2**: `_run_scoped_ocr` triggers dynamically if `grounding_mode == "ocr_only"` or if Tier 1 yields $< 6$ interactive elements (tested and confirmed in `test_scoped_ocr_sparse_fallback` and `test_scoped_ocr_sufficient_uia_skips_ocr`). When triggered, it scopes capture to the target window rect, and adds `(offset_x, offset_y)` to preserve screen-absolute coordinates.
   - **Tier 3**: `_deduplicate_and_merge` calculates IoU with threshold 0.35 and containment with threshold 0.70. When an OCR box is contained in or overlaps with a generic/unlabeled UIA element, it enriches the label (`uia.label = ocr.label`, `uia.source = "merged"`) and discards the redundant OCR element (tested in `test_spatial_containment_and_label_merge`).

3. **Adversarial & Edge Case Robustness**:
   - Degenerate box filtering (`w < 8 or h < 8`) prevents zero-pixel dividers and invisible spacers from polluting the Set-of-Mark list.
   - Synthetic frame fallback in `ScreenCapture` ensures headless CI environments and display-locked sessions never raise unhandled exceptions.
   - Downsampled `compute_frame_diff` uses `int16` subtraction to avoid `uint8` wrapping underflow, with a 15-intensity noise gate that ignores monitor backlight jitter.

4. **Integrity & Zero-Regression**:
   - All tests execute real logic with genuine geometric formulas and mocking only external OS/hardware interfaces (`uiautomation`, screen grabber, OCR ONNX).
   - Full test run yielded 475 passed out of 475 tests (Observation 3).

---

## 3. Caveats & Adversarial Challenges

1. **Virtual Monitor Coordinate Range**:
   - In `grounding.py` line 244: `if rect.left < -1000 or rect.top < -1000: continue`.
   - *Adversarial Observation*: This check was designed to filter out minimized Win32 windows (which Windows positions at coordinates around $(-32000, -32000)$). However, in multi-monitor setups where a secondary monitor is positioned to the left of the primary monitor, valid UI controls might have coordinates in the range $[-1920, -1001]$.
   - *Impact*: Low for primary desktop operation; for complex left-extended multi-monitor setups, controls beyond $-1000$ px would be omitted.
   - *Recommendation for future hardening*: In a future maintenance pass, use Win32 `IsIconic(hwnd)` or adjust the negative coordinate threshold to $<-10000$ to support ultra-wide multi-monitor configurations on negative axes.
2. **RapidOCR ONNX Model Initialization**:
   - Initial initialization of the ONNX model can take 200–400ms on first load. The implementation correctly handles this via lazy instantiation (`_get_ocr_engine`) so that standard UIA runs incur 0ms OCR overhead.

---

## 4. Conclusion

The implementation of **Feature 12 — Hybrid Screen Grounding & Perception** meets all functional, architectural, safety, and testing requirements specified in `ORIGINAL_REQUEST.md` and `orchestrator/PROJECT.md`. The Set-of-Mark 1-based indexing, Tier 1/2/3 pipeline, UI subsystem interoperability, and headless fallbacks operate reliably without regressions.

**Final Verdict: APPROVE**

---

## 5. Verification Method

To independently verify this assessment:

1. **Run Unit & Integration Grounding Tests**:
   ```powershell
   uv run pytest tests/test_grounding.py -v
   ```
   *Expected Result*: 13 passed in $< 3.5\text{s}$.

2. **Run Full Test Suite**:
   ```powershell
   uv run pytest
   ```
   *Expected Result*: 475 passed, 0 failures, 0 regressions in $< 45\text{s}$.

3. **Inspect Contracts**:
   - Check `parasite_ai/ui/types.py`: confirm `UIElement` has `bbox` and `center` as computed fields, and `id` constrained to `ge=1`.
   - Check `parasite_ai/vision/grounding.py`: confirm `INTERACTIVE_ROLES`, `_walk_uia_tree`, `_run_scoped_ocr`, and `_deduplicate_and_merge`.
