"""
ParasiteAI UI Subsystem - 100% Visible Desktop Companion Dock & Ghost-Hand Overlay.
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
from parasite_ai.ui.win32_styles import (
    apply_click_through_styles,
    GWL_EXSTYLE,
    WS_EX_LAYERED,
    WS_EX_TRANSPARENT,
    WS_EX_TOPMOST,
    WS_EX_NOACTIVATE,
    WS_EX_TOOLWINDOW,
    REQUIRED_HUD_EX_STYLES,
)
from parasite_ai.ui.bridge import UIBridge
from parasite_ai.ui.companion_dock import CompanionDock, ndarray_to_qimage
from parasite_ai.ui.ghost_hud import GhostHUD

__all__ = [
    "UIElement",
    "TargetElement",
    "UIState",
    "UIMood",
    "STATE_COLORS",
    "SOM_ROLE_COLORS",
    "init_high_dpi_awareness",
    "init_dpi_awareness",
    "ndarray_to_qimage",
    "apply_click_through_styles",
    "GWL_EXSTYLE",
    "WS_EX_LAYERED",
    "WS_EX_TRANSPARENT",
    "WS_EX_TOPMOST",
    "WS_EX_NOACTIVATE",
    "WS_EX_TOOLWINDOW",
    "REQUIRED_HUD_EX_STYLES",
    "UIBridge",
    "CompanionDock",
    "GhostHUD",
]
