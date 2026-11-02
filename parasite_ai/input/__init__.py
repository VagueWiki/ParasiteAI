"""
parasite_ai/input - Win32 input drivers, hook structures, and hardware types.
"""

from parasite_ai.input.types import (
    POINT,
    RECT,
    MSLLHOOKSTRUCT,
    KBDLLHOOKSTRUCT,
    MOUSEINPUT,
    KEYBDINPUT,
    HARDWAREINPUT,
    INPUT_UNION,
    INPUT,
    GUITHREADINFO,
)

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
