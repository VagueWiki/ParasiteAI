"""
tests/test_challenger_m3_2.py - Cross-Subsystem Adversarial Stress Suite (Challenger M3 Iteration 2).

Adversarially tests cross-subsystem interactions between:
1. CompanionDock (telemetry, state/mood, speech/thought, goal queue, perception)
2. GhostHUD (Set-of-Mark targeting, 300ms pre-click reticle, trajectory preview)
3. UIBridge (central signal hub marshalling across background threads and Qt GUI thread)

Specific challenge vectors:
- Concurrent multi-threaded flood assaulting Dock and HUD simultaneously.
- Reticle animation completion and responsiveness during heavy telemetry deluge.
- Simultaneous emergency panic abort during active reticle and streaming telemetry.
- Companion Dock HUD checkbox toggle synchronization with GhostHUD visibility.
- Perception preview and Set-of-Mark target synchronization across thread boundaries.
- Extreme coordinates, boundary conditions, and painter safety under concurrent load.
"""

from __future__ import annotations

import queue
import sys
import threading
import time
from typing import List
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtCore import QPoint, QRect, Qt
from PyQt6.QtGui import QColor, QImage, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication

from parasite_ai.config import CompanionDockConfig, GhostHUDConfig
from parasite_ai.ui.bridge import UIBridge
from parasite_ai.ui.companion_dock import STATE_CONFIG, CompanionDock
from parasite_ai.ui.ghost_hud import GhostHUD, HUDTarget
from parasite_ai.ui.types import UIElement


@pytest.fixture
def shared_dock_config() -> CompanionDockConfig:
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


@pytest.fixture
def shared_hud_config() -> GhostHUDConfig:
    return GhostHUDConfig(
        enabled=True,
        fps_target=60,
        reticle_duration_ms=100,
        som_box_color="#00E5FF",
        som_glow_color="#00FFCC",
        box_alpha=0.3,
        stroke_width_px=2.0,
    )


