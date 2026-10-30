"""ParasiteAI Vision Subsystem - Screen Capture & Grounding Perception Engine."""

from parasite_ai.vision.capture import ScreenCapture, compute_frame_diff
from parasite_ai.vision.grounding import (
    INTERACTIVE_ROLES,
    RawElement,
    ScreenGrounder,
    compute_containment,
    compute_iou,
)

__all__ = [
    "INTERACTIVE_ROLES",
    "RawElement",
    "ScreenCapture",
    "ScreenGrounder",
    "compute_containment",
    "compute_frame_diff",
    "compute_iou",
]
