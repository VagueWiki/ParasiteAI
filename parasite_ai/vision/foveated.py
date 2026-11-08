"""
parasite_ai/vision/foveated.py - Foveated Multi-Scale Vision Engine.

Provides high-resolution 1:1 native pixel crops around cursor/active window targets
alongside a lightweight global macro view, with 64-bit dHash change gating and
adaptive rate limiting.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
import io
import logging
import sys
import time
from typing import Any, List, Optional, Tuple
import numpy as np
from PIL import Image, ImageDraw

from parasite_ai.mind.memory import compute_dhash, hamming_distance
from parasite_ai.vision.capture import ScreenCapture, get_virtual_screen_bounds

logger = logging.getLogger(__name__)


def encode_image_to_data_uri(
    image: np.ndarray,
    max_dim: int = 640,
    quality: int = 80,
) -> str:
    """
    Encodes a numpy RGB/BGR image into a base64 JPEG data URI suitable for
    OpenAI-compatible multimodal chat completions and llama-cpp-python MTMD/Qwen25VL handlers.
    Resizes preserving aspect ratio so the longest side is at most `max_dim` pixels.
    """
    if image is None or image.size == 0:
        return ""
    arr = np.asarray(image)
    if arr.ndim == 2:
        pil_img = Image.fromarray(arr).convert("RGB")
    elif arr.shape[2] == 4:
        pil_img = Image.fromarray(arr[:, :, :3].astype(np.uint8), mode="RGB")
    else:
        pil_img = Image.fromarray(arr[:, :, :3].astype(np.uint8), mode="RGB")

    w, h = pil_img.size
    if max_dim > 0 and max(w, h) > max_dim:
        scale = max_dim / float(max(w, h))
        new_w = max(1, int(round(w * scale)))
        new_h = max(1, int(round(h * scale)))
        pil_img = pil_img.resize((new_w, new_h), Image.Resampling.BILINEAR)

    buf = io.BytesIO()
    pil_img.save(buf, format="JPEG", quality=quality, optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


@dataclass
class FoveatedFrame:
    """Represents a multi-scale captured frame."""
    macro_image: np.ndarray             # Scaled global overview (e.g. 1024x576)
    fovea_image: np.ndarray             # 1:1 unscaled native pixel crop around focus area
    fovea_rect: Tuple[int, int, int, int] # (x, y, w, h) in virtual desktop coordinates
    macro_scale_x: float                # Horizontal scaling factor for macro image
    macro_scale_y: float                # Vertical scaling factor for macro image
    full_shape: Tuple[int, int, int]    # Shape of full virtual desktop (H, W, C)
    dhash: str                          # 64-bit perceptual hash of the fovea
    is_changed: bool                    # Whether visual state changed since prior capture
    timestamp: float                    # Time of capture


class FoveatedVisionEngine:
    """
    Two-tier perception engine:
    1. Global Macro Glance (downscaled full virtual desktop for layout awareness)
    2. Foveal 1:1 Native Resolution Crop (around active window or cursor for small text/buttons)
    3. Adaptive Rate Limiting & 64-bit dHash Change Gating (0% GPU computation when static)
    """

    def __init__(
        self,
        capturer: Optional[ScreenCapture] = None,
        macro_width: int = 1024,
        default_fovea_size: Tuple[int, int] = (768, 768),
        min_interval_s: float = 0.1,  # Max 10 Hz during active interaction
        idle_interval_s: float = 1.0, # 1 Hz during idle monitoring
        change_threshold: int = 1,    # Hamming distance threshold to qualify as visual change
    ) -> None:
        self.capturer = capturer or ScreenCapture()
        self.macro_width = macro_width
        self.default_fovea_size = default_fovea_size
        self.min_interval_s = min_interval_s
        self.idle_interval_s = idle_interval_s
        self.change_threshold = change_threshold

        self._last_capture_time: float = 0.0
        self._last_dhash: Optional[str] = None
        self._last_frame: Optional[FoveatedFrame] = None

    def capture_foveated(
        self,
        cursor_pos: Optional[Tuple[int, int]] = None,
        active_window_rect: Optional[Tuple[int, int, int, int]] = None,
        fovea_size: Optional[Tuple[int, int]] = None,
        force: bool = False,
        full_frame_override: Optional[np.ndarray] = None,
    ) -> FoveatedFrame:
        """
        Captures or constructs a multi-scale FoveatedFrame.
        Throttles capture if invoked faster than min_interval_s unless force=True.
        """
        now = time.perf_counter()
        if not force and self._last_frame is not None:
            if (now - self._last_capture_time) < self.min_interval_s:
                return self._last_frame

        # 1. Capture or receive full virtual desktop frame
        if full_frame_override is not None:
            full_frame = full_frame_override
        else:
            full_frame = self.capturer.capture_screen(monitor_idx=0)

        fh, fw = full_frame.shape[:2]
        vx, vy, vw, vh = get_virtual_screen_bounds()

        # If capturer frame dimensions differ from Win32 metrics, use frame dimensions
        vw = max(vw, fw)
        vh = max(vh, fh)

        # 2. Determine Foveal Crop Bounds
        fw_size, fh_size = fovea_size or self.default_fovea_size

        if active_window_rect is not None and active_window_rect[2] > 0 and active_window_rect[3] > 0:
            # Center on active window if given, or clip to window size if smaller than fovea
            wx, wy, ww, wh = active_window_rect
            cx = wx + ww // 2
            cy = wy + wh // 2
            target_w = max(fw_size, min(ww, fw))
            target_h = max(fh_size, min(wh, fh))
        elif cursor_pos is not None:
            cx, cy = cursor_pos
            target_w, target_h = fw_size, fh_size
        else:
            # Default center of primary monitor
            cx, cy = fw // 4, fh // 2
            target_w, target_h = fw_size, fh_size

        # Translate virtual (cx, cy) to frame-relative indices
        rel_cx = max(0, min(cx - vx, fw - 1))
        rel_cy = max(0, min(cy - vy, fh - 1))

        half_w = target_w // 2
        half_h = target_h // 2

        # Clamp crop bounds to frame boundaries
        x1 = max(0, rel_cx - half_w)
        y1 = max(0, rel_cy - half_h)
        x2 = min(fw, x1 + target_w)
        y2 = min(fh, y1 + target_h)

        # Adjust back if cropped near right/bottom edge
        if (x2 - x1) < target_w and x1 > 0:
            x1 = max(0, x2 - target_w)
        if (y2 - y1) < target_h and y1 > 0:
            y1 = max(0, y2 - target_h)

        fovea_crop = full_frame[y1:y2, x1:x2].copy()
        fovea_rect = (vx + x1, vy + y1, x2 - x1, y2 - y1)

        # 3. Compute 64-bit dHash of the foveal crop
        current_dhash = compute_dhash(fovea_crop)
        is_changed = True
        if self._last_dhash is not None:
            h_dist = hamming_distance(self._last_dhash, current_dhash)
            if h_dist <= self.change_threshold:
                is_changed = False

        # 4. Generate Global Macro Overview
        macro_h = max(1, int(fh * (self.macro_width / max(1, fw))))
        pil_full = Image.fromarray(full_frame)
        pil_macro = pil_full.resize((self.macro_width, macro_h), Image.Resampling.BILINEAR)
        macro_arr = np.array(pil_macro)

        scale_x = self.macro_width / max(1, fw)
        scale_y = macro_h / max(1, fh)

        frame = FoveatedFrame(
            macro_image=macro_arr,
            fovea_image=fovea_crop,
            fovea_rect=fovea_rect,
            macro_scale_x=scale_x,
            macro_scale_y=scale_y,
            full_shape=(fh, fw, full_frame.shape[2] if full_frame.ndim > 2 else 1),
            dhash=current_dhash,
            is_changed=is_changed,
            timestamp=now,
        )

        self._last_capture_time = now
        self._last_dhash = current_dhash
        self._last_frame = frame
        return frame

    def transform_fovea_to_screen(
        self,
        local_x: int,
        local_y: int,
        fovea_rect: Tuple[int, int, int, int],
    ) -> Tuple[int, int]:
        """Maps pixel coordinate within the fovea crop to physical virtual desktop pixels."""
        fx, fy, fw, fh = fovea_rect
        clamped_x = max(0, min(local_x, fw))
        clamped_y = max(0, min(local_y, fh))
        return (fx + clamped_x, fy + clamped_y)

    def transform_macro_to_screen(
        self,
        macro_x: int,
        macro_y: int,
        frame: FoveatedFrame,
    ) -> Tuple[int, int]:
        """Maps pixel coordinate within the downscaled macro view to physical virtual desktop pixels."""
        vx, vy, _, _ = get_virtual_screen_bounds()
        screen_rel_x = int(macro_x / max(1e-6, frame.macro_scale_x))
        screen_rel_y = int(macro_y / max(1e-6, frame.macro_scale_y))
        return (vx + screen_rel_x, vy + screen_rel_y)

    def build_vlm_composite(
        self,
        frame: FoveatedFrame,
        elements: Optional[List[Any]] = None,
        use_fovea: bool = True,
        max_dim: int = 640,
        quality: int = 80,
    ) -> str:
        """
        Builds a Set-of-Mark annotated image data URI from the FoveatedFrame for VLM inference.
        Overlays [#ID] tags onto the foveal active-window crop (or macro desktop overview)
        so the VLM can directly read custom-rendered/console text and visual UI controls.
        """
        base_img = frame.fovea_image if (use_fovea and frame.fovea_image is not None and frame.fovea_image.size > 0) else frame.macro_image
        if base_img is None or base_img.size == 0:
            return ""

        arr = np.asarray(base_img)
        if arr.ndim == 2:
            pil_img = Image.fromarray(arr).convert("RGB")
        else:
            pil_img = Image.fromarray(arr[:, :, :3].astype(np.uint8), mode="RGB")

        if elements:
            draw = ImageDraw.Draw(pil_img)
            fx, fy, fw, fh = frame.fovea_rect
            vx, vy, _, _ = get_virtual_screen_bounds()
            for elem in elements[:40]:
                eid = getattr(elem, "id", None) if not isinstance(elem, dict) else elem.get("id")
                ex = getattr(elem, "x", None) if not isinstance(elem, dict) else elem.get("x")
                ey = getattr(elem, "y", None) if not isinstance(elem, dict) else elem.get("y")
                ew = getattr(elem, "width", 0) if not isinstance(elem, dict) else elem.get("width", 0)
                eh = getattr(elem, "height", 0) if not isinstance(elem, dict) else elem.get("height", 0)
                if eid is None or ex is None or ey is None:
                    continue
                if use_fovea:
                    rx = int(ex - fx)
                    ry = int(ey - fy)
                    rw = int(ew)
                    rh = int(eh)
                else:
                    rx = int((ex - vx) * frame.macro_scale_x)
                    ry = int((ey - vy) * frame.macro_scale_y)
                    rw = int(ew * frame.macro_scale_x)
                    rh = int(eh * frame.macro_scale_y)

                if rx + rw < 0 or ry + rh < 0 or rx >= pil_img.width or ry >= pil_img.height:
                    continue

                x1 = max(0, min(rx, pil_img.width - 1))
                y1 = max(0, min(ry, pil_img.height - 1))
                x2 = max(x1 + 1, min(rx + max(4, rw), pil_img.width - 1))
                y2 = max(y1 + 1, min(ry + max(4, rh), pil_img.height - 1))
                draw.rectangle([x1, y1, x2, y2], outline=(0, 229, 255), width=1)
                tag = f"#{eid}"
                tw = max(14, len(tag) * 6 + 4)
                th = 12
                tx = max(0, min(x1, pil_img.width - tw))
                ty = max(0, y1 - th if y1 >= th else y1)
                draw.rectangle([tx, ty, tx + tw, ty + th], fill=(10, 14, 23), outline=(0, 229, 255))
                draw.text((tx + 2, ty + 1), tag, fill=(0, 255, 200))

        return encode_image_to_data_uri(np.array(pil_img), max_dim=max_dim, quality=quality)

    def reset_history(self) -> None:
        """Clears cached dHash and frame state."""
        self._last_capture_time = 0.0
        self._last_dhash = None
        self._last_frame = None
