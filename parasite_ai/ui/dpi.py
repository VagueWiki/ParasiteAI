"""
parasite_ai/ui/dpi.py - High-DPI Awareness Bootstrapper.

Ensures 1:1 pixel coordinate parity between Windows physical display,
Win32 UI Automation, screen capture (mss), and PyQt6 overlays.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import logging
import sys

logger = logging.getLogger(__name__)


def init_high_dpi_awareness() -> bool:
    """
    Initializes Windows Per-Monitor v2 High-DPI awareness before QApplication startup.
    Idempotent and safe across multiple invocations, headless environments, and non-Windows OS.

    Returns:
        bool: True if DPI awareness is active (or already set), False on unsupported platforms.
    """
    if sys.platform != "win32":
        return False

    # 1. Primary: Windows 10 Creators Update 1703+ (Per-Monitor v2)
    try:
        user32 = ctypes.windll.user32
        user32.SetProcessDpiAwarenessContext.restype = wintypes.BOOL
        user32.SetProcessDpiAwarenessContext.argtypes = [wintypes.HANDLE]
        DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)
        if user32.SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2):
            logger.debug("Initialized Per-Monitor v2 DPI Awareness via SetProcessDpiAwarenessContext.")
            return True
        # If returns False, check if it was already set (ERROR_ACCESS_DENIED = 5)
        err = ctypes.windll.kernel32.GetLastError()
        if err == 5:
            logger.debug("DPI awareness already configured for this process (ERROR_ACCESS_DENIED).")
            return True
    except (AttributeError, OSError) as e:
        logger.debug(f"SetProcessDpiAwarenessContext unavailable: {e}")

    # 2. Secondary: Windows 8.1+ (shcore.SetProcessDpiAwareness(2))
    try:
        shcore = ctypes.windll.shcore
        shcore.SetProcessDpiAwareness.restype = ctypes.c_long
        shcore.SetProcessDpiAwareness.argtypes = [ctypes.c_int]
        # PROCESS_PER_MONITOR_DPI_AWARE = 2
        hr = shcore.SetProcessDpiAwareness(2)
        # S_OK = 0, E_ACCESSDENIED = 0x80070005 (-2147024891)
        if hr == 0 or hr == -2147024891 or (hr & 0xFFFFFFFF) == 0x80070005:
            logger.debug("Initialized Per-Monitor DPI Awareness via shcore.SetProcessDpiAwareness.")
            return True
    except (AttributeError, OSError) as e:
        logger.debug(f"shcore.SetProcessDpiAwareness unavailable: {e}")

    # 3. Fallback: Windows Vista+ (user32.SetProcessDPIAware())
    try:
        user32 = ctypes.windll.user32
        user32.SetProcessDPIAware.restype = wintypes.BOOL
        return bool(user32.SetProcessDPIAware())
    except (AttributeError, OSError) as e:
        logger.debug(f"SetProcessDPIAware fallback failed: {e}")
        return False


# Interface alias for M5 contract compliance
init_dpi_awareness = init_high_dpi_awareness

