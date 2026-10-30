"""
tests/test_companion_dock_adversarial.py - Adversarial Stress Test Suite for CompanionDock & UIBridge.

Covers:
1. High-throughput concurrent cross-thread signal emission (flooding status, speech, thoughts, telemetry).
2. Rapid state cycling across all 6 states (WATCHING -> THINKING -> DRIVING -> USER_OVERRIDE -> OFFLOADING -> PROTECTED).
3. Telemetry bursts, boundary conditions, and progress bar percentage accuracy.
4. Privacy blackout masking transitions and strict pixel leakage verification.
5. Goal submission queue under thread contention, empty strings, and multi-KB payloads.
6. Header drag coordinate clamping (negative coordinates, multi-monitor bounds, interactive widget pass-through).
7. UIElement validation and immutability invariants.
"""

from __future__ import annotations

import queue
import threading
import time
from typing import List
from unittest.mock import MagicMock

import pytest
from PyQt6.QtCore import QPoint, QPointF, QRect, Qt
from PyQt6.QtGui import QColor, QGuiApplication, QImage, QMouseEvent, QPixmap
from PyQt6.QtWidgets import QApplication

from parasite_ai.config import CompanionDockConfig
from parasite_ai.ui.bridge import UIBridge
from parasite_ai.ui.companion_dock import STATE_CONFIG, CompanionDock
from parasite_ai.ui.types import UIElement


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


