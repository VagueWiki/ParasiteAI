"""
tests/unit/ui/test_ui_bridge.py - Pure-Python UIBridge Event Bus & Queue Test Suite.
Verifies thread-safe communication, goal queue routing, episode events, and zero Qt dependencies.
"""

from __future__ import annotations

import threading
import time
import pytest

from parasite_ai.ui.bridge import EpisodeEvent, GoalRequest, UIBridge
from parasite_ai.ui.types import UIElement


class TestUIBridge:
    def test_ui_bridge_cross_thread_state_notification(self) -> None:
        """Verifies state changes emitted from background thread are delivered to connected listener."""
        bridge = UIBridge()
        received = []
        event = threading.Event()

        def on_state(state: str, mood: str) -> None:
            received.append((state, mood))
            event.set()

        bridge.sig_state_changed.connect(on_state)

        def worker():
            time.sleep(0.01)
            bridge.notify_state("DRIVING", "Focused")

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        t.join(timeout=1.0)
        assert event.wait(timeout=1.0)
        assert received == [("DRIVING", "Focused")]

    def test_ui_bridge_cross_thread_thought_and_speech(self) -> None:
        """Verifies thoughts and speech emitted reach signal listeners."""
        bridge = UIBridge()
        thoughts = []
        speeches = []

        bridge.sig_thought_updated.connect(lambda t: thoughts.append(t))
        bridge.sig_speech_updated.connect(lambda s: speeches.append(s))

        bridge.notify_thought("Analyzing DOM...")
        bridge.notify_speech("Clicking the login button.")

        assert thoughts == ["Analyzing DOM..."]
        assert speeches == ["Clicking the login button."]

    def test_ui_bridge_cross_thread_telemetry_notification(self) -> None:
        """Verifies action telemetry is emitted across threads with step tracking."""
        bridge = UIBridge()
        telemetry_msgs = []

        def on_telem(msg: str, cur: int = 0, tot: int = 0) -> None:
            telemetry_msgs.append((msg, cur, tot))

        bridge.sig_telemetry_updated.connect(on_telem)

        bridge.notify_telemetry("Target: [#2] Edit 'Search'", current_step=2, total_steps=10)
        assert len(telemetry_msgs) == 1
        assert telemetry_msgs[0] == ("Target: [#2] Edit 'Search'", 2, 10)

    def test_ui_bridge_cross_thread_reticle_request_and_clear(self) -> None:
        """Verifies pre-click reticle request and abort signals."""
        bridge = UIBridge()
        reticles = []
        cleared = []

        bridge.sig_reticle_requested.connect(lambda x, y, dur, tid, lbl: reticles.append((x, y, dur, tid, lbl)))
        bridge.sig_reticle_cleared.connect(lambda: cleared.append(True))

        bridge.show_reticle(450, 320, 300, 14, "Submit Button")
        bridge.clear_reticle()

        assert reticles == [(450, 320, 300, 14, "Submit Button")]
        assert cleared == [True]

    def test_ui_bridge_targets_signal_marshalling(self) -> None:
        """Verifies UIElement objects are marshalled across threads."""
        bridge = UIBridge()
        targets_received = []
        cleared = []

        bridge.sig_targets_updated.connect(lambda elems: targets_received.append(elems))
        bridge.sig_targets_cleared.connect(lambda: cleared.append(True))

        elem1 = UIElement.from_bbox(id=1, bbox=(10, 20, 100, 40), label="Search", role="Edit")
        elem2 = UIElement.from_bbox(id=2, bbox=(120, 20, 60, 40), label="Go", role="Button")

        bridge.set_hud_targets([elem1, elem2])
        assert len(targets_received) == 1
        assert len(targets_received[0]) == 2
        assert targets_received[0][0].label == "Search"
        assert targets_received[0][1].label == "Go"

        bridge.clear_hud_targets()
        assert cleared == [True]

    def test_ui_bridge_structured_goal_queue(self) -> None:
        """Verifies user goal submitted with source/metadata is queued and retrievable."""
        bridge = UIBridge()

        # Submit structured goal
        bridge.submit_goal(
            goal="Open Google Chrome and search for news",
            max_steps=20,
            source="discord",
            metadata={"user_id": 12345},
        )

        req = bridge.get_next_goal_request(timeout_sec=0.5)
        assert req is not None
        assert req.goal == "Open Google Chrome and search for news"
        assert req.max_steps == 20
        assert req.source == "discord"
        assert req.metadata == {"user_id": 12345}

        # Empty queue returns None
        assert bridge.get_next_goal_request(timeout_sec=0.01) is None
        assert bridge.get_next_goal(timeout_sec=0.01) is None

    def test_ui_bridge_clear_goals(self) -> None:
        """Verifies purge of goal queue."""
        bridge = UIBridge()
        bridge.submit_goal("Goal 1")
        bridge.submit_goal("Goal 2")
        bridge.submit_goal("Goal 3")

        discarded = bridge.clear_goals()
        assert discarded == 3
        assert bridge.get_next_goal(timeout_sec=0.01) is None

    def test_ui_bridge_control_signals(self) -> None:
        """Verifies control signals (pause, panic, hud toggle, brain mode)."""
        bridge = UIBridge()
        pauses = []
        panics = []
        huds = []
        brain_modes = []

        bridge.sig_pause_toggled.connect(lambda p: pauses.append(p))
        bridge.sig_panic_triggered.connect(lambda: panics.append(True))
        bridge.sig_hud_toggled.connect(lambda h: huds.append(h))
        bridge.sig_brain_mode_changed.connect(lambda m: brain_modes.append(m))

        bridge.trigger_pause(True)
        bridge.trigger_panic(source="test")
        bridge.sig_hud_toggled.emit(False)
        bridge.sig_brain_mode_changed.emit("browser_offload")

        assert pauses == [True]
        assert panics == [True]
        assert huds == [False]
        assert brain_modes == ["browser_offload"]

    def test_ui_bridge_episode_lifecycle_events(self) -> None:
        """Verifies episode lifecycle subscription and fanout."""
        bridge = UIBridge()
        events = []

        def on_event(ev: EpisodeEvent) -> None:
            events.append(ev)

        bridge.subscribe_episode_events(on_event)

        ev_start = EpisodeEvent(kind="started", goal="Test Goal", step=0)
        ev_step = EpisodeEvent(kind="step_completed", goal="Test Goal", step=1, data={"status": "ok"})
        ev_done = EpisodeEvent(kind="finished", goal="Test Goal", step=1)

        bridge.notify_episode_event(ev_start)
        bridge.notify_episode_event(ev_step)
        bridge.notify_episode_event(ev_done)

        assert len(events) == 3
        assert events[0].kind == "started"
        assert events[1].kind == "step_completed"
        assert events[2].kind == "finished"

        # Test unsubscribe
        bridge.unsubscribe_episode_events(on_event)
        bridge.notify_episode_event(EpisodeEvent(kind="extra", goal="Test"))
        assert len(events) == 3
