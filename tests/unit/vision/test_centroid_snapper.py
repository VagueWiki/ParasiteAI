"""
tests/unit/vision/test_centroid_snapper.py - Stint P4.1 Unit Tests.

Verifies CentroidSnapper (UIA bounding box snapping on <=120x120 px controls,
CPU OpenCV contour edge fallback, Edit/Document passthrough),
PreClickOpticalVerifier (128x128 crop, RapidOCR alignment nudge, Hybrid Option C VLM glance),
and ActionDispatcher integration.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import cv2
import numpy as np
import pytest

from parasite_ai.mind.dual_mind import ActionDispatcher
from parasite_ai.mind.memory import ActionPlan, ActionType
from parasite_ai.ui.types import UIElement
from parasite_ai.vision.foveated import (
    PreClickOpticalVerifier,
    extract_target_glyph_hint,
)
from parasite_ai.vision.grounding import CentroidSnapper


def _build_calculator_grid_elements() -> list[UIElement]:
    """Builds a realistic 3x3 dense Calculator-style digit grid of 60x44 px buttons."""
    elements: list[UIElement] = []
    labels = ["7", "8", "9", "4", "5", "6", "1", "2", "3"]
    eid = 1
    for row in range(3):
        for col in range(3):
            bx = 100 + col * 64
            by = 200 + row * 48
            elements.append(
                UIElement.from_bbox(
                    eid,
                    (bx, by, 60, 44),
                    label=labels[eid - 1],
                    role="Button",
                    source="uia",
                )
            )
            eid += 1
    return elements


class TestCentroidSnapperUIA:
    """Verifies UIA bounding box centroid snapping on small dense controls."""

    def test_centroid_snapping_dense_grid_edge_inside_and_outside(self) -> None:
        snapper = CentroidSnapper(max_button_size=120, edge_margin_px=8)
        elements = _build_calculator_grid_elements()
        # Button '7' is at (100, 200, 60, 44) -> center (130, 222)

        # Case 1: Near left/top border inside button '7' (2px from top-left edge)
        res_inside = snapper.snap_with_details(102, 202, elements=elements)
        assert res_inside.snapped is True
        assert res_inside.strategy == "uia_bbox"
        assert (res_inside.x, res_inside.y) == (130, 222)
        assert res_inside.matched_label == "7"

        # Case 2: Narrow border miss (2px outside left edge of button '7')
        res_outside = snapper.snap_with_details(98, 222, elements=elements)
        assert res_outside.snapped is True
        assert (res_outside.x, res_outside.y) == (130, 222)

    def test_centroid_snapper_large_element_passthrough(self) -> None:
        snapper = CentroidSnapper(max_button_size=120, edge_margin_px=8)
        elements = [
            UIElement.from_bbox(1, (100, 100, 300, 180), label="LargePanel", role="Button"),
            UIElement.from_bbox(2, (100, 350, 140, 40), label="WideToolbarButton", role="Button"),
        ]

        # Click near border of >120px controls must NOT snap
        assert snapper.snap(103, 120, elements=elements) == (103, 120)
        assert snapper.snap(103, 360, elements=elements) == (103, 360)

    def test_centroid_snapper_excludes_edit_and_document(self) -> None:
        snapper = CentroidSnapper(max_button_size=120, edge_margin_px=8)
        elements = [
            UIElement.from_bbox(1, (100, 100, 80, 28), label="SmallInput", role="Edit"),
            UIElement.from_bbox(2, (100, 150, 100, 100), label="MiniDoc", role="Document"),
        ]

        # Clicking near right edge of an Edit field to place caret must NOT snap to center
        assert snapper.snap(176, 114, elements=elements) == (176, 114)
        assert snapper.snap(104, 160, elements=elements) == (104, 160)

    def test_centroid_snapper_interior_passthrough(self) -> None:
        snapper = CentroidSnapper(max_button_size=120, edge_margin_px=8)
        elements = [
            UIElement.from_bbox(1, (100, 100, 100, 100), label="SquareIcon", role="Button"),
        ]
        # (130, 130) is 30px from every edge (> 8px margin) -> preserved
        assert snapper.snap(130, 130, elements=elements) == (130, 130)


class TestCentroidSnapperContours:
    """Verifies fast CPU OpenCV contour fallback when UIA elements are absent."""

    def test_contour_snapping_fallback_synthetic_button(self) -> None:
        frame = np.full((300, 300, 3), 240, dtype=np.uint8)
        # Draw a crisp 60x44 button at (100, 100) to (160, 144) -> center (130, 122)
        cv2.rectangle(frame, (100, 100), (160, 144), (255, 255, 255), -1)
        cv2.rectangle(frame, (100, 100), (160, 144), (160, 160, 160), 1)
        cv2.putText(frame, "7", (123, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (20, 20, 20), 2)

        snapper = CentroidSnapper(max_button_size=120, edge_margin_px=8)
        # Click near top-left edge (103, 104) with empty UIA list
        res = snapper.snap_with_details(103, 104, elements=[], frame=frame)

        assert res.snapped is True
        assert res.strategy == "contour_edge"
        assert abs(res.x - 130) <= 2
        assert abs(res.y - 122) <= 2

    def test_contour_snapping_respects_frame_origin(self) -> None:
        frame = np.full((300, 300, 3), 240, dtype=np.uint8)
        cv2.rectangle(frame, (100, 100), (160, 144), (255, 255, 255), -1)
        cv2.rectangle(frame, (100, 100), (160, 144), (160, 160, 160), 1)

        snapper = CentroidSnapper(max_button_size=120, edge_margin_px=8)
        # Frame origin is (-1920, 0), so button is at (-1820, 100) -> center (-1790, 122)
        res = snapper.snap_with_details(
            -1817,
            104,
            elements=[],
            frame=frame,
            frame_origin=(-1920, 0),
        )
        assert res.snapped is True
        assert abs(res.x - (-1790)) <= 2
        assert abs(res.y - 122) <= 2


class TestPreClickOpticalVerifierOptionC:
    """Verifies 128x128 optical crop, CPU RapidOCR glyph nudge, and Hybrid VLM glance."""

    def test_extract_target_glyph_hint(self) -> None:
        assert extract_target_glyph_hint("Click the '7' button on Calculator.") == "7"
        assert extract_target_glyph_hint('Click "Save" to confirm') == "Save"
        assert extract_target_glyph_hint("Click at '(450, 320)'") is None
        assert extract_target_glyph_hint(None) is None

    def test_optical_zoom_cpu_ocr_nudges_to_glyph_center(self) -> None:
        frame = np.zeros((400, 400, 3), dtype=np.uint8)
        # Mock RapidOCR detecting '7' shifted (+6, -4) from crop center (64, 64) -> box around (70, 60)
        mock_ocr = MagicMock(
            return_value=(
                [[[[64, 54], [76, 54], [76, 66], [64, 66]], "7", 0.98]],
                0.004,
            )
        )
        verifier = PreClickOpticalVerifier(ocr_engine=mock_ocr, crop_size=128, max_nudge_px=24)

        res = verifier.verify_and_nudge(200, 200, frame=frame, target_glyph="7")
        assert res.verified is True
        assert res.tier_used == "cpu_ocr"
        assert (res.nudge_dx, res.nudge_dy) == (6, -4)
        assert (res.x, res.y) == (206, 196)

    def test_optical_zoom_vlm_micro_glance_fallback_offset_and_mismatch(self) -> None:
        frame = np.zeros((400, 400, 3), dtype=np.uint8)
        mock_ocr = MagicMock(return_value=([], 0.003))  # Ambiguous / icon-only crop
        verifier = PreClickOpticalVerifier(ocr_engine=mock_ocr, crop_size=128, max_nudge_px=24)

        # Subcase A: VLM micro-glance returns OFFSET(5, -3)
        res_offset = verifier.verify_and_nudge(
            200,
            200,
            frame=frame,
            target_glyph="Settings",
            vlm_glance_fn=lambda crop, glyph: "OFFSET(5, -3)",
        )
        assert res_offset.verified is True
        assert res_offset.tier_used == "vlm_glance"
        assert (res_offset.x, res_offset.y) == (205, 197)

        # Subcase B: VLM micro-glance returns YES
        res_yes = verifier.verify_and_nudge(
            200,
            200,
            frame=frame,
            target_glyph="Settings",
            vlm_glance_fn=lambda crop, glyph: "YES",
        )
        assert res_yes.verified is True
        assert res_yes.tier_used == "vlm_glance"
        assert (res_yes.x, res_yes.y) == (200, 200)

        # Subcase C: VLM micro-glance returns MISMATCH
        res_mismatch = verifier.verify_and_nudge(
            200,
            200,
            frame=frame,
            target_glyph="Save",
            vlm_glance_fn=lambda crop, glyph: "MISMATCH: showing Delete",
        )
        assert res_mismatch.verified is False
        assert res_mismatch.tier_used == "mismatch"


class TestActionDispatcherPrecisionWiring:
    """Verifies CentroidSnapper and PreClickOpticalVerifier inside ActionDispatcher.dispatch."""

    def test_dispatcher_snaps_near_edge_click_to_button_centroid(self) -> None:
        mock_mouse = MagicMock()
        mock_mouse.click.return_value = True
        dispatcher = ActionDispatcher(
            mouse_driver=mock_mouse,
            optical_verifier=PreClickOpticalVerifier(ocr_engine=MagicMock(return_value=([], 0.0))),
        )
        elements = _build_calculator_grid_elements()
        # Button '7' is at (100, 200, 60, 44) -> center (130, 222)
        action = ActionPlan(
            action=ActionType.CLICK,
            coordinates=(103, 203),
            reasoning="Click the '7' button",
        )
        res = dispatcher.dispatch(action, elements)

        assert res.success is True
        assert res.resolved_coordinates == (130, 222)
        mock_mouse.click.assert_called_once_with(
            x=130,
            y=222,
            button="left",
            clicks=1,
            cancellation_token=None,
        )

    def test_dispatcher_aborts_on_optical_mismatch(self) -> None:
        mock_mouse = MagicMock()
        mock_ocr = MagicMock(return_value=([], 0.002))
        dispatcher = ActionDispatcher(
            mouse_driver=mock_mouse,
            optical_verifier=PreClickOpticalVerifier(ocr_engine=mock_ocr),
            vlm_glance_fn=lambda crop, glyph: "MISMATCH: cursor is on Cancel",
        )
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        action = ActionPlan(
            action=ActionType.CLICK,
            coordinates=(500, 500),
            reasoning="Click the 'Save' button",
        )
        res = dispatcher.dispatch(action, [], cua_mode=True, frame=frame)

        assert res.success is False
        assert "Pre-click optical mismatch" in (res.error or "")
        mock_mouse.click.assert_not_called()


class TestStintP411Stabilization:
    """Stint P4.1.1 tests for O(1) UIA point-probe snapping and safe unquoted hint extraction."""

    def test_centroid_snapper_uia_point_probe_center_and_border_miss(self) -> None:
        btn_seven = UIElement.from_bbox(1, (100, 200, 60, 44), label="Seven", role="Button", source="uia")
        edit_box = UIElement.from_bbox(2, (300, 200, 80, 28), label="Search", role="Edit", source="uia")

        def fake_uia_point(px: int, py: int) -> UIElement | None:
            if btn_seven.x <= px < btn_seven.x + btn_seven.width and btn_seven.y <= py < btn_seven.y + btn_seven.height:
                return btn_seven
            if edit_box.x <= px < edit_box.x + edit_box.width and edit_box.y <= py < edit_box.y + edit_box.height:
                return edit_box
            return None

        snapper = CentroidSnapper(
            max_button_size=120,
            edge_margin_px=8,
            enable_uia_point_probe=True,
            uia_point_fn=fake_uia_point,
        )

        # 1. Near inner edge -> snaps to center via uia_point
        res_inner = snapper.snap_with_details(102, 203, elements=[])
        assert res_inner.snapped is True
        assert res_inner.strategy == "uia_point"
        assert (res_inner.x, res_inner.y) == (130, 222)

        # 2. Narrow outside border miss (5px left of button boundary) -> recovered via cardinal probe
        res_outer = snapper.snap_with_details(95, 222, elements=[])
        assert res_outer.snapped is True
        assert res_outer.strategy == "uia_point"
        assert (res_outer.x, res_outer.y) == (130, 222)

        # 3. Strictly interior already centered click -> untouched
        res_center = snapper.snap_with_details(130, 222, elements=[])
        assert res_center.snapped is False
        assert (res_center.x, res_center.y) == (130, 222)

        # 4. Edit control hit suppresses both uia_point AND contour_edge caret shifting
        frame = np.zeros((400, 500, 3), dtype=np.uint8)
        cv2.rectangle(frame, (300, 200), (380, 228), (255, 255, 255), thickness=2)
        res_edit = snapper.snap_with_details(303, 214, elements=[], frame=frame)
        assert res_edit.snapped is False
        assert res_edit.strategy == "none"
        assert (res_edit.x, res_edit.y) == (303, 214)

    def test_extract_target_glyph_hint_unquoted_safe(self) -> None:
        assert extract_target_glyph_hint("Click on Calculator") == "Calculator"
        assert extract_target_glyph_hint("Click Start") == "Start"
        assert extract_target_glyph_hint("Click on the Calculator button to launch it") == "Calculator"
        assert extract_target_glyph_hint("Press Save and continue") == "Save"

        # Generic nouns and coordinates must be filtered out safely
        assert extract_target_glyph_hint("Click on the icon") is None
        assert extract_target_glyph_hint("Click inside window") is None
        assert extract_target_glyph_hint("Click at (100, 200)") is None
        assert extract_target_glyph_hint("Click the top-left corner of the window") is None

    def test_centroid_snapper_uia_point_probe_uwp_parent_walk(self) -> None:
        """Verifies live ControlFromPoint walks from inner TextControl up to parent ButtonControl."""
        class _Rect:
            def __init__(self, left: int, top: int, right: int, bottom: int) -> None:
                self.left, self.top, self.right, self.bottom = left, top, right, bottom

        parent_btn = MagicMock()
        parent_btn.ControlTypeName = "ButtonControl"
        parent_btn.Name = "Seven"
        parent_btn.BoundingRectangle = _Rect(100, 200, 160, 244)

        inner_txt = MagicMock()
        inner_txt.ControlTypeName = "TextControl"
        inner_txt.Name = "7"
        inner_txt.BoundingRectangle = _Rect(120, 210, 140, 234)
        inner_txt.GetParentControl.return_value = parent_btn

        mock_auto = MagicMock()
        mock_auto.ControlFromPoint.return_value = inner_txt

        snapper = CentroidSnapper(enable_uia_point_probe=True)
        with (
            patch("sys.platform", "win32"),
            patch.dict("sys.modules", {"uiautomation": mock_auto}),
        ):
            res = snapper.snap_with_details(103, 222, elements=[])

        assert res.snapped is True
        assert res.strategy == "uia_point"
        assert res.matched_label == "Seven"
        assert (res.x, res.y) == (130, 222)
