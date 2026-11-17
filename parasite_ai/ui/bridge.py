"""
parasite_ai/ui/bridge.py - Pure-Python Decoupled UI & C2 Event Bridge.

Provides a centralized, thread-safe event bus and goal queue connecting
background worker threads with remote C2 interfaces (e.g. Discord bot)
and external subscribers with zero PyQt6 dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
import queue
import threading
from typing import Any, Callable, Dict, List, Optional

from parasite_ai.ui.types import UIElement

logger = logging.getLogger(__name__)


@dataclass
class GoalRequest:
    """Encapsulates a user goal execution request with caller metadata and consent routing."""
    goal: str
    max_steps: Optional[int] = None
    source: str = "local"  # "local" | "discord" | "benchmark"
    metadata: Dict[str, Any] = field(default_factory=dict)
    consent_callback: Optional[Callable[[Any], bool]] = None


@dataclass
class EpisodeEvent:
    """Structured event emitted across the lifecycle of a goal episode."""
    kind: str  # "started" | "step_completed" | "finished" | "interrupted" | "consent_requested"
    goal: str
    step: int = 0
    data: Dict[str, Any] = field(default_factory=dict)


class Signal:
    """
    Lightweight, thread-safe pure-Python signal dispatcher.
    Provides .connect() and .emit() compatibility with Qt-style call sites without Qt.
    """

    def __init__(self, name: str = "signal") -> None:
        self.name = name
        self._callbacks: List[Callable[..., Any]] = []
        self._lock = threading.RLock()

    def connect(self, callback: Callable[..., Any]) -> None:
        with self._lock:
            if callback not in self._callbacks:
                self._callbacks.append(callback)

    def disconnect(self, callback: Callable[..., Any]) -> None:
        with self._lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)

    def emit(self, *args: Any, **kwargs: Any) -> None:
        with self._lock:
            callbacks = list(self._callbacks)
        for cb in callbacks:
            try:
                cb(*args, **kwargs)
            except Exception as e:
                logger.warning(f"Error executing callback in signal '{self.name}': {e}", exc_info=True)

    def __getitem__(self, item: Any) -> Signal:
        """Compatibility shim for typed indexing e.g. sig_telemetry_updated[str, int, int]."""
        return self


class UIBridge:
    """
    Central thread-safe pure-Python signal bridge for ParasiteAI.
    Background worker threads call notify_* methods;
    C2 listeners and subscribers connect to signals or register event handlers.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._goal_queue: queue.Queue[GoalRequest] = queue.Queue()
        self._episode_event_subscribers: List[Callable[[EpisodeEvent], None]] = []

        # --- Worker -> GUI/C2 Signals ---
        self.sig_state_changed = Signal("sig_state_changed")              # (state: str, mood: str)
        self.sig_thought_updated = Signal("sig_thought_updated")          # (thought: str)
        self.sig_speech_updated = Signal("sig_speech_updated")            # (speech: str)
        self.sig_telemetry_updated = Signal("sig_telemetry_updated")      # (telemetry: str, [cur_step, tot_step])
        self.sig_perception_updated = Signal("sig_perception_updated")    # (preview_image, elements)
        self.sig_targets_updated = Signal("sig_targets_updated")          # (elements: list)
        self.sig_targets_cleared = Signal("sig_targets_cleared")          # ()
        self.sig_reticle_requested = Signal("sig_reticle_requested")      # (x, y, duration_ms, target_id, label)
        self.sig_reticle_cleared = Signal("sig_reticle_cleared")          # ()
        self.sig_dock_minimize_requested = Signal("sig_dock_minimize")    # ()
        self.sig_dock_restore_requested = Signal("sig_dock_restore")      # ()
        self.sig_dock_evade_requested = Signal("sig_dock_evade")          # (x, y)

        # --- GUI/C2 -> Worker Signals ---
        self.sig_goal_submitted = Signal("sig_goal_submitted")            # (goal: str)
        self.sig_pause_toggled = Signal("sig_pause_toggled")              # (is_paused: bool)
        self.sig_panic_triggered = Signal("sig_panic_triggered")          # ()
        self.sig_hud_toggled = Signal("sig_hud_toggled")                  # (is_active: bool)
        self.sig_brain_mode_changed = Signal("sig_brain_mode_changed")    # (mode: str)
        self.sig_close_requested = Signal("sig_close_requested")          # ()

        # Connect standard goal signal to internal queue
        self.sig_goal_submitted.connect(self._on_internal_goal_submitted)

    def _on_internal_goal_submitted(self, goal: str) -> None:
        """Internal handler translating raw string submission into a GoalRequest."""
        req = GoalRequest(goal=goal, source="local")
        self._goal_queue.put(req)

    # -----------------------------------------------------------------------
    # Goal Queue & Control APIs
    # -----------------------------------------------------------------------

    def submit_goal(
        self,
        goal: str,
        max_steps: Optional[int] = None,
        source: str = "local",
        metadata: Optional[Dict[str, Any]] = None,
        consent_callback: Optional[Callable[[Any], bool]] = None,
    ) -> None:
        """Submit a structured goal request into the engine queue."""
        req = GoalRequest(
            goal=goal,
            max_steps=max_steps,
            source=source,
            metadata=metadata or {},
            consent_callback=consent_callback,
        )
        self._goal_queue.put(req)

    def get_next_goal_request(self, timeout_sec: Optional[float] = None) -> Optional[GoalRequest]:
        """Retrieve the next structured GoalRequest (thread-safe, blocking/polling)."""
        try:
            return self._goal_queue.get(timeout=timeout_sec)
        except queue.Empty:
            return None

    def get_next_goal(self, timeout_sec: Optional[float] = None) -> Optional[str]:
        """Backward-compatible getter returning raw goal string."""
        req = self.get_next_goal_request(timeout_sec=timeout_sec)
        return req.goal if req else None

    def clear_goals(self) -> int:
        """Purge all pending goals from the queue. Returns count discarded."""
        discarded = 0
        while not self._goal_queue.empty():
            try:
                self._goal_queue.get_nowait()
                discarded += 1
            except queue.Empty:
                break
        return discarded

    def trigger_pause(self, paused: bool) -> None:
        """Toggle pause state from any C2 thread."""
        self.sig_pause_toggled.emit(paused)

    def trigger_panic(self, source: str = "ui") -> None:
        """Trigger emergency abort from any C2 thread."""
        logger.warning(f"Panic triggered via UIBridge from source: {source}")
        self.sig_panic_triggered.emit()

    # -----------------------------------------------------------------------
    # Worker Thread Helper Methods (Signal Emitters)
    # -----------------------------------------------------------------------

    def notify_state(self, state: str, mood: str = "Curious") -> None:
        """Update state and mood from any thread."""
        self.sig_state_changed.emit(state, mood)

    def notify_thought(self, thought: str) -> None:
        """Stream internal thought monologue."""
        self.sig_thought_updated.emit(thought)

    def notify_speech(self, speech: str) -> None:
        """Stream character dialogue speech."""
        self.sig_speech_updated.emit(speech)

    def notify_telemetry(
        self,
        telemetry: str,
        current_step: int = 0,
        total_steps: int = 0,
    ) -> None:
        """Update pending action telemetry and step progress."""
        if current_step != 0 or total_steps != 0:
            self.sig_telemetry_updated.emit(telemetry, current_step, total_steps)
        else:
            self.sig_telemetry_updated.emit(telemetry)

    def notify_perception(
        self,
        preview_image: Any,
        elements: Optional[List[UIElement]] = None,
    ) -> None:
        """Update perception preview and detected elements."""
        self.sig_perception_updated.emit(preview_image, elements or [])

    def set_hud_targets(self, elements: List[Any]) -> None:
        """Publish grounded UI elements for visualizers."""
        self.sig_targets_updated.emit(elements)

    def clear_hud_targets(self) -> None:
        """Clear all HUD bounding targets."""
        self.sig_targets_cleared.emit()

    def show_reticle(
        self,
        x: int,
        y: int,
        duration_ms: int = 300,
        target_id: int = 0,
        label: str = "",
    ) -> None:
        """Request targeting reticle visualization."""
        self.sig_reticle_requested.emit(x, y, duration_ms, target_id, label)

    def clear_reticle(self) -> None:
        """Cancel active reticle visualization."""
        self.sig_reticle_cleared.emit()

    def minimize_dock(self) -> None:
        """Compatibility no-op."""
        self.sig_dock_minimize_requested.emit()

    def evade_dock(self, x: int, y: int) -> None:
        """Compatibility no-op."""
        self.sig_dock_evade_requested.emit(int(x), int(y))

    def restore_dock(self) -> None:
        """Compatibility no-op."""
        self.sig_dock_restore_requested.emit()

    # -----------------------------------------------------------------------
    # Structured Episode Lifecycle Events
    # -----------------------------------------------------------------------

    def subscribe_episode_events(self, callback: Callable[[EpisodeEvent], None]) -> None:
        with self._lock:
            if callback not in self._episode_event_subscribers:
                self._episode_event_subscribers.append(callback)

    def unsubscribe_episode_events(self, callback: Callable[[EpisodeEvent], None]) -> None:
        with self._lock:
            if callback in self._episode_event_subscribers:
                self._episode_event_subscribers.remove(callback)

    def notify_episode_event(self, event: EpisodeEvent) -> None:
        with self._lock:
            subscribers = list(self._episode_event_subscribers)
        for sub in subscribers:
            try:
                sub(event)
            except Exception as e:
                logger.warning(f"Error executing episode event subscriber: {e}", exc_info=True)
