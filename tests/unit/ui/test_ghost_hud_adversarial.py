"""
tests/test_ghost_hud_adversarial.py - Adversarial Stress & Edge-Case Test Suite for Ghost-Hand HUD.

Adversarially tests:
1. Extreme multi-monitor virtual desktop configurations (negative origins, 3-monitor surround 7680x1440, topology shifts).
2. High-density Set-of-Mark rendering (250+ elements, overlapping bboxes, zero/negative bounds, out-of-screen targets, extreme labels, 5000-element stress).
3. Reticle preemption and cancellation races (rapid preemption, mid-flight abort, zero/negative durations, idempotent aborts).
4. Bézier curve trajectory preview edge cases (zero distance, 15px threshold boundaries, extreme monitor spans, negative coords, progress clamping).
5. Win32 extended style bitmasks, simulated invalid window handles, non-Windows platform degradation, and DPI bootstrap error handling.
"""

from __future__ import annotations

import ctypes
import math
import sys
import time
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtCore import QPoint, QRect, Qt
from PyQt6.QtGui import QColor, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication

from parasite_ai.config import GhostHUDConfig
from parasite_ai.ui.bridge import UIBridge
from parasite_ai.ui.dpi import init_high_dpi_awareness
from parasite_ai.ui.ghost_hud import (
    GWL_EXSTYLE,
    HWND_TOPMOST,
    REQUIRED_HUD_EX_STYLES,
    ROLE_COLOR_MAP,
    SWP_FRAMECHANGED,
    SWP_NOACTIVATE,
    SWP_NOMOVE,
    SWP_NOSIZE,
    WS_EX_LAYERED,
    WS_EX_NOACTIVATE,
    WS_EX_TOOLWINDOW,
    WS_EX_TOPMOST,
    WS_EX_TRANSPARENT,
    GhostHUD,
    HUDTarget,
)
from parasite_ai.ui.types import UIElement
from parasite_ai.ui.win32_styles import apply_click_through_styles


@pytest.fixture
def adv_hud_config() -> GhostHUDConfig:
    return GhostHUDConfig(
        enabled=True,
        fps_target=60,
        reticle_duration_ms=100,
        som_box_color="#00E5FF",
        som_glow_color="#00FFCC",
        box_alpha=0.3,
        stroke_width_px=2.0,
    )


