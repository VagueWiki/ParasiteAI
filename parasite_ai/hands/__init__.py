"""
ParasiteAI Hands Subsystem.
Physical human-like mouse kinematics, reticle preview, and Unicode physical keyboard driver.
"""

from parasite_ai.hands.clipboard import (
    BI_RGB,
    CF_DIB,
    CF_UNICODETEXT,
    ClipboardError,
    ClipboardLockedError,
    ClipboardSnapshot,
    DibPackError,
    IImageClipboard,
    IWin32ClipboardAPI,
    MockWin32ClipboardAPI,
    Win32ClipboardAPI,
    Win32ImageClipboard,
    pack_dib,
)
from parasite_ai.hands.keyboard import (
    CapturedInputEvent,
    IInputBackend,
    INPUT,
    INPUT_KEYBOARD,
    INPUT_MOUSE,
    KEYBDINPUT,
    KeyboardDriver,
    MockInputBackend,
    MOUSEINPUT,
    Win32InputBackend,
)
from parasite_ai.hands.kinematics import (
    KinematicConfig,
    KinematicsEngine,
)
from parasite_ai.hands.mouse import MouseDriver
from parasite_ai.hands.reflex import ReflexBurstDispatcher, ReflexBurstResult

__all__ = [
    "KinematicConfig",
    "KinematicsEngine",
    "MouseDriver",
    "KeyboardDriver",
    "ReflexBurstDispatcher",
    "ReflexBurstResult",
    "IInputBackend",
    "Win32InputBackend",
    "MockInputBackend",
    "INPUT",
    "KEYBDINPUT",
    "MOUSEINPUT",
    "INPUT_MOUSE",
    "INPUT_KEYBOARD",
    "CapturedInputEvent",
    "BI_RGB",
    "CF_DIB",
    "CF_UNICODETEXT",
    "ClipboardError",
    "ClipboardLockedError",
    "ClipboardSnapshot",
    "DibPackError",
    "IImageClipboard",
    "IWin32ClipboardAPI",
    "MockWin32ClipboardAPI",
    "Win32ClipboardAPI",
    "Win32ImageClipboard",
    "pack_dib",
]
