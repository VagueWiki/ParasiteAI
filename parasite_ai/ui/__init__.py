"""
ParasiteAI UI & C2 Subsystem - Pure-Python Event Bus & Remote Discord C2.
"""

from parasite_ai.ui.types import (
    UIElement,
    TargetElement,
    UIState,
    UIMood,
    STATE_COLORS,
    SOM_ROLE_COLORS,
)
from parasite_ai.ui.dpi import init_high_dpi_awareness, init_dpi_awareness
from parasite_ai.ui.bridge import (
    UIBridge,
    GoalRequest,
    EpisodeEvent,
)

__all__ = [
    "UIElement",
    "TargetElement",
    "UIState",
    "UIMood",
    "STATE_COLORS",
    "SOM_ROLE_COLORS",
    "init_high_dpi_awareness",
    "init_dpi_awareness",
    "UIBridge",
    "GoalRequest",
    "EpisodeEvent",
]