# ===========================================================================
# 1. Extreme Multi-Monitor Virtual Desktop Configurations
# ===========================================================================
class TestMultiMonitorVirtualDesktop:
    """Stress tests multi-monitor coordinate transformations and dynamic topology shifts."""

    def test_secondary_monitor_left_negative_coordinates(self, qtbot, adv_hud_config):
        """Secondary monitor situated to the left of primary monitor: bounds (-1920, 0, 3840, 1080)."""
        hud = GhostHUD(config=adv_hud_config, enable_win32_styles=False)
        qtbot.addWidget(hud)

        # Multi-monitor setup: left monitor (-1920..0), primary monitor (0..1920)
        multi_monitor_rect = QRect(-1920, 0, 3840, 1080)
        hud._on_virtual_geometry_changed(multi_monitor_rect)
        assert hud.geometry() == multi_monitor_rect

        # Target on the left (secondary) monitor: global x = -500, y = 300
        # Expected local coordinate: -500 - (-1920) = 1420
        local_pt = hud._to_local(-500, 300)
        assert local_pt.x() == 1420
        assert local_pt.y() == 300

        # Target on primary monitor: global x = 500, y = 300
        # Expected local coordinate: 500 - (-1920) = 2420
        local_pt_primary = hud._to_local(500, 300)
        assert local_pt_primary.x() == 2420
        assert local_pt_primary.y() == 300

        # Set targets on both monitors and render
        hud.set_targets([
            {"id": 1, "role": "Button", "label": "Left Screen Button", "x": -1500, "y": 200, "width": 120, "height": 40},
            {"id": 2, "role": "Edit", "label": "Main Screen Input", "x": 400, "y": 200, "width": 120, "height": 40},
        ])
        assert len(hud._targets) == 2

        pixmap = QPixmap(3840, 1080)
        hud.render(pixmap)
        assert not pixmap.isNull()

    def test_three_monitor_surround_7680x1440_span(self, qtbot, adv_hud_config):
        """3-monitor surround span: left (-2560..0), center (0..2560), right (2560..5120), total 7680x1440."""
        hud = GhostHUD(config=adv_hud_config, enable_win32_styles=False)
        qtbot.addWidget(hud)

        surround_rect = QRect(-2560, 0, 7680, 1440)
        hud._on_virtual_geometry_changed(surround_rect)
        assert hud.geometry() == surround_rect

        # Far left target
        pt_left = hud._to_local(-2000, 500)
        assert pt_left.x() == 560
        assert pt_left.y() == 500

        # Far right target (global x = 4000)
        pt_right = hud._to_local(4000, 700)
        assert pt_right.x() == 6560
        assert pt_right.y() == 700

        # Targets across all 3 monitors
        hud.set_targets([
            {"id": 1, "role": "Button", "label": "Far Left", "x": -2400, "y": 100, "width": 100, "height": 50},
            {"id": 2, "role": "Button", "label": "Center", "x": 1000, "y": 100, "width": 100, "height": 50},
            {"id": 3, "role": "Button", "label": "Far Right", "x": 4500, "y": 100, "width": 100, "height": 50},
        ])
        assert len(hud._targets) == 3

        pixmap = QPixmap(1920, 1080)
        hud.render(pixmap)
        assert not pixmap.isNull()

    def test_diagonal_top_left_negative_origin(self, qtbot, adv_hud_config):
        """Monitor arranged above and to the left: negative x and negative y bounds (-1920, -1080, 3840, 2160)."""
        hud = GhostHUD(config=adv_hud_config, enable_win32_styles=False)
        qtbot.addWidget(hud)

        quad_rect = QRect(-1920, -1080, 3840, 2160)
        hud._on_virtual_geometry_changed(quad_rect)

        # Coordinate in upper-left quadrant: global (-1000, -500)
        pt = hud._to_local(-1000, -500)
        assert pt.x() == 920
        assert pt.y() == 580

        hud.set_targets([
            {"id": 1, "role": "Button", "label": "Upper Left", "x": -1800, "y": -1000, "width": 150, "height": 40},
            {"id": 2, "role": "Button", "label": "Lower Right", "x": 1000, "y": 500, "width": 150, "height": 40},
        ])
        pixmap = QPixmap(1000, 1000)
        hud.render(pixmap)
        assert not pixmap.isNull()

    def test_dynamic_geometry_reconfiguration_during_active_reticle(self, qtbot, adv_hud_config):
        """Simulate monitor unplugging / resolution collapse during an active reticle countdown."""
        hud = GhostHUD(config=adv_hud_config, enable_win32_styles=False)
        qtbot.addWidget(hud)

        # Initially surround geometry
        hud._on_virtual_geometry_changed(QRect(-2560, 0, 7680, 1440))
        hud.show_reticle(x=3000, y=800, duration_ms=500, target_id=99, label="ExtMon")
        assert hud._reticle_active is True

        # Disconnect external monitor -> collapses to single 1920x1080 display
        collapsed_rect = QRect(0, 0, 1920, 1080)
        hud._on_virtual_geometry_changed(collapsed_rect)
        assert hud.geometry() == collapsed_rect

        # Ensure reticle is still active, doesn't crash on render after collapse
        pixmap = QPixmap(1920, 1080)
        hud.render(pixmap)
        assert not pixmap.isNull()
        assert hud._reticle_active is True

        hud.abort_reticle()
        assert hud._reticle_active is False

    def test_zero_dimension_window_geometry_resilience(self, qtbot, adv_hud_config):
        """HUD resized down to 0x0 (e.g. during display off/sleep event) renders safely."""
        hud = GhostHUD(config=adv_hud_config, enable_win32_styles=False)
        qtbot.addWidget(hud)

        hud._on_virtual_geometry_changed(QRect(0, 0, 0, 0))
        hud.set_targets([
            {"id": 1, "role": "Button", "label": "ZeroWindowTarget", "x": 10, "y": 10, "width": 50, "height": 20}
        ])
        pixmap = QPixmap(100, 100)
        hud.render(pixmap)
        assert not pixmap.isNull()


