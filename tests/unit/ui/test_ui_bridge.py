"""
tests/test_ui_bridge.py - Tests for UIBridge Cross-Thread Signal Delivery and Queue.
Verifies thread-safe communication between background worker threads and Qt main GUI thread.
"""

from __future__ import annotations

import threading
import time
import pytest
from PyQt6.QtCore import Qt

from parasite_ai.ui.bridge import UIBridge
from parasite_ai.ui.types import UIElement


class TestUIBridge:
    def test_ui_bridge_cross_thread_state_notification(self, qtbot):
        """Verifies state changes emitted from background thread are delivered via Qt signal."""
        bridge = UIBridge()

        def worker():
            time.sleep(0.02)
            bridge.notify_state("DRIVING", "Focused")

        with qtbot.waitSignal(bridge.sig_state_changed, timeout=1500) as blocker:
            t = threading.Thread(target=worker, daemon=True)
            t.start()
            t.join()

        assert blocker.args == ["DRIVING", "Focused"]

    def test_ui_bridge_cross_thread_thought_and_speech(self, qtbot):
        """Verifies thoughts and speech emitted from worker thread reach Qt signal slots."""
        bridge = UIBridge()

        with qtbot.waitSignal(bridge.sig_thought_updated, timeout=1000) as blocker:
            threading.Thread(target=lambda: bridge.notify_thought("Analyzing DOM..."), daemon=True).start()
        assert blocker.args == ["Analyzing DOM..."]

        with qtbot.waitSignal(bridge.sig_speech_updated, timeout=1000) as blocker:
            threading.Thread(target=lambda: bridge.notify_speech("Clicking the login button."), daemon=True).start()
        assert blocker.args == ["Clicking the login button."]

    def test_ui_bridge_cross_thread_telemetry_notification(self, qtbot):
        """Verifies action telemetry is emitted across threads."""
        bridge = UIBridge()

        with qtbot.waitSignal(bridge.sig_telemetry_updated, timeout=1000) as blocker:
            threading.Thread(target=lambda: bridge.notify_telemetry("Target: [#2] Edit 'Search'"), daemon=True).start()
        assert blocker.args == ["Target: [#2] Edit 'Search'"]

    def test_ui_bridge_cross_thread_reticle_request_and_clear(self, qtbot):
        """Verifies pre-click reticle request and abort signals across threads."""
        bridge = UIBridge()

        with qtbot.waitSignal(bridge.sig_reticle_requested, timeout=1000) as blocker:
            threading.Thread(
                target=lambda: bridge.show_reticle(450, 320, 300, 14, "Submit Button"),
                daemon=True,
            ).start()
        assert blocker.args == [450, 320, 300, 14, "Submit Button"]

        with qtbot.waitSignal(bridge.sig_reticle_cleared, timeout=1000):
            threading.Thread(target=bridge.clear_reticle, daemon=True).start()

    def test_ui_bridge_targets_signal_marshalling(self, qtbot):
        """Verifies UIElement objects are marshalled across threads."""
        bridge = UIBridge()
        elem1 = UIElement.from_bbox(id=1, bbox=(10, 20, 100, 40), label="Search", role="Edit")
        elem2 = UIElement.from_bbox(id=2, bbox=(120, 20, 60, 40), label="Go", role="Button")

        with qtbot.waitSignal(bridge.sig_targets_updated, timeout=1000) as blocker:
            threading.Thread(target=lambda: bridge.set_hud_targets([elem1, elem2]), daemon=True).start()

        received = blocker.args[0]
        assert len(received) == 2
        assert received[0].id == 1
        assert received[0].label == "Search"
        assert received[1].id == 2
        assert received[1].role == "Button"

        with qtbot.waitSignal(bridge.sig_targets_cleared, timeout=1000):
            threading.Thread(target=bridge.clear_hud_targets, daemon=True).start()

    def test_ui_bridge_goal_queue_consumption(self, qtbot):
        """Verifies user goal submitted via signal is queued and retrievable by worker thread."""
        bridge = UIBridge()

        bridge.sig_goal_submitted.emit("Open Google Chrome and search for news")

        # Worker thread retrieves next goal
        retrieved_goal = []

        def worker():
            goal = bridge.get_next_goal(timeout_sec=1.0)
            retrieved_goal.append(goal)

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        t.join(timeout=1.5)

        assert retrieved_goal == ["Open Google Chrome and search for news"]

        # Empty queue returns None
        assert bridge.get_next_goal(timeout_sec=0.01) is None

    def test_ui_bridge_control_signals(self, qtbot):
        """Verifies GUI control signals (pause, panic, hud toggle, brain mode)."""
        bridge = UIBridge()

        with qtbot.waitSignal(bridge.sig_pause_toggled, timeout=500) as blocker:
            bridge.sig_pause_toggled.emit(True)
        assert blocker.args == [True]

        with qtbot.waitSignal(bridge.sig_panic_triggered, timeout=500):
            bridge.sig_panic_triggered.emit()

        with qtbot.waitSignal(bridge.sig_hud_toggled, timeout=500) as blocker:
            bridge.sig_hud_toggled.emit(False)
        assert blocker.args == [False]

        with qtbot.waitSignal(bridge.sig_brain_mode_changed, timeout=500) as blocker:
            bridge.sig_brain_mode_changed.emit("browser_offload")
        assert blocker.args == ["browser_offload"]
