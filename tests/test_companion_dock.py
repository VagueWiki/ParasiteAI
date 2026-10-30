"""
tests/test_companion_dock.py - Tests for Desktop Companion Dock Widget (PyQt6).
Verifies window flags, anchoring, state and mood transitions, dialogue bubbles,
internal thoughts, telemetry, perception privacy masking, and interactive controls.
"""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QPoint, QPointF, QRect, QSize, Qt
from PyQt6.QtGui import QColor, QGuiApplication, QImage, QMouseEvent, QPixmap
from PyQt6.QtWidgets import QApplication

from parasite_ai.config import CompanionDockConfig
from parasite_ai.ui.bridge import UIBridge
from parasite_ai.ui.companion_dock import STATE_CONFIG, CompanionDock


@pytest.fixture
def dock_config():
    return CompanionDockConfig(
        width=340,
        height=540,
        anchor="bottom_right",
        margin_x=24,
        margin_y=24,
        opacity=0.95,
        always_on_top=True,
        frameless=True,
        show_thought_stream=True,
        show_perception_preview=True,
    )


class TestCompanionDock:
    def test_dock_initialization_and_window_flags(self, qtbot, dock_config):
        dock = CompanionDock(config=dock_config)
        qtbot.addWidget(dock)

        flags = dock.windowFlags()
        assert bool(flags & Qt.WindowType.WindowStaysOnTopHint)
        assert bool(flags & Qt.WindowType.FramelessWindowHint)
        assert bool(flags & Qt.WindowType.Tool)

        assert dock.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        assert dock.width() == 340
        assert dock.height() == 540
        assert abs(dock.windowOpacity() - 0.95) < 0.01

    def test_dock_screen_anchoring(self, qtbot, dock_config):
        dock = CompanionDock(config=dock_config)
        qtbot.addWidget(dock)

        screen = QGuiApplication.primaryScreen()
        if screen:
            screen_rect = screen.availableGeometry()

            # 1. bottom_right
            dock.config.anchor = "bottom_right"
            dock.anchor_to_screen(screen)
            expected_x = screen_rect.x() + screen_rect.width() - dock.width() - 24
            expected_y = screen_rect.y() + screen_rect.height() - dock.height() - 24
            assert dock.pos() == QPoint(expected_x, expected_y)

            # 2. bottom_left
            dock.config.anchor = "bottom_left"
            dock.anchor_to_screen(screen)
            assert dock.pos() == QPoint(screen_rect.x() + 24, expected_y)

            # 3. top_right
            dock.config.anchor = "top_right"
            dock.anchor_to_screen(screen)
            assert dock.pos() == QPoint(expected_x, screen_rect.y() + 24)

            # 4. top_left
            dock.config.anchor = "top_left"
            dock.anchor_to_screen(screen)
            assert dock.pos() == QPoint(screen_rect.x() + 24, screen_rect.y() + 24)

    def test_dock_state_transitions_and_pill_styles(self, qtbot, dock_config):
        dock = CompanionDock(config=dock_config)
        qtbot.addWidget(dock)

        states = ["WATCHING", "THINKING", "DRIVING", "USER_OVERRIDE", "OFFLOADING", "PROTECTED"]
        for st in states:
            with qtbot.waitSignal(dock.sig_status_changed, timeout=500) as blocker:
                dock.update_state(st, mood="Focused")

            assert blocker.args == [st, "Focused"]
            assert dock.state_pill.text() == STATE_CONFIG[st]["label"]
            assert dock._current_state == st

    def test_dock_mood_updates(self, qtbot, dock_config):
        dock = CompanionDock(config=dock_config)
        qtbot.addWidget(dock)

        dock.update_state("WATCHING", mood="Panic-Averted")
        assert dock.mood_pill.text() == "[Panic-Averted]"
        assert dock._current_mood == "Panic-Averted"

    def test_dock_speech_updates_and_streaming(self, qtbot, dock_config):
        dock = CompanionDock(config=dock_config)
        qtbot.addWidget(dock)

        # Direct text update
        with qtbot.waitSignal(dock.sig_speech_updated, timeout=500) as blocker:
            dock.update_speech("I am ready to help.")
        assert blocker.args == ["I am ready to help."]
        assert dock.dialogue_label.text() == "I am ready to help."

        # Typewriter streaming
        with qtbot.waitSignal(dock.sig_speech_updated, timeout=2000):
            dock.update_speech("Hi!", stream=True)
        assert dock.dialogue_label.text() == "Hi!"

    def test_dock_thought_stream(self, qtbot, dock_config):
        dock = CompanionDock(config=dock_config)
        qtbot.addWidget(dock)

        with qtbot.waitSignal(dock.sig_thought_updated, timeout=500) as blocker:
            dock.update_thought("Parsed 14 elements from screen.")
        assert blocker.args == ["Parsed 14 elements from screen."]
        assert "Parsed 14 elements from screen." in dock.thought_text.toPlainText()

    def test_dock_telemetry_feed(self, qtbot, dock_config):
        dock = CompanionDock(config=dock_config)
        qtbot.addWidget(dock)

        with qtbot.waitSignal(dock.sig_telemetry_updated, timeout=500) as blocker:
            dock.update_telemetry("Target: [#3] Edit 'Address'", current_step=3, total_steps=10)
        assert blocker.args == ["Target: [#3] Edit 'Address'"]
        assert dock.telemetry_label.text() == "Target: [#3] Edit 'Address'"
        assert dock.step_label.text() == "Step: 3/10"
        assert dock.step_progress.value() == 30

    def test_dock_perception_preview_and_privacy_masking(self, qtbot, dock_config):
        dock = CompanionDock(config=dock_config)
        qtbot.addWidget(dock)

        # Normal frame preview
        pix = QPixmap(100, 100)
        pix.fill(QColor("blue"))
        with qtbot.waitSignal(dock.sig_perception_updated, timeout=500):
            dock.update_perception_preview(pix, elements=[1, 2, 3])
        assert "3 Targets" in dock.grounding_badge.text()

        # Entering PROTECTED state triggers automatic blackout privacy mask
        dock.update_state("PROTECTED", mood="Cautious")
        assert dock._is_masked is True
        assert "SENSITIVE" in dock.grounding_badge.text()

        # Returning to WATCHING lifts blackout
        dock.update_state("WATCHING", mood="Curious")
        assert dock._is_masked is False

    def test_goal_input_send_button(self, qtbot, dock_config):
        dock = CompanionDock(config=dock_config)
        qtbot.addWidget(dock)

        qtbot.keyClicks(dock.goal_input, "Open Chrome")
        assert dock.goal_input.text() == "Open Chrome"

        with qtbot.waitSignal(dock.sig_goal_submitted, timeout=500) as blocker:
            qtbot.mouseClick(dock.btn_send, Qt.MouseButton.LeftButton)

        assert blocker.args == ["Open Chrome"]
        assert dock.goal_input.text() == ""

    def test_goal_input_return_key(self, qtbot, dock_config):
        dock = CompanionDock(config=dock_config)
        qtbot.addWidget(dock)

        qtbot.keyClicks(dock.goal_input, "Take screenshot")
        with qtbot.waitSignal(dock.sig_goal_submitted, timeout=500) as blocker:
            qtbot.keyClick(dock.goal_input, Qt.Key.Key_Return)

        assert blocker.args == ["Take screenshot"]
        assert dock.goal_input.text() == ""

    def test_goal_input_empty_or_whitespace_ignored(self, qtbot, dock_config):
        dock = CompanionDock(config=dock_config)
        qtbot.addWidget(dock)

        received = []
        dock.sig_goal_submitted.connect(received.append)

        qtbot.keyClicks(dock.goal_input, "   ")
        qtbot.mouseClick(dock.btn_send, Qt.MouseButton.LeftButton)
        assert len(received) == 0

    def test_pause_resume_toggle_button(self, qtbot, dock_config):
        dock = CompanionDock(config=dock_config)
        qtbot.addWidget(dock)

        # 1st click -> Pause
        with qtbot.waitSignal(dock.sig_pause_toggled, timeout=500) as blocker:
            qtbot.mouseClick(dock.btn_pause, Qt.MouseButton.LeftButton)
        assert blocker.args == [True]
        assert "Resume" in dock.btn_pause.text()

        # 2nd click -> Resume
        with qtbot.waitSignal(dock.sig_pause_toggled, timeout=500) as blocker:
            qtbot.mouseClick(dock.btn_pause, Qt.MouseButton.LeftButton)
        assert blocker.args == [False]
        assert "Pause" in dock.btn_pause.text()

    def test_panic_button_signal(self, qtbot, dock_config):
        dock = CompanionDock(config=dock_config)
        qtbot.addWidget(dock)

        with qtbot.waitSignal(dock.sig_panic_triggered, timeout=500):
            qtbot.mouseClick(dock.btn_panic, Qt.MouseButton.LeftButton)

    def test_hud_checkbox_toggle(self, qtbot, dock_config):
        dock = CompanionDock(config=dock_config)
        qtbot.addWidget(dock)

        with qtbot.waitSignal(dock.sig_hud_toggled, timeout=500) as blocker:
            dock.chk_hud.setChecked(False)
        assert blocker.args == [False]

    def test_brain_mode_dropdown_selection(self, qtbot, dock_config):
        dock = CompanionDock(config=dock_config)
        qtbot.addWidget(dock)

        with qtbot.waitSignal(dock.sig_brain_mode_changed, timeout=500) as blocker:
            dock.combo_brain_mode.setCurrentIndex(1)
        assert blocker.args == ["local_llm"]

    def test_mouse_drag_repositioning(self, qtbot, dock_config):
        dock = CompanionDock(config=dock_config)
        qtbot.addWidget(dock)
        dock.show()

        start_pos = dock.pos()

        # Simulate click on header grip
        press_event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(20.0, 15.0),
            QPointF(dock.mapToGlobal(QPoint(20, 15))),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        dock.mousePressEvent(press_event)
        assert dock._is_dragging is True

        # Simulate move
        move_event = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(30.0, 25.0),
            QPointF(dock.mapToGlobal(QPoint(30, 25))),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        dock.mouseMoveEvent(move_event)

        # Release
        release_event = QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease,
            QPointF(30.0, 25.0),
            QPointF(dock.mapToGlobal(QPoint(30, 25))),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        dock.mouseReleaseEvent(release_event)
        assert dock._is_dragging is False

    def test_bridge_integration_wiring(self, qtbot, dock_config):
        bridge = UIBridge()
        dock = CompanionDock(config=dock_config, bridge=bridge)
        qtbot.addWidget(dock)

        # Bridge updates dock state
        bridge.notify_state("DRIVING", "Aggressive")
        qtbot.waitUntil(lambda: dock._current_state == "DRIVING", timeout=1000)
        assert dock._current_mood == "Aggressive"

        # Dock emits goal to bridge
        with qtbot.waitSignal(bridge.sig_goal_submitted, timeout=1000) as blocker:
            dock.goal_input.setText("Test goal")
            dock._on_submit_goal()
        assert blocker.args == ["Test goal"]
        assert bridge.get_next_goal(timeout_sec=0.5) == "Test goal"