class TestCrossSubsystemAdversarialStress:
    """Rigorous empirical challenge suite testing cross-subsystem UI interactions."""

    def test_cross_subsystem_multithreaded_flood_dock_and_hud(
        self, qtbot, shared_dock_config, shared_hud_config
    ):
        """
        Adversarial Stress: 6 concurrent worker threads flooding UIBridge with:
        - Worker 1: 300 telemetry updates with step variations (0/0, normal, negative, overflow)
        - Worker 2: 60 rapid reticle show and clear requests
        - Worker 3: 60 Set-of-Mark target batch replacements (up to 100 targets per batch)
        - Worker 4: 200 state and mood transitions across all valid and invalid states
        - Worker 5: 150 thought and speech streaming messages
        - Worker 6: 50 perception preview image updates with element summaries
        Concurrently, GUI thread submits 20 user goals and retrieves them.
        Verifies zero deadlocks, zero unhandled exceptions, and complete signal delivery.
        """
        bridge = UIBridge()
        dock = CompanionDock(config=shared_dock_config, bridge=bridge)
        hud = GhostHUD(config=shared_hud_config, bridge=bridge, enable_win32_styles=False)
        qtbot.addWidget(dock)
        qtbot.addWidget(hud)
        dock.show()
        hud.show()

        worker_errors: List[Exception] = []
        stop_barrier = threading.Barrier(7)  # 6 workers + main test thread

        def worker_telemetry():
            try:
                stop_barrier.wait()
                for i in range(300):
                    step = i % 50
                    total = 50
                    if i % 7 == 0:
                        bridge.notify_telemetry(f"Step {step}/{total}", step, total)
                    elif i % 11 == 0:
                        bridge.notify_telemetry(f"Step {step}/0 (boundary)", step, 0)
                    elif i % 13 == 0:
                        bridge.notify_telemetry("Idle status string without steps")
                    else:
                        bridge.notify_telemetry(f"Telemetry burst #{i}", i, 300)
                    time.sleep(0.001)
            except Exception as e:
                worker_errors.append(e)

        def worker_reticles():
            try:
                stop_barrier.wait()
                for i in range(60):
                    x = (i * 37) % 1920
                    y = (i * 23) % 1080
                    bridge.show_reticle(x, y, duration_ms=40, target_id=i, label=f"Button #{i}")
                    if i % 3 == 0:
                        bridge.clear_reticle()
                    time.sleep(0.005)
            except Exception as e:
                worker_errors.append(e)

        def worker_targets():
            try:
                stop_barrier.wait()
                for i in range(60):
                    count = (i % 25) + 1
                    elems = [
                        UIElement.from_bbox(
                            id=j + 1,
                            bbox=(10 * j, 20 * j, 80, 30),
                            label=f"Elem {j + 1}",
                            role="button" if j % 2 == 0 else "edit",
                        )
                        for j in range(count)
                    ]
                    bridge.set_hud_targets(elems)
                    if i % 5 == 0:
                        bridge.clear_hud_targets()
                    time.sleep(0.004)
            except Exception as e:
                worker_errors.append(e)

        def worker_states():
            try:
                stop_barrier.wait()
                states = ["WATCHING", "THINKING", "DRIVING", "USER_OVERRIDE", "OFFLOADING", "PROTECTED"]
                moods = ["Curious", "Focused", "Cautious", "Analytical", "Alarmed"]
                for i in range(200):
                    s = states[i % len(states)]
                    m = moods[i % len(moods)]
                    bridge.notify_state(s, m)
                    time.sleep(0.002)
            except Exception as e:
                worker_errors.append(e)

        def worker_speech():
            try:
                stop_barrier.wait()
                for i in range(150):
                    bridge.notify_thought(f"Thinking cycle {i}: verifying bounds.")
                    if i % 2 == 0:
                        bridge.notify_speech(f"Assistant action message {i}.")
                    time.sleep(0.002)
            except Exception as e:
                worker_errors.append(e)

        def worker_perception():
            try:
                stop_barrier.wait()
                for i in range(50):
                    img = QImage(160, 90, QImage.Format.Format_RGB32)
                    img.fill(QColor(i % 255, (i * 5) % 255, 128))
                    elems = [
                        UIElement.from_bbox(id=1, bbox=(10, 10, 50, 20), label="Target"),
                    ]
                    bridge.notify_perception(img, elems)
                    time.sleep(0.006)
            except Exception as e:
                worker_errors.append(e)

        threads = [
            threading.Thread(target=worker_telemetry, daemon=True),
            threading.Thread(target=worker_reticles, daemon=True),
            threading.Thread(target=worker_targets, daemon=True),
            threading.Thread(target=worker_states, daemon=True),
            threading.Thread(target=worker_speech, daemon=True),
            threading.Thread(target=worker_perception, daemon=True),
        ]
        for t in threads:
            t.start()

        # Release all workers simultaneously
        stop_barrier.wait()

        # Concurrently submit goals from GUI
        submitted_goals = []
        for g_idx in range(20):
            goal = f"Cross-subsystem stress goal #{g_idx}"
            dock.goal_input.setText(goal)
            dock._on_submit_goal()
            submitted_goals.append(goal)
            qtbot.wait(10)

        # Wait for all workers to complete
        for t in threads:
            t.join(timeout=10.0)
            assert not t.is_alive(), "Worker thread deadlocked during concurrent flood"

        assert len(worker_errors) == 0, f"Worker thread raised exceptions: {worker_errors}"

        # Verify all submitted goals arrived cleanly in thread-safe queue
        retrieved_goals = []
        for _ in range(len(submitted_goals)):
            retrieved = bridge.get_next_goal(timeout_sec=1.0)
            assert retrieved is not None
            retrieved_goals.append(retrieved)

        assert retrieved_goals == submitted_goals

        # Verify widgets remain fully operational and responsive
        pixmap = QPixmap(dock.size())
        dock.render(pixmap)
        assert not pixmap.isNull()

        hud_pixmap = QPixmap(400, 300)
        hud.render(hud_pixmap)
        assert not hud_pixmap.isNull()

    def test_reticle_completion_timing_unstarved_by_telemetry_burst(
        self, qtbot, shared_dock_config, shared_hud_config
    ):
        """
        Adversarial Stress: Tests that a short-lived targeting reticle (duration 50ms)
        completes and emits sig_reticle_finished without being starved or delayed by
        a simultaneous burst of 500 telemetry messages from multiple background threads.
        """
        bridge = UIBridge()
        dock = CompanionDock(config=shared_dock_config, bridge=bridge)
        hud = GhostHUD(config=shared_hud_config, bridge=bridge, enable_win32_styles=False)
        qtbot.addWidget(dock)
        qtbot.addWidget(hud)

        telemetry_running = threading.Event()
        telemetry_running.set()

        def telemetry_blaster():
            count = 0
            while telemetry_running.is_set() and count < 500:
                count += 1
                bridge.notify_telemetry(f"Heavy load telemetry packet {count}", count, 500)
                time.sleep(0.001)

        t1 = threading.Thread(target=telemetry_blaster, daemon=True)
        t2 = threading.Thread(target=telemetry_blaster, daemon=True)
        t1.start()
        t2.start()

        # Start reticle with 50ms duration
        with qtbot.waitSignal(hud.sig_reticle_finished, timeout=2000) as blocker:
            bridge.show_reticle(x=720, y=480, duration_ms=50, target_id=99, label="Confirm")

        telemetry_running.clear()
        t1.join(timeout=3.0)
        t2.join(timeout=3.0)

        # Reticle finished at correct coordinates and deactivated
        assert blocker.args == [720, 480]
        assert hud._reticle_active is False

    def test_emergency_panic_cancels_reticle_and_notifies_bridge(
        self, qtbot, shared_dock_config, shared_hud_config
    ):
        """
        Adversarial Stress: While reticle is mid-flight and telemetry is streaming,
        the user clicks the emergency PANIC button on CompanionDock.
        Verifies:
        1. sig_panic_triggered is emitted through bridge.
        2. Reticle on GhostHUD is instantly aborted.
        3. All targets can be cleared and UI remains stable.
        """
        bridge = UIBridge()
        dock = CompanionDock(config=shared_dock_config, bridge=bridge)
        hud = GhostHUD(config=shared_hud_config, bridge=bridge, enable_win32_styles=False)
        qtbot.addWidget(dock)
        qtbot.addWidget(hud)

        # Set up active reticle and targets
        hud.set_targets([{"id": 1, "role": "Button", "label": "Dangerous Button", "x": 100, "y": 100, "width": 80, "height": 30}])
        bridge.show_reticle(x=140, y=115, duration_ms=500, target_id=1, label="Dangerous Button")
        qtbot.waitUntil(lambda: hud._reticle_active is True, timeout=1000)

        # Wire panic to clear reticle as application would
        bridge.sig_panic_triggered.connect(bridge.clear_reticle)
        bridge.sig_panic_triggered.connect(bridge.clear_hud_targets)

        # Trigger panic from companion dock button
        with qtbot.waitSignal(hud.sig_reticle_aborted, timeout=1000):
            with qtbot.waitSignal(bridge.sig_panic_triggered, timeout=1000):
                dock.btn_panic.click()

        qtbot.waitUntil(lambda: hud._reticle_active is False, timeout=500)
        qtbot.waitUntil(lambda: len(hud._targets) == 0, timeout=500)
        assert hud._reticle_active is False
        assert len(hud._targets) == 0

    def test_companion_dock_hud_checkbox_toggles_ghost_hud_visibility(
        self, qtbot, shared_dock_config, shared_hud_config
    ):
        """
        Cross-Subsystem Integration: Tests toggling the 'Show HUD Tags' checkbox
        on CompanionDock propagates via bridge to toggle GhostHUD visibility.
        """
        bridge = UIBridge()
        dock = CompanionDock(config=shared_dock_config, bridge=bridge)
        hud = GhostHUD(config=shared_hud_config, bridge=bridge, enable_win32_styles=False)
        qtbot.addWidget(dock)
        qtbot.addWidget(hud)
        dock.show()
        hud.show()

        assert hud.isVisible() is True
        assert dock.chk_hud.isChecked() is True

        # Toggle OFF
        dock.chk_hud.setChecked(False)
        qtbot.waitUntil(lambda: hud.isVisible() is False, timeout=1000)
        assert hud.isVisible() is False

        # Toggle ON
        dock.chk_hud.setChecked(True)
        qtbot.waitUntil(lambda: hud.isVisible() is True, timeout=1000)
        assert hud.isVisible() is True

    def test_perception_and_hud_targets_lockstep_synchronization(
        self, qtbot, shared_dock_config, shared_hud_config
    ):
        """
        Adversarial Stress: Tests lockstep synchronization between perception preview
        element count badge in CompanionDock and Set-of-Mark target count in GhostHUD.
        """
        bridge = UIBridge()
        dock = CompanionDock(config=shared_dock_config, bridge=bridge)
        hud = GhostHUD(config=shared_hud_config, bridge=bridge, enable_win32_styles=False)
        qtbot.addWidget(dock)
        qtbot.addWidget(hud)

        for target_count in [0, 1, 15, 80, 0, 150]:
            elements = [
                UIElement.from_bbox(id=i + 1, bbox=(i * 5, i * 5, 40, 20), label=f"T{i + 1}")
                for i in range(target_count)
            ]
            img = QImage(320, 180, QImage.Format.Format_RGB32)
            img.fill(QColor(30, 41, 59))

            bridge.notify_perception(img, elements)
            bridge.set_hud_targets(elements)

            expected_badge = f"Grounding: {target_count} Targets Active"

            qtbot.waitUntil(lambda: dock.grounding_badge.text() == expected_badge, timeout=1000)
            qtbot.waitUntil(lambda: len(hud._targets) == target_count, timeout=1000)
            assert dock.grounding_badge.text() == expected_badge
            assert len(hud._targets) == target_count

    def test_rapid_alternating_reticle_and_state_change_race(
        self, qtbot, shared_dock_config, shared_hud_config
    ):
        """
        Adversarial Stress: Simultaneously triggers rapid alternating reticle show/abort
        while rapidly switching between DRIVING and USER_OVERRIDE states.
        Tests for race conditions between QTimer ticks, QPainter render calls, and state pill updates.
        """
        bridge = UIBridge()
        dock = CompanionDock(config=shared_dock_config, bridge=bridge)
        hud = GhostHUD(config=shared_hud_config, bridge=bridge, enable_win32_styles=False)
        qtbot.addWidget(dock)
        qtbot.addWidget(hud)
        hud.resize(1024, 768)

        for i in range(40):
            # Show reticle
            bridge.show_reticle(x=200 + i * 5, y=150 + i * 5, duration_ms=25, target_id=i, label=f"Act {i}")
            bridge.notify_state("DRIVING", "Executing")
            qtbot.wait(5)

            # Abort reticle & override
            bridge.clear_reticle()
            bridge.notify_state("USER_OVERRIDE", "Suspended")
            qtbot.wait(5)

            # Paint HUD offscreen to ensure no painter crashes during state shifts
            pixmap = QPixmap(1024, 768)
            hud.render(pixmap)
            assert not pixmap.isNull()

        assert hud._reticle_active is False
        assert dock._current_state == "USER_OVERRIDE"

    def test_typewriter_speech_stream_and_reticle_animation_coexistence(
        self, qtbot, shared_dock_config, shared_hud_config
    ):
        """
        Adversarial Stress: Streams a 500-token speech monologue into CompanionDock
        triggering typewriter animation timer while GhostHUD reticle animation is ticking.
        Verifies both timers execute concurrently without starving or blocking Qt event loop.
        """
        bridge = UIBridge()
        dock = CompanionDock(config=shared_dock_config, bridge=bridge)
        hud = GhostHUD(config=shared_hud_config, bridge=bridge, enable_win32_styles=False)
        qtbot.addWidget(dock)
        qtbot.addWidget(hud)

        # Start reticle with 120ms duration
        bridge.show_reticle(x=500, y=300, duration_ms=120, target_id=42, label="Typewriter Test")

        # Blast speech stream
        long_monologue = "Executing desktop action pipeline. " * 20
        bridge.notify_speech(long_monologue)

        # Wait for reticle completion while typewriter is actively ticking
        with qtbot.waitSignal(hud.sig_reticle_finished, timeout=2000):
            pass

        assert hud._reticle_active is False
        # Verify dialogue label received text
        assert len(dock.dialogue_label.text()) > 0

    def test_virtual_geometry_change_during_multithreaded_reticle_and_telemetry(
        self, qtbot, shared_dock_config, shared_hud_config
    ):
        """
        Adversarial Stress: Simulates monitor topology and resolution reconfigurations
        (e.g., secondary monitor added with negative origin) while reticle is active
        and telemetry is streaming from a background thread.
        """
        bridge = UIBridge()
        dock = CompanionDock(config=shared_dock_config, bridge=bridge)
        hud = GhostHUD(config=shared_hud_config, bridge=bridge, enable_win32_styles=False)
        qtbot.addWidget(dock)
        qtbot.addWidget(hud)

        stop_event = threading.Event()

        def stream_telemetry():
            step = 0
            while not stop_event.is_set():
                step += 1
                bridge.notify_telemetry(f"Topology shift telemetry {step}", step, 100)
                time.sleep(0.002)

        t = threading.Thread(target=stream_telemetry, daemon=True)
        t.start()

        # Start reticle
        bridge.show_reticle(x=400, y=300, duration_ms=200, target_id=1, label="Display Shift")

        # Simulate dynamic monitor geometry changes
        geometries = [
            QRect(-1920, 0, 3840, 1080),   # Left secondary monitor
            QRect(0, 0, 7680, 1440),        # Triple surround
            QRect(-1080, -500, 3000, 2000), # Diagonal offset
            QRect(0, 0, 1920, 1080),        # Reset to standard 1080p
        ]
        for geom in geometries:
            hud._on_virtual_geometry_changed(geom)
            assert hud.geometry() == geom
            pixmap = QPixmap(800, 600)
            hud.render(pixmap)
            assert not pixmap.isNull()
            qtbot.wait(10)

        stop_event.set()
        t.join(timeout=2.0)
        bridge.clear_reticle()
        qtbot.waitUntil(lambda: hud._reticle_active is False, timeout=1000)
        assert hud._reticle_active is False

    def test_malformed_perception_and_extreme_step_telemetry_resilience(
        self, qtbot, shared_dock_config, shared_hud_config
    ):
        """
        Adversarial Stress: Emits corrupt/malformed perception frames and extreme
        telemetry steps (overflows, negatives, zero total_steps) concurrently.
        Verifies graceful degradation, zero crashes, and strict progress clamping.
        """
        bridge = UIBridge()
        dock = CompanionDock(config=shared_dock_config, bridge=bridge)
        hud = GhostHUD(config=shared_hud_config, bridge=bridge, enable_win32_styles=False)
        qtbot.addWidget(dock)
        qtbot.addWidget(hud)

        # 1. Malformed perception frames
        malformed_inputs = [
            None,
            "not_an_image",
            12345,
            {"raw": "bytes"},
            b"\x00\xFF\xAA\xBB",
            [1, 2, 3],
        ]
        for malformed in malformed_inputs:
            bridge.notify_perception(malformed, None)
            qtbot.wait(5)
            # Dock should fallback to "No Frame Available" without crashing
            assert dock.thumbnail_view.text() == "No Frame Available"

        # 2. Extreme telemetry step variations
        extreme_steps = [
            (999999, 100),    # Over 100% -> should clamp to 100
            (-50, 100),       # Negative current -> should clamp to 0
            (10, -20),        # Negative total -> total_steps <= 0 -> 0%
            (0, 0),           # Zero/Zero -> idle -> 0%
            (29, 100),        # Float precision boundary -> exactly 29%
            (50, 50),         # Exact 100%
        ]
        for curr, tot in extreme_steps:
            bridge.notify_telemetry(f"Extreme {curr}/{tot}", curr, tot)
            qtbot.wait(5)
            progress_val = dock.step_progress.value()
            assert 0 <= progress_val <= 100, f"Progress value {progress_val} not in [0, 100]"
            if curr == 29 and tot == 100:
                assert progress_val == 29
            elif curr == 999999 and tot == 100:
                assert progress_val == 100
            elif curr == -50 and tot == 100:
                assert progress_val == 0
            elif tot <= 0:
                assert progress_val == 0
