# Implementation Plan: Feature 12 — Hybrid Screen Grounding (`parasite_ai/vision/grounding.py`)

## 1. Executive Architecture Overview

The Hybrid Screen Grounding engine is the primary visual perception subsystem of ParasiteAI. Its responsibility is to locate, classify, and normalize interactive desktop UI elements into a compact list of tagged targets (`list[UIElement]`) tagged with sequential 1-based indices `[#1..#N]`. These targets are displayed in real-time on the transparent `GhostHUD` overlay and consumed by the `DualMind` planner and `ActionDispatcher` to guide physical mouse and keyboard actions.

To deliver high accuracy while preserving system resources (0 MB VRAM overhead and < 500ms total latency budget), the system utilizes a **three-tier perception pipeline**:
1. **Tier 1 — Win32 UI Automation Tree Walk (`uiautomation`)**:
   Inspects native OS accessibility trees of the active foreground window in ~15ms with zero GPU/VRAM consumption. Traverses interactive controls (`Button`, `Edit`, `Hyperlink`, `ComboBox`, `TabItem`, `CheckBox`, `RadioButton`, `MenuItem`, `ListItem`, `Document`).
2. **Tier 2 — Scoped RapidOCR Fallback (`rapidocr-onnxruntime`)**:
   Executes on CPU via ONNX Runtime when Tier 1 yields sparse controls (< 6 elements, typical of Chromium Canvas, WebGL, custom game toolkits, or desktop remote sessions), or when explicitly configured in hybrid/ocr mode. Scopes OCR strictly to the active window rectangle to minimize image size and keep latency under ~100ms.
3. **Tier 3 — Spatial IoU & Containment Deduplication**:
   Computes Intersection-over-Union (IoU) and bounding box containment ratio between OCR text boxes and UIA controls. When an OCR text box is contained within or overlaps a UIA control, it merges any missing label into the native UIA element and suppresses the redundant OCR box, eliminating duplicate Set-of-Mark tags.

```
                              Desktop Screen State
                                       |
                   +-------------------+-------------------+
                   |                                       |
                   v                                       v
      Tier 1: Win32 UIA Tree Walk              Fast Screen Capture (MSS)
      - Foreground Window / HWND Filter                    |
      - Depth-limited BFS/Walk (depth=5)                   v
      - Interactive Control Type Filter         Window Rect Scoped Crop
                   |                                       |
                   v                                       v
          UIA Raw Elements (0 MB VRAM)         Tier 2: Scoped RapidOCR
                   |                           - CPU ONNX Execution Provider
                   |                           - Local -> Global Coordinate Map
                   |                                       |
                   |                                       v
                   |                               OCR Raw Elements
                   |                                       |
                   +-------------------+-------------------+
                                       |
                                       v
                     Tier 3: Spatial Deduplication & Merge
                     - Bounding Box Intersection & IoU (threshold=0.35)
                     - Containment Suppression (threshold=0.70)
                     - Label Enrichment (OCR text -> empty UIA control)
                                       |
                                       v
                       Normalization & 1-Based Tagging
                       - Filter degenerate/offscreen boxes (<8px, offscreen)
                       - Prioritize active window elements
                       - Cap at max_som_elements (default 60)
                       - Assign sequential IDs [#1..#N]
                                       |
                                       v
                              list[UIElement]
                                       |
                   +-------------------+-------------------+
                   |                                       |
                   v                                       v
             GhostHUD Overlay                       CompanionDock
       (sig_targets_updated [#1..#N])        (grounding_badge + thumbnail)
```

---

## 2. Component Design & Interfaces

### 2.1 Screen Capture Module (`parasite_ai/vision/capture.py`)

A high-performance screen capture utility wrapping `mss` with graceful fallbacks.

