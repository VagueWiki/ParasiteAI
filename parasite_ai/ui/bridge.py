"""
parasite_ai/ui/bridge.py - Cross-Thread UI Communication Bridge.

Provides a centralized, thread-safe signal hub connecting background worker threads
with the CompanionDock and GhostHUD widgets on the Qt main GUI thread.
"""

from __future__ import annotations

import logging
import queue
from typing import Any, List, Optional
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from parasite_ai.ui.types import UIElement

logger = logging.getLogger(__name__)


class UIBridge(QObject):
    """
    Central thread-safe signal bridge for ParasiteAI.
    Background threads call public notify_* methods;
    Qt widgets on the main thread connect to the corresponding pyqtSignals.
    """

    # --- Background Worker -> GUI Signals ---
    sig_state_changed = pyqtSignal(str, str)             # (state, mood)
    sig_thought_updated = pyqtSignal(str)                # internal monologue
    sig_speech_updated = pyqtSignal(str)                 # character dialogue
    sig_telemetry_updated = pyqtSignal([str], [str, int, int])  # (telemetry: str) or (telemetry: str, current_step: int, total_steps: int)
    sig_perception_updated = pyqtSignal(object, list)    # (QImage/QPixmap/ndarray, list[UIElement])
    sig_targets_updated = pyqtSignal(list)               # list[UIElement]
    sig_targets_cleared = pyqtSignal()                   # clear all HUD boxes
    sig_reticle_requested = pyqtSignal(int, int, int, int, str)  # (x, y, duration_ms, target_id, label)
    sig_reticle_cleared = pyqtSignal()                   # cancel reticle immediately (abort)

    # --- GUI -> Background Worker Signals ---
    sig_goal_submitted = pyqtSignal(str)                 # user goal string
    sig_pause_toggled = pyqtSignal(bool)                 # is_paused
    sig_panic_triggered = pyqtSignal()                   # emergency abort requested
    sig_hud_toggled = pyqtSignal(bool)                   # show/hide HUD overlay
    sig_brain_mode_changed = pyqtSignal(str)             # "local_llm" | "browser_offload" | "mock"

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._goal_queue: queue.Queue[str] = queue.Queue()
        # Connect goal submission to internal thread-safe queue
        self.sig_goal_submitted.connect(self._on_internal_goal_submitted)

    @pyqtSlot(str)
    def _on_internal_goal_submitted(self, goal: str) -> None:
        """Internal handler pushing user goals into the thread-safe queue."""
        self._goal_queue.put(goal)

    # -----------------------------------------------------------------------
    # Background Thread Helper Methods (Thread-Safe Signal Emitters)
    # -----------------------------------------------------------------------

    def notify_state(self, state: str, mood: str = "Curious") -> None:
        """Update companion state and mood badge from any thread."""
        self.sig_state_changed.emit(state, mood)

    def notify_thought(self, thought: str) -> None:
        """Stream internal thought monologue to companion dock."""
        self.sig_thought_updated.emit(thought)

    def notify_speech(self, speech: str) -> None:
        """Stream character dialogue speech bubble to companion dock."""
        self.sig_speech_updated.emit(speech)

    def notify_telemetry(
        self,
        telemetry: str,
        current_step: int = 0,
        total_steps: int = 0,
    ) -> None:
        """
        Update pending action telemetry and optional step progress.
        Emits 3-arg signal when step progress is provided, or 1-arg string signal for idle/simple updates.
        """
        if current_step != 0 or total_steps != 0:
            self.sig_telemetry_updated[str, int, int].emit(telemetry, current_step, total_steps)
        else:
            self.sig_telemetry_updated[str].emit(telemetry)

    def notify_perception(
        self,
        preview_image: Any,
        elements: Optional[List[UIElement]] = None,
    ) -> None:
        """Update perception preview thumbnail and detected element summary."""
        self.sig_perception_updated.emit(preview_image, elements or [])

    def set_hud_targets(self, elements: List[Any]) -> None:
        """Publish grounded UI elements to GhostHUD for Set-of-Mark overlay."""
        self.sig_targets_updated.emit(elements)

    def clear_hud_targets(self) -> None:
        """Remove all Set-of-Mark bounding boxes from GhostHUD."""
        self.sig_targets_cleared.emit()

    def show_reticle(
        self,
        x: int,
        y: int,
        duration_ms: int = 300,
        target_id: int = 0,
        label: str = "",
    ) -> None:
        """
        Request 300ms pre-click targeting reticle on GhostHUD.
        Can be plugged directly into MouseDriver as reticle_callback:
        MouseDriver(..., reticle_callback=bridge.show_reticle)
        """
        self.sig_reticle_requested.emit(x, y, duration_ms, target_id, label)

    def clear_reticle(self) -> None:
        """Immediately abort and remove the active reticle (e.g. on interrupt touch)."""
        self.sig_reticle_cleared.emit()

    def get_next_goal(self, timeout_sec: Optional[float] = None) -> Optional[str]:
        """
        Thread-safe blocking or polling getter for background engine
        to retrieve the next user goal submitted from the GUI.
        """
        try:
            return self._goal_queue.get(timeout=timeout_sec)
        except queue.Empty:
            return None

    def clear_goals(self) -> int:
        """
        Purges all pending goals from the queue (e.g. on emergency panic).
        Returns the number of discarded goals.
        """
        discarded = 0
        while not self._goal_queue.empty():
            try:
                self._goal_queue.get_nowait()
                discarded += 1
            except queue.Empty:
                break
        return discarded

