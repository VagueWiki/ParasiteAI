"""
ParasiteAI Hands Subsystem.
Physical human-like mouse kinematics, reticle preview, and Unicode physical keyboard driver.
"""

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

__all__ = [
    "KinematicConfig",
    "KinematicsEngine",
    "MouseDriver",
    "KeyboardDriver",
    "IInputBackend",
    "Win32InputBackend",
    "MockInputBackend",
    "INPUT",
    "KEYBDINPUT",
    "MOUSEINPUT",
    "INPUT_MOUSE",
    "INPUT_KEYBOARD",
    "CapturedInputEvent",
]
