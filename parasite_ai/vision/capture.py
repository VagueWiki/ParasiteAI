"""
parasite_ai/vision/capture.py - Fast Desktop Screen Capture Manager.

Provides high-performance desktop screenshot capture using mss with PIL ImageGrab
and synthetic numpy frame fallbacks for headless CI environments.
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)


def compute_frame_diff(frame_a: np.ndarray, frame_b: np.ndarray) -> float:
    """
    Calculates normalized visual frame difference ratio in [0.0, 1.0].
    Downsamples 4x for speed and computes mean absolute channel differences.
    """
    if frame_a is None or frame_b is None:
        return 0.0

    if frame_a.shape != frame_b.shape:
        return 1.0

    if frame_a.size == 0 or frame_b.size == 0:
        return 0.0

    # Downsample 4x if large enough
    sub_a = frame_a[::4, ::4]
    sub_b = frame_b[::4, ::4]

    # Convert to int16 to avoid unsigned underflow
    arr_a = sub_a.astype(np.int16)
    arr_b = sub_b.astype(np.int16)

    # Pixel-wise max channel difference
    if arr_a.ndim == 3 and arr_a.shape[2] >= 3:
        # Check first 3 channels (RGB / BGR)
        diff = np.max(np.abs(arr_a[:, :, :3] - arr_b[:, :, :3]), axis=2)
    else:
        diff = np.abs(arr_a - arr_b)

    # Threshold channel noise > 15
    changed_pixels = np.count_nonzero(diff > 15)
    total_pixels = diff.size

    if total_pixels == 0:
        return 0.0

    return float(changed_pixels / total_pixels)


class ScreenCapture:
    """Fast screen capture manager supporting mss, PIL, and synthetic fallbacks."""

    def __init__(self, backend: str = "mss") -> None:
        self.backend = backend.lower()
        self._sct: Optional[Any] = None
        self._tls = __import__("threading").local()
        self._init_backend()

    def _init_backend(self) -> None:
        """Initialize capture provider."""
        if self.backend == "mss":
            try:
                import mss
                if hasattr(mss, "MSS"):
                    self._sct = mss.MSS()
                else:
                    self._sct = mss.mss()
                self._tls.sct = self._sct
                self._owned_sct = self._sct
            except Exception as exc:
                logger.warning("Could not initialize mss screen capturer: %s. Falling back to PIL.", exc)
                self.backend = "pillow"

    def _get_thread_sct(self) -> Optional[Any]:
        """Returns a thread-local mss instance so Windows GDI HDC handles are valid on worker threads."""
        if self._sct is not None and self._sct is not getattr(self, "_owned_sct", None):
            # Custom or mock sct object injected externally (e.g. unit tests)
            return self._sct
        sct = getattr(self._tls, "sct", None)
        if sct is not None:
            return sct
        try:
            import mss
            sct = mss.mss()
            self._tls.sct = sct
            return sct
        except Exception:
            return self._sct

    def capture_screen(self, monitor_idx: int = 0) -> np.ndarray:
        """
        Captures full virtual desktop (monitor_idx=0) or specific monitor returning RGB numpy array (H, W, 3).
        Gracefully falls back to PIL ImageGrab or blank synthetic frame
        if running headless or in restricted Win32 desktop sessions.
        """
        sct = self._get_thread_sct() if self.backend == "mss" else None
        if self.backend == "mss" and sct is not None:
            try:
                monitors = sct.monitors
                if len(monitors) > monitor_idx:
                    mon = monitors[monitor_idx]
                elif len(monitors) > 0:
                    mon = monitors[0]
                else:
                    mon = {"top": 0, "left": 0, "width": 1920, "height": 1080}

                sct_img = sct.grab(mon)
                # sct_img.rgb is RGB bytes, shape (H, W, 3)
                arr = np.frombuffer(sct_img.rgb, dtype=np.uint8)
                arr = arr.reshape((sct_img.height, sct_img.width, 3))
                return arr
            except Exception as exc:
                logger.debug("mss capture failed (%s), falling back to PIL", exc)

        # Fallback to PIL ImageGrab
        try:
            from PIL import ImageGrab
            try:
                pil_img = ImageGrab.grab(all_screens=True)
            except TypeError:
                pil_img = ImageGrab.grab()
            if pil_img is not None:
                return np.array(pil_img.convert("RGB"))
        except Exception as exc:
            logger.debug("PIL capture failed (%s), returning synthetic frame", exc)

        # Headless synthetic fallback: blank 1920x1080 frame
        return np.zeros((1080, 1920, 3), dtype=np.uint8)

    def capture_rect(self, rect: Tuple[int, int, int, int]) -> np.ndarray:
        """Captures specific bounding rectangle (x, y, width, height)."""
        x, y, width, height = rect
        if width <= 0 or height <= 0:
            return np.zeros((1, 1, 3), dtype=np.uint8)

        sct = self._get_thread_sct() if self.backend == "mss" else None
        if self.backend == "mss" and sct is not None:
            try:
                mon = {"top": y, "left": x, "width": width, "height": height}
                sct_img = sct.grab(mon)
                arr = np.frombuffer(sct_img.rgb, dtype=np.uint8)
                return arr.reshape((sct_img.height, sct_img.width, 3))
            except Exception as exc:
                logger.debug("mss rect capture failed (%s), falling back to full crop", exc)

        full = self.capture_screen()
        h, w = full.shape[:2]
        crop_y1 = max(0, min(y, h))
        crop_y2 = max(0, min(y + height, h))
        crop_x1 = max(0, min(x, w))
        crop_x2 = max(0, min(x + width, w))

        if crop_y2 <= crop_y1 or crop_x2 <= crop_x1:
            return np.zeros((max(1, height), max(1, width), 3), dtype=np.uint8)

        return full[crop_y1:crop_y2, crop_x1:crop_x2]

    def close(self) -> None:
        """Release underlying capture resources."""
        if self._sct is not None:
            try:
                self._sct.close()
            except Exception:
                pass
            self._sct = None