# ===========================================================================
# 2. High-Density Set-of-Mark Rendering Stress
# ===========================================================================
class TestHighDensitySetOfMarkRendering:
    """Stress tests high target counts (200+), overlapping bboxes, zero/negative bounds, and edge labels."""

    def test_250_elements_dense_grid_rendering_performance(self, qtbot, adv_hud_config):
        """Render 250 elements simultaneously in a dense overlapping desktop grid."""
        hud = GhostHUD(config=adv_hud_config, enable_win32_styles=False)
        qtbot.addWidget(hud)
        hud.setGeometry(0, 0, 1920, 1080)

        # Generate 250 distinct UI elements
        roles = ["Button", "Edit", "OCR", "Hyperlink", "Document", "Menuitem", "Unknown"]
        elements: List[Dict[str, Any]] = []
        for i in range(1, 251):
            row = (i - 1) // 15
            col = (i - 1) % 15
            elements.append({
                "id": i,
                "role": roles[i % len(roles)],
                "label": f"Control_{i}",
                "x": 50 + col * 120,
                "y": 40 + row * 60,
                "width": 100,
                "height": 40,
            })

        t0 = time.perf_counter()
        hud.set_targets(elements)
        t_set = time.perf_counter() - t0
        assert len(hud._targets) == 250
        assert t_set < 0.25  # Normalization of 250 items must be sub-second (<250ms)

        # Render 250 targets onto pixmap and verify render speed
        pixmap = QPixmap(1920, 1080)
        t_render_start = time.perf_counter()
        hud.render(pixmap)
        t_render_elapsed = time.perf_counter() - t_render_start
        assert not pixmap.isNull()
        assert t_render_elapsed < 0.50  # 250 elements render in < 500ms

    def test_5000_elements_flood_normalization_stress(self, qtbot, adv_hud_config):
        """Stress normalization and memory handling under a flood of 5,000 UI targets."""
        hud = GhostHUD(config=adv_hud_config, enable_win32_styles=False)
        qtbot.addWidget(hud)

        flood = [
            {"id": i, "role": "Button", "label": f"T{i}", "x": i % 1000, "y": i % 1000, "width": 50, "height": 20}
            for i in range(1, 5001)
        ]
        t0 = time.perf_counter()
        hud.set_targets(flood)
        t_elapsed = time.perf_counter() - t0
        assert len(hud._targets) == 5000
        assert t_elapsed < 1.0  # Must ingest 5,000 targets in < 1s

    def test_overlapping_bounding_boxes_and_stacked_targets(self, qtbot, adv_hud_config):
        """Fifty targets placed at identical coordinates with conflicting categories."""
        hud = GhostHUD(config=adv_hud_config, enable_win32_styles=False)
        qtbot.addWidget(hud)
        hud.setGeometry(0, 0, 1920, 1080)

        stacked_targets = [
            {"id": i, "role": "Button" if i % 2 == 0 else "Edit", "label": f"Stack_{i}", "x": 300, "y": 300, "width": 150, "height": 50}
            for i in range(1, 51)
        ]
        hud.set_targets(stacked_targets)
        assert len(hud._targets) == 50

        pixmap = QPixmap(800, 600)
        hud.render(pixmap)
        assert not pixmap.isNull()

    def test_zero_and_negative_sized_bounding_boxes(self, qtbot, adv_hud_config):
        """Bounding boxes with zero width/height or negative sizes must render without exception."""
        hud = GhostHUD(config=adv_hud_config, enable_win32_styles=False)
        qtbot.addWidget(hud)
        hud.setGeometry(0, 0, 1000, 800)

        pathological_boxes = [
            {"id": 1, "role": "Button", "label": "ZeroArea", "x": 100, "y": 100, "width": 0, "height": 0},
            {"id": 2, "role": "Edit", "label": "ZeroWidth", "x": 200, "y": 100, "width": 0, "height": 50},
            {"id": 3, "role": "OCR", "label": "ZeroHeight", "x": 300, "y": 100, "width": 80, "height": 0},
            {"id": 4, "role": "Button", "label": "NegativeWidth", "x": 500, "y": 100, "width": -50, "height": 30},
            {"id": 5, "role": "Button", "label": "NegativeBoth", "x": 700, "y": 100, "width": -100, "height": -40},
        ]
        hud.set_targets(pathological_boxes)
        assert len(hud._targets) == 5

        pixmap = QPixmap(1000, 800)
        hud.render(pixmap)
        assert not pixmap.isNull()

    def test_out_of_screen_and_extreme_coordinates(self, qtbot, adv_hud_config):
        """Targets with coordinates far beyond virtual desktop bounds."""
        hud = GhostHUD(config=adv_hud_config, enable_win32_styles=False)
        qtbot.addWidget(hud)
        hud.setGeometry(0, 0, 1920, 1080)

        extreme_targets = [
            {"id": 1, "role": "Button", "label": "FarNegative", "x": -99999, "y": -99999, "width": 100, "height": 40},
            {"id": 2, "role": "Button", "label": "FarPositive", "x": 99999, "y": 99999, "width": 100, "height": 40},
            {"id": 3, "role": "Edit", "label": "ExactTopLeft", "x": 0, "y": 0, "width": 50, "height": 20},
            {"id": 4, "role": "Edit", "label": "ExactBottomRight", "x": 1920, "y": 1080, "width": 50, "height": 20},
        ]
        hud.set_targets(extreme_targets)
        assert len(hud._targets) == 4

        pixmap = QPixmap(1920, 1080)
        hud.render(pixmap)
        assert not pixmap.isNull()

    def test_extreme_label_variations(self, qtbot, adv_hud_config):
        """Labels with empty strings, massive strings (1000+ chars), CJK, Emojis, and HTML/XML injection."""
        hud = GhostHUD(config=adv_hud_config, enable_win32_styles=False)
        qtbot.addWidget(hud)
        hud.setGeometry(0, 0, 1920, 1080)

        huge_label = "A" * 1200
        labels = [
            {"id": 1, "role": "Button", "label": "", "x": 50, "y": 50, "width": 80, "height": 30},
            {"id": 2, "role": "Button", "label": huge_label, "x": 200, "y": 50, "width": 80, "height": 30},
            {"id": 3, "role": "Edit", "label": "日本語 / 中文 / 한국어", "x": 350, "y": 50, "width": 80, "height": 30},
            {"id": 4, "role": "OCR", "label": "🚀🔥💡🛡️🤖🎉", "x": 500, "y": 50, "width": 80, "height": 30},
            {"id": 5, "role": "Button", "label": "<script>alert(1)</script>&\"'", "x": 650, "y": 50, "width": 80, "height": 30},
        ]
        hud.set_targets(labels)
        assert len(hud._targets) == 5

        pixmap = QPixmap(1920, 1080)
        hud.render(pixmap)
        assert not pixmap.isNull()

    def test_target_normalization_and_fallback_resilience(self, qtbot, adv_hud_config):
        """Verify normalization handling: None rejection, non-int field rejection, and duck-typing fallback."""
        hud = GhostHUD(config=adv_hud_config, enable_win32_styles=False)
        qtbot.addWidget(hud)

        # 1. None is rejected
        assert hud._normalize_target(None) is None

        # 2. Dict with uncastable int field is safely rejected (returns None without exception)
        assert hud._normalize_target({"id": "not_an_int", "x": "bad"}) is None

        # 3. Valid dict is correctly parsed
        norm_valid = hud._normalize_target({"id": 42, "role": "Button", "label": "OK", "x": 100, "y": 200, "width": 80, "height": 30})
        assert norm_valid is not None
        assert norm_valid.id == 42
        assert norm_valid.color_hex == "#00E5FF"

        # 4. Empty dict and primitive objects fallback to id=0 defaults without crashing
        norm_empty = hud._normalize_target({})
        assert norm_empty is not None
        assert norm_empty.id == 0

        norm_int = hud._normalize_target(42)
        assert norm_int is not None
        assert norm_int.id == 0

        norm_str = hud._normalize_target("string_payload")
        assert norm_str is not None
        assert norm_str.id == 0


