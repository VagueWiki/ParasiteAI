"""
parasite_ai/input/types.py - Win32 Ctypes Structures Inventory.
Verified 64-bit Windows ABI memory layouts for input hooks, window metrics, and caret detection.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes

from parasite_ai.safety.interrupt_guard import (
    POINT,
    MSLLHOOKSTRUCT,
    KBDLLHOOKSTRUCT,
)
from parasite_ai.safety.window_guard import RECT
from parasite_ai.hands.keyboard import (
    MOUSEINPUT,
    KEYBDINPUT,
    HARDWAREINPUT,
    INPUT_UNION,
    INPUT,
)
from parasite_ai.mind.dual_mind import GUITHREADINFO

__all__ = [
    "POINT",
    "RECT",
    "MSLLHOOKSTRUCT",
    "KBDLLHOOKSTRUCT",
    "MOUSEINPUT",
    "KEYBDINPUT",
    "HARDWAREINPUT",
    "INPUT_UNION",
    "INPUT",
    "GUITHREADINFO",
]
