"""
tests/test_vlm_grounder.py - Unit Tests for VLM Visual Grounding Engine.

Verifies:
1. Base64 JPEG image encoding from numpy arrays.
2. Robust parsing of Qwen2.5-VL tags, JSON point/box structures, and coordinate normalization.
3. Hybrid UIA element coordinate snapping within radius.
4. Crop offset coordinate translation and fuzzy label fallbacks.
"""

from __future__ import annotations

from unittest.mock import MagicMock
import numpy as np
import pytest

from parasite_ai.ui.types import UIElement
from parasite_ai.vision.vlm_grounder import (
    VLMGrounder,
    encode_image_to_base64,
    parse_vlm_coordinates,
)


def test_encode_image_to_base64() -> None:
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    b64_str = encode_image_to_base64(img)
    assert isinstance(b64_str, str)
    assert len(b64_str) > 50


def test_parse_vlm_coordinates_qwen_tags() -> None:
    # 1000-scale box: ymin=100, xmin=200, ymax=300, xmax=400
    # Center: x_norm = 300/1000 = 0.3, y_norm = 200/1000 = 0.2
    # In 1000x1000 image: (300, 200)
    text = "The button is located at <|box_start|>(100,200),(300,400)<|box_end|>"
    coords = parse_vlm_coordinates(text, image_width=1000, image_height=1000)
    assert coords == (300, 200)

    # Point tag: y=500, x=750 -> x=750, y=500
    text_pt = "Found at <|coord_start|>(500,750)<|coord_end|>"
    coords_pt = parse_vlm_coordinates(text_pt, image_width=1000, image_height=1000)
    assert coords_pt == (750, 500)


def test_parse_vlm_coordinates_json_and_array() -> None:
    text_json = 'Result: {"point": [400, 600]}'
    coords = parse_vlm_coordinates(text_json, image_width=1920, image_height=1080)
    # x = (600/1000)*1920 = 1152, y = (400/1000)*1080 = 432
    assert coords == (1152, 432)

    text_arr = "Coordinates: [100, 200, 300, 400]"
    coords_arr = parse_vlm_coordinates(text_arr, image_width=1000, image_height=1000)
    assert coords_arr == (300, 200)


def test_snap_to_element() -> None:
    grounder = VLMGrounder(snap_radius_px=35.0)
    elements = [
        UIElement.from_bbox(1, (100, 100, 80, 40), label="TargetBtn"),  # center: (140, 120)
        UIElement.from_bbox(2, (500, 500, 100, 40), label="OtherBtn"),   # center: (550, 520)
    ]

    # Predict (145, 125) -> 7.07 pixels away from (140, 120) -> should snap
    snapped, elem = grounder.snap_to_element((145, 125), elements)
    assert snapped == (140, 120)
    assert elem is not None and elem.id == 1

    # Predict (250, 250) -> far away from all elements -> should retain predicted
    unsnapped, elem_none = grounder.snap_to_element((250, 250), elements)
    assert unsnapped == (250, 250)
    assert elem_none is None


def test_ground_target_with_crop_offset() -> None:
    mock_backend = MagicMock()
    # Returns Qwen box inside crop: ymin=400, xmin=400, ymax=600, xmax=600 -> center: (500, 500)
    mock_backend.generate.return_value = "<|box_start|>(400,400),(600,600)<|box_end|>"

    grounder = VLMGrounder(backend=mock_backend)
    crop = np.zeros((1000, 1000, 3), dtype=np.uint8)

    # Offset of crop is at (500, 200) in global desktop space
    coords, elem = grounder.ground_target(
        image=crop,
        target_description="Save",
        crop_offset=(500, 200),
    )

    # Local center is (500, 500) + offset (500, 200) = (1000, 700)
    assert coords == (1000, 700)
    assert elem is None