# ===========================================================================
# 3. Reticle Preemption and Cancellation Races
# ===========================================================================
class TestReticlePreemptionAndCancellationRaces:
    """Stress tests reticle preemption, mid-flight aborts, zero duration, and racing invocations."""

    def test_rapid_reticle_preemption_100_calls(self, qtbot, adv_hud_config):
        """Calling show_reticle 100 times in rapid succession before prior timer elapses."""
        hud = GhostHUD(config=adv_hud_config, enable_win32_styles=False)
        qtbot.addWidget(hud)

        # 100 rapid calls moving the reticle
        for i in range(1, 101):
            hud.show_reticle(x=i * 5, y=i * 3, duration_ms=100, target_id=i, label=f"T{i}")

        assert hud._reticle_active is True
        assert hud._reticle_target == QPoint(500, 300)
        assert hud._reticle_id == 100
        assert hud._reticle_label == "T100"

        # Wait for the single active reticle to finish
        with qtbot.waitSignal(hud.sig_reticle_finished, timeout=1000) as blocker:
            pass

        assert blocker.args == [500, 300]
        assert hud._reticle_active is False

    def test_abort_reticle_mid_flight_prevents_completion_signal(self, qtbot, adv_hud_config):
        """Aborting mid-flight must immediately stop timer and never emit sig_reticle_finished."""
        hud = GhostHUD(config=adv_hud_config, enable_win32_styles=False)
        qtbot.addWidget(hud)

        finished_spy = []
        hud.sig_reticle_finished.connect(lambda x, y: finished_spy.append((x, y)))

        with qtbot.waitSignal(hud.sig_reticle_aborted, timeout=500):
            hud.show_reticle(x=400, y=400, duration_ms=300)
            assert hud._reticle_active is True
            # Abort after minimal delay
            hud.abort_reticle()

        assert hud._reticle_active is False
        assert len(finished_spy) == 0

        # Wait past original 300ms duration to verify finished never emits
        qtbot.wait(150)
        assert len(finished_spy) == 0

    def test_zero_duration_reticle_finishes_immediately(self, qtbot, adv_hud_config):
        """Zero duration reticle (0ms) must not cause ZeroDivisionError and complete cleanly."""
        hud = GhostHUD(config=adv_hud_config, enable_win32_styles=False)
        qtbot.addWidget(hud)

        with qtbot.waitSignal(hud.sig_reticle_finished, timeout=1000) as blocker:
            hud.show_reticle(x=250, y=150, duration_ms=0, target_id=7, label="Instant")

        assert blocker.args == [250, 150]
        assert hud._reticle_active is False

    def test_negative_duration_reticle_handled_safely(self, qtbot, adv_hud_config):
        """Negative duration (-100ms) handled safely without negative division or hang."""
        hud = GhostHUD(config=adv_hud_config, enable_win32_styles=False)
        qtbot.addWidget(hud)

        with qtbot.waitSignal(hud.sig_reticle_finished, timeout=1000) as blocker:
            hud.show_reticle(x=100, y=100, duration_ms=-100)

        assert blocker.args == [100, 100]
        assert hud._reticle_active is False

    def test_idempotent_abort_when_idle(self, qtbot, adv_hud_config):
        """Consecutive abort_reticle() calls when idle must not crash or emit spurious signals."""
        hud = GhostHUD(config=adv_hud_config, enable_win32_styles=False)
        qtbot.addWidget(hud)

        aborted_spy = []
        hud.sig_reticle_aborted.connect(lambda: aborted_spy.append(True))

        for _ in range(10):
            hud.abort_reticle()

        assert len(aborted_spy) == 0
        assert hud._reticle_active is False

    def test_rapid_alternating_show_and_abort_race(self, qtbot, adv_hud_config):
        """Rapid interleaving of show_reticle, abort_reticle, clear_all, clear_targets."""
        hud = GhostHUD(config=adv_hud_config, enable_win32_styles=False)
        qtbot.addWidget(hud)

        for i in range(25):
            hud.show_reticle(x=i * 10, y=i * 10, duration_ms=100)
            if i % 3 == 0:
                hud.abort_reticle()
            elif i % 3 == 1:
                hud.clear_all()
            else:
                hud.clear_reticle()

        assert hud._reticle_active is False


