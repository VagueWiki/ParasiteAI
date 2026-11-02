"""
parasite_ai/vision/vlm_grounder.py - Local Vision-Language Model Visual Grounder.

Implements visual target localization using local Qwen2.5-VL with hybrid coordinate snapping:
- Encodes full-screen or foveated desktop crops into multimodal payload.
- Parses normalized bounding boxes/points ([0, 1000] scale) from model completions.
- Converts local crop coordinates to global desktop coordinates.
- Snaps predicted visual coordinates to nearest UIA/SOM element if within snap radius.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import math
import re
from typing import Any, List, Optional, Tuple, Union
import numpy as np
from PIL import Image

from parasite_ai.ui.types import UIElement

logger = logging.getLogger(__name__)


def encode_image_to_base64(image_arr: np.ndarray, format: str = "JPEG", quality: int = 85) -> str:
    """Encodes a numpy RGB image array into a base64 string."""
    if image_arr.ndim == 2:
        pil_img = Image.fromarray(image_arr, mode="L")
    elif image_arr.shape[2] == 4:
        pil_img = Image.fromarray(image_arr, mode="RGBA").convert("RGB")
    else:
        pil_img = Image.fromarray(image_arr, mode="RGB")

    buf = io.BytesIO()
    pil_img.save(buf, format=format, quality=quality)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def parse_vlm_coordinates(
    response_text: str,
    image_width: int,
    image_height: int,
) -> Optional[Tuple[int, int]]:
    """
    Parses normalized coordinates or bounding boxes from VLM responses.
    Supports:
      1. Qwen2.5-VL tags: <|box_start|>(ymin,xmin),(ymax,xmax)<|box_end|> normalized [0..1000]
      2. Coordinate tags: <|coord_start|>(y,x)<|coord_end|>
      3. JSON schemas: {"point": [y, x]} or {"box_2d": [ymin, xmin, ymax, xmax]}
      4. Plain regex matches: [ymin, xmin, ymax, xmax] or (y, x)
    Returns (center_x, center_y) in local image pixel coordinates.
    """
    if not response_text:
        return None

    # 1. Check Qwen2.5-VL box tags: (ymin,xmin),(ymax,xmax)
    box_tag_pattern = r"(?:<\|box_start\|>)?\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)\s*,\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)\s*(?:<\|box_end\|>)?"
    m_box = re.search(box_tag_pattern, response_text)
    if m_box:
        ymin, xmin, ymax, xmax = (int(g) for g in m_box.groups())
        cx_norm = (xmin + xmax) / 2.0 / 1000.0
        cy_norm = (ymin + ymax) / 2.0 / 1000.0
        return (int(cx_norm * image_width), int(cy_norm * image_height))

    # 2. Check Qwen2.5-VL point tags: (y,x)
    pt_tag_pattern = r"<\|coord_start\|>\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)\s*<\|coord_end\|>"
    m_pt = re.search(pt_tag_pattern, response_text)
    if m_pt:
        y_val, x_val = (int(g) for g in m_pt.groups())
        return (int((x_val / 1000.0) * image_width), int((y_val / 1000.0) * image_height))

    # 3. Check JSON structure
    try:
        json_matches = re.findall(r"\{[^{}]*\}", response_text)
        for jm in json_matches:
            data = json.loads(jm)
            if "point" in data and isinstance(data["point"], (list, tuple)) and len(data["point"]) == 2:
                py, px = data["point"]
                # Determine if normalized [0..1000] or [0..1]
                scale = 1000.0 if (px > 1.0 or py > 1.0) else 1.0
                return (int((px / scale) * image_width), int((py / scale) * image_height))
            if "box_2d" in data and isinstance(data["box_2d"], (list, tuple)) and len(data["box_2d"]) == 4:
                ymin, xmin, ymax, xmax = data["box_2d"]
                scale = 1000.0 if (xmax > 1.0 or ymax > 1.0) else 1.0
                cx = (xmin + xmax) / 2.0 / scale
                cy = (ymin + ymax) / 2.0 / scale
                return (int(cx * image_width), int(cy * image_height))
    except Exception:
        pass

    # 4. Standard 4-number array fallback: [ymin, xmin, ymax, xmax]
    arr_pattern = r"\[\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\]"
    m_arr = re.search(arr_pattern, response_text)
    if m_arr:
        ymin, xmin, ymax, xmax = (int(g) for g in m_arr.groups())
        if max(xmin, xmax, ymin, ymax) <= 1000:
            cx_norm = (xmin + xmax) / 2.0 / 1000.0
            cy_norm = (ymin + ymax) / 2.0 / 1000.0
            return (int(cx_norm * image_width), int(cy_norm * image_height))
        else:
            # Already in pixel space
            return (int((xmin + xmax) / 2), int((ymin + ymax) / 2))

    return None


class VLMGrounder:
    """
    Multimodal visual grounder combining local VLM bounding box prediction
    with UIA Set-of-Mark spatial coordinate snapping.
    """

    def __init__(
        self,
        backend: Optional[Any] = None,
        snap_radius_px: float = 35.0,
    ) -> None:
        self.backend = backend
        self.snap_radius_px = snap_radius_px

    def snap_to_element(
        self,
        predicted_coords: Tuple[int, int],
        candidate_elements: List[UIElement],
    ) -> Tuple[Tuple[int, int], Optional[UIElement]]:
        """
        Snaps (x, y) coordinates to the center of the closest UIElement within snap_radius_px.
        If no element is within radius, returns original coordinates.
        """
        px, py = predicted_coords
        best_elem: Optional[UIElement] = None
        min_dist = float("inf")

        for elem in candidate_elements:
            dist = math.hypot(px - elem.center_x, py - elem.center_y)
            if dist < min_dist and dist <= self.snap_radius_px:
                min_dist = dist
                best_elem = elem

        if best_elem is not None:
            return ((best_elem.center_x, best_elem.center_y), best_elem)

        return (predicted_coords, None)

    def ground_target(
        self,
        image: np.ndarray,
        target_description: str,
        candidate_elements: Optional[List[UIElement]] = None,
        crop_offset: Tuple[int, int] = (0, 0),
    ) -> Tuple[Optional[Tuple[int, int]], Optional[UIElement]]:
        """
        Predicts visual target coordinates and snaps to UIA elements.
        Args:
            image: RGB image (macro view or foveal crop).
            target_description: Natural language target (e.g. 'search box', 'submit button').
            candidate_elements: Grounded UIA elements in the same coordinate space.
            crop_offset: (offset_x, offset_y) to add if image is a cropped patch.
        Returns:
            ((screen_x, screen_y), snapped_element_or_None)
        """
        if image is None or image.size == 0:
            return (None, None)

        h, w = image.shape[:2]
        predicted_local: Optional[Tuple[int, int]] = None

        if self.backend is not None and hasattr(self.backend, "generate"):
            try:
                b64_img = encode_image_to_base64(image)
                prompt = (
                    f"Locate the visual target '{target_description}' on screen. "
                    "Output the bounding box as [ymin, xmin, ymax, xmax] scaled to 1000."
                )
                response = self.backend.generate(
                    prompt=prompt,
                    image_base64=b64_img,
                    max_tokens=64,
                    temperature=0.1,
                )
                predicted_local = parse_vlm_coordinates(response, image_width=w, image_height=h)
            except Exception as exc:
                logger.debug("VLM grounding inference failed: %s", exc)

        # Fallback to candidate element fuzzy label match if VLM unavailable or produced no output
        if predicted_local is None and candidate_elements:
            target_lower = target_description.lower()
            matched = next(
                (
                    e for e in candidate_elements
                    if target_lower in (e.label or "").lower() or (e.label and e.label.lower() in target_lower)
                ),
                None,
            )
            if matched:
                return ((matched.center_x, matched.center_y), matched)

        if predicted_local is None:
            return (None, None)

        # Apply crop offset to transform into global coordinates
        gx = predicted_local[0] + crop_offset[0]
        gy = predicted_local[1] + crop_offset[1]
        global_coords = (gx, gy)

        # Perform hybrid snapping if candidate elements are provided
        if candidate_elements:
            return self.snap_to_element(global_coords, candidate_elements)

        return (global_coords, None)
