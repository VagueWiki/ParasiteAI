"""
parasite_ai/ui/types.py - UI Element and Subsystem Data Contracts.

Defines the standard data representations for grounded UI elements,
operational states, mood badges, and category color themes.
"""

from __future__ import annotations

from typing import Dict, Literal, Optional, Tuple
import numpy as np
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


class BoundingBox(BaseModel):
    """
    Immutable 2D bounding box with padding, virtual screen boundary clamping, and frame slicing.
    """
    model_config = ConfigDict(extra="ignore", validate_default=True, frozen=True)

    x: int
    y: int
    width: int
    height: int

    def pad(
        self,
        padding_px: int = 20,
        bounds: Optional[Tuple[int, int, int, int]] = None,
    ) -> BoundingBox:
        """
        Expands the bounding box uniformly by padding_px on all four sides,
        clamping coordinates to virtual desktop bounds (min_x, min_y, max_w, max_h).
        Defaults to get_virtual_screen_bounds() if bounds is None.
        """
        if bounds is None:
            from parasite_ai.vision.capture import get_virtual_screen_bounds
            vx, vy, vw, vh = get_virtual_screen_bounds()
        else:
            vx, vy, vw, vh = bounds

        min_x = vx
        min_y = vy
        max_x = vx + vw
        max_y = vy + vh

        new_x = max(min_x, self.x - padding_px)
        new_y = max(min_y, self.y - padding_px)
        new_right = min(max_x, self.x + self.width + padding_px)
        new_bottom = min(max_y, self.y + self.height + padding_px)

        new_w = max(0, new_right - new_x)
        new_h = max(0, new_bottom - new_y)
        return BoundingBox(x=new_x, y=new_y, width=new_w, height=new_h)

    def as_tuple(self) -> Tuple[int, int, int, int]:
        """Returns (x, y, width, height) tuple."""
        return (self.x, self.y, self.width, self.height)

    def crop_frame(
        self,
        frame: Optional[np.ndarray],
        bounds: Optional[Tuple[int, int, int, int]] = None,
    ) -> Optional[np.ndarray]:
        """
        Extracts localized ROI crop from a numpy image frame clamped to array dimensions.
        """
        if frame is None or frame.size == 0:
            return None
        fh, fw = frame.shape[:2]
        vx = bounds[0] if bounds else 0
        vy = bounds[1] if bounds else 0

        rel_x1 = max(0, min(self.x - vx, fw))
        rel_y1 = max(0, min(self.y - vy, fh))
        rel_x2 = max(0, min(self.x + self.width - vx, fw))
        rel_y2 = max(0, min(self.y + self.height - vy, fh))

        if rel_y2 <= rel_y1 or rel_x2 <= rel_x1:
            return None
        return frame[rel_y1:rel_y2, rel_x1:rel_x2]


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
    process_name: str = Field(
        default="",
        description="Parent application process executable name, e.g. notepad.exe."
    )
    window_title: str = Field(
        default="",
        description="Parent window title containing this element."
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

    @property
    def target_bbox(self) -> BoundingBox:
        """Returns BoundingBox instance corresponding to this element."""
        return BoundingBox(x=self.x, y=self.y, width=self.width, height=self.height)

    def pad(
        self,
        padding_px: int = 20,
        bounds: Optional[Tuple[int, int, int, int]] = None,
    ) -> BoundingBox:
        """Convenience method returning target_bbox padded and clamped to virtual bounds."""
        return self.target_bbox.pad(padding_px=padding_px, bounds=bounds)

    @classmethod
    def from_bbox(
        cls,
        id: int,
        bbox: Tuple[int, int, int, int],
        label: str = "",
        role: str = "Button",
        source: Literal["uia", "ocr", "merged", "mock"] = "uia",
        is_active_window: bool = True,
        process_name: str = "",
        window_title: str = "",
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
            process_name=process_name,
            window_title=window_title,
        )


# Alias for explicit target references
TargetElement = UIElement