```python
class ScreenCapture:
    """Fast screen capture manager supporting mss, PIL, and synthetic fallbacks."""
    
    def __init__(self, backend: str = "mss") -> None:
        self.backend = backend
        self._sct = None
        
    def capture_screen(self, monitor_idx: int = 1) -> np.ndarray:
        """
        Captures full primary display returning BGRA or RGB numpy array.
        Gracefully falls back to PIL ImageGrab or blank synthetic frame
        if running headless or in restricted Win32 desktop sessions.
        """
        ...

    def capture_rect(self, rect: Tuple[int, int, int, int]) -> np.ndarray:
        """Captures specific bounding rectangle (x, y, width, height)."""
        ...

    @staticmethod
    def compute_frame_diff(frame_a: np.ndarray, frame_b: np.ndarray) -> float:
        """
        Calculates normalized visual frame difference ratio [0.0, 1.0].
        Downsamples 4x and computes mean absolute difference on grayscale.
        """
        ...
```

### 2.2 Data Contract: Raw Element vs `UIElement`

`parasite_ai/ui/types.py` already defines the canonical `UIElement` model:
- `id: int`: 1-based Set-of-Mark unique index `[#1..#N]`.
- `role: str`: Control category (`Button`, `Edit`, `Hyperlink`, `TabItem`, `ComboBox`, `Text`, etc.).
- `label: str`: Accessible name or recognized OCR text.
- `x, y, width, height: int`: Desktop global pixel coordinates.
- `center_x, center_y: int`: Computed click target point.
- `source: Literal["uia", "ocr", "merged", "mock"]`.
- `is_active_window: bool`: Foreground status.
- Properties: `bbox -> (x, y, w, h)`, `center -> (cx, cy)`, `control_type -> role`.

During tree walking and OCR extraction, an intermediate internal dataclass `RawElement` is used before final deduplication and 1-based indexing:

```python
@dataclass
class RawElement:
    role: str
    label: str
    x: int
    y: int
    width: int
    height: int
    center_x: int
    center_y: int
    source: str  # "uia" | "ocr"
    is_active_window: bool = True
    confidence: float = 1.0
    control_ref: Optional[Any] = None
```

### 2.3 `ScreenGrounder` Class Interface (`parasite_ai/vision/grounding.py`)

```python
class ScreenGrounder:
    """
    Hybrid UI perception engine combining Win32 UI Automation,
    scoped RapidOCR fallback, and spatial IoU deduplication.
    """

    def __init__(
        self,
        config: Optional[VisionConfig] = None,
        capturer: Optional[ScreenCapture] = None,
        ocr_engine: Optional[Any] = None,
    ) -> None:
        self.config = config or VisionConfig()
        self.capturer = capturer or ScreenCapture(backend=self.config.capture_backend)
        self._ocr_engine = ocr_engine  # Lazily instantiated if None
        self._depth_limit: int = 5
        self._min_uia_threshold: int = 6

    def ground(
        self,
        window_filter: Optional[int] = None,
        force_ocr: bool = False,
        image_override: Optional[np.ndarray] = None,
    ) -> List[UIElement]:
        """
        Executes hybrid grounding pipeline.
        1. Enumerates UIA controls from active window or window_filter HWND.
        2. Evaluates if OCR fallback is needed (< 6 UIA controls, or force_ocr=True, or ocr_only).
        3. Invokes scoped RapidOCR on active window bounds if needed.
        4. Performs spatial IoU and containment deduplication and label merging.
        5. Normalizes, filters degenerate elements, caps to max_som_elements, and assigns 1-based IDs.
        """
        ...

    def format_som_summary(self, elements: List[UIElement]) -> str:
        """
        Formats normalized UI elements into a compact Set-of-Mark table
        suitable for direct prompt injection into the DualMind cognitive pipeline.
        Example:
        [#1] Button "Search" at (340, 45) [120x32]
        [#2] Edit "Search or enter address" at (470, 45) [400x32]
        """
        ...
```

---

## 3. Detailed Algorithmic Specifications

### 3.1 Tier 1: Win32 UI Automation Tree Walk

1. **Target Window Acquisition**:
   - If `window_filter` (HWND integer) is supplied:
     `root_control = uiautomation.ControlFromHandle(window_filter)`
   - Else:
     `root_control = uiautomation.GetForegroundControl()`
   - Fallback:
     If `root_control` is `None` (headless, locked, or background execution), fallback to `uiautomation.GetRootControl()`. If still `None`, return empty list safely without exception.
