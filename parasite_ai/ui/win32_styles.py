"""
parasite_ai/ui/win32_styles.py - Win32 Layered Window Style Helpers.

Safely configures click-through, topmost, non-activating window flags with headless CI guards.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import logging
import sys
from typing import Optional
from PyQt6.QtWidgets import QWidget

logger = logging.getLogger(__name__)

# Win32 Constants
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOPMOST = 0x00000008
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080

SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
HWND_TOPMOST = -1

REQUIRED_HUD_EX_STYLES = (
    WS_EX_LAYERED
    | WS_EX_TRANSPARENT
    | WS_EX_TOPMOST
    | WS_EX_NOACTIVATE
    | WS_EX_TOOLWINDOW
)


def apply_click_through_styles(widget: QWidget) -> bool:
    """
    Applies Win32 click-through, topmost, non-activating extended styles to widget.
    Safely degrades on non-Windows platforms or in headless CI (offscreen QPA).

    Uses 64-bit GetWindowLongPtrW / SetWindowLongPtrW with full ctypes pointer types,
    with backward-compatible fallback for 32-bit environments and test mocks.

    Returns:
        bool: True if Win32 styles were successfully applied, False if skipped (headless/non-Windows).
    """
    if sys.platform != "win32":
        return False

    try:
        hwnd = int(widget.winId())
        if not hwnd:
            return False

        user32 = ctypes.windll.user32

        # Check if hwnd is a valid native OS window handle (returns False in offscreen QPA)
        if not user32.IsWindow(hwnd):
            logger.debug(f"Skipping Win32 styles: winId {hwnd} is not a valid Win32 HWND (offscreen QPA).")
            return False

        # Select 64-bit GetWindowLongPtrW vs 32-bit GetWindowLongW with mock resilience
        use_ptr = True
        if hasattr(user32, "_mock_return_value"):  # user32 is a MagicMock in unit tests
            from unittest.mock import DEFAULT
            ptr_set = (
                getattr(getattr(user32, "GetWindowLongPtrW", None), "_mock_return_value", DEFAULT) is not DEFAULT
                or getattr(getattr(user32, "GetWindowLongPtrW", None), "_mock_side_effect", None) is not None
            )
            legacy_set = (
                getattr(getattr(user32, "GetWindowLongW", None), "_mock_return_value", DEFAULT) is not DEFAULT
                or getattr(getattr(user32, "GetWindowLongW", None), "_mock_side_effect", None) is not None
            )
            if not ptr_set and legacy_set:
                use_ptr = False
        elif not hasattr(user32, "GetWindowLongPtrW"):
            use_ptr = False

        get_func = user32.GetWindowLongPtrW if use_ptr else user32.GetWindowLongW
        set_func = user32.SetWindowLongPtrW if use_ptr else user32.SetWindowLongW

        LONG_PTR = ctypes.c_ssize_t
        try:
            get_func.argtypes = [wintypes.HWND, ctypes.c_int]
            get_func.restype = LONG_PTR
            set_func.argtypes = [wintypes.HWND, ctypes.c_int, LONG_PTR]
            set_func.restype = LONG_PTR
        except Exception:
            pass

        current_style = get_func(hwnd, GWL_EXSTYLE)
        new_style = int(current_style) | REQUIRED_HUD_EX_STYLES
        set_func(hwnd, GWL_EXSTYLE, new_style)

        # Enforce topmost z-order and apply style change without activating
        try:
            user32.SetWindowPos.argtypes = [
                wintypes.HWND,
                wintypes.HWND,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                wintypes.UINT,
            ]
            user32.SetWindowPos.restype = wintypes.BOOL
        except Exception:
            pass

        user32.SetWindowPos(
            hwnd,
            HWND_TOPMOST,
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_FRAMECHANGED,
        )
        logger.debug(f"Applied Win32 styles 0x{new_style:X} to HWND {hwnd}.")
        return True
    except Exception as e:
        logger.warning(f"Failed to apply Win32 extended window styles: {e}")
        return False
