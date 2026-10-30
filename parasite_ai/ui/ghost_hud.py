"""
parasite_ai/ui/ghost_hud.py - Ghost-Hand Screen Overlay HUD.

Transparent, click-through Win32 layered screen overlay rendering Set-of-Mark (SoM)
numbered bounding boxes, category color badges, and a 300ms pre-click targeting reticle
with kinematic curved Bézier trajectory path preview.
"""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
import logging
import math
import sys
from typing import Any, Dict, List, Optional, Tuple, Union

from PyQt6.QtCore import (
    QElapsedTimer,
    QPoint,
    QPointF,
    QRect,
    QRectF,
    QTimer,
    Qt,
    pyqtSignal,
    pyqtSlot,
)
from PyQt6.QtGui import (
    QColor,
    QCursor,
    QFont,
    QFontMetrics,
    QGuiApplication,
    QPainter,
    QPainterPath,
    QPen,
)
from PyQt6.QtWidgets import QWidget

from parasite_ai.config import GhostHUDConfig
from parasite_ai.ui.win32_styles import (
    GWL_EXSTYLE,
    HWND_TOPMOST,
    REQUIRED_HUD_EX_STYLES,
    SWP_FRAMECHANGED,
    SWP_NOACTIVATE,
    SWP_NOMOVE,
    SWP_NOSIZE,
    WS_EX_LAYERED,
    WS_EX_NOACTIVATE,
    WS_EX_TOOLWINDOW,
    WS_EX_TOPMOST,
    WS_EX_TRANSPARENT,
    apply_click_through_styles,
)

logger = logging.getLogger(__name__)

# Category Color Mapping
ROLE_COLOR_MAP: Dict[str, str] = {
    # Buttons & Clickables -> Neon Cyan
    "button": "#00E5FF",
    "buttoncontrol": "#00E5FF",
    "splitbutton": "#00E5FF",
    "menuitem": "#00E5FF",
    "menuitemcontrol": "#00E5FF",
    "radiobutton": "#00E5FF",
    "checkbox": "#00E5FF",
    # Text Inputs -> Hot Magenta
    "edit": "#FF007F",
    "editcontrol": "#FF007F",
    "combobox": "#FF007F",
    "comboboxcontrol": "#FF007F",
    "input": "#FF007F",
    "textbox": "#FF007F",
    "document": "#FF007F",
    "documentcontrol": "#FF007F",
    # OCR Fallback -> Gold Amber
    "ocr": "#F59E0B",
    "text": "#F59E0B",
    "textcontrol": "#F59E0B",
    "label": "#F59E0B",
    # Links & Tabs -> Electric Blue
    "link": "#3B82F6",
    "hyperlink": "#3B82F6",
    "hyperlinkcontrol": "#3B82F6",
    "tabitem": "#3B82F6",
    "tabitemcontrol": "#3B82F6",
}


@dataclass
class HUDTarget:
    """Internal normalized representation of a grounded UI element."""
    id: int
    role: str
    label: str
    x: int
    y: int
    width: int
    height: int
    center_x: int
    center_y: int
    color_hex: str


