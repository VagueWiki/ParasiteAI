"""
tests/test_grounding.py - Automated Unit & Integration Tests for Screen Grounding.

Tests UI Automation tree walking, scoped RapidOCR fallback, spatial IoU/containment
deduplication, degenerate box filtering, headless resilience, and UI interop.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from parasite_ai.config import VisionConfig
from parasite_ai.ui.bridge import UIBridge
from parasite_ai.ui.ghost_hud import GhostHUD
from parasite_ai.ui.types import UIElement
from parasite_ai.vision.capture import ScreenCapture, compute_frame_diff
from parasite_ai.vision.grounding import (
    RawElement,
    ScreenGrounder,
    compute_containment,
    compute_iou,
)


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
        name: str,
        ctl_type: str,
        left: int = 100,
        top: int = 100,
        width: int = 120,
        height: int = 32,
        is_offscreen: bool = False,
    ) -> None:
        self.Name = name
        self.ControlTypeName = ctl_type
        self.BoundingRectangle = MockRect(left, top, width, height)
        self.IsOffscreen = is_offscreen
        self.AutomationId = f"auto_{name}"
        self.HelpText = ""


def test_grounder_init_defaults() -> None:
    grounder = ScreenGrounder()
    assert grounder.config.grounding_mode == "hybrid"
    assert grounder.config.max_som_elements == 60
    assert grounder._depth_limit == 5
    assert grounder._min_uia_threshold == 6


def test_spatial_iou_calculation() -> None:
    # Identical boxes
    box_a = (10, 10, 100, 50)
    assert compute_iou(box_a, box_a) == pytest.approx(1.0)

    # Completely disjoint boxes
    box_b = (200, 200, 50, 50)
    assert compute_iou(box_a, box_b) == 0.0

    # Partially overlapping boxes:
    # Box 1: (0, 0, 10, 10) area = 100
    # Box 2: (5, 0, 10, 10) area = 100
    # Intersection: (5, 0, 5, 10) area = 50
    # Union: 100 + 100 - 50 = 150
    # IoU = 50 / 150 = 1/3
    box1 = (0, 0, 10, 10)
    box2 = (5, 0, 10, 10)
    assert compute_iou(box1, box2) == pytest.approx(1.0 / 3.0)


def test_spatial_containment_calculation() -> None:
    # Inner box fully contained in outer box
    inner = (20, 20, 30, 30)  # area = 900
    outer = (10, 10, 100, 100)  # contains inner completely
    assert compute_containment(inner, outer) == pytest.approx(1.0)

    # Disjoint boxes
    disjoint = (200, 200, 50, 50)
    assert compute_containment(inner, disjoint) == 0.0

    # Zero size box
    zero_box = (0, 0, 0, 0)
    assert compute_containment(zero_box, outer) == 0.0


def test_uia_enumeration_interactive_types() -> None:
    cfg = VisionConfig(grounding_mode="uia_only")
    grounder = ScreenGrounder(config=cfg)

    controls = [
        (MockControl("Submit", "ButtonControl", 50, 50, 100, 40), 1),
        (MockControl("Username", "EditControl", 50, 100, 200, 30), 1),
        (MockControl("Forgot Password", "HyperlinkControl", 50, 140, 120, 20), 1),
        (MockControl("Invisible", "ButtonControl", 50, 180, 100, 40, is_offscreen=True), 1),
        (MockControl("TinySpacer", "ButtonControl", 50, 230, 4, 4), 1),  # Degenerate
        (MockControl("IgnoredWindow", "WindowControl", 0, 0, 800, 600), 1),
    ]

    mock_auto = MagicMock()
    mock_auto.GetForegroundControl.return_value = MockControl("MainWindow", "WindowControl", 0, 0, 800, 600)
    mock_auto.WalkControl.return_value = controls

    with patch.dict("sys.modules", {"uiautomation": mock_auto}):
        elements = grounder.ground()

    assert len(elements) == 3
    assert elements[0].label == "Submit"
    assert elements[0].role == "Button"
    assert elements[1].label == "Username"
    assert elements[1].role == "Edit"
    assert elements[2].label == "Forgot Password"
    assert elements[2].role == "Hyperlink"


def test_scoped_ocr_sparse_fallback() -> None:
    cfg = VisionConfig(grounding_mode="hybrid")
    grounder = ScreenGrounder(config=cfg)

    # Only 2 UIA controls (< min_uia_threshold of 6)
    uia_controls = [
        (MockControl("OK", "ButtonControl", 50, 50, 80, 30), 1),
        (MockControl("Cancel", "ButtonControl", 140, 50, 80, 30), 1),
    ]

    mock_auto = MagicMock()
    mock_auto.GetForegroundControl.return_value = MockControl("App", "WindowControl", 0, 0, 800, 600)
    mock_auto.WalkControl.return_value = uia_controls

    # Mock OCR returning 2 text boxes
    mock_ocr = MagicMock()
    # Format: [[[x1,y1],[x2,y2],[x3,y3],[x4,y4]], text, confidence]
    mock_ocr.return_value = (
        [
            [[[300, 100], [400, 100], [400, 130], [300, 130]], "Canvas Button", 0.95],
            [[[300, 150], [450, 150], [450, 180], [300, 180]], "Game Menu", 0.88],
        ],
        0.05,
    )
    grounder._ocr_engine = mock_ocr

    # Provide synthetic screen image
    dummy_frame = np.zeros((600, 800, 3), dtype=np.uint8)

    with patch.dict("sys.modules", {"uiautomation": mock_auto}):
        elements = grounder.ground(image_override=dummy_frame)

    assert len(elements) == 4
    labels = [e.label for e in elements]
    assert "OK" in labels
    assert "Cancel" in labels
    assert "Canvas Button" in labels
    assert "Game Menu" in labels


def test_scoped_ocr_sufficient_uia_skips_ocr() -> None:
    cfg = VisionConfig(grounding_mode="hybrid")
    grounder = ScreenGrounder(config=cfg)

    # 8 UIA controls (>= 6 threshold)
    uia_controls = [(MockControl(f"Btn_{i}", "ButtonControl", 50, 40 * i, 100, 30), 1) for i in range(8)]

    mock_auto = MagicMock()
    mock_auto.GetForegroundControl.return_value = MockControl("App", "WindowControl", 0, 0, 800, 600)
    mock_auto.WalkControl.return_value = uia_controls

    mock_ocr = MagicMock()
    grounder._ocr_engine = mock_ocr

    with patch.dict("sys.modules", {"uiautomation": mock_auto}):
        elements = grounder.ground()

    assert len(elements) == 8
    # OCR should NOT have been invoked
    mock_ocr.assert_not_called()


def test_spatial_containment_and_label_merge() -> None:
    cfg = VisionConfig(grounding_mode="hybrid")
    grounder = ScreenGrounder(config=cfg)

    # UIA button has empty or generic label "button"
    uia_controls = [
        (MockControl("", "ButtonControl", 100, 100, 120, 40), 1),
    ]

    mock_auto = MagicMock()
    mock_auto.GetForegroundControl.return_value = MockControl("App", "WindowControl", 0, 0, 800, 600)
    mock_auto.WalkControl.return_value = uia_controls

    # OCR detected text "Download" right inside the button: (110, 110, 80, 20)
    mock_ocr = MagicMock()
    mock_ocr.return_value = (
        [
            [[[110, 110], [190, 110], [190, 130], [110, 130]], "Download", 0.96],
        ],
        0.02,
    )
    grounder._ocr_engine = mock_ocr
    dummy_frame = np.zeros((600, 800, 3), dtype=np.uint8)

    with patch.dict("sys.modules", {"uiautomation": mock_auto}):
        elements = grounder.ground(image_override=dummy_frame)

    # Should have merged OCR label into the UIA element and suppressed the duplicate OCR element!
    assert len(elements) == 1
    assert elements[0].label == "Download"
    assert elements[0].source == "merged"
    assert elements[0].role == "Button"


def test_max_elements_capping() -> None:
    cfg = VisionConfig(max_som_elements=10, grounding_mode="uia_only")
    grounder = ScreenGrounder(config=cfg)

    # 30 UIA controls
    uia_controls = [(MockControl(f"Btn_{i}", "ButtonControl", 50, 20 * i, 100, 15), 1) for i in range(30)]

    mock_auto = MagicMock()
    mock_auto.GetForegroundControl.return_value = MockControl("App", "WindowControl", 0, 0, 800, 600)
    mock_auto.WalkControl.return_value = uia_controls

    with patch.dict("sys.modules", {"uiautomation": mock_auto}):
        elements = grounder.ground()

    assert len(elements) == 10
    # Sequential 1-based IDs
    for idx, elem in enumerate(elements, start=1):
        assert elem.id == idx


def test_window_filter_hwnd() -> None:
    cfg = VisionConfig(grounding_mode="uia_only")
    grounder = ScreenGrounder(config=cfg)

    mock_auto = MagicMock()
    mock_auto.ControlFromHandle.return_value = MockControl("TargetApp", "WindowControl", 100, 100, 500, 400)
    mock_auto.WalkControl.return_value = [
        (MockControl("Save", "ButtonControl", 120, 120, 80, 30), 1),
    ]

    with patch.dict("sys.modules", {"uiautomation": mock_auto}):
        elements = grounder.ground(window_filter=998877)

    mock_auto.ControlFromHandle.assert_called_once_with(998877)
    assert len(elements) == 1
    assert elements[0].label == "Save"


def test_headless_resilience_screen_grab_failure() -> None:
    capturer = ScreenCapture(backend="mss")
    # Simulate screen capture failure
    with patch.object(capturer, "capture_screen", side_effect=OSError("No video display available")):
        grounder = ScreenGrounder(capturer=capturer)
        # Should not crash; returns empty or UIA-only list gracefully
        res = grounder.ground(force_ocr=True)
        assert isinstance(res, list)


def test_format_som_summary() -> None:
    grounder = ScreenGrounder()
    elements = [
        UIElement.from_bbox(1, (100, 200, 80, 30), label="Search", role="Button"),
        UIElement.from_bbox(2, (200, 200, 300, 30), label="Enter URL", role="Edit"),
    ]
    summary = grounder.format_som_summary(elements)
    assert "[#1] Button \"Search\" at (140, 215) [80x30]" in summary
    assert "[#2] Edit \"Enter URL\" at (350, 215) [300x30]" in summary


def test_compute_frame_diff() -> None:
    frame1 = np.zeros((100, 100, 3), dtype=np.uint8)
    frame2 = np.zeros((100, 100, 3), dtype=np.uint8)

    # Identical frames -> diff 0.0
    assert compute_frame_diff(frame1, frame2) == 0.0

    # Inverted frame -> diff 1.0
    frame_inv = np.full((100, 100, 3), 255, dtype=np.uint8)
    assert compute_frame_diff(frame1, frame_inv) == 1.0

    # Noise below channel threshold (<= 15) -> diff 0.0
    frame_noise = np.full((100, 100, 3), 10, dtype=np.uint8)
    assert compute_frame_diff(frame1, frame_noise) == 0.0


def test_ghost_hud_and_bridge_interop(qapp: Any) -> None:
    bridge = UIBridge()
    hud = GhostHUD(bridge=bridge)

    elements = [
        UIElement.from_bbox(1, (10, 20, 100, 40), label="TestButton", role="Button"),
        UIElement.from_bbox(2, (150, 20, 120, 30), label="TestEdit", role="Edit"),
    ]

    bridge.set_hud_targets(elements)
    qapp.processEvents()
    assert len(hud._targets) == 2
    assert hud._targets[0].id == 1
    assert hud._targets[0].label == "TestButton"

    bridge.clear_hud_targets()
    qapp.processEvents()
    assert len(hud._targets) == 0
    hud.close()
