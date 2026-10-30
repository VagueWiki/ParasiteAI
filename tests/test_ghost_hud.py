"""
tests/test_ghost_hud.py - Tests for Ghost-Hand Screen Overlay HUD (parasite_ai/ui/ghost_hud.py).
Verifies Win32 extended styles, virtual desktop geometry, Set-of-Mark rendering,
color themes, 300ms reticle countdown, Bezier path calculation, and interrupt aborts.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch
import pytest
from PyQt6.QtCore import QPoint, QRect, Qt
from PyQt6.QtGui import QColor, QPixmap
from PyQt6.QtWidgets import QApplication

from parasite_ai.config import GhostHUDConfig
from parasite_ai.ui.bridge import UIBridge
from parasite_ai.ui.ghost_hud import (
    GWL_EXSTYLE,
    REQUIRED_HUD_EX_STYLES,
    ROLE_COLOR_MAP,
    WS_EX_LAYERED,
    WS_EX_NOACTIVATE,
    WS_EX_TOOLWINDOW,
    WS_EX_TOPMOST,
    WS_EX_TRANSPARENT,
    GhostHUD,
    HUDTarget,
)
from parasite_ai.ui.types import UIElement


@pytest.fixture
def hud_config():
    return GhostHUDConfig(
        enabled=True,
        fps_target=60,
        reticle_duration_ms=100,  # Validated duration for tests
        som_box_color="#00E5FF",
        som_glow_color="#00FFCC",
        box_alpha=0.25,
        stroke_width_px=1.5,
    )


class TestGhostHUD:
    def test_window_flags_and_attributes(self, qtbot, hud_config):
        hud = GhostHUD(config=hud_config, enable_win32_styles=False)
        qtbot.addWidget(hud)

        flags = hud.windowFlags()
        assert bool(flags & Qt.WindowType.FramelessWindowHint)
        assert bool(flags & Qt.WindowType.WindowStaysOnTopHint)
        assert bool(flags & Qt.WindowType.Tool)

        assert hud.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        assert hud.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        assert hud.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        assert hud.testAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)

    def test_virtual_desktop_geometry_span(self, qtbot, hud_config):
        hud = GhostHUD(config=hud_config, enable_win32_styles=False)
        qtbot.addWidget(hud)

        screen = QApplication.primaryScreen()
        if screen:
            expected_geo = screen.virtualGeometry()
            assert hud.geometry() == expected_geo

            # Topology change slot
            new_rect = QRect(0, 0, 1920, 1080)
            hud._on_virtual_geometry_changed(new_rect)
            assert hud.geometry() == new_rect

    def test_win32_extended_window_styles_mocked(self, qtbot, hud_config):
        hud = GhostHUD(config=hud_config, enable_win32_styles=False)
        qtbot.addWidget(hud)

        mock_user32 = MagicMock()
        mock_user32.IsWindow.return_value = 1
        mock_user32.GetWindowLongW.return_value = 0x00000000

        with patch("sys.platform", "win32"), patch("ctypes.windll.user32", mock_user32):
            applied = hud.apply_win32_styles()
            assert applied is True
            mock_user32.SetWindowLongW.assert_called_once()
            args = mock_user32.SetWindowLongW.call_args[0]
            new_style = args[2]
            assert bool(new_style & WS_EX_LAYERED)
            assert bool(new_style & WS_EX_TRANSPARENT)
            assert bool(new_style & WS_EX_TOPMOST)
            assert bool(new_style & WS_EX_NOACTIVATE)
            assert bool(new_style & WS_EX_TOOLWINDOW)

    def test_win32_extended_styles_invalid_window_handled(self, qtbot, hud_config):
        hud = GhostHUD(config=hud_config, enable_win32_styles=False)
        qtbot.addWidget(hud)

        mock_user32 = MagicMock()
        mock_user32.IsWindow.return_value = 0  # Invalid handle / offscreen handle

        with patch("sys.platform", "win32"), patch("ctypes.windll.user32", mock_user32):
            applied = hud.apply_win32_styles()
            assert applied is False
            mock_user32.SetWindowLongW.assert_not_called()

    def test_normalize_target_from_dict_and_object(self, qtbot, hud_config):
        hud = GhostHUD(config=hud_config, enable_win32_styles=False)
        qtbot.addWidget(hud)

        # 1. From dict
        dict_target = {
            "id": 1,
            "role": "Button",
            "label": "Submit",
            "x": 100,
            "y": 200,
            "width": 80,
            "height": 30,
        }
        norm1 = hud._normalize_target(dict_target)
        assert norm1 is not None
        assert norm1.id == 1
        assert norm1.role == "Button"
        assert norm1.color_hex == "#00E5FF"
        assert norm1.center_x == 140
        assert norm1.center_y == 215

        # 2. From UIElement
        elem = UIElement.from_bbox(id=2, bbox=(50, 60, 120, 40), label="Search", role="Edit")
        norm2 = hud._normalize_target(elem)
        assert norm2 is not None
        assert norm2.id == 2
        assert norm2.role == "Edit"
        assert norm2.color_hex == "#FF007F"
        assert norm2.center_x == 110
        assert norm2.center_y == 80

        # 3. Invalid target
        assert hud._normalize_target(None) is None

    def test_role_color_theme_mapping(self, qtbot, hud_config):
        hud = GhostHUD(config=hud_config, enable_win32_styles=False)
        qtbot.addWidget(hud)

        elements = [
            {"id": 1, "role": "Button", "label": "Click Me", "x": 10, "y": 10, "width": 50, "height": 20},
            {"id": 2, "role": "Edit", "label": "Username", "x": 10, "y": 40, "width": 50, "height": 20},
            {"id": 3, "role": "OCR", "label": "Heading", "x": 10, "y": 70, "width": 50, "height": 20},
            {"id": 4, "role": "Hyperlink", "label": "Docs", "x": 10, "y": 100, "width": 50, "height": 20},
            {"id": 5, "role": "UnknownRole", "label": "Other", "x": 10, "y": 130, "width": 50, "height": 20},
        ]
        hud.set_targets(elements)
        assert len(hud._targets) == 5
        assert hud._targets[0].color_hex == "#00E5FF"  # Cyan
        assert hud._targets[1].color_hex == "#FF007F"  # Magenta
        assert hud._targets[2].color_hex == "#F59E0B"  # Amber
        assert hud._targets[3].color_hex == "#3B82F6"  # Blue
        assert hud._targets[4].color_hex == hud_config.som_box_color

    def test_clear_targets_and_clear_all(self, qtbot, hud_config):
        hud = GhostHUD(config=hud_config, enable_win32_styles=False)
        qtbot.addWidget(hud)

        with qtbot.waitSignal(hud.sig_targets_updated) as blocker:
            hud.set_targets([{"id": 1, "role": "Button", "label": "OK", "x": 50, "y": 50, "width": 40, "height": 20}])
        assert blocker.args == [1]
        assert len(hud._targets) == 1

        with qtbot.waitSignal(hud.sig_targets_updated) as blocker:
            hud.clear_targets()
        assert blocker.args == [0]
        assert len(hud._targets) == 0

        # clear_all
        hud.set_targets([{"id": 2, "role": "Edit", "label": "Text", "x": 10, "y": 10, "width": 50, "height": 20}])
        hud.show_reticle(x=100, y=100, duration_ms=500)
        assert hud._reticle_active is True

        with qtbot.waitSignal(hud.sig_hud_cleared):
            hud.clear_all()
        assert len(hud._targets) == 0
        assert hud._reticle_active is False

    def test_offscreen_paint_execution(self, qtbot, hud_config):
        hud = GhostHUD(config=hud_config, enable_win32_styles=False)
        qtbot.addWidget(hud)
        hud.resize(800, 600)

        hud.set_targets([
            {"id": 1, "role": "Button", "label": "Submit Form Now", "x": 50, "y": 50, "width": 100, "height": 40},
            {"id": 2, "role": "Edit", "label": "Input Field", "x": 200, "y": 50, "width": 100, "height": 40},
        ])

        pixmap = QPixmap(800, 600)
        hud.render(pixmap)
        assert not pixmap.isNull()

    def test_screen_edge_pill_badge_clamping(self, qtbot, hud_config):
        hud = GhostHUD(config=hud_config, enable_win32_styles=False)
        qtbot.addWidget(hud)
        hud.setGeometry(0, 0, 1000, 800)

        # 1. Target at top-left edge (y=0, so y - ph - 2 < 0 -> clamped inside box)
        # 2. Target near right edge (x + w near right -> clamped within window width)
        hud.set_targets([
            {"id": 1, "role": "Button", "label": "Top", "x": 0, "y": 0, "width": 100, "height": 40},
            {"id": 2, "role": "Button", "label": "Very Long Label Near Right Edge", "x": 950, "y": 200, "width": 50, "height": 40},
        ])

        pixmap = QPixmap(1000, 800)
        hud.render(pixmap)
        assert not pixmap.isNull()

    def test_show_reticle_countdown_and_completion_signal(self, qtbot, hud_config):
        hud = GhostHUD(config=hud_config, enable_win32_styles=False)
        qtbot.addWidget(hud)

        with qtbot.waitSignal(hud.sig_reticle_finished, timeout=1000) as blocker:
            hud.show_reticle(x=350, y=250, duration_ms=40, target_id=14, label="New Tab")

        assert blocker.args == [350, 250]
        assert hud._reticle_active is False

    def test_abort_reticle_cancels_immediately(self, qtbot, hud_config):
        hud = GhostHUD(config=hud_config, enable_win32_styles=False)
        qtbot.addWidget(hud)

        with qtbot.waitSignal(hud.sig_reticle_aborted, timeout=500):
            hud.show_reticle(x=500, y=500, duration_ms=500)
            assert hud._reticle_active is True
            hud.abort_reticle()

        assert hud._reticle_active is False

    def test_bezier_path_and_reticle_paint(self, qtbot, hud_config):
        hud = GhostHUD(config=hud_config, enable_win32_styles=False)
        qtbot.addWidget(hud)
        hud.resize(1000, 800)

        hud.show_reticle(x=600, y=400, duration_ms=500, target_id=5, label="Search")
        pixmap = QPixmap(1000, 800)
        hud.render(pixmap)
        assert not pixmap.isNull()
        hud.abort_reticle()

    def test_hud_enabled_toggle(self, qtbot, hud_config):
        hud = GhostHUD(config=hud_config, enable_win32_styles=False)
        qtbot.addWidget(hud)

        hud.set_hud_enabled(False)
        assert hud._enabled is False

        # Rendering with enabled=False executes paintEvent early return
        pixmap = QPixmap(200, 200)
        hud.render(pixmap)
        assert not pixmap.isNull()

    def test_bridge_integration_wiring(self, qtbot, hud_config):
        bridge = UIBridge()
        hud = GhostHUD(config=hud_config, bridge=bridge, enable_win32_styles=False)
        qtbot.addWidget(hud)

        # Bridge sets targets
        elem = UIElement.from_bbox(id=1, bbox=(20, 20, 80, 30), label="Bridge Target")
        bridge.set_hud_targets([elem])
        qtbot.waitUntil(lambda: len(hud._targets) == 1, timeout=1000)
        assert hud._targets[0].label == "Bridge Target"

        # Bridge requests reticle
        bridge.show_reticle(200, 150, 50, 1, "Bridge Target")
        qtbot.waitUntil(lambda: hud._reticle_active is True, timeout=1000)

        # Bridge clears reticle
        bridge.clear_reticle()
        qtbot.waitUntil(lambda: hud._reticle_active is False, timeout=1000)

        # Bridge clears targets
        bridge.clear_hud_targets()
        qtbot.waitUntil(lambda: len(hud._targets) == 0, timeout=1000)