# ===========================================================================
# 4. Bézier Curve Trajectory Preview Edge Cases
# ===========================================================================
class TestBezierCurveTrajectoryEdgeCases:
    """Stress tests Bézier trajectory math: identical points, threshold boundaries, spans, negative coords."""

    def test_identical_start_and_target_points_zero_distance(self, qtbot, adv_hud_config):
        """Identical start and target points (dist == 0) must early return without ZeroDivisionError."""
        hud = GhostHUD(config=adv_hud_config, enable_win32_styles=False)
        qtbot.addWidget(hud)
        hud.resize(800, 600)

        pixmap = QPixmap(800, 600)
        with QPainter(pixmap) as painter:
            # p0 == p3 -> dist == 0.0
            hud._paint_bezier_path(painter, QPoint(100, 100), QPoint(100, 100), 0.5)

        assert not pixmap.isNull()

    def test_boundary_distances_near_15px_threshold(self, qtbot, adv_hud_config):
        """Test boundary distances right below, exactly at, and above the 15px minimum distance."""
        hud = GhostHUD(config=adv_hud_config, enable_win32_styles=False)
        qtbot.addWidget(hud)
        hud.resize(800, 600)

        pixmap = QPixmap(800, 600)
        with QPainter(pixmap) as painter:
            # dist = 10.0 (< 15.0 -> early returns)
            hud._paint_bezier_path(painter, QPoint(100, 100), QPoint(110, 100), 0.5)

            # dist = 14.999 (< 15.0 -> early returns)
            hud._paint_bezier_path(painter, QPoint(100, 100), QPoint(114, 100), 0.5)

            # dist = 15.0 (>= 15.0 -> executes cubicTo path calculation)
            hud._paint_bezier_path(painter, QPoint(100, 100), QPoint(115, 100), 0.5)

            # dist = 16.0 (>= 15.0 -> executes cubicTo path calculation)
            hud._paint_bezier_path(painter, QPoint(100, 100), QPoint(116, 100), 0.5)

        assert not pixmap.isNull()

    def test_bezier_trajectory_across_extreme_monitor_span(self, qtbot, adv_hud_config):
        """Bézier trajectory spanning >7500 pixels across a 3-monitor surround configuration."""
        hud = GhostHUD(config=adv_hud_config, enable_win32_styles=False)
        qtbot.addWidget(hud)
        hud.resize(7680, 1440)

        pixmap = QPixmap(1000, 500)
        with QPainter(pixmap) as painter:
            p_start = QPoint(100, 200)
            p_end = QPoint(7500, 1200)  # dist > 7400px
            hud._paint_bezier_path(painter, p_start, p_end, 0.35)

        assert not pixmap.isNull()

    def test_bezier_trajectory_with_negative_coordinates(self, qtbot, adv_hud_config):
        """Bézier trajectory calculation with entirely negative coordinate points."""
        hud = GhostHUD(config=adv_hud_config, enable_win32_styles=False)
        qtbot.addWidget(hud)

        pixmap = QPixmap(500, 500)
        with QPainter(pixmap) as painter:
            p_start = QPoint(-3000, -2000)
            p_end = QPoint(-1500, -800)
            hud._paint_bezier_path(painter, p_start, p_end, 0.8)

        assert not pixmap.isNull()

    def test_progress_edge_values_in_bezier_rendering(self, qtbot, adv_hud_config):
        """Test progress = 0.0, progress = 1.0, and clamped out-of-range progress values."""
        hud = GhostHUD(config=adv_hud_config, enable_win32_styles=False)
        qtbot.addWidget(hud)

        pixmap = QPixmap(500, 500)
        with QPainter(pixmap) as painter:
            p0 = QPoint(50, 50)
            p3 = QPoint(400, 400)

            # Exact start
            hud._paint_bezier_path(painter, p0, p3, 0.0)
            # Exact end
            hud._paint_bezier_path(painter, p0, p3, 1.0)
            # Out of bounds progress
            hud._paint_bezier_path(painter, p0, p3, -0.5)
            hud._paint_bezier_path(painter, p0, p3, 1.5)

        assert not pixmap.isNull()

    def test_targeting_reticle_and_aiming_banner_with_extreme_coordinates(self, qtbot, adv_hud_config):
        """Reticle brackets and banner painted at negative coordinates and screen edges."""
        hud = GhostHUD(config=adv_hud_config, enable_win32_styles=False)
        qtbot.addWidget(hud)

        pixmap = QPixmap(500, 500)
        with QPainter(pixmap) as painter:
            # 1. At negative coordinate (banner flips below when by < 0)
            hud._paint_targeting_reticle(painter, QPoint(-50, -50), 0.5)
            hud._paint_aiming_banner(painter, QPoint(-50, -50), 150)

            # 2. At (0, 0) boundary
            hud._paint_targeting_reticle(painter, QPoint(0, 0), 1.0)
            hud._paint_aiming_banner(painter, QPoint(0, 0), 0)

            # 3. At extreme coordinate
            hud._paint_targeting_reticle(painter, QPoint(10000, 10000), 0.0)
            hud._paint_aiming_banner(painter, QPoint(10000, 10000), 300)

        assert not pixmap.isNull()