class TestCompanionDockAdversarial:
    """Adversarial challenge test suite for CompanionDock, UIBridge, and UI types."""

    # -------------------------------------------------------------------------
    # 1. High-Throughput Concurrent Cross-Thread Signal Emission
    # -------------------------------------------------------------------------
    def test_concurrent_signal_emission_multithreaded_flood(self, qtbot, dock_config):
        """
        Floods UIBridge and CompanionDock with hundreds of concurrent updates
        from 8 background worker threads simultaneously.
        Verifies thread safety, absence of deadlocks, and clean GUI event processing.
        """
        bridge = UIBridge()
        dock = CompanionDock(config=dock_config, bridge=bridge)
        qtbot.addWidget(dock)

        num_threads = 8
        updates_per_thread = 50
        errors: List[Exception] = []

        def worker(w_id: int):
            try:
                for i in range(updates_per_thread):
                    state = "THINKING" if i % 2 == 0 else "DRIVING"
                    mood = "Focused" if i % 2 == 0 else "Curious"
                    bridge.notify_state(state, mood)
                    bridge.notify_speech(f"Worker {w_id} monologue step {i}")
                    bridge.notify_thought(f"Worker {w_id} internal thought token {i}")
                    bridge.notify_telemetry(f"Worker {w_id} action #{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(t,), daemon=True) for t in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=3.0)

        # Flush Qt queued events
        qtbot.wait(300)
        QApplication.processEvents()

        assert len(errors) == 0, f"Thread errors encountered: {errors}"
        # Ensure dock is in a valid state
        assert dock._current_state in STATE_CONFIG
        assert dock.dialogue_label.text() != ""
        assert dock.thought_text.toPlainText() != ""
        assert dock.telemetry_label.text() != ""

    # -------------------------------------------------------------------------
    # 2. Rapid State Cycling Across All 6 States
    # -------------------------------------------------------------------------
    def test_rapid_state_cycling_all_six_states(self, qtbot, dock_config):
        """
        Rapidly cycles through all 6 operational states across 300 cycles.
        Verifies style updates, pill badges, and automatic privacy masking triggers.
        """
        dock = CompanionDock(config=dock_config)
        qtbot.addWidget(dock)

        states = ["WATCHING", "THINKING", "DRIVING", "USER_OVERRIDE", "OFFLOADING", "PROTECTED"]

        for i in range(300):
            st = states[i % len(states)]
            mood = f"Mood_{i % 5}"
            dock.update_state(st, mood=mood)

            assert dock._current_state == st
            assert dock._current_mood == mood
            assert dock.state_pill.text() == STATE_CONFIG[st]["label"]

            # Strict privacy mask check
            if st == "PROTECTED":
                assert dock._is_masked is True, "PROTECTED state must engage privacy mask"
            else:
                assert dock._is_masked is False, f"State {st} must not be masked"

    def test_invalid_and_adversarial_state_inputs(self, qtbot, dock_config):
        """
        Adversarial inputs: unknown states, case variations, empty string.
        Verifies fallback to WATCHING without unhandled exceptions.
        """
        dock = CompanionDock(config=dock_config)
        qtbot.addWidget(dock)

        # Unknown state -> fallback to WATCHING
        dock.update_state("COMPLETELY_UNKNOWN_STATE", mood="Confused")
        assert dock._current_state == "WATCHING"
        assert dock.state_pill.text() == STATE_CONFIG["WATCHING"]["label"]

        # Lowercase state -> normalized to DRIVING
        dock.update_state("driving", mood="Fast")
        assert dock._current_state == "DRIVING"
        assert dock.state_pill.text() == STATE_CONFIG["DRIVING"]["label"]

        # Empty string -> fallback to WATCHING
        dock.update_state("", mood="Empty")
        assert dock._current_state == "WATCHING"

    # -------------------------------------------------------------------------
    # 3. Telemetry Bursts & Boundary Conditions
    # -------------------------------------------------------------------------
    def test_telemetry_burst_and_progress_clamping(self, qtbot, dock_config):
        """
        Tests rapid bursts of telemetry updates with extreme boundary conditions.
        Verifies progress bar stays within [0, 100] and division-by-zero is avoided.
        """
        dock = CompanionDock(config=dock_config)
        qtbot.addWidget(dock)

        # 1. Clamped overshoot
        dock.update_telemetry("Overshoot step", current_step=500, total_steps=100)
        assert dock.step_progress.value() == 100
        assert dock.step_label.text() == "Step: 500/100"

        # 2. Clamped negative
        dock.update_telemetry("Negative step", current_step=-20, total_steps=100)
        assert dock.step_progress.value() == 0

        # 3. Zero total steps (avoid ZeroDivisionError)
        dock.update_telemetry("Zero total steps", current_step=0, total_steps=0)
        assert dock.step_progress.value() == 0
        assert dock.step_label.text() == "Step: Idle"

        # 4. Negative total steps
        dock.update_telemetry("Negative total steps", current_step=5, total_steps=-10)
        assert dock.step_progress.value() == 0
        assert dock.step_label.text() == "Step: Idle"

        # 5. Rapid jump between 0 and 100
        for _ in range(50):
            dock.update_telemetry("Min", current_step=0, total_steps=100)
            assert dock.step_progress.value() == 0
            dock.update_telemetry("Max", current_step=100, total_steps=100)
            assert dock.step_progress.value() == 100

    def test_telemetry_step_precision_calculation(self, qtbot, dock_config):
        """
        EMPIRICAL DEFECT CHECK:
        Verifies telemetry progress percentage calculation accuracy.
        At step 29 of 100, (29/100)*100 evaluates to 28.999999999999996 in IEEE 754 floats.
        Using int() truncates this to 28 instead of 29!
        Similarly, step 57 truncates to 56, and step 58 truncates to 57.
        """
        dock = CompanionDock(config=dock_config)
        qtbot.addWidget(dock)

        # Test step 29 of 100
        dock.update_telemetry("Step 29", current_step=29, total_steps=100)
        # Expected: 29%. If int((29/100)*100) truncation bug is present, this evaluates to 28.
        assert dock.step_progress.value() == 29, (
            f"Step progress truncation bug: expected 29% but got {dock.step_progress.value()}%"
        )

    def test_ui_bridge_telemetry_step_progress_parameters(self, qtbot, dock_config):
        """
        EMPIRICAL DEFECT CHECK:
        Verifies that UIBridge.notify_telemetry can communicate action step progress
        (current_step and total_steps) to CompanionDock.
        Currently, UIBridge.sig_telemetry_updated is pyqtSignal(str) and notify_telemetry
        only takes a single str, so background engines cannot report plan execution progress
        to the companion dock UI, and any call resets the progress bar.
        """
        bridge = UIBridge()
        dock = CompanionDock(config=dock_config, bridge=bridge)
        qtbot.addWidget(dock)

        # Background worker attempts to report step progress
        try:
            bridge.notify_telemetry("Executing action #3", current_step=3, total_steps=10)
        except TypeError as e:
            pytest.fail(f"UIBridge.notify_telemetry does not accept step progress parameters: {e}")

        qtbot.wait(100)
        QApplication.processEvents()
        assert dock.step_progress.value() == 30
        assert dock.step_label.text() == "Step: 3/10"

    # -------------------------------------------------------------------------
    # 4. Privacy Blackout Masking Transitions & Pixel Leakage
    # -------------------------------------------------------------------------
    def test_perception_privacy_blackout_zero_pixel_leakage(self, qtbot, dock_config):
        """
        Rigorous pixel-level audit:
        1. Feed a high-contrast pure bright green image (#00FF00).
        2. Transition to PROTECTED (masking engaged).
        3. Audit every pixel: verify ZERO bright green pixels remain in thumbnail.
        4. Attempt to feed another sensitive frame while masked: verify ZERO pixel leakage.
        5. Return to WATCHING: verify thumbnail reverts to placeholder without showing stale frame.
        """
        dock = CompanionDock(config=dock_config)
        qtbot.addWidget(dock)

        # 1. Feed pure green test image
        green_frame = QPixmap(120, 80)
        green_frame.fill(QColor(0, 255, 0))
        dock.update_perception_preview(green_frame)
        QApplication.processEvents()

        # 2. Transition to PROTECTED
        dock.update_state("PROTECTED", mood="Cautious")
        QApplication.processEvents()

        assert dock._is_masked is True
        assert "SENSITIVE" in dock.grounding_badge.text()

        # 3. Pixel-level inspection of blackout pixmap
        blackout_pix = dock.thumbnail_view.pixmap()
        assert blackout_pix is not None and not blackout_pix.isNull()
        img = blackout_pix.toImage()

        green_leakage = 0
        for x in range(img.width()):
            for y in range(img.height()):
                c = img.pixelColor(x, y)
                # Pure green has high green and low red/blue
                if c.green() > 60 and c.red() < 40 and c.blue() < 40:
                    green_leakage += 1

        assert green_leakage == 0, f"Privacy violation: {green_leakage} green pixels leaked in blackout shield!"

        # 4. Attempt to update perception preview while in PROTECTED state
        sensitive_yellow_frame = QPixmap(120, 80)
        sensitive_yellow_frame.fill(QColor(255, 255, 0))
        dock.update_perception_preview(sensitive_yellow_frame)
        QApplication.processEvents()

        blackout_pix2 = dock.thumbnail_view.pixmap()
        img2 = blackout_pix2.toImage()
        yellow_leakage = 0
        for x in range(img2.width()):
            for y in range(img2.height()):
                c = img2.pixelColor(x, y)
                if c.red() > 200 and c.green() > 200:
                    yellow_leakage += 1

        assert yellow_leakage == 0, f"Privacy violation: {yellow_leakage} yellow pixels leaked during masked update!"

        # 5. Return to WATCHING state
        dock.update_state("WATCHING", mood="Curious")
        QApplication.processEvents()

        assert dock._is_masked is False
        assert dock.thumbnail_view.text() == "Live Perception Feed"

    def test_perception_preview_malformed_inputs(self, qtbot, dock_config):
        """Adversarial preview inputs: None, null pixmap, 0x0 size, unhandled types."""
        dock = CompanionDock(config=dock_config)
        qtbot.addWidget(dock)

        # None input
        dock.update_perception_preview(None)
        assert dock.thumbnail_view.text() == "No Frame Available"

        # Null pixmap
        null_pix = QPixmap()
        dock.update_perception_preview(null_pix)
        assert dock.thumbnail_view.text() == "No Frame Available"

        # QImage input
        valid_img = QImage(40, 40, QImage.Format.Format_RGB32)
        valid_img.fill(QColor("blue"))
        dock.update_perception_preview(valid_img)
        assert dock.thumbnail_view.pixmap() is not None

    def test_ui_bridge_perception_elements_slot_signature(self, qtbot, dock_config):
        """
        EMPIRICAL DEFECT CHECK:
        Verifies that when UIBridge.notify_perception(frame, elements) emits (object, list),
        CompanionDock.update_perception_preview receives the elements list.
        If CompanionDock only declares @pyqtSlot(object), Qt queued connection drops
        the second argument, leaving elements=None and the grounding badge un-updated.
        """
        bridge = UIBridge()
        dock = CompanionDock(config=dock_config, bridge=bridge)
        qtbot.addWidget(dock)

        elem1 = UIElement.from_bbox(id=1, bbox=(0, 0, 50, 50), label="Search", role="Edit")
        elem2 = UIElement.from_bbox(id=2, bbox=(60, 0, 50, 50), label="Submit", role="Button")

        frame = QPixmap(100, 100)
        frame.fill(QColor("black"))

        bridge.notify_perception(frame, [elem1, elem2])
        qtbot.wait(100)
        QApplication.processEvents()

        # Expected: "Grounding: 2 Targets Active"
        # If @pyqtSlot(object, list) is missing, badge remains "Grounding: Active"
        assert dock.grounding_badge.text() == "Grounding: 2 Targets Active", (
            f"Missing @pyqtSlot(object, list) on CompanionDock.update_perception_preview! "
            f"Grounding badge text is '{dock.grounding_badge.text()}', elements argument was dropped."
        )

    # -------------------------------------------------------------------------
    # 5. Goal Submission Queue Under Thread Competition
    # -------------------------------------------------------------------------
    def test_goal_submission_queue_thread_competition(self, qtbot):
        """
        Stress-tests UIBridge goal queue under heavy concurrent multi-threaded producer
        and consumer contention.
        """
        bridge = UIBridge()

        num_producers = 8
        goals_per_producer = 50
        total_expected = num_producers * goals_per_producer
        consumed_goals: List[str] = []
        produced_goals: List[str] = []

        def producer(tid: int):
            for i in range(goals_per_producer):
                goal_str = f"Task payload from producer {tid} - item #{i}"
                bridge.sig_goal_submitted.emit(goal_str)
                produced_goals.append(goal_str)

        def consumer():
            while len(consumed_goals) < total_expected:
                g = bridge.get_next_goal(timeout_sec=0.05)
                if g is not None:
                    consumed_goals.append(g)

        consumers = [threading.Thread(target=consumer, daemon=True) for _ in range(3)]
        producers = [threading.Thread(target=producer, args=(i,), daemon=True) for i in range(num_producers)]

        for c in consumers:
            c.start()
        for p in producers:
            p.start()
        for p in producers:
            p.join(timeout=3.0)

        # Process Qt events to deliver queued signals
        start_time = time.time()
        while len(consumed_goals) < total_expected and (time.time() - start_time) < 3.0:
            QApplication.processEvents()
            time.sleep(0.01)

        for c in consumers:
            c.join(timeout=1.0)

        assert len(consumed_goals) == total_expected, (
            f"Goal queue lost messages under competition: {len(consumed_goals)} != {total_expected}"
        )

    def test_goal_input_payload_boundaries(self, qtbot, dock_config):
        """
        Tests empty strings, whitespace, large multi-KB payloads, and special unicode.
        """
        dock = CompanionDock(config=dock_config)
        qtbot.addWidget(dock)

        submitted: List[str] = []
        dock.sig_goal_submitted.connect(submitted.append)

        # 1. Empty string
        dock.goal_input.setText("")
        dock._on_submit_goal()
        assert len(submitted) == 0, "Empty string must not be submitted"

        # 2. Whitespace-only string
        dock.goal_input.setText("   \t  \n  ")
        dock._on_submit_goal()
        assert len(submitted) == 0, "Whitespace must not be submitted"

        # 3. Multi-KB payload (15 KB prompt)
        multi_kb_payload = "Search and analyze document: " + ("X" * 15000)
        dock.goal_input.setText(multi_kb_payload)
        assert len(dock.goal_input.text()) == len(multi_kb_payload)
        dock._on_submit_goal()
        assert len(submitted) == 1
        assert submitted[0] == multi_kb_payload
        assert dock.goal_input.text() == ""

        # 4. Unicode symbols & emojis
        unicode_prompt = "Click 🔥 and submit 🚀 [Tag #42] \u26a1"
        dock.goal_input.setText(unicode_prompt)
        dock._on_submit_goal()
        assert len(submitted) == 2
        assert submitted[1] == unicode_prompt

    # -------------------------------------------------------------------------
    # 6. Header Drag Coordinate Clamping & Widget Pass-Through
    # -------------------------------------------------------------------------
    def test_header_drag_coordinate_clamping_extremes(self, qtbot, dock_config):
        """
        Tests clamping when dragging to negative coordinates, offscreen bounds,
        and multi-monitor setups with negative virtual screen coordinates.
        """
        dock = CompanionDock(config=dock_config)
        qtbot.addWidget(dock)
        dock.show()

        screen = QGuiApplication.primaryScreen()
        vgeom = screen.virtualGeometry() if screen else QRect(0, 0, 1920, 1080)

        # 1. Extreme negative coordinates
        neg_pos = QPoint(-99999, -99999)
        clamped_neg = dock._clamp_to_virtual_desktop(neg_pos)
        assert clamped_neg.x() >= vgeom.x() - dock.width() + 60
        assert clamped_neg.y() >= vgeom.y()

        # 2. Extreme positive coordinates
        pos_pos = QPoint(999999, 999999)
        clamped_pos = dock._clamp_to_virtual_desktop(pos_pos)
        assert clamped_pos.x() <= vgeom.right() - 60
        assert clamped_pos.y() <= vgeom.bottom() - 40

        # 3. Simulated multi-monitor with negative origin (-1920 to 1920)
        mock_screen = MagicMock()
        mock_screen.virtualGeometry.return_value = QRect(-1920, 0, 3840, 1080)

        import PyQt6.QtGui as qtgui
        orig_primary = qtgui.QGuiApplication.primaryScreen
        qtgui.QGuiApplication.primaryScreen = lambda: mock_screen
        try:
            clamped_multi_neg = dock._clamp_to_virtual_desktop(QPoint(-10000, 500))
            expected_min_x = -1920 - dock.width() + 60
            assert clamped_multi_neg.x() == expected_min_x
        finally:
            qtgui.QGuiApplication.primaryScreen = orig_primary

    def test_header_drag_interactive_widget_passthrough(self, qtbot, dock_config):
        """
        Verifies that clicking interactive child widgets (buttons, dropdown, lineedit)
        does NOT initiate window drag, while clicking header labels DOES initiate drag.
        """
        dock = CompanionDock(config=dock_config)
        qtbot.addWidget(dock)
        dock.show()

        def simulate_press(widget_target, button=Qt.MouseButton.LeftButton):
            local_pt = widget_target.mapTo(dock, QPoint(5, 5))
            event = QMouseEvent(
                QMouseEvent.Type.MouseButtonPress,
                QPointF(local_pt),
                QPointF(dock.mapToGlobal(local_pt)),
                button,
                button,
                Qt.KeyboardModifier.NoModifier,
            )
            dock.mousePressEvent(event)
            was_dragging = dock._is_dragging
            dock._is_dragging = False  # Reset
            return was_dragging

        # Header labels and header frame background -> MUST start drag
        assert simulate_press(dock.avatar_icon) is True, "avatar_icon should start drag"
        assert simulate_press(dock.title_label) is True, "title_label should start drag"
        assert simulate_press(dock.state_pill) is True, "state_pill should start drag"
        assert simulate_press(dock.header_frame) is True, "header_frame should start drag"

        # Interactive controls -> MUST NOT start drag
        assert simulate_press(dock.goal_input) is False, "goal_input must not start drag"
        assert simulate_press(dock.btn_send) is False, "btn_send must not start drag"
        assert simulate_press(dock.btn_pause) is False, "btn_pause must not start drag"
        assert simulate_press(dock.btn_panic) is False, "btn_panic must not start drag"
        assert simulate_press(dock.chk_hud) is False, "chk_hud must not start drag"
        assert simulate_press(dock.combo_brain_mode) is False, "combo_brain_mode must not start drag"

        # Right-click or middle-click on header -> MUST NOT start drag
        assert simulate_press(dock.header_frame, button=Qt.MouseButton.RightButton) is False
        assert simulate_press(dock.header_frame, button=Qt.MouseButton.MiddleButton) is False

    # -------------------------------------------------------------------------
    # 7. UIElement Validation Invariants
    # -------------------------------------------------------------------------
    def test_ui_element_adversarial_validation_invariants(self):
        """Tests pydantic schema validation boundaries and frozen immutability."""
        from pydantic import ValidationError

        # 1. Invalid ID (< 1)
        with pytest.raises(ValidationError):
            UIElement(id=0, x=10, y=10, width=50, height=50, center_x=35, center_y=35)

        # 2. Negative width/height
        with pytest.raises(ValidationError):
            UIElement(id=1, x=10, y=10, width=-10, height=50, center_x=35, center_y=35)

        with pytest.raises(ValidationError):
            UIElement(id=1, x=10, y=10, width=50, height=-5, center_x=35, center_y=35)

        # 3. Invalid source literal
        with pytest.raises(ValidationError):
            UIElement(id=1, x=10, y=10, width=50, height=50, center_x=35, center_y=35, source="invalid")

        # 4. Frozen immutability
        elem = UIElement.from_bbox(id=5, bbox=(10, 20, 100, 40), label="OK")
        with pytest.raises(ValidationError):
            elem.id = 10

        assert elem.bbox == (10, 20, 100, 40)
        assert elem.center == (60, 40)
        assert elem.control_type == "Button"

    # -------------------------------------------------------------------------
    # 8. Telemetry Interleaving, Signal Overload Routing & Step Edge Bounds
    # -------------------------------------------------------------------------
    def test_telemetry_signature_interleaving_and_overload_routing(self, qtbot, dock_config):
        """
        Adversarial Re-Challenge:
        1. Verifies that 1-arg notify_telemetry emissions strictly route to sig_telemetry_updated[str].
        2. Verifies that 3-arg notify_telemetry emissions strictly route to sig_telemetry_updated[str, int, int].
        3. Rapidly alternates between 1-arg and 3-arg calls across 200 cycles.
        4. Stresses edge-case bounds:
           - current_step > total_steps (step overflow: e.g. 15 of 10) -> clamped to 100%
           - current_step > 0 with total_steps == 0 (zero total steps) -> avoids ZeroDivision, defaults to Step: Idle
           - negative current_step with valid total_steps (-5 of 10) -> clamped to 0%
           - total_steps < 0 -> avoids division by zero, defaults to Step: Idle
        """
        bridge = UIBridge()
        dock = CompanionDock(config=dock_config, bridge=bridge)
        qtbot.addWidget(dock)

        str_emissions: List[tuple] = []
        three_arg_emissions: List[tuple] = []

        bridge.sig_telemetry_updated[str].connect(lambda t: str_emissions.append((t,)))
        bridge.sig_telemetry_updated[str, int, int].connect(lambda t, c, tot: three_arg_emissions.append((t, c, tot)))

        # 1. Verify 1-arg emission routing
        bridge.notify_telemetry("Single string action")
        qtbot.wait(50)
        QApplication.processEvents()

        assert len(str_emissions) == 1
        assert str_emissions[0] == ("Single string action",)
        assert len(three_arg_emissions) == 0
        assert dock.telemetry_label.text() == "Single string action"
        assert dock.step_label.text() == "Step: Idle"
        assert dock.step_progress.value() == 0

        # 2. Verify 3-arg emission routing
        bridge.notify_telemetry("Multi-step action", current_step=3, total_steps=10)
        qtbot.wait(50)
        QApplication.processEvents()

        assert len(three_arg_emissions) == 1
        assert three_arg_emissions[0] == ("Multi-step action", 3, 10)
        assert len(str_emissions) == 1  # No unexpected 1-arg emission
        assert dock.telemetry_label.text() == "Multi-step action"
        assert dock.step_label.text() == "Step: 3/10"
        assert dock.step_progress.value() == 30

        # 3. Rapid interleaving (100 alternating cycles)
        for i in range(1, 101):
            if i % 2 == 1:
                bridge.notify_telemetry(f"Interleaved 3-arg {i}", current_step=i, total_steps=100)
            else:
                bridge.notify_telemetry(f"Interleaved 1-arg {i}")

        qtbot.wait(200)
        QApplication.processEvents()

        # The last emission was i=100 (1-arg)
        assert dock.telemetry_label.text() == "Interleaved 1-arg 100"
        assert dock.step_label.text() == "Step: Idle"
        assert dock.step_progress.value() == 0

        # 4. Step overflow: current_step > total_steps (15 of 10)
        bridge.notify_telemetry("Step overflow", current_step=15, total_steps=10)
        qtbot.wait(50)
        QApplication.processEvents()
        assert dock.step_label.text() == "Step: 15/10"
        assert dock.step_progress.value() == 100  # Clamped to max 100%

        # 5. Zero total steps with non-zero current step (5 of 0)
        bridge.notify_telemetry("Nonzero step with zero total", current_step=5, total_steps=0)
        qtbot.wait(50)
        QApplication.processEvents()
        assert dock.step_label.text() == "Step: Idle"
        assert dock.step_progress.value() == 0

        # 6. Negative current_step (-5 of 10)
        bridge.notify_telemetry("Negative current step", current_step=-5, total_steps=10)
        qtbot.wait(50)
        QApplication.processEvents()
        assert dock.step_label.text() == "Step: -5/10"
        assert dock.step_progress.value() == 0  # Clamped to min 0%

        # 7. Negative total steps (-10)
        bridge.notify_telemetry("Negative total steps", current_step=5, total_steps=-10)
        qtbot.wait(50)
        QApplication.processEvents()
        assert dock.step_label.text() == "Step: Idle"
        assert dock.step_progress.value() == 0

    # -------------------------------------------------------------------------
    # 9. Perception Preview Elements Mutation & Empty List Resilience
    # -------------------------------------------------------------------------
    def test_perception_elements_mutation_and_empty_list_resilience(self, qtbot, dock_config):
        """
        Adversarial Re-Challenge:
        1. Tests notify_perception with None -> should default safely to empty list without error.
        2. Tests notify_perception with empty list [] -> badge updates to 'Grounding: 0 Targets Active'.
        3. Tests high target count (500 elements) -> badge displays 'Grounding: 500 Targets Active'.
        4. Tests background thread creating and mutating a list post-emission -> no memory fault or exception.
        5. Tests direct call dock.update_perception_preview(frame, elements=None) -> preserves existing badge text.
        """
        bridge = UIBridge()
        dock = CompanionDock(config=dock_config, bridge=bridge)
        qtbot.addWidget(dock)

        test_pix = QPixmap(60, 60)
        test_pix.fill(QColor("magenta"))

        # 1. notify_perception with elements=None
        bridge.notify_perception(test_pix, elements=None)
        qtbot.wait(50)
        QApplication.processEvents()
        assert dock.grounding_badge.text() == "Grounding: 0 Targets Active"

        # 2. notify_perception with explicit empty list []
        bridge.notify_perception(test_pix, elements=[])
        qtbot.wait(50)
        QApplication.processEvents()
        assert dock.grounding_badge.text() == "Grounding: 0 Targets Active"

        # 3. High target count (500 elements)
        large_elements = [
            UIElement.from_bbox(id=i, bbox=(i % 100, i % 100, 20, 20), label=f"Item {i}")
            for i in range(1, 501)
        ]
        bridge.notify_perception(test_pix, elements=large_elements)
        qtbot.wait(100)
        QApplication.processEvents()
        assert dock.grounding_badge.text() == "Grounding: 500 Targets Active"

        # 4. Background thread mutating elements list after emission
        shared_list = [
            UIElement.from_bbox(id=1, bbox=(0, 0, 10, 10), label="Target A"),
            UIElement.from_bbox(id=2, bbox=(20, 20, 10, 10), label="Target B"),
        ]
        bridge.notify_perception(test_pix, elements=shared_list)
        # Immediate in-place mutation by background producer
        shared_list.clear()

        qtbot.wait(50)
        QApplication.processEvents()
        # Should not raise exception and should reflect processed state cleanly
        assert "Grounding:" in dock.grounding_badge.text()

        # 5. Direct call with elements=None retains existing badge text
        dock.update_perception_preview(test_pix, elements=None)
        QApplication.processEvents()
        assert "Grounding:" in dock.grounding_badge.text()

    # -------------------------------------------------------------------------
    # 10. High-Frequency Frame Streaming Concurrency Under Privacy State Toggle
    # -------------------------------------------------------------------------
    def test_concurrent_frame_streaming_with_rapid_privacy_mask_toggles(self, qtbot, dock_config):
        """
        Adversarial Re-Challenge:
        High-throughput stress: 4 worker threads streaming frames continuously while
        a supervisor thread rapidly toggles between WATCHING and PROTECTED.
        Verifies:
        - No Qt cross-thread paint crashes or race conditions.
        - Whenever dock is in PROTECTED state, perception preview is strictly masked.
        """
        bridge = UIBridge()
        dock = CompanionDock(config=dock_config, bridge=bridge)
        qtbot.addWidget(dock)

        stop_event = threading.Event()
        errors: List[Exception] = []

        def frame_streamer(tid: int):
            try:
                for frame_idx in range(60):
                    if stop_event.is_set():
                        break
                    # Generate test frame
                    pix = QPixmap(80, 50)
                    pix.fill(QColor(tid * 30, frame_idx % 255, 100))
                    elems = [UIElement.from_bbox(id=1, bbox=(5, 5, 15, 15), label=f"T{tid}")]
                    bridge.notify_perception(pix, elems)
                    time.sleep(0.005)
            except Exception as e:
                errors.append(e)

        def state_toggler():
            try:
                for cycle in range(20):
                    if stop_event.is_set():
                        break
                    bridge.notify_state("PROTECTED", mood="Guarded")
                    time.sleep(0.015)
                    bridge.notify_state("WATCHING", mood="Observant")
                    time.sleep(0.015)
            except Exception as e:
                errors.append(e)

        streamers = [threading.Thread(target=frame_streamer, args=(i,), daemon=True) for i in range(4)]
        toggler = threading.Thread(target=state_toggler, daemon=True)

        for s in streamers:
            s.start()
        toggler.start()

        for s in streamers:
            s.join(timeout=3.0)
        toggler.join(timeout=3.0)
        stop_event.set()

        qtbot.wait(200)
        QApplication.processEvents()

        assert len(errors) == 0, f"Concurrent frame streaming errors: {errors}"
        # Finally transition to PROTECTED and verify mask integrity
        dock.update_state("PROTECTED", mood="FinalAudit")
        QApplication.processEvents()
        assert dock._is_masked is True
        assert "SENSITIVE" in dock.grounding_badge.text()