class GhostHUD(QWidget):
    """
    Transparent click-through Win32 layered screen overlay.
    Spans full virtual desktop and renders Set-of-Mark tags and 300ms pre-click reticle.
    """

    # Qt Signals for decoupled thread-safe communication
    sig_targets_updated = pyqtSignal(int)                         # count of targets
    sig_reticle_started = pyqtSignal(int, int, int)              # x, y, duration_ms
    sig_reticle_finished = pyqtSignal(int, int)                  # x, y
    sig_reticle_aborted = pyqtSignal()
    sig_hud_cleared = pyqtSignal()

    def __init__(
        self,
        config: Optional[GhostHUDConfig] = None,
        bridge: Optional[Any] = None,
        parent: Optional[QWidget] = None,
        enable_win32_styles: bool = True,
    ) -> None:
        super().__init__(parent)
        self.config = config or GhostHUDConfig()
        self.bridge = bridge
        self._enabled: bool = self.config.enabled
        self._enable_win32_styles: bool = enable_win32_styles

        # Target Set-of-Mark state
        self._targets: List[HUDTarget] = []

        # Reticle animation state
        self._reticle_active: bool = False
        self._reticle_target: QPoint = QPoint(0, 0)
        self._reticle_start: QPoint = QPoint(0, 0)
        self._reticle_id: Optional[int] = None
        self._reticle_label: Optional[str] = None
        self._reticle_duration_ms: int = self.config.reticle_duration_ms
        self._elapsed_timer = QElapsedTimer()

        # Animation timer
        self._anim_timer = QTimer(self)
        fps = max(15, min(144, self.config.fps_target))
        self._anim_timer.setInterval(max(5, int(1000 / fps)))
        self._anim_timer.timeout.connect(self._on_animation_tick)

        # Fonts & styling
        self._badge_font = QFont("Segoe UI", 8, QFont.Weight.Bold)
        self._banner_font = QFont("Segoe UI", 9, QFont.Weight.Bold)

        self._init_window()

        # Connect bridge if provided
        if self.bridge is not None:
            self._connect_bridge(self.bridge)

    def _init_window(self) -> None:
        """Sets frameless, transparent, tool, and topmost Qt flags."""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)

        self._update_geometry()

        # Listen for screen topology changes
        screen = QGuiApplication.primaryScreen()
        if screen:
            screen.virtualGeometryChanged.connect(self._on_virtual_geometry_changed)

    def _update_geometry(self) -> None:
        """Spans the entire virtual desktop."""
        screen = QGuiApplication.primaryScreen()
        if screen:
            vgeom = screen.virtualGeometry()
            self.setGeometry(vgeom)

    def _on_virtual_geometry_changed(self, rect: QRect) -> None:
        """Handles monitor resolution or topology changes."""
        self.setGeometry(rect)
        self.update()

    def showEvent(self, event: Any) -> None:
        """Applies Win32 click-through styles upon window display."""
        super().showEvent(event)
        if self._enable_win32_styles:
            self.apply_win32_styles()

    def apply_win32_styles(self) -> bool:
        """Applies hardware click-through, layered, and no-activate styles."""
        return apply_click_through_styles(self)

    # -----------------------------------------------------------------------
    # Public API / Slots
    # -----------------------------------------------------------------------
    @pyqtSlot(list)
    def set_targets(self, targets: List[Any]) -> None:
        """Populates grounded UI elements for Set-of-Mark visual rendering."""
        normalized: List[HUDTarget] = []
        for raw in targets:
            norm = self._normalize_target(raw)
            if norm:
                normalized.append(norm)
        self._targets = normalized
        self.sig_targets_updated.emit(len(self._targets))
        self.update()

    @pyqtSlot(int, int)
    @pyqtSlot(int, int, int)
    @pyqtSlot(int, int, int, object)
    @pyqtSlot(int, int, int, object, object)
    def show_reticle(
        self,
        x: int,
        y: int,
        duration_ms: Optional[int] = None,
        target_id: Optional[int] = None,
        label: Optional[str] = None,
    ) -> None:
        """Initiates animated targeting reticle, aiming banner, and trajectory preview."""
        self._reticle_target = QPoint(x, y)
        self._reticle_start = QCursor.pos()
        self._reticle_id = target_id
        self._reticle_label = label
        self._reticle_duration_ms = (
            duration_ms if duration_ms is not None else self.config.reticle_duration_ms
        )

        self._reticle_active = True
        self._elapsed_timer.restart()
        self._anim_timer.start()
        self.sig_reticle_started.emit(x, y, self._reticle_duration_ms)
        self.update()

    @pyqtSlot()
    def abort_reticle(self) -> None:
        """Immediately halts and clears targeting reticle on interrupt/panic."""
        if self._reticle_active:
            self._anim_timer.stop()
            self._reticle_active = False
            self.sig_reticle_aborted.emit()
            self.update()

    @pyqtSlot()
    def clear_reticle(self) -> None:
        """Alias for abort_reticle."""
        self.abort_reticle()

    @pyqtSlot()
    def clear_targets(self) -> None:
        """Clears all Set-of-Mark bounding boxes."""
        self._targets.clear()
        self.sig_targets_updated.emit(0)
        self.update()

    @pyqtSlot()
    def clear_all(self) -> None:
        """Clears both targets and active reticle."""
        self._targets.clear()
        self.abort_reticle()
        self.sig_hud_cleared.emit()
        self.update()

    def set_hud_enabled(self, enabled: bool) -> None:
        """Toggles HUD visibility."""
        self._enabled = enabled
        self.update()

    # -----------------------------------------------------------------------
    # Animation Tick
    # -----------------------------------------------------------------------
    def _on_animation_tick(self) -> None:
        if not self._reticle_active:
            self._anim_timer.stop()
            return

        elapsed = self._elapsed_timer.elapsed()
        if elapsed >= self._reticle_duration_ms:
            self._anim_timer.stop()
            self._reticle_active = False
            self.sig_reticle_finished.emit(self._reticle_target.x(), self._reticle_target.y())

        self.update()

    # -----------------------------------------------------------------------
    # Normalization & Coordinates
    # -----------------------------------------------------------------------
    def _normalize_target(self, raw: Any) -> Optional[HUDTarget]:
        if raw is None:
            return None
        try:
            if isinstance(raw, dict):
                tid = int(raw.get("id", 0))
                role = str(raw.get("role") or raw.get("control_type") or "Button")
                label = str(raw.get("label") or raw.get("name") or "")
                x = int(raw.get("x", 0))
                y = int(raw.get("y", 0))
                w = int(raw.get("width", 0))
                h = int(raw.get("height", 0))
                cx = int(raw.get("center_x", x + w // 2))
                cy = int(raw.get("center_y", y + h // 2))
            else:
                tid = int(getattr(raw, "id", 0))
                role = str(getattr(raw, "role", getattr(raw, "control_type", "Button")))
                label = str(getattr(raw, "label", getattr(raw, "name", "")))
                x = int(getattr(raw, "x", 0))
                y = int(getattr(raw, "y", 0))
                w = int(getattr(raw, "width", 0))
                h = int(getattr(raw, "height", 0))
                cx = int(getattr(raw, "center_x", x + w // 2))
                cy = int(getattr(raw, "center_y", y + h // 2))

            color_hex = ROLE_COLOR_MAP.get(role.lower(), self.config.som_box_color)
            return HUDTarget(
                id=tid,
                role=role,
                label=label,
                x=x,
                y=y,
                width=w,
                height=h,
                center_x=cx,
                center_y=cy,
                color_hex=color_hex,
            )
        except Exception:
            return None

    def _to_local(self, x: int, y: int) -> QPoint:
        geo = self.geometry()
        return QPoint(x - geo.x(), y - geo.y())

    # -----------------------------------------------------------------------
    # Painting
    # -----------------------------------------------------------------------
    def paintEvent(self, event: Any) -> None:
        if not self._enabled:
            return

        with QPainter(self) as painter:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

            # 1. Paint Set-of-Mark elements
            if self._targets:
                self._paint_som_elements(painter)

            # 2. Paint Reticle, Banner, and Trajectory
            if self._reticle_active:
                self._paint_reticle_and_path(painter)

    def _paint_som_elements(self, painter: QPainter) -> None:
        vgeom = self.geometry()
        box_alpha_int = max(0, min(255, int(255 * self.config.box_alpha)))
        stroke_w = self.config.stroke_width_px
        metrics = QFontMetrics(self._badge_font)

        for target in self._targets:
            local_pos = self._to_local(target.x, target.y)
            rect = QRectF(local_pos.x(), local_pos.y(), target.width, target.height)

            color = QColor(target.color_hex)
            fill_color = QColor(color.red(), color.green(), color.blue(), box_alpha_int)

            # Bounding box
            painter.setPen(QPen(color, stroke_w))
            painter.setBrush(fill_color)
            painter.drawRoundedRect(rect, 3.0, 3.0)

            # Pill Badge Text
            trunc_label = target.label[:14] + "…" if len(target.label) > 14 else target.label
            text = f"[#{target.id}: {trunc_label}]" if trunc_label else f"[#{target.id}]"

            tw = metrics.horizontalAdvance(text)
            th = metrics.height()
            pw = tw + 12
            ph = th + 4

            # Pill position: Above box, or inside box if at top screen edge
            bx = local_pos.x()
            by = local_pos.y() - ph - 2
            if by < 0:
                by = local_pos.y() + 2
            if bx + pw > vgeom.width():
                bx = max(0, vgeom.width() - pw - 2)

            pill_rect = QRectF(bx, by, pw, ph)

            # Draw Pill Card
            painter.setPen(QPen(color, 1.0))
            painter.setBrush(QColor(17, 24, 39, 230))  # Slate-900 90% opacity
            painter.drawRoundedRect(pill_rect, 4.0, 4.0)

            # Draw Pill Text
            painter.setPen(QColor(255, 255, 255))
            painter.setFont(self._badge_font)
            painter.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter, text)

    def _paint_reticle_and_path(self, painter: QPainter) -> None:
        elapsed = self._elapsed_timer.elapsed()
        duration = max(1, self._reticle_duration_ms)
        progress = max(0.0, min(1.0, elapsed / duration))
        remaining_ms = max(0, duration - elapsed)

        start_loc = self._to_local(self._reticle_start.x(), self._reticle_start.y())
        target_loc = self._to_local(self._reticle_target.x(), self._reticle_target.y())

        # 1. Dynamic Curved Bézier Trajectory Preview
        self._paint_bezier_path(painter, start_loc, target_loc, progress)

        # 2. Contracting Reticle Brackets & Center Crosshair
        self._paint_targeting_reticle(painter, target_loc, progress)

        # 3. Floating Aiming Banner
        self._paint_aiming_banner(painter, target_loc, remaining_ms)

    def _paint_bezier_path(
        self, painter: QPainter, p0: QPoint, p3: QPoint, progress: float
    ) -> None:
        dx = p3.x() - p0.x()
        dy = p3.y() - p0.y()
        dist = math.hypot(dx, dy)
        if dist < 15.0:
            return

        nx = -dy / dist
        ny = dx / dist
        arc_amp = dist * 0.12

        p1 = QPointF(p0.x() + 0.32 * dx + arc_amp * nx, p0.y() + 0.32 * dy + arc_amp * ny)
        p2 = QPointF(p0.x() + 0.68 * dx + 0.45 * arc_amp * nx, p0.y() + 0.68 * dy + 0.45 * arc_amp * ny)

        path = QPainterPath()
        path.moveTo(QPointF(p0.x(), p0.y()))
        path.cubicTo(p1, p2, QPointF(p3.x(), p3.y()))

        # Glowing dashed path
        pen = QPen(QColor(0, 229, 255, 175), 2.0, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        # Active pulse traveling orb along curve
        u = 1.0 - progress
        bx = (u**3)*p0.x() + 3*(u**2)*progress*p1.x() + 3*u*(progress**2)*p2.x() + (progress**3)*p3.x()
        by = (u**3)*p0.y() + 3*(u**2)*progress*p1.y() + 3*u*(progress**2)*p2.y() + (progress**3)*p3.y()

        # Orb halo + center dot
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 229, 255, 90))
        painter.drawEllipse(QPointF(bx, by), 6.0, 6.0)
        painter.setBrush(QColor(255, 255, 255, 230))
        painter.drawEllipse(QPointF(bx, by), 2.5, 2.5)

    def _paint_targeting_reticle(self, painter: QPainter, center: QPoint, progress: float) -> None:
        cx, cy = center.x(), center.y()
        reticle_color = QColor(self.config.reticle_color)

        # Dynamic contracting radius: from 32px down to 16px
        radius = 16.0 + 16.0 * ((1.0 - progress) ** 2)
        arm = 7.0

        # Pulsing outer ring
        pulse_alpha = int(70 * (1.0 - 0.5 * progress))
        painter.setPen(QPen(QColor(reticle_color.red(), reticle_color.green(), reticle_color.blue(), pulse_alpha), 1.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(cx, cy), radius + 5.0, radius + 5.0)

        # 4 Corner brackets: Top-Left, Top-Right, Bottom-Left, Bottom-Right
        bracket_pen = QPen(reticle_color, 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap)
        painter.setPen(bracket_pen)

        # ⌜ Top-Left
        painter.drawLine(int(cx - radius), int(cy - radius), int(cx - radius + arm), int(cy - radius))
        painter.drawLine(int(cx - radius), int(cy - radius), int(cx - radius), int(cy - radius + arm))

        # ⌝ Top-Right
        painter.drawLine(int(cx + radius), int(cy - radius), int(cx + radius - arm), int(cy - radius))
        painter.drawLine(int(cx + radius), int(cy - radius), int(cx + radius), int(cy - radius + arm))

        # ⌞ Bottom-Left
        painter.drawLine(int(cx - radius), int(cy + radius), int(cx - radius + arm), int(cy + radius))
        painter.drawLine(int(cx - radius), int(cy + radius), int(cx - radius), int(cy + radius - arm))

        # ⌟ Bottom-Right
        painter.drawLine(int(cx + radius), int(cy + radius), int(cx + radius - arm), int(cy + radius))
        painter.drawLine(int(cx + radius), int(cy + radius), int(cx + radius), int(cy + radius - arm))

        # Center Crosshair ticks
        ch_pen = QPen(QColor(255, 255, 255, 210), 1.2)
        painter.setPen(ch_pen)
        painter.drawLine(cx - 7, cy, cx - 2, cy)
        painter.drawLine(cx + 2, cy, cx + 7, cy)
        painter.drawLine(cx, cy - 7, cx, cy - 2)
        painter.drawLine(cx, cy + 2, cx, cy + 7)

        # Center dot
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(reticle_color)
        painter.drawEllipse(QPointF(cx, cy), 1.5, 1.5)

    def _paint_aiming_banner(self, painter: QPainter, center: QPoint, remaining_ms: int) -> None:
        cx, cy = center.x(), center.y()
        reticle_color = QColor(self.config.reticle_color)
        metrics = QFontMetrics(self._banner_font)

        if self._reticle_id is not None and self._reticle_label:
            lbl = self._reticle_label[:12] + "…" if len(self._reticle_label) > 12 else self._reticle_label
            text = f"Aiming: [#{self._reticle_id}] {lbl} ({remaining_ms}ms)"
        elif self._reticle_id is not None:
            text = f"Aiming: [#{self._reticle_id}] Click in {remaining_ms}ms"
        else:
            text = f"Aiming: Click in {remaining_ms}ms"

        tw = metrics.horizontalAdvance(text)
        th = metrics.height()
        bw = tw + 16
        bh = th + 6

        # Position banner above reticle brackets
        bx = cx - bw // 2
        by = cy - 42
        if by < 0:
            by = cy + 24  # Flip below if at top edge

        banner_rect = QRectF(bx, by, bw, bh)

        # Card container
        painter.setPen(QPen(reticle_color, 1.5))
        painter.setBrush(QColor(15, 23, 42, 235))  # Deep midnight slate
        painter.drawRoundedRect(banner_rect, 5.0, 5.0)

        # Text
        painter.setPen(QColor(248, 250, 252))
        painter.setFont(self._banner_font)
        painter.drawText(banner_rect, Qt.AlignmentFlag.AlignCenter, text)

    # -----------------------------------------------------------------------
    # Bridge Connection Helper
    # -----------------------------------------------------------------------
    def _connect_bridge(self, bridge: Any) -> None:
        """Wires Qt bridge signals to HUD slots."""
        try:
            bridge.sig_targets_updated.connect(self.set_targets, Qt.ConnectionType.QueuedConnection)
            bridge.sig_targets_cleared.connect(self.clear_targets, Qt.ConnectionType.QueuedConnection)
            bridge.sig_reticle_requested.connect(self.show_reticle, Qt.ConnectionType.QueuedConnection)
            bridge.sig_reticle_cleared.connect(self.clear_reticle, Qt.ConnectionType.QueuedConnection)
            bridge.sig_hud_toggled.connect(self.setVisible, Qt.ConnectionType.QueuedConnection)
        except Exception as e:
            logger.warning(f"Failed to wire bridge to GhostHUD: {e}")
