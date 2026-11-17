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
import math
import re
import sys
import time
from typing import Any, Callable, List, Optional, Tuple
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
        Builds an encoded image data URI from the FoveatedFrame for VLM inference.
        Note: Deprecated for UI-TARS single-pass CUA (which receives unscaled Monitor 1 frames).
        Retained for legacy 2-pass compatibility and mock testing.
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


@dataclass
class OpticalVerificationResult:
    """Result of pre-click 128x128 optical crop verification (Hybrid Option C)."""
    x: int
    y: int
    verified: bool = True
    nudge_dx: int = 0
    nudge_dy: int = 0
    tier_used: str = "none"   # "none" | "cpu_ocr" | "vlm_glance" | "mismatch"
    detected_text: str = ""
    mismatch_reason: Optional[str] = None


_ACTION_QUOTED_HINT_RE = re.compile(
    r"(?:click|press|hit|select|tap|button|key|icon|tab|menu)\s+(?:on\s+)?(?:the\s+)?['\"]([^'\"]{1,24})['\"]",
    re.IGNORECASE,
)
_GENERIC_QUOTED_HINT_RE = re.compile(r"['\"]([^'\"]{1,24})['\"]")
_ACTION_UNQUOTED_HINT_RE = re.compile(
    r"\b(?:click|press|hit|select|tap|open|launch)\s+(?:on\s+)?(?:the\s+)?([A-Za-z0-9][A-Za-z0-9\+\-\./_]*(?:\s+[A-Za-z0-9][A-Za-z0-9\+\-\./_]*)?)",
    re.IGNORECASE,
)
_COORD_LIKE_RE = re.compile(r"^\s*\(?\s*-?\d+\s*,\s*-?\d+\s*\)?\s*$")
_MULTI_INT_RE = re.compile(r"^\d+(?:\s+\d+)+$")
_LARGE_INT_RE = re.compile(r"^\d{3,}$")
_OFFSET_RESPONSE_RE = re.compile(r"OFFSET\s*\(\s*([+-]?\d+)\s*,\s*([+-]?\d+)\s*\)", re.IGNORECASE)
_GENERIC_UI_NOUNS = frozenset({
    "icon", "menu", "screen", "window", "area", "button", "tab", "item",
    "target", "box", "field", "element", "control", "widget", "panel", "pane",
    "dialog", "modal", "popup", "toolbar", "taskbar", "desktop", "app",
    "application", "program", "bar", "link", "coordinates", "coordinate",
    "coords", "point", "pixel", "pixels", "location", "position", "spot",
    "corner", "edge", "center", "middle", "top", "bottom", "left", "right",
    "upper", "lower", "top-left", "top-right", "bottom-left", "bottom-right",
    "upper-left", "upper-right", "lower-left", "lower-right",
})
_UNQUOTED_STOPWORDS = frozenset({
    "the", "a", "an", "this", "that", "it", "its", "there", "here",
    "at", "in", "on", "of", "to", "for", "from", "with", "by", "as",
    "into", "onto", "near", "around", "inside", "outside", "under", "over",
    "and", "or", "but", "so", "then", "than", "when", "while", "which",
    "is", "are", "was", "be", "will", "would", "can", "could", "should",
    "x", "y",
})


def extract_target_glyph_hint(reasoning: Optional[str]) -> Optional[str]:
    """
    Extracts a concise target glyph or button label (e.g. '7', 'Save', 'Don't Save')
    from action reasoning text while filtering out raw coordinate strings and
    generic UI filler nouns.
    """
    if not reasoning or not isinstance(reasoning, str):
        return None

    for pattern in (_ACTION_QUOTED_HINT_RE, _GENERIC_QUOTED_HINT_RE):
        for match in pattern.finditer(reasoning):
            token = match.group(1).strip()
            if not token or len(token) > 20:
                continue
            if _COORD_LIKE_RE.match(token):
                continue
            return token

    for match in _ACTION_UNQUOTED_HINT_RE.finditer(reasoning):
        words = [w for w in match.group(1).strip().split() if w]
        while words and words[-1].lower() in (_GENERIC_UI_NOUNS | _UNQUOTED_STOPWORDS):
            # Keep uppercase/titlecase second word when preceded by a concrete verb/noun (e.g. "Save As")
            if len(words) == 2 and words[-1].lower() == "as" and words[-1][:1].isupper():
                break
            words.pop()
        if not words:
            continue
        if words[0].lower() in (_GENERIC_UI_NOUNS | _UNQUOTED_STOPWORDS):
            continue
        token = " ".join(words)
        if not token or len(token) > 20:
            continue
        if _COORD_LIKE_RE.match(token) or _MULTI_INT_RE.match(token) or _LARGE_INT_RE.match(token):
            continue
        return token

    return None


