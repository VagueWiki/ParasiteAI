"""
tests/test_dpi.py - Tests for Windows High-DPI Awareness Bootstrap.
Verifies Per-Monitor v2 initialization, idempotency across repeated runs, and fallback handling.
"""

from __future__ import annotations

import ctypes
import sys
from unittest.mock import MagicMock, patch
import pytest

from parasite_ai.ui.dpi import init_high_dpi_awareness


class TestHighDPIAwareness:
    def test_init_high_dpi_awareness_success(self):
        """Verifies that init_high_dpi_awareness returns a boolean without throwing."""
        result = init_high_dpi_awareness()
        if sys.platform == "win32":
            assert result is True
        else:
            assert result is False

    def test_init_high_dpi_awareness_idempotency(self):
        """Verifies multiple consecutive invocations succeed idempotently."""
        r1 = init_high_dpi_awareness()
        r2 = init_high_dpi_awareness()
        assert r1 == r2

    def test_init_high_dpi_non_windows_fallback(self):
        """Verifies that on non-Windows platforms it safely returns False."""
        with patch("sys.platform", "linux"):
            assert init_high_dpi_awareness() is False

        with patch("sys.platform", "darwin"):
            assert init_high_dpi_awareness() is False

    def test_fallback_to_shcore_when_user32_v2_fails(self):
        """Tests fallback to shcore.SetProcessDpiAwareness when context call fails."""
        mock_user32 = MagicMock()
        mock_user32.SetProcessDpiAwarenessContext.side_effect = AttributeError("No SetProcessDpiAwarenessContext")
        mock_user32.SetProcessDPIAware.return_value = 1

        mock_shcore = MagicMock()
        mock_shcore.SetProcessDpiAwareness.return_value = 0  # S_OK

        with patch("sys.platform", "win32"), \
             patch("ctypes.windll.user32", mock_user32), \
             patch("ctypes.windll.shcore", mock_shcore):
            res = init_high_dpi_awareness()
            assert res is True
            mock_shcore.SetProcessDpiAwareness.assert_called_once_with(2)

    def test_fallback_to_user32_dpi_aware(self):
        """Tests fallback to legacy user32.SetProcessDPIAware when shcore fails."""
        mock_user32 = MagicMock()
        mock_user32.SetProcessDpiAwarenessContext.side_effect = AttributeError("No context API")
        mock_user32.SetProcessDPIAware.return_value = 1

        mock_shcore = MagicMock()
        mock_shcore.SetProcessDpiAwareness.side_effect = OSError("No shcore.dll")

        with patch("sys.platform", "win32"), \
             patch("ctypes.windll.user32", mock_user32), \
             patch("ctypes.windll.shcore", mock_shcore):
            res = init_high_dpi_awareness()
            assert res is True
            mock_user32.SetProcessDPIAware.assert_called_once()

    def test_all_dpi_apis_fail_returns_false(self):
        """Tests that when all Win32 DPI APIs fail, returns False gracefully."""
        mock_user32 = MagicMock()
        mock_user32.SetProcessDpiAwarenessContext.side_effect = OSError("Failed")
        mock_user32.SetProcessDPIAware.side_effect = OSError("Failed")

        mock_shcore = MagicMock()
        mock_shcore.SetProcessDpiAwareness.side_effect = OSError("Failed")

        with patch("sys.platform", "win32"), \
             patch("ctypes.windll.user32", mock_user32), \
             patch("ctypes.windll.shcore", mock_shcore):
            res = init_high_dpi_awareness()
            assert res is False
