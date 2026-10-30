"""
ParasiteAI Safety Subsystem.
Low-level Win32 hardware hooks, sub-2ms preemption, panic hotkeys, and window privacy guard.
"""

from parasite_ai.safety.interrupt_guard import (
    InterruptGuard,
    LLKHF_INJECTED,
    LLMHF_INJECTED,
    LLMHF_LOWER_IL_INJECTED,
    PanicInterruptException,
    PhysicalInterruptException,
    WH_KEYBOARD_LL,
    WH_MOUSE_LL,
)
from parasite_ai.safety.panic import (
    PanicManager,
    PanicTriggerSource,
)
from parasite_ai.safety.window_guard import (
    DEFAULT_SENSITIVE_PROCESSES,
    DEFAULT_SENSITIVE_TITLES,
    WindowGuard,
    WindowGuardedException,
    WindowInfo,
)

__all__ = [
    "InterruptGuard",
    "PhysicalInterruptException",
    "PanicInterruptException",
    "PanicManager",
    "PanicTriggerSource",
    "WindowGuard",
    "WindowInfo",
    "WindowGuardedException",
    "LLMHF_INJECTED",
    "LLMHF_LOWER_IL_INJECTED",
    "LLKHF_INJECTED",
    "WH_MOUSE_LL",
    "WH_KEYBOARD_LL",
    "DEFAULT_SENSITIVE_PROCESSES",
    "DEFAULT_SENSITIVE_TITLES",
]
