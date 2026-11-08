"""
tests/conftest.py - Centralized Pytest Test Doubles and Shared Fixtures for ParasiteAI.
"""

from __future__ import annotations

import os
from types import SimpleNamespace
from typing import Any, Generator, Tuple
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from parasite_ai.config import AppConfig


class MockRect:
    """Mock bounding rectangle conforming to Win32 UIA BoundingRectangle methods and attributes."""

    def __init__(self, left: int, top: int, width: int, height: int) -> None:
        self.left = left
        self.top = top
        self._w = width
        self._h = height
        self.right = left + width
        self.bottom = top + height

    def width(self) -> int:
        return self._w

    def height(self) -> int:
        return self._h

    def xcenter(self) -> int:
        return self.left + self._w // 2

    def ycenter(self) -> int:
        return self.top + self._h // 2


class MockControl:
    """Mock Win32 UI Automation control node."""

    def __init__(
        self,
        name: str,
        ctl_type: str,
        left: int = 100,
        top: int = 100,
        width: int = 120,
        height: int = 32,
        is_offscreen: bool = False,
        class_name: str = "Button",
        process_id: int = 99999,
        native_window_handle: int = 0,
        help_text: str = "",
        auto_id: str = "",
    ) -> None:
        self.Name = name
        self.ControlTypeName = ctl_type
        self.ClassName = class_name
        self.ProcessId = process_id
        self.NativeWindowHandle = native_window_handle
        self.BoundingRectangle = MockRect(left, top, width, height)
        self.IsOffscreen = is_offscreen
        self.AutomationId = auto_id or f"auto_{name}"
        self.HelpText = help_text


@pytest.fixture
def dummy_1080p_frame() -> np.ndarray:
    """Returns a synthetic 1080p BGR frame (1080, 1920, 3)."""
    return np.zeros((1080, 1920, 3), dtype=np.uint8)


@pytest.fixture
def dummy_720p_frame() -> np.ndarray:
    """Returns a synthetic 720p BGR frame (720, 1280, 3)."""
    return np.zeros((720, 1280, 3), dtype=np.uint8)


@pytest.fixture
def mock_app_config() -> AppConfig:
    """Returns standard AppConfig instance for unit tests."""
    return AppConfig()