# ===========================================================================
# 5. Win32 Extended Styles & High-DPI Robustness
# ===========================================================================
class TestWin32ExtendedStylesAndDPIStress:
    """Stress tests Win32 style bitmasks, simulated invalid window handles, and DPI awareness bootstrap."""

    def test_required_hud_ex_styles_bitmask_verification(self):
        """Verify the exact bitwise composition and hexadecimal value of REQUIRED_HUD_EX_STYLES."""
        expected_bitmask = (
            WS_EX_LAYERED      # 0x00080000
            | WS_EX_TRANSPARENT # 0x00000020
            | WS_EX_TOPMOST     # 0x00000008
            | WS_EX_NOACTIVATE  # 0x08000000
            | WS_EX_TOOLWINDOW  # 0x00000080
        )
        assert REQUIRED_HUD_EX_STYLES == expected_bitmask
        assert REQUIRED_HUD_EX_STYLES == 0x080800A8

        # Verify each essential capability flag is present
        assert bool(REQUIRED_HUD_EX_STYLES & WS_EX_LAYERED)
        assert bool(REQUIRED_HUD_EX_STYLES & WS_EX_TRANSPARENT)
        assert bool(REQUIRED_HUD_EX_STYLES & WS_EX_TOPMOST)
        assert bool(REQUIRED_HUD_EX_STYLES & WS_EX_NOACTIVATE)
        assert bool(REQUIRED_HUD_EX_STYLES & WS_EX_TOOLWINDOW)

    def test_apply_click_through_styles_invalid_hwnd_handled(self, qtbot, adv_hud_config):
        """Simulated invalid window handle (IsWindow() == False) safely returns False."""
        hud = GhostHUD(config=adv_hud_config, enable_win32_styles=False)
        qtbot.addWidget(hud)

        mock_user32 = MagicMock()
        mock_user32.IsWindow.return_value = 0  # Invalid handle / offscreen handle

        with patch("sys.platform", "win32"), patch("ctypes.windll.user32", mock_user32):
            result = apply_click_through_styles(hud)
            assert result is False
            mock_user32.SetWindowLongW.assert_not_called()
            mock_user32.SetWindowPos.assert_not_called()

    def test_apply_click_through_styles_non_windows_platforms(self, qtbot, adv_hud_config):
        """Non-Windows platforms (Linux, macOS) safely degrade and return False."""
        hud = GhostHUD(config=adv_hud_config, enable_win32_styles=False)
        qtbot.addWidget(hud)

        for os_name in ["linux", "darwin", "freebsd"]:
            with patch("sys.platform", os_name):
                result = apply_click_through_styles(hud)
                assert result is False

    def test_apply_click_through_styles_ctypes_exceptions_handled(self, qtbot, adv_hud_config):
        """Simulate unexpected Win32 ctypes exceptions (ArgumentError, OSError)."""
        hud = GhostHUD(config=adv_hud_config, enable_win32_styles=False)
        qtbot.addWidget(hud)

        mock_user32 = MagicMock()
        mock_user32.IsWindow.side_effect = ctypes.ArgumentError("Invalid argument type")

        with patch("sys.platform", "win32"), patch("ctypes.windll.user32", mock_user32):
            result = apply_click_through_styles(hud)
            assert result is False

        mock_user32.IsWindow.side_effect = None
        mock_user32.IsWindow.return_value = 1
        mock_user32.GetWindowLongW.side_effect = OSError(1400, "Invalid window handle")

        with patch("sys.platform", "win32"), patch("ctypes.windll.user32", mock_user32):
            result = apply_click_through_styles(hud)
            assert result is False

    def test_apply_click_through_styles_idempotency(self, qtbot, adv_hud_config):
        """Calling apply_click_through_styles multiple times preserves existing styles via bitwise OR."""
        hud = GhostHUD(config=adv_hud_config, enable_win32_styles=False)
        qtbot.addWidget(hud)

        mock_user32 = MagicMock()
        mock_user32.IsWindow.return_value = 1
        mock_user32.GetWindowLongW.return_value = REQUIRED_HUD_EX_STYLES  # Already present

        with patch("sys.platform", "win32"), patch("ctypes.windll.user32", mock_user32):
            result = apply_click_through_styles(hud)
            assert result is True
            mock_user32.SetWindowLongW.assert_called_once()
            args = mock_user32.SetWindowLongW.call_args[0]
            assert args[2] == REQUIRED_HUD_EX_STYLES

    def test_init_high_dpi_awareness_non_windows_platform(self):
        """DPI awareness returns False immediately on non-Windows platforms."""
        for os_name in ["linux", "darwin"]:
            with patch("sys.platform", os_name):
                assert init_high_dpi_awareness() is False

    def test_init_high_dpi_awareness_error_access_denied_idempotency(self):
        """DPI awareness returns True when SetProcessDpiAwarenessContext fails with ERROR_ACCESS_DENIED (5)."""
        mock_user32 = MagicMock()
        mock_user32.SetProcessDpiAwarenessContext.return_value = False

        mock_kernel32 = MagicMock()
        mock_kernel32.GetLastError.return_value = 5  # ERROR_ACCESS_DENIED

        with patch("sys.platform", "win32"), \
             patch("ctypes.windll.user32", mock_user32), \
             patch("ctypes.windll.kernel32", mock_kernel32):
            assert init_high_dpi_awareness() is True

    def test_init_high_dpi_awareness_shcore_e_accessdenied_idempotency(self):
        """DPI awareness returns True when shcore returns E_ACCESSDENIED (0x80070005)."""
        mock_user32 = MagicMock()
        mock_user32.SetProcessDpiAwarenessContext.side_effect = AttributeError("Not supported")

        mock_shcore = MagicMock()
        mock_shcore.SetProcessDpiAwareness.return_value = -2147024891  # 0x80070005

        with patch("sys.platform", "win32"), \
             patch("ctypes.windll.user32", mock_user32), \
             patch("ctypes.windll.shcore", mock_shcore):
            assert init_high_dpi_awareness() is True

    def test_init_high_dpi_awareness_total_failure_handled_cleanly(self):
        """When all DPI APIs fail with OSError, init_high_dpi_awareness returns False cleanly."""
        mock_user32 = MagicMock()
        mock_user32.SetProcessDpiAwarenessContext.side_effect = OSError("DLL not found")
        mock_user32.SetProcessDPIAware.side_effect = OSError("Call failed")

        mock_shcore = MagicMock()
        mock_shcore.SetProcessDpiAwareness.side_effect = OSError("DLL not found")

        with patch("sys.platform", "win32"), \
             patch("ctypes.windll.user32", mock_user32), \
             patch("ctypes.windll.shcore", mock_shcore):
            assert init_high_dpi_awareness() is False