2. **Active Window Bounding Rectangle**:
   - `win_rect = root_control.BoundingRectangle`
   - Store window bounds `(win_rect.left, win_rect.top, win_rect.width(), win_rect.height())`.
3. **Interactive Control Type Mapping**:
   Map UIA `ControlTypeName` to normalized role names:
   ```python
   INTERACTIVE_ROLES: Dict[str, str] = {
       "ButtonControl": "Button",
       "SplitButtonControl": "Button",
       "EditControl": "Edit",
       "HyperlinkControl": "Hyperlink",
       "TabItemControl": "TabItem",
       "ComboBoxControl": "ComboBox",
       "CheckBoxControl": "CheckBox",
       "RadioButtonControl": "RadioButton",
       "MenuItemControl": "MenuItem",
       "ListItemControl": "ListItem",
       "DocumentControl": "Document",
       "TextControl": "Text",
       "CustomControl": "Button",  # Custom controls with accessible names
   }
   ```
4. **Traversal & Filtering Criteria**:
   Traverse tree using `uiautomation.WalkControl(root_control, includeTop=False, maxDepth=self._depth_limit)`:
   - **Offscreen check**: If `control.IsOffscreen` is `True`, skip.
   - **Bounding box check**: If `rect.width() < 8` or `rect.height() < 8`, skip degenerate or invisible spacer nodes.
   - **Extreme coordinate check**: If `rect.left < -1000` or `rect.top < -1000` (minimized windows), skip.
   - **Role relevance**: If `control.ControlTypeName` not in `INTERACTIVE_ROLES`, skip (unless it's a `PaneControl` with a non-empty name and reasonable button dimensions < 300x100).
   - **Label extraction**:
     `label = (control.Name or control.AutomationId or control.HelpText or "").strip()`
     Truncate label to 80 characters.
   - **Element construction**:
     `RawElement(role=role, label=label, x=rect.left, y=rect.top, width=rect.width(), height=rect.height(), center_x=rect.xcenter(), center_y=rect.ycenter(), source="uia", is_active_window=True)`
   - **Early exit guard**: Stop traversal if UIA raw element count reaches 120 to guarantee < 15ms execution time even on complex Chromium/Electron DOM trees.

### 3.2 Tier 2: Scoped RapidOCR Fallback

1. **Trigger Condition**:
   - `self.config.grounding_mode == "ocr_only"` -> Always run OCR.
   - `self.config.grounding_mode == "hybrid"`:
     - Run OCR if `len(uia_elements) < self._min_uia_threshold` (default 6).
     - Run OCR if `force_ocr is True`.
2. **Lazy Initialization**:
   - `RapidOCR` model loading takes ~3-4 seconds on first import.
   - Instantiate `self._ocr_engine = RapidOCR()` lazily on first OCR call, caching the instance as a singleton.
3. **Region Scoping**:
   - If `image_override` is passed (e.g. from tests or capture cache), use it.
   - Otherwise capture desktop image via `self.capturer.capture_screen()`.
   - If `ocr_scoped_only` is `True` and active window bounds `(win_x, win_y, win_w, win_h)` are valid:
     Crop image to `image[win_y : win_y + win_h, win_x : win_x + win_w]`.
     Track `offset_x = win_x`, `offset_y = win_y`.
   - Else:
     Crop is entire image; `offset_x = 0`, `offset_y = 0`.
4. **Execution & Coordinate Un-scoping**:
   - Invoke `result, elapse = self._ocr_engine(crop)`.
   - If `result` is `None` or empty, return empty OCR list.
   - For each detected item `[polygon_pts, text, confidence]`:
     - If `confidence < 0.40`: skip low-confidence noise.
     - Calculate axis-aligned bounding box from 4 corner points:
       `min_x = min(pt[0] for pt in polygon_pts)`
       `max_x = max(pt[0] for pt in polygon_pts)`
       `min_y = min(pt[1] for pt in polygon_pts)`
       `max_y = max(pt[1] for pt in polygon_pts)`
     - Map to desktop global pixel space:
       `x = int(offset_x + min_x)`
       `y = int(offset_y + min_y)`
       `w = int(max_x - min_x)`
       `h = int(max_y - min_y)`
     - Filter small noise boxes: `w < 10` or `h < 8`.
     - Construct `RawElement(role="Text", label=text.strip(), x=x, y=y, width=w, height=h, center_x=x + w // 2, center_y=y + h // 2, source="ocr", confidence=float(confidence))`.

### 3.3 Tier 3: Spatial IoU & Containment Deduplication

Given lists `uia_elements` and `ocr_elements`:

1. **Overlap Mathematics**:
   For box $A = (x_a, y_a, w_a, h_a)$ and box $B = (x_b, y_b, w_b, h_b)$:
   $$\text{ix}_1 = \max(x_a, x_b), \quad \text{iy}_1 = \max(y_a, y_b)$$
   $$\text{ix}_2 = \min(x_a + w_a, x_b + w_b), \quad \text{iy}_2 = \min(y_a + h_a, y_b + h_b)$$
   $$\text{inter\_w} = \max(0, \text{ix}_2 - \text{ix}_1), \quad \text{inter\_h} = \max(0, \text{iy}_2 - \text{iy}_1)$$
   $$\text{intersection} = \text{inter\_w} \times \text{inter\_h}$$
   $$\text{area}_a = w_a \times h_a, \quad \text{area}_b = w_b \times h_b$$
   $$\text{union} = \text{area}_a + \text{area}_b - \text{intersection}$$
   $$\text{IoU} = \frac{\text{intersection}}{\text{union}} \quad (\text{if union} > 0 \text{ else } 0)$$
   $$\text{containment}_b = \frac{\text{intersection}}{\text{area}_b} \quad (\text{if } \text{area}_b > 0 \text{ else } 0)$$

2. **Deduplication Logic**:
   - Thresholds: `IOU_THRESHOLD = 0.35`, `CONTAINMENT_THRESHOLD = 0.70`.
   - Initialize `surviving_ocr: List[RawElement] = []`.
   - For each `ocr_elem` in `ocr_elements`:
     - Check overlap against all `uia_elem` in `uia_elements`:
       - If `iou >= IOU_THRESHOLD` or `containment_b >= CONTAINMENT_THRESHOLD`:
         - The OCR box is an internal or duplicate label of `uia_elem`!
         - **Label Merge**: If `uia_elem.label == ""` or `uia_elem.label.lower() in ("button", "pane", "custom")`:
           Update `uia_elem.label = ocr_elem.label`.
           Update `uia_elem.source = "merged"`.
         - **Suppress**: Do NOT add `ocr_elem` to `surviving_ocr`.
         - Break early to next `ocr_elem`.
     - If no UIA control overlaps or contains `ocr_elem`:
       - Add `ocr_elem` to `surviving_ocr`.

3. **Synthesis & Sequential Normalization**:
   - Combine `combined = uia_elements + surviving_ocr`.
   - Sort elements: Active window elements first, then top-to-bottom (`y`), then left-to-right (`x`).
   - Cap length to `self.config.max_som_elements` (default 60).
   - Re-index with sequential 1-based unique IDs: `[#1, #2, ..., #N]`.
   - Construct immutable `UIElement` instances using `UIElement.from_bbox(...)` or direct instantiation.

---

## 4. UI Layer Integration

### 4.1 Integration with `GhostHUD` (`parasite_ai/ui/ghost_hud.py`)
- Background reasoning loop calls `bridge.set_hud_targets(grounded_elements)`.
- `GhostHUD.set_targets()` receives `list[UIElement]`.
- As verified during investigation, `GhostHUD._normalize_target` accepts `UIElement` directly, maps role to high-contrast colors via `ROLE_COLOR_MAP` (`Button` -> Neon Cyan, `Edit` -> Hot Magenta, `Text`/`OCR` -> Gold Amber), and renders Set-of-Mark numbered boxes `[#1..#N]`.

### 4.2 Integration with `CompanionDock` (`parasite_ai/ui/companion_dock.py`)
- Background loop calls `bridge.notify_perception(preview_pixmap, grounded_elements)`.
- `CompanionDock.update_perception_preview(frame_data, elements)` receives the list and updates `self.grounding_badge.setText(f"Grounding: {len(elements)} Targets Active")`.

---

## 5. Automated Headless Test Strategy (`tests/test_grounding.py`)

All tests must execute cleanly in headless environments (Windows GitHub Actions / local background runs where active GUI displays may not be present).

### Test Fixtures
1. `mock_uia_tree`:
   Hierarchical mock objects implementing `ControlTypeName`, `Name`, `BoundingRectangle` (with `left, top, right, bottom, width(), height(), xcenter(), ycenter()`), `IsOffscreen`, and `GetChildren()`.
2. `mock_rapid_ocr`:
   Mock callable returning canned RapidOCR predictions `[[[[x1, y1], [x2, y2], [x3, y3], [x4, y4]], "Text", score]]`.
3. `synthetic_screen_image`:
   NumPy array / PIL Image with synthetic colored buttons and text.

### Test Matrix
| Test Case | Scenario | Expected Outcome |
|---|---|---|
| `test_grounder_init_defaults` | Initialize with default config | Correct `depth_limit`, `min_uia_threshold`, and `capture_backend` |
| `test_uia_enumeration_interactive_types` | Tree with Button, Edit, Hyperlink, ComboBox, Pane, and offscreen nodes | Only interactive onscreen controls extracted; offscreen and tiny nodes ignored |
| `test_uia_depth_limit_enforcement` | Deep tree with 10 nested levels | Traversal terminates at `depth_limit=5` without infinite recursion |
| `test_scoped_ocr_sparse_fallback` | UIA tree yields 2 controls (< 6 threshold) | RapidOCR fallback automatically triggers; returns combined list |
| `test_scoped_ocr_sufficient_uia_skips_ocr` | UIA tree yields 12 controls | RapidOCR fallback skipped in hybrid mode, preserving latency |
| `test_spatial_iou_calculation` | Identical boxes, disjoint boxes, partially overlapping boxes | Exact IoU values verified (1.0, 0.0, expected ratio) |
| `test_spatial_containment_and_label_merge` | Empty-labeled UIA button with OCR text box inside | OCR duplicate suppressed; button label updated to OCR text; source="merged" |
| `test_max_elements_capping` | 100 elements found | Output capped at `max_som_elements` (60); sequential IDs 1..60 |
| `test_window_filter_hwnd` | Specify `window_filter=12345` | Calls `ControlFromHandle(12345)` instead of `GetForegroundControl()` |
| `test_headless_resilience_screen_grab_failure` | Screen capture raises `ScreenShotError` or returns None | Grounder catches exception gracefully, returns safe fallback without crash |
| `test_ghost_hud_and_bridge_interop` | Feed grounded `UIElement` list to `UIBridge` and `GhostHUD` | `GhostHUD._targets` populated, correct colors assigned, `sig_targets_updated` emitted |
| `test_format_som_summary` | Format list of 3 elements | Returns clean markdown/tabular representation with IDs, roles, labels, and coordinates |

---

## 6. Implementation Task Breakdown for Worker

1. **Step 1**: Create `parasite_ai/vision/__init__.py` exporting `ScreenGrounder`, `ScreenCapture`, `compute_frame_diff`.
2. **Step 2**: Create `parasite_ai/vision/capture.py` implementing `ScreenCapture` with `mss` and headless fallbacks.
3. **Step 3**: Create `parasite_ai/vision/grounding.py` implementing `ScreenGrounder` with UIA tree walking, scoped RapidOCR fallback, spatial IoU deduplication, normalization, and SoM summary formatting.
4. **Step 4**: Create `tests/test_grounding.py` with the 12+ headless test cases.
5. **Step 5**: Run `uv run pytest tests/test_grounding.py` and full test suite to verify 100% pass rate.
