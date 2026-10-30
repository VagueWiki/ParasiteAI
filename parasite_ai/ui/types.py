"""
parasite_ai/ui/types.py - UI Element and Subsystem Data Contracts.

Defines the standard data representations for grounded UI elements,
operational states, mood badges, and category color themes.
"""

from __future__ import annotations

from typing import Dict, Literal, Tuple
from pydantic import BaseModel, ConfigDict, Field, computed_field

# Operational cognitive states
UIState = Literal[
    "WATCHING",      # Idling, observing screen, waiting for goal
    "THINKING",      # LLM reasoning / planning next step
    "DRIVING",       # Moving physical mouse or typing
    "USER_OVERRIDE", # Paused due to physical human touch (<2ms abort)
    "OFFLOADING",    # Interacting with Chrome web AI
    "PROTECTED",     # Sensitive window active; vision masked
]

# Character moods
UIMood = Literal[
    "Curious",
    "Focused",
    "Cautious",
    "Amused",
    "Panic-Averted",
    "Idle",
]

# State accent color palette (Hex codes)
STATE_COLORS: Dict[str, str] = {
    "WATCHING": "#10B981",       # Emerald Green
    "THINKING": "#F59E0B",       # Amber Orange
    "DRIVING": "#EF4444",        # Crimson Red
    "USER_OVERRIDE": "#06B6D4",  # Cyan Blue
    "OFFLOADING": "#8B5CF6",     # Electric Purple
    "PROTECTED": "#94A3B8",      # Steely Grey
}

# Set-of-Mark color theme by control role
SOM_ROLE_COLORS: Dict[str, str] = {
    "Button": "#00E5FF",         # Neon Cyan
    "Edit": "#FF007F",           # Hot Magenta
    "Hyperlink": "#3B82F6",      # Electric Blue
    "TabItem": "#3B82F6",        # Electric Blue
    "Text": "#F59E0B",           # Gold Amber (OCR)
    "Document": "#00E5FF",       # Cyan
    "MenuItem": "#00E5FF",       # Cyan
    "CheckBox": "#00E5FF",       # Cyan
    "RadioButton": "#00E5FF",    # Cyan
    "ComboBox": "#FF007F",       # Hot Magenta
    "OCR": "#F59E0B",            # Gold Amber
    "Label": "#F59E0B",          # Gold Amber
}


class UIElement(BaseModel):
    """
    Standard data contract representing a grounded desktop interactive element.
    Used by ScreenGrounder, GhostHUD, ActionDispatcher, and DualMindPipeline.
    """
    model_config = ConfigDict(extra="ignore", validate_default=True, frozen=True)

    id: int = Field(ge=1, description="1-based Set-of-Mark unique index [#1..#N].")
    role: str = Field(default="Button", description="Control role (Button, Edit, Text, etc.).")
    label: str = Field(default="", description="Accessible name or OCR text label.")
    x: int = Field(description="Top-left X coordinate in desktop pixel space.")
    y: int = Field(description="Top-left Y coordinate in desktop pixel space.")
    width: int = Field(ge=0, description="Element width in pixels.")
    height: int = Field(ge=0, description="Element height in pixels.")
    center_x: int = Field(description="Center target X coordinate for clicking.")
    center_y: int = Field(description="Center target Y coordinate for clicking.")
    source: Literal["uia", "ocr", "merged", "mock"] = Field(
        default="uia",
        description="Grounding origin source."
    )
    is_active_window: bool = Field(
        default=True,
        description="Whether element resides within the active foreground window."
    )

    @computed_field
    @property
    def bbox(self) -> Tuple[int, int, int, int]:
        """Returns (x, y, width, height) tuple."""
        return (self.x, self.y, self.width, self.height)

    @computed_field
    @property
    def center(self) -> Tuple[int, int]:
        """Returns (center_x, center_y) click coordinate tuple."""
        return (self.center_x, self.center_y)

    @property
    def control_type(self) -> str:
        """Alias returning role for compatibility with PROJECT.md spec."""
        return self.role

    @classmethod
    def from_bbox(
        cls,
        id: int,
        bbox: Tuple[int, int, int, int],
        label: str = "",
        role: str = "Button",
        source: Literal["uia", "ocr", "merged", "mock"] = "uia",
        is_active_window: bool = True,
    ) -> UIElement:
        """Convenience constructor calculating centers automatically."""
        x, y, w, h = bbox
        return cls(
            id=id,
            role=role,
            label=label,
            x=x,
            y=y,
            width=w,
            height=h,
            center_x=x + w // 2,
            center_y=y + h // 2,
            source=source,
            is_active_window=is_active_window,
        )


# Alias for explicit target references
TargetElement = UIElement
