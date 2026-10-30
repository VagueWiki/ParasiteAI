"""
tests/test_challenger_m4_1.py - Adversarial Stress Test Suite for Screen Grounding (Milestone M4).

Challenger 1 Empirical Verification:
1. Extreme spatial IoU and containment boundary conditions (0.349 vs 0.351, 0.699 vs 0.701, concentric, zero/negative).
2. Deep UIA trees (>15 levels, 500+ controls, element count clamping).
3. RapidOCR fallback under corrupted and non-standard image arrays (1x1, black, white, 16-bit, RGBA, 2D, NaNs).
4. Degenerate Set-of-Mark tags (empty labels, non-standard control types, prompt injections, boundary dimensions).
5. Screen capture and frame diff resilience under degenerate geometry.
"""

from __future__ import annotations

import logging
from typing import Any, List, Tuple
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from parasite_ai.config import VisionConfig
from parasite_ai.ui.types import UIElement
from parasite_ai.vision.capture import ScreenCapture, compute_frame_diff
from parasite_ai.vision.grounding import (
    RawElement,
    ScreenGrounder,
    compute_containment,
    compute_iou,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Helpers & Mock Implementations
# ============================================================================

class MockRect:
    def __init__(self, left: int, top: int, width: int, height: int) -> None:
        self.left = left
        self.top = top
        self._w = width
        self._h = height

    def width(self) -> int:
        return self._w

    def height(self) -> int:
        return self._h

    def xcenter(self) -> int:
        return self.left + self._w // 2

    def ycenter(self) -> int:
        return self.top + self._h // 2


class MockControl:
    def __init__(
        self,
        name: str | None,
        ctl_type: str,
        left: int = 100,
        top: int = 100,
        width: int = 120,
        height: int = 32,
        is_offscreen: bool = False,
        auto_id: str | None = None,
        help_text: str | None = None,
    ) -> None:
        self.Name = name
        self.ControlTypeName = ctl_type
        self.BoundingRectangle = MockRect(left, top, width, height)
        self.IsOffscreen = is_offscreen
        self.AutomationId = auto_id if auto_id is not None else (f"auto_{name}" if name else "")
        self.HelpText = help_text or ""


# ============================================================================
# Dimension 1: Extreme Spatial IoU and Containment Boundary Conditions
# ============================================================================

class TestSpatialIoUAndContainmentBoundaries:
    """Stress tests for compute_iou, compute_containment, and deduplication boundaries."""

    def test_iou_threshold_boundary_0349_vs_0351(self) -> None:
        """
        ScreenGrounder.IOU_THRESHOLD is 0.35.
        Verify that boxes at IoU ~0.342 do NOT trigger IoU match,
        while boxes at IoU ~0.351 DO trigger IoU match.
        """
        grounder = ScreenGrounder()
        assert grounder.IOU_THRESHOLD == 0.35

        # Base box: (0, 0, 100, 100) -> Area = 10,000
        # Overlapping box with offset x:
        # If x=49: intersection=(51*100)=5100, union=10000+4900=14900, IoU = 5100/14900 = 0.34228 (< 0.35)
        # If x=48: intersection=(52*100)=5200, union=10000+4800=14800, IoU = 5200/14800 = 0.35135 (> 0.35)
        box_base = (0, 0, 100, 100)
        box_sub = (49, 0, 100, 100)
        box_super = (48, 0, 100, 100)

        iou_sub = compute_iou(box_base, box_sub)
        iou_super = compute_iou(box_base, box_super)

        assert iou_sub < 0.35
        assert iou_sub == pytest.approx(5100 / 14900, rel=1e-3)
        assert iou_super > 0.35
        assert iou_super == pytest.approx(5200 / 14800, rel=1e-3)

        # Test deduplication effect:
        # When IoU is 0.351, OCR element matches UIA and merges label
        uia_elem = RawElement(role="Button", label="", x=0, y=0, width=100, height=100, center_x=50, center_y=50, source="uia")
        ocr_elem_match = RawElement(role="Text", label="Save", x=48, y=0, width=100, height=100, center_x=98, center_y=50, source="ocr")
        merged = grounder._deduplicate_and_merge([uia_elem], [ocr_elem_match])
        assert len(merged) == 1
        assert merged[0].label == "Save"
        assert merged[0].source == "merged"

        # When IoU is 0.342 (and containment is 5100/10000 = 0.51 < 0.70), OCR element does NOT merge
        uia_elem2 = RawElement(role="Button", label="", x=0, y=0, width=100, height=100, center_x=50, center_y=50, source="uia")
        ocr_elem_no_match = RawElement(role="Text", label="Save", x=49, y=0, width=100, height=100, center_x=99, center_y=50, source="ocr")
        merged2 = grounder._deduplicate_and_merge([uia_elem2], [ocr_elem_no_match])
        assert len(merged2) == 2  # Both survive as distinct elements

    def test_containment_threshold_boundary_069_vs_071(self) -> None:
        """
        ScreenGrounder.CONTAINMENT_THRESHOLD is 0.70.
        Verify containment at 0.69 vs 0.71 with IoU strictly below 0.35.
        """
        grounder = ScreenGrounder()
        assert grounder.CONTAINMENT_THRESHOLD == 0.70

        # Outer box: (0, 0, 200, 200) -> Area = 40,000
        # Inner box: width=100, height=100 -> Area = 10,000
        # Placed at x=131: overlap x in [131, 200] -> width 69, intersection = 6900
        # Containment = 6900 / 10000 = 0.690 (< 0.70)
        # IoU = 6900 / (40000 + 10000 - 6900) = 6900 / 43100 = 0.160 (< 0.35)
        outer_box = (0, 0, 200, 200)
        inner_box_sub = (131, 0, 100, 100)
        inner_box_super = (129, 0, 100, 100)

        cont_sub = compute_containment(inner_box_sub, outer_box)
        cont_super = compute_containment(inner_box_super, outer_box)

        assert cont_sub == pytest.approx(0.69, rel=1e-3)
        assert cont_sub < 0.70
        assert cont_super == pytest.approx(0.71, rel=1e-3)
        assert cont_super > 0.70

        # Deduplication behavior:
        uia_outer = RawElement(role="Button", label="", x=0, y=0, width=200, height=200, center_x=100, center_y=100, source="uia")
        ocr_sub = RawElement(role="Text", label="SubLabel", x=131, y=0, width=100, height=100, center_x=181, center_y=50, source="ocr")
        res_sub = grounder._deduplicate_and_merge([uia_outer], [ocr_sub])
        assert len(res_sub) == 2  # Does NOT match, both survive

        uia_outer2 = RawElement(role="Button", label="", x=0, y=0, width=200, height=200, center_x=100, center_y=100, source="uia")
        ocr_super = RawElement(role="Text", label="SuperLabel", x=129, y=0, width=100, height=100, center_x=179, center_y=50, source="ocr")
        res_super = grounder._deduplicate_and_merge([uia_outer2], [ocr_super])
        assert len(res_super) == 1  # Matches containment threshold, merged!
        assert res_super[0].label == "SuperLabel"

    def test_concentric_boxes(self) -> None:
        """Concentric inner box perfectly inside outer box with identical centers."""
        # Outer: center (150, 150), size 100x100
        outer = (100, 100, 100, 100)
        # Inner: center (150, 150), size 40x40 -> Area 1600
        inner = (130, 130, 40, 40)

        assert compute_containment(inner, outer) == pytest.approx(1.0)
        assert compute_iou(inner, outer) == pytest.approx(1600 / 10000)

        # Reversed containment: outer inside inner is 1600 / 10000 = 0.16
        assert compute_containment(outer, inner) == pytest.approx(0.16)

    def test_zero_area_and_negative_dimension_boxes(self) -> None:
        """Boxes with 0 width, 0 height, or negative dimensions must not cause ZeroDivisionError."""
        normal_box = (10, 10, 100, 100)
        zero_w = (10, 10, 0, 50)
        zero_h = (10, 10, 50, 0)
        zero_both = (10, 10, 0, 0)
        neg_dim = (10, 10, -50, 50)
        neg_both = (10, 10, -20, -20)

        for b in [zero_w, zero_h, zero_both, neg_dim, neg_both]:
            assert compute_iou(b, normal_box) == 0.0
            assert compute_iou(normal_box, b) == 0.0
            assert compute_iou(b, b) == 0.0
            assert compute_containment(b, normal_box) == 0.0
            assert compute_containment(normal_box, b) == 0.0

    def test_multi_monitor_negative_coordinates(self) -> None:
        """Coordinates on secondary monitors placed to the left or top of primary display."""
        # Monitor 2 at x: [-1920, 0]
        box_left1 = (-800, 200, 100, 50)
        box_left2 = (-750, 200, 100, 50)

        # Overlap x in [-750, -700] -> width 50, height 50 -> intersection 2500
        # Union = 5000 + 5000 - 2500 = 7500. IoU = 1/3
        iou = compute_iou(box_left1, box_left2)
        assert iou == pytest.approx(1.0 / 3.0)

        # Negative containment
        inner_neg = (-780, 210, 40, 20)  # entirely inside box_left1
        assert compute_containment(inner_neg, box_left1) == pytest.approx(1.0)


# ============================================================================
# Dimension 2: Deep UIA Trees and Massive Element Blowout
# ============================================================================

class TestUIATreeDepthAndElementBlowout:
    """Stress tests UIA tree recursion depth, element cap limits, and performance under massive trees."""

    def test_deep_tree_depth_over_15_levels(self) -> None:
        """UIA tree walk with 20 levels of nesting does not stack overflow or exceed depth limit."""
        grounder = ScreenGrounder()
        assert grounder._depth_limit == 5

        # Generate a 20-level deep mock tree: depth 1 to 20
        controls_by_depth: List[Tuple[MockControl, int]] = []
        for d in range(1, 21):
            ctrl = MockControl(
                name=f"Level_{d}_Btn",
                ctl_type="ButtonControl",
                left=100 + d * 5,
                top=100 + d * 5,
                width=100,
                height=30,
            )
            controls_by_depth.append((ctrl, d))

        mock_auto = MagicMock()
        mock_auto.GetForegroundControl.return_value = MockControl("DeepApp", "WindowControl", 0, 0, 1000, 1000)
        # WalkControl should be called with maxDepth=5
        mock_auto.WalkControl.return_value = controls_by_depth

        with patch.dict("sys.modules", {"uiautomation": mock_auto}):
            elements = grounder.ground()

        mock_auto.WalkControl.assert_called_once()
        # Ensure maxDepth argument passed to WalkControl matches _depth_limit
        _, kwargs = mock_auto.WalkControl.call_args
        assert kwargs.get("maxDepth") == 5

        # All yielded elements were processed safely
        assert len(elements) == 20
        assert elements[0].id == 1
        assert elements[-1].id == 20

    def test_massive_tree_blowout_600_controls(self) -> None:
        """
        Tree with 600+ controls must be safely clamped by raw_elements limit (120)
        and max_som_elements (default 60).
        """
        cfg = VisionConfig(max_som_elements=60)
        grounder = ScreenGrounder(config=cfg)

        # 600 valid button controls
        massive_controls = [
            (
                MockControl(
                    name=f"Button_{i}",
                    ctl_type="ButtonControl",
                    left=50 + (i % 10) * 80,
                    top=50 + (i // 10) * 20,
                    width=75,
                    height=18,
                ),
                1,
            )
            for i in range(600)
        ]

        mock_auto = MagicMock()
        mock_auto.GetForegroundControl.return_value = MockControl("MassiveApp", "WindowControl", 0, 0, 1920, 1080)
        mock_auto.WalkControl.return_value = massive_controls

        with patch.dict("sys.modules", {"uiautomation": mock_auto}):
            elements = grounder.ground()

        # Must be strictly clamped to max_som_elements = 60
        assert len(elements) == 60
        # Sequential IDs 1..60
        assert [e.id for e in elements] == list(range(1, 61))

    def test_infinite_generator_control_tree_terminates_early(self) -> None:
        """WalkControl returning an infinite stream of nodes terminates at raw_elements cap (120)."""
        grounder = ScreenGrounder()

        def infinite_controls():
            idx = 0
            while True:
                yield (
                    MockControl(
                        name=f"Infinite_{idx}",
                        ctl_type="ButtonControl",
                        left=50,
                        top=50 + idx * 10,
                        width=100,
                        height=20,
                    ),
                    1,
                )
                idx += 1

        mock_auto = MagicMock()
        mock_auto.GetForegroundControl.return_value = MockControl("App", "WindowControl", 0, 0, 1920, 1080)
        mock_auto.WalkControl.return_value = infinite_controls()

        with patch.dict("sys.modules", {"uiautomation": mock_auto}):
            raw_elements, _ = grounder._walk_uia_tree()

        # Must break at 120 elements
        assert len(raw_elements) == 120

    def test_null_or_exceptional_root_control_handling(self) -> None:
        """When GetForegroundControl raises an exception or returns None, handles gracefully."""
        grounder = ScreenGrounder()

        mock_auto = MagicMock()
        mock_auto.GetForegroundControl.side_effect = RuntimeError("Win32 UIA COM marshaling failure")
        mock_auto.GetRootControl.return_value = None

        with patch.dict("sys.modules", {"uiautomation": mock_auto}):
            elements = grounder.ground()

        assert elements == []


# ============================================================================
# Dimension 3: RapidOCR Fallback Under Corrupted and Non-Standard Image Arrays
# ============================================================================

class TestRapidOCRCorruptedAndNonStandardImages:
    """Stress tests RapidOCR and screen perception under hostile and unusual image arrays."""

    def test_ocr_with_1x1_image(self) -> None:
        """1x1 image array passed to grounder does not crash."""
        grounder = ScreenGrounder(config=VisionConfig(grounding_mode="ocr_only"))
        tiny_frame = np.zeros((1, 1, 3), dtype=np.uint8)

        # Mock OCR engine returning empty for tiny image
        mock_ocr = MagicMock(return_value=([], 0.001))
        grounder._ocr_engine = mock_ocr

        elements = grounder.ground(image_override=tiny_frame)
        assert elements == []

    def test_ocr_with_pure_black_and_pure_white_frames(self) -> None:
        """Pure black and pure white screens (no text detected) return empty list cleanly."""
        grounder = ScreenGrounder(config=VisionConfig(grounding_mode="ocr_only"))
        mock_ocr = MagicMock(return_value=([], 0.01))
        grounder._ocr_engine = mock_ocr

        black_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        elements_black = grounder.ground(image_override=black_frame)
        assert elements_black == []

        white_frame = np.full((1080, 1920, 3), 255, dtype=np.uint8)
        elements_white = grounder.ground(image_override=white_frame)
        assert elements_white == []

    def test_ocr_with_16bit_and_float32_nan_arrays(self) -> None:
        """16-bit uint16 and float32 image arrays with NaNs do not cause unhandled crashes."""
        grounder = ScreenGrounder(config=VisionConfig(grounding_mode="ocr_only"))
        mock_ocr = MagicMock(return_value=([], 0.01))
        grounder._ocr_engine = mock_ocr

        uint16_frame = np.zeros((100, 100, 3), dtype=np.uint16)
        elements_16 = grounder.ground(image_override=uint16_frame)
        assert elements_16 == []

        float_nan_frame = np.full((100, 100, 3), np.nan, dtype=np.float32)
        elements_nan = grounder.ground(image_override=float_nan_frame)
        assert elements_nan == []

    def test_ocr_with_rgba_4_channels_and_2d_grayscale(self) -> None:
        """4-channel RGBA and 2-channel/grayscale arrays handled without dimension crash."""
        grounder = ScreenGrounder(config=VisionConfig(grounding_mode="ocr_only"))
        mock_ocr = MagicMock(return_value=([], 0.01))
        grounder._ocr_engine = mock_ocr

        rgba_frame = np.zeros((100, 100, 4), dtype=np.uint8)
        elements_rgba = grounder.ground(image_override=rgba_frame)
        assert elements_rgba == []

        gray_frame = np.zeros((100, 100), dtype=np.uint8)
        elements_gray = grounder.ground(image_override=gray_frame)
        assert elements_gray == []

    def test_ocr_engine_raising_exception_resilience(self) -> None:
        """When RapidOCR engine raises an internal ONNX or OpenCV error, returns empty gracefully."""
        grounder = ScreenGrounder(config=VisionConfig(grounding_mode="ocr_only"))
        mock_ocr = MagicMock(side_effect=RuntimeError("ONNX Runtime execution provider crashed"))
        grounder._ocr_engine = mock_ocr

        dummy_frame = np.zeros((100, 100, 3), dtype=np.uint8)
        elements = grounder.ground(image_override=dummy_frame)
        assert elements == []

    def test_ocr_malformed_box_results(self) -> None:
        """RapidOCR returning malformed, empty, or corrupted bounding polygon structures."""
        grounder = ScreenGrounder(config=VisionConfig(grounding_mode="ocr_only"))

        corrupted_ocr_return = (
            [
                # Malformed: empty item
                [],
                # Malformed: only 1 element
                ["Some text"],
                # Malformed: confidence is string
                [[[10, 10], [50, 10], [50, 30], [10, 30]], "BadConf", "not_a_float"],
                # Malformed: points polygon has wrong shape
                [[], "EmptyPoints", 0.9],
                # Normal valid element
                [[[100, 100], [200, 100], [200, 140], [100, 140]], "ValidText", 0.95],
                # Below confidence threshold (< 0.40)
                [[[300, 100], [400, 100], [400, 140], [300, 140]], "LowConfText", 0.35],
                # Below size threshold (< 10 width or < 8 height)
                [[[500, 100], [505, 100], [505, 105], [500, 105]], "Tiny", 0.99],
            ],
            0.05,
        )

        mock_ocr = MagicMock(return_value=corrupted_ocr_return)
        grounder._ocr_engine = mock_ocr
        dummy_frame = np.zeros((600, 800, 3), dtype=np.uint8)

        elements = grounder.ground(image_override=dummy_frame)

        # Only ValidText should survive!
        assert len(elements) == 1
        assert elements[0].label == "ValidText"
        assert elements[0].source == "ocr"


# ============================================================================
# Dimension 4: Degenerate Set-of-Mark Tags and Hostile Inputs
# ============================================================================

class TestDegenerateSetOfMarkTags:
    """Stress tests missing labels, long strings, injection payloads, and unusual control roles."""

    def test_missing_or_empty_labels_fallback_hierarchy(self) -> None:
        """
        Verify label resolution:
        1. Name -> 2. HelpText -> 3. AutomationId (if not starting with auto_) -> 4. Empty string.
        """
        grounder = ScreenGrounder(config=VisionConfig(grounding_mode="uia_only"))

        controls = [
            # 1. Normal Name
            (MockControl(name="Submit", ctl_type="ButtonControl"), 1),
            # 2. Empty Name, has HelpText
            (MockControl(name="", ctl_type="ButtonControl", help_text="Click to proceed"), 1),
            # 3. None Name, has explicit AutomationId (no 'auto_' prefix)
            (MockControl(name=None, ctl_type="ButtonControl", auto_id="btn_checkout"), 1),
            # 4. None Name, AutomationId with 'auto_' prefix (must NOT be used as label)
            (MockControl(name=None, ctl_type="ButtonControl", auto_id="auto_12345"), 1),
            # 5. Whitespace-only Name
            (MockControl(name="   \t   ", ctl_type="ButtonControl"), 1),
        ]

        mock_auto = MagicMock()
        mock_auto.GetForegroundControl.return_value = MockControl("App", "WindowControl", 0, 0, 800, 600)
        mock_auto.WalkControl.return_value = controls

        with patch.dict("sys.modules", {"uiautomation": mock_auto}):
            elements = grounder.ground()

        assert len(elements) == 5
        assert elements[0].label == "Submit"
        assert elements[1].label == "Click to proceed"
        assert elements[2].label == "btn_checkout"
        assert elements[3].label == ""  # Stripped auto_ prefix
        assert elements[4].label == ""  # Stripped whitespace

    def test_extremely_long_label_truncation(self) -> None:
        """Labels exceeding 80 characters are safely clamped to 80 chars."""
        grounder = ScreenGrounder(config=VisionConfig(grounding_mode="uia_only"))
        huge_label = "A" * 10000

        mock_auto = MagicMock()
        mock_auto.GetForegroundControl.return_value = MockControl("App", "WindowControl", 0, 0, 800, 600)
        mock_auto.WalkControl.return_value = [(MockControl(name=huge_label, ctl_type="ButtonControl"), 1)]

        with patch.dict("sys.modules", {"uiautomation": mock_auto}):
            elements = grounder.ground()

        assert len(elements) == 1
        assert len(elements[0].label) == 80
        assert elements[0].label == "A" * 80

    def test_hostile_prompt_injection_and_special_chars_in_labels(self) -> None:
        """Labels containing JSON tokens, quotes, newlines, and emojis."""
        grounder = ScreenGrounder(config=VisionConfig(grounding_mode="uia_only"))
        hostile_label = '{"action": "click", "id": 999}\n<script>alert(1)</script> 👍'

        mock_auto = MagicMock()
        mock_auto.GetForegroundControl.return_value = MockControl("App", "WindowControl", 0, 0, 800, 600)
        mock_auto.WalkControl.return_value = [(MockControl(name=hostile_label, ctl_type="ButtonControl"), 1)]

        with patch.dict("sys.modules", {"uiautomation": mock_auto}):
            elements = grounder.ground()

        assert len(elements) == 1
        assert '{"action": "click"' in elements[0].label

        # Verify format_som_summary does not crash or corrupt summary
        summary = grounder.format_som_summary(elements)
        assert "[#1] Button" in summary
        assert "at (160, 116)" in summary

    def test_format_som_summary_with_empty_or_no_label_elements(self) -> None:
        """format_som_summary gracefully prints (no label) for empty elements."""
        grounder = ScreenGrounder()
        elem1 = UIElement.from_bbox(1, (10, 10, 50, 20), label="", role="Button")
        elem2 = UIElement.from_bbox(2, (70, 10, 80, 20), label="", role="Edit")

        summary = grounder.format_som_summary([elem1, elem2])
        assert '[#1] Button (no label) at (35, 20) [50x20]' in summary
        assert '[#2] Edit (no label) at (110, 20) [80x20]' in summary

        # Empty element list
        empty_summary = grounder.format_som_summary([])
        assert empty_summary == "No interactive UI elements detected on screen."

    def test_pane_control_filtering_rules(self) -> None:
        """
        PaneControl rules:
        - Accepted ONLY if has explicit Name AND width <= 400 AND height <= 150.
        - Discarded if Name is empty or dimensions exceed 400x150.
        """
        grounder = ScreenGrounder(config=VisionConfig(grounding_mode="uia_only"))

        controls = [
            # Valid Pane: has name, 300x50 <= 400x150
            (MockControl(name="MiniTabPane", ctl_type="PaneControl", width=300, height=50), 1),
            # Invalid Pane: has name, but width=500 > 400
            (MockControl(name="GiantContainer", ctl_type="PaneControl", width=500, height=100), 1),
            # Invalid Pane: has name, but height=200 > 150
            (MockControl(name="TallContainer", ctl_type="PaneControl", width=300, height=200), 1),
            # Invalid Pane: no name, 200x50
            (MockControl(name="", ctl_type="PaneControl", width=200, height=50), 1),
        ]

        mock_auto = MagicMock()
        mock_auto.GetForegroundControl.return_value = MockControl("App", "WindowControl", 0, 0, 800, 600)
        mock_auto.WalkControl.return_value = controls

        with patch.dict("sys.modules", {"uiautomation": mock_auto}):
            elements = grounder.ground()

        assert len(elements) == 1
        assert elements[0].label == "MiniTabPane"
        assert elements[0].role == "Button"

    def test_dimension_and_coordinate_boundaries(self) -> None:
        """
        Size filter: w < 8 or h < 8 are skipped. w=8, h=8 are accepted.
        Coordinate filter: left < -1000 or top < -1000 are skipped. -1000 is accepted.
        """
        grounder = ScreenGrounder(config=VisionConfig(grounding_mode="uia_only"))

        controls = [
            # Accepted exact size boundaries: 8x8
            (MockControl(name="Valid8x8", ctl_type="ButtonControl", left=10, top=10, width=8, height=8), 1),
            # Rejected size: 7x8
            (MockControl(name="BadWidth7", ctl_type="ButtonControl", left=20, top=10, width=7, height=8), 1),
            # Rejected size: 8x7
            (MockControl(name="BadHeight7", ctl_type="ButtonControl", left=30, top=10, width=8, height=7), 1),
            # Accepted coordinate boundary: negative secondary-monitor coords (left=-1000)
            (MockControl(name="ValidCoord1000", ctl_type="ButtonControl", left=-1000, top=100, width=50, height=20), 1),
            # Accepted: left=-1001 is still a legitimate secondary-monitor position
            (MockControl(name="ValidCoord1001", ctl_type="ButtonControl", left=-1001, top=100, width=50, height=20), 1),
            # Rejected: Win32 minimized-window sentinel coordinates (-32000)
            (MockControl(name="MinimizedCoord", ctl_type="ButtonControl", left=-32000, top=100, width=50, height=20), 1),
        ]

        mock_auto = MagicMock()
        mock_auto.GetForegroundControl.return_value = MockControl("App", "WindowControl", 0, 0, 800, 600)
        mock_auto.WalkControl.return_value = controls

        with patch.dict("sys.modules", {"uiautomation": mock_auto}):
            elements = grounder.ground()

        labels = [e.label for e in elements]
        assert "Valid8x8" in labels
        assert "ValidCoord1000" in labels
        assert "BadWidth7" not in labels
        assert "BadHeight7" not in labels
        assert "ValidCoord1001" in labels
        assert "MinimizedCoord" not in labels


# ============================================================================
# Dimension 5: Screen Capture & Frame Diff Adversarial Tests
# ============================================================================

class TestScreenCaptureAndFrameDiffAdversarial:
    """Stress tests for ScreenCapture and compute_frame_diff."""

    def test_compute_frame_diff_degenerate_inputs(self) -> None:
        """compute_frame_diff handles None, zero-size, shape mismatches, and 1x1 arrays."""
        # None
        assert compute_frame_diff(None, None) == 0.0
        assert compute_frame_diff(np.zeros((10, 10, 3)), None) == 0.0

        # Shape mismatch
        assert compute_frame_diff(np.zeros((10, 10, 3)), np.zeros((20, 20, 3))) == 1.0

        # Empty / zero size
        assert compute_frame_diff(np.zeros((0, 0, 3)), np.zeros((0, 0, 3))) == 0.0

        # 1x1 arrays: identical vs different
        f1 = np.array([[[100, 100, 100]]], dtype=np.uint8)
        f2 = np.array([[[100, 100, 100]]], dtype=np.uint8)
        assert compute_frame_diff(f1, f2) == 0.0

        f3 = np.array([[[200, 200, 200]]], dtype=np.uint8)
        assert compute_frame_diff(f1, f3) == 1.0

    def test_screen_capture_rect_out_of_bounds_and_zero_dimensions(self) -> None:
        """capture_rect handles negative/zero dimensions and out-of-screen crops."""
        capturer = ScreenCapture(backend="pillow")

        # Zero or negative width/height
        r_zero = capturer.capture_rect((10, 10, 0, 50))
        assert r_zero.shape == (1, 1, 3)

        r_neg = capturer.capture_rect((10, 10, -100, -50))
        assert r_neg.shape == (1, 1, 3)

        # Out-of-bounds coordinates
        with patch.object(capturer, "capture_screen", return_value=np.zeros((600, 800, 3), dtype=np.uint8)):
            # Completely beyond right/bottom
            r_oob = capturer.capture_rect((1000, 1000, 100, 100))
            assert r_oob.shape == (100, 100, 3)
            assert np.all(r_oob == 0)

    def test_screen_capture_monitor_idx_fallback(self) -> None:
        """ScreenCapture with out-of-range monitor index does not crash."""
        capturer = ScreenCapture(backend="mss")
        # Mock mss with 1 monitor
        mock_sct = MagicMock()
        mock_sct.monitors = [{"top": 0, "left": 0, "width": 800, "height": 600}]
        mock_img = MagicMock()
        mock_img.rgb = bytes(800 * 600 * 3)
        mock_img.width = 800
        mock_img.height = 600
        mock_sct.grab.return_value = mock_img
        capturer._sct = mock_sct

        frame = capturer.capture_screen(monitor_idx=999)
        assert frame.shape == (600, 800, 3)
        mock_sct.grab.assert_called_with(mock_sct.monitors[0])


# ============================================================================
# Dimension 6: Concurrency and Scoping Boundaries
# ============================================================================

class TestConcurrencyAndScopingBoundaries:
    """Stress tests concurrent ground() execution and extreme window_rect scoping."""

    def test_multiple_ocr_overlapping_single_uia(self) -> None:
        """When multiple OCR texts fall inside a single UIA container, the first merges and duplicates drop."""
        grounder = ScreenGrounder()
        uia_elem = RawElement(role="Button", label="", x=100, y=100, width=200, height=100, center_x=200, center_y=150, source="uia")

        # Two OCR elements inside the same button
        ocr_1 = RawElement(role="Text", label="PrimaryText", x=110, y=110, width=80, height=30, center_x=150, center_y=125, source="ocr")
        ocr_2 = RawElement(role="Text", label="SecondaryText", x=110, y=150, width=80, height=30, center_x=150, center_y=165, source="ocr")

        merged = grounder._deduplicate_and_merge([uia_elem], [ocr_1, ocr_2])
        # Only 1 element survives (UIA), adopting the first OCR's label
        assert len(merged) == 1
        assert merged[0].label == "PrimaryText"
        assert merged[0].source == "merged"

    def test_sorting_order_active_vs_inactive_window(self) -> None:
        """Elements from active window strictly precede inactive window elements, then sorted by (y, x)."""
        grounder = ScreenGrounder()

        raw = [
            RawElement(role="Button", label="Inactive_Top", x=10, y=10, width=50, height=20, center_x=35, center_y=20, source="uia", is_active_window=False),
            RawElement(role="Button", label="Active_Bottom", x=10, y=500, width=50, height=20, center_x=35, center_y=510, source="uia", is_active_window=True),
            RawElement(role="Button", label="Active_Top_Right", x=200, y=100, width=50, height=20, center_x=225, center_y=110, source="uia", is_active_window=True),
            RawElement(role="Button", label="Active_Top_Left", x=50, y=100, width=50, height=20, center_x=75, center_y=110, source="uia", is_active_window=True),
        ]

        normalized = grounder._normalize_elements(raw)
        labels = [e.label for e in normalized]
        # Active window elements first:
        # y=100, x=50 (Active_Top_Left)
        # y=100, x=200 (Active_Top_Right)
        # y=500, x=10 (Active_Bottom)
        # Inactive window element last:
        # y=10, x=10 (Inactive_Top)
        assert labels == ["Active_Top_Left", "Active_Top_Right", "Active_Bottom", "Inactive_Top"]

    def test_scoped_ocr_extreme_window_rects(self) -> None:
        """Scoping logic handles negative, out-of-screen, and zero-dimension window_rects."""
        cfg = VisionConfig(ocr_scoped_only=True)
        grounder = ScreenGrounder(config=cfg)

        mock_ocr = MagicMock(return_value=([], 0.01))
        grounder._ocr_engine = mock_ocr
        dummy_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

        # 1. Negative window rect: (-500, -200, 400, 300) -> does not crash
        res_neg = grounder._run_scoped_ocr(window_rect=(-500, -200, 400, 300), image_override=dummy_frame)
        assert res_neg == []

        # 2. Giant out-of-screen window rect: (5000, 5000, 1000, 1000)
        res_giant = grounder._run_scoped_ocr(window_rect=(5000, 5000, 1000, 1000), image_override=dummy_frame)
        assert res_giant == []

        # 3. Tiny/zero-dimension window rect: (100, 100, 10, 10) -> falls back to full_frame
        res_tiny = grounder._run_scoped_ocr(window_rect=(100, 100, 10, 10), image_override=dummy_frame)
        assert res_tiny == []

    def test_concurrent_grounding_multithreaded_hammer(self) -> None:
        """Concurrent grounding calls from 10 threads do not cause race conditions or state corruption."""
        import concurrent.futures

        grounder = ScreenGrounder(config=VisionConfig(grounding_mode="uia_only"))

        mock_auto = MagicMock()
        mock_auto.GetForegroundControl.return_value = MockControl("App", "WindowControl", 0, 0, 800, 600)
        mock_auto.WalkControl.return_value = [
            (MockControl(name=f"Btn_{i}", ctl_type="ButtonControl", left=10, top=10 + i * 25, width=100, height=20), 1)
            for i in range(10)
        ]

        def call_ground(seed: int) -> int:
            with patch.dict("sys.modules", {"uiautomation": mock_auto}):
                elems = grounder.ground()
                return len(elems)

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(call_ground, i) for i in range(25)]
            results = [f.result(timeout=5.0) for f in futures]

        assert all(r == 10 for r in results)
