"""
tests/test_foveated_vision.py - Unit & Integration Tests for Foveated Multi-Scale Vision.
"""

from __future__ import annotations

import time
import numpy as np
import pytest

from parasite_ai.vision.foveated import FoveatedVisionEngine, FoveatedFrame, get_virtual_screen_bounds


class MockCapturer:
    """Mock capturer providing deterministic synthetic frames."""

    def __init__(self, width: int = 3840, height: int = 1080) -> None:
        self.width = width
        self.height = height
        self._frame = np.full((height, width, 3), 128, dtype=np.uint8)

    def capture_screen(self, monitor_idx: int = 0) -> np.ndarray:
        return self._frame.copy()

    def set_content(self, x: int, y: int, w: int, h: int, color: int = 255) -> None:
        self._frame[y:y+h, x:x+w] = color


def test_foveated_crop_dimensions():
    capturer = MockCapturer(width=3840, height=1080)
    engine = FoveatedVisionEngine(capturer=capturer, macro_width=1024, default_fovea_size=(768, 768))

    frame = engine.capture_foveated(cursor_pos=(500, 500), force=True)
    assert isinstance(frame, FoveatedFrame)
    assert frame.fovea_image.shape == (768, 768, 3)
    assert frame.macro_image.shape[1] == 1024
    # Height of macro should preserve 3840:1080 aspect ratio (~288px)
    assert 280 <= frame.macro_image.shape[0] <= 295
    assert frame.is_changed is True


def test_foveated_crop_edge_clamping():
    capturer = MockCapturer(width=3840, height=1080)
    engine = FoveatedVisionEngine(capturer=capturer, default_fovea_size=(512, 512))

    # Top-left corner
    frame_tl = engine.capture_foveated(cursor_pos=(0, 0), force=True)
    assert frame_tl.fovea_image.shape == (512, 512, 3)
    assert frame_tl.fovea_rect[0] == 0
    assert frame_tl.fovea_rect[1] == 0

    # Bottom-right corner of dual monitor (3840, 1080)
    frame_br = engine.capture_foveated(cursor_pos=(3840, 1080), force=True)
    assert frame_br.fovea_image.shape == (512, 512, 3)
    assert frame_br.fovea_rect[0] == 3840 - 512
    assert frame_br.fovea_rect[1] == 1080 - 512


def test_dhash_change_gating():
    capturer = MockCapturer(width=1920, height=1080)
    engine = FoveatedVisionEngine(capturer=capturer, default_fovea_size=(512, 512), min_interval_s=0.0)

    # Initial frame
    frame1 = engine.capture_foveated(cursor_pos=(500, 500), force=True)
    assert frame1.is_changed is True

    # Identical frame -> should not be marked as changed
    frame2 = engine.capture_foveated(cursor_pos=(500, 500), force=True)
    assert frame2.is_changed is False

    # Modify content inside fovea
    capturer.set_content(400, 400, 100, 100, color=0)
    frame3 = engine.capture_foveated(cursor_pos=(500, 500), force=True)
    assert frame3.is_changed is True


def test_rate_limiter():
    capturer = MockCapturer(width=1920, height=1080)
    engine = FoveatedVisionEngine(capturer=capturer, min_interval_s=0.2)

    frame1 = engine.capture_foveated(cursor_pos=(200, 200), force=True)
    # Immediate subsequent call without force should return cached frame
    frame2 = engine.capture_foveated(cursor_pos=(900, 900), force=False)
    assert frame1 is frame2
    assert frame2.fovea_rect == frame1.fovea_rect

    # After sleeping > min_interval_s, fresh frame is generated
    time.sleep(0.25)
    frame3 = engine.capture_foveated(cursor_pos=(900, 900), force=False)
    assert frame3 is not frame1


def test_coordinate_transforms():
    capturer = MockCapturer(width=3840, height=1080)
    engine = FoveatedVisionEngine(capturer=capturer, macro_width=1024, default_fovea_size=(500, 500))

    frame = engine.capture_foveated(cursor_pos=(2000, 500), force=True)
    fovea_rect = frame.fovea_rect

    # Local fovea (50, 50) -> screen (fovea_rect[0] + 50, fovea_rect[1] + 50)
    sx, sy = engine.transform_fovea_to_screen(50, 50, fovea_rect)
    assert sx == fovea_rect[0] + 50
    assert sy == fovea_rect[1] + 50

    # Macro center transform
    macro_w = frame.macro_image.shape[1]
    macro_h = frame.macro_image.shape[0]
    screen_x, screen_y = engine.transform_macro_to_screen(macro_w // 2, macro_h // 2, frame)
    assert 1800 <= screen_x <= 2000
    assert 500 <= screen_y <= 580