class PreClickOpticalVerifier:
    """
    Hybrid Option C pre-click optical zoom verifier:
    1. Extracts a native 128x128 px crop centered on (x, y) in <1ms on CPU.
    2. Tier 1 (CPU RapidOCR): Confirms target glyph alignment and nudges cursor to
       the glyph center when offset within max_nudge_px.
    3. Tier 2 (Optional VLM Micro-Glance): If Tier 1 is ambiguous and vlm_glance_fn
       is provided, runs a constrained small-crop neural check (~20-36 visual tokens).
    """

    def __init__(
        self,
        ocr_engine: Optional[Any] = None,
        crop_size: int = 128,
        max_nudge_px: int = 24,
    ) -> None:
        self._ocr_engine = ocr_engine
        self.crop_size = int(crop_size)
        self.max_nudge_px = int(max_nudge_px)

    def _get_ocr_engine(self) -> Optional[Any]:
        """Lazy initializer for RapidOCR ONNX engine."""
        if self._ocr_engine is None:
            try:
                from rapidocr_onnxruntime import RapidOCR
                self._ocr_engine = RapidOCR()
            except Exception as exc:
                logger.debug("PreClickOpticalVerifier RapidOCR unavailable: %s", exc)
                self._ocr_engine = None
        return self._ocr_engine

    def extract_crop(
        self,
        x: int,
        y: int,
        frame: np.ndarray,
        crop_size: Optional[int] = None,
        frame_origin: Tuple[int, int] = (0, 0),
    ) -> Tuple[np.ndarray, Tuple[int, int], Tuple[int, int]]:
        """
        Extracts a square 1:1 native pixel crop centered on (x, y) in <1ms on CPU.
        Returns (crop_array, (crop_origin_x, crop_origin_y), (cursor_local_x, cursor_local_y)).
        """
        if frame is None or frame.size == 0:
            return np.empty((0, 0, 3), dtype=np.uint8), (0, 0), (0, 0)

        fh, fw = frame.shape[:2]
        ox, oy = frame_origin
        fx = x - ox
        fy = y - oy
        if fx < 0 or fy < 0 or fx >= fw or fy >= fh:
            return np.empty((0, 0, 3), dtype=np.uint8), (0, 0), (0, 0)

        sz = max(16, int(crop_size or self.crop_size))
        half = sz // 2
        x1 = max(0, fx - half)
        y1 = max(0, fy - half)
        x2 = min(fw, x1 + sz)
        y2 = min(fh, y1 + sz)
        if (x2 - x1) < sz and x1 > 0:
            x1 = max(0, x2 - sz)
        if (y2 - y1) < sz and y1 > 0:
            y1 = max(0, y2 - sz)

        crop = frame[y1:y2, x1:x2]
        return crop, (ox + x1, oy + y1), (fx - x1, fy - y1)

    @staticmethod
    def _match_glyph_in_ocr(
        boxes: List[Any],
        target_glyph: str,
        cx_local: int,
        cy_local: int,
        max_nudge_px: int,
    ) -> Optional[Tuple[int, int, str]]:
        """Finds closest OCR box matching target_glyph within max_nudge_px."""
        target_clean = target_glyph.strip().lower()
        if not target_clean:
            return None

        best_match: Optional[Tuple[float, int, int, str]] = None
        for item in boxes:
            try:
                if len(item) < 3:
                    continue
                pts, text, conf = item[0], item[1], item[2]
                if float(conf) < 0.35:
                    continue
                text_str = str(text).strip()
                text_clean = text_str.lower()
                if not text_clean:
                    continue

                if len(target_clean) == 1:
                    matched = (
                        text_clean == target_clean
                        or bool(re.search(rf"(?<!\w){re.escape(target_clean)}(?!\w)", text_clean))
                    )
                else:
                    matched = (text_clean == target_clean or target_clean in text_clean)

                if not matched:
                    continue

                pts_arr = np.array(pts)
                gx = int(round((float(np.min(pts_arr[:, 0])) + float(np.max(pts_arr[:, 0]))) / 2.0))
                gy = int(round((float(np.min(pts_arr[:, 1])) + float(np.max(pts_arr[:, 1]))) / 2.0))
                dx = gx - cx_local
                dy = gy - cy_local
                if abs(dx) > max_nudge_px or abs(dy) > max_nudge_px:
                    continue

                dist = math.hypot(dx, dy)
                if best_match is None or dist < best_match[0]:
                    best_match = (dist, dx, dy, text_str)
            except Exception:
                continue

        if best_match is None:
            return None
        return (best_match[1], best_match[2], best_match[3])

    def verify_and_nudge(
        self,
        x: int,
        y: int,
        frame: Optional[np.ndarray],
        target_glyph: Optional[str] = None,
        crop_size: Optional[int] = None,
        frame_origin: Tuple[int, int] = (0, 0),
        vlm_glance_fn: Optional[Callable[[np.ndarray, str], str]] = None,
        max_nudge_px: Optional[int] = None,
    ) -> OpticalVerificationResult:
        """
        Verifies the target region under (x, y) using a 128x128 crop:
        - Tier 1: RapidOCR glyph check on CPU.
        - Tier 2: Optional VLM micro-glance callback if Tier 1 yields no match.
        """
        if frame is None or frame.size == 0 or not target_glyph or not target_glyph.strip():
            return OpticalVerificationResult(x=x, y=y, verified=True, tier_used="none")

        crop, _, (cx_local, cy_local) = self.extract_crop(
            x=x,
            y=y,
            frame=frame,
            crop_size=crop_size,
            frame_origin=frame_origin,
        )
        if crop.size == 0:
            return OpticalVerificationResult(x=x, y=y, verified=True, tier_used="none")

        nudge_cap = self.max_nudge_px if max_nudge_px is None else int(max_nudge_px)

        # Tier 1: Fast CPU RapidOCR glyph alignment check
        engine = self._get_ocr_engine()
        if engine is not None:
            try:
                ocr_res = engine(crop)
                boxes = ocr_res[0] if isinstance(ocr_res, tuple) else ocr_res
                if boxes:
                    matched = self._match_glyph_in_ocr(
                        boxes=boxes,
                        target_glyph=target_glyph,
                        cx_local=cx_local,
                        cy_local=cy_local,
                        max_nudge_px=nudge_cap,
                    )
                    if matched is not None:
                        dx, dy, matched_text = matched
                        return OpticalVerificationResult(
                            x=x + dx,
                            y=y + dy,
                            verified=True,
                            nudge_dx=dx,
                            nudge_dy=dy,
                            tier_used="cpu_ocr",
                            detected_text=matched_text,
                        )
            except Exception as exc:
                logger.debug("PreClickOpticalVerifier OCR pass failed: %s", exc)

        # Tier 2: Hybrid Option C VLM Micro-Glance fallback on ambiguous targets
        if vlm_glance_fn is not None:
            try:
                raw_resp = (vlm_glance_fn(crop, target_glyph) or "").strip()
                upper = raw_resp.upper()
                if upper.startswith("MISMATCH") or upper == "NO" or upper.startswith("NO "):
                    return OpticalVerificationResult(
                        x=x,
                        y=y,
                        verified=False,
                        tier_used="mismatch",
                        mismatch_reason=raw_resp,
                    )
                offset_m = _OFFSET_RESPONSE_RE.search(raw_resp)
                if offset_m:
                    dx = int(offset_m.group(1))
                    dy = int(offset_m.group(2))
                    if abs(dx) <= nudge_cap and abs(dy) <= nudge_cap:
                        return OpticalVerificationResult(
                            x=x + dx,
                            y=y + dy,
                            verified=True,
                            nudge_dx=dx,
                            nudge_dy=dy,
                            tier_used="vlm_glance",
                        )
                if "YES" in upper or "CONFIRM" in upper:
                    return OpticalVerificationResult(
                        x=x,
                        y=y,
                        verified=True,
                        tier_used="vlm_glance",
                    )
            except Exception as exc:
                logger.debug("PreClickOpticalVerifier VLM glance fallback failed: %s", exc)

        return OpticalVerificationResult(x=x, y=y, verified=True, tier_used="none")
