"""
parasite_ai/ui/companion_dock.py - Desktop Companion Dock Widget (PyQt6).

Provides the 100% visible, always-on-top companion GUI displaying character
state, mood, speech monologue, internal thoughts, action telemetry, perception
preview with privacy blackout masking, and interactive user controls.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from PyQt6.QtCore import (
    QObject,
    QPoint,
    QRect,
    QSize,
    Qt,
    QTimer,
    pyqtSignal,
    pyqtSlot,
)
from PyQt6.QtGui import (
    QColor,
    QFont,
    QGuiApplication,
    QImage,
    QMouseEvent,
    QPainter,
    QPixmap,
    QScreen,
)
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from parasite_ai.config import CompanionDockConfig
from parasite_ai.ui.types import STATE_COLORS, UIMood, UIState

import numpy as np

logger = logging.getLogger(__name__)


def ndarray_to_qimage(frame: Optional[Any]) -> QImage:
    """Safely converts a numpy image array (H, W, 3/4) or grayscale (H, W) to a detached PyQt6 QImage."""
    if frame is None or not hasattr(frame, "shape") or len(frame.shape) < 2:
        return QImage()
    h, w = frame.shape[:2]
    if frame.ndim == 2:
        contig = np.ascontiguousarray(frame)
        return QImage(contig.data, w, h, w, QImage.Format.Format_Grayscale8).copy()
    if frame.ndim == 3:
        ch = frame.shape[2]
        contig = np.ascontiguousarray(frame)
        if ch == 3:
            return QImage(contig.data, w, h, w * 3, QImage.Format.Format_RGB888).copy()
        if ch == 4:
            return QImage(contig.data, w, h, w * 4, QImage.Format.Format_RGBA8888).copy()
    return QImage()


# State Configuration Metadata
STATE_CONFIG: Dict[str, Dict[str, str]] = {
    "WATCHING": {
        "color": "#10B981",
        "bg": "rgba(16, 185, 129, 0.15)",
        "label": "● WATCHING",
    },
    "THINKING": {
        "color": "#F59E0B",
        "bg": "rgba(245, 158, 11, 0.15)",
        "label": "● THINKING",
    },
    "DRIVING": {
        "color": "#EF4444",
        "bg": "rgba(239, 68, 68, 0.15)",
        "label": "● DRIVING",
    },
    "USER_OVERRIDE": {
        "color": "#06B6D4",
        "bg": "rgba(6, 182, 212, 0.15)",
        "label": "● OVERRIDE",
    },
    "OFFLOADING": {
        "color": "#8B5CF6",
        "bg": "rgba(139, 92, 246, 0.15)",
        "label": "● OFFLOADING",
    },
    "PROTECTED": {
        "color": "#94A3B8",
        "bg": "rgba(148, 163, 184, 0.15)",
        "label": "🔒 PROTECTED",
    },
}


class CompanionDock(QWidget):
    """
    Always-on-top desktop companion dock widget for ParasiteAI.
    Renders status telemetry, character thoughts, dialogue bubble, perception preview,
    and user interactive controls (goal input, pause hands, panic abort).
    """

    # Signals for UI -> Core and state changes
    sig_status_changed = pyqtSignal(str, str)         # (state: str, mood: str)
    sig_thought_updated = pyqtSignal(str)             # (thought_text: str)
    sig_speech_updated = pyqtSignal(str)              # (speech_text: str)
    sig_telemetry_updated = pyqtSignal(str)           # (telemetry_text: str)
    sig_perception_updated = pyqtSignal(object)        # (pixmap_or_image)

    sig_goal_submitted = pyqtSignal(str)              # (goal_text: str)
    sig_pause_toggled = pyqtSignal(bool)              # (is_paused: bool)
    sig_panic_triggered = pyqtSignal()                # ()
    sig_hud_toggled = pyqtSignal(bool)                # (show_hud: bool)
    sig_brain_mode_changed = pyqtSignal(str)          # (mode: str)

    def __init__(
        self,
        config: Optional[CompanionDockConfig] = None,
        bridge: Optional[Any] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.config = config or CompanionDockConfig()
        self.bridge = bridge

        # Internal operational states
        self._current_state: str = "WATCHING"
        self._current_mood: str = "Curious"
        self._is_paused: bool = False
        self._is_masked: bool = False
        self._is_dragging: bool = False
        self._drag_start_pos: QPoint = QPoint()

        # Typewriter animation state
        self._speech_stream_queue: List[str] = []
        self._speech_stream_timer = QTimer(self)
        self._speech_stream_timer.setInterval(20)
        self._speech_stream_timer.timeout.connect(self._on_typewriter_tick)

        # Track most recent external foreground HWND so submitting a goal restores focus outside the dock
        self._last_external_hwnd: int = 0
        self._focus_tracker_timer = QTimer(self)
        self._focus_tracker_timer.setInterval(250)
        self._focus_tracker_timer.timeout.connect(self._poll_external_foreground_window)
        self._focus_tracker_timer.start()

        # Build window and UI hierarchy
        self._init_window()
        self._init_ui()

        # Screen anchoring
        self.anchor_to_screen()

        # Connect bridge if provided
        if self.bridge is not None:
            self._connect_bridge(self.bridge)

    def _init_window(self) -> None:
        """Sets window flags, attributes, sizing and opacity."""
        flags = Qt.WindowType.Window
        if self.config.always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        if self.config.frameless:
            flags |= Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool

        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowOpacity(self.config.opacity)

        self.resize(self.config.width, self.config.height)
        self.setMinimumSize(300, 480)

    def _init_ui(self) -> None:
        """Constructs layout hierarchy, styled frames, cards and controls."""
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(0)

        # Outer Main Container Card
        self.main_card = QFrame(self)
        self.main_card.setObjectName("MainCard")
        self._update_card_style(STATE_CONFIG["WATCHING"]["color"])

        card_layout = QVBoxLayout(self.main_card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(8)

        # -------------------------------------------------------------
        # 1. Header Drag Grip & State / Mood Bar
        # -------------------------------------------------------------
        self.header_frame = QFrame(self.main_card)
        self.header_frame.setObjectName("HeaderFrame")
        self.header_frame.setFixedHeight(36)
        header_layout = QHBoxLayout(self.header_frame)
        header_layout.setContentsMargins(2, 2, 2, 2)
        header_layout.setSpacing(6)

        self.avatar_icon = QLabel("⚡", self.header_frame)
        self.avatar_icon.setFixedSize(24, 24)
        self.avatar_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar_icon.setStyleSheet(
            "background-color: #1e293b; color: #00e5ff; border-radius: 6px; font-weight: bold; font-size: 11pt;"
        )

        self.title_label = QLabel("PARASITE", self.header_frame)
        self.title_label.setStyleSheet("color: #f8fafc; font-weight: bold; font-size: 10pt;")

        self.state_pill = QLabel(STATE_CONFIG["WATCHING"]["label"], self.header_frame)
        self.state_pill.setObjectName("StatePill")
        self._update_state_pill_style("WATCHING")

        self.mood_pill = QLabel(f"[{self._current_mood}]", self.header_frame)
        self.mood_pill.setObjectName("MoodPill")
        self.mood_pill.setStyleSheet(
            "color: #94a3b8; background-color: #1e293b; border-radius: 8px; padding: 2px 6px; font-size: 8.5pt;"
        )

        header_layout.addWidget(self.avatar_icon)
        header_layout.addWidget(self.title_label)
        header_layout.addWidget(self.state_pill)
        header_layout.addWidget(self.mood_pill)
        header_layout.addStretch()

        card_layout.addWidget(self.header_frame)

        # -------------------------------------------------------------
        # 2. Character Speech Bubble (Dialogue Card)
        # -------------------------------------------------------------
        self.speech_card = QFrame(self.main_card)
        self.speech_card.setObjectName("SpeechCard")
        self.speech_card.setStyleSheet(
            "#SpeechCard { background-color: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 8px; }"
        )
        speech_layout = QVBoxLayout(self.speech_card)
        speech_layout.setContentsMargins(8, 8, 8, 8)
        speech_layout.setSpacing(4)

        self.sender_label = QLabel("Parasite", self.speech_card)
        self.sender_label.setStyleSheet("color: #00e5ff; font-weight: bold; font-size: 9pt;")
        self.dialogue_label = QLabel("Online and watching desktop controls.", self.speech_card)
        self.dialogue_label.setWordWrap(True)
        self.dialogue_label.setStyleSheet("color: #f1f5f9; font-size: 9.5pt;")

        speech_layout.addWidget(self.sender_label)
        speech_layout.addWidget(self.dialogue_label)
        card_layout.addWidget(self.speech_card)

        # -------------------------------------------------------------
        # 3. Internal Thought Stream Card
        # -------------------------------------------------------------
        self.thought_card = QFrame(self.main_card)
        self.thought_card.setObjectName("ThoughtCard")
        self.thought_card.setStyleSheet(
            "#ThoughtCard { background-color: #090d16; border: 1px solid #1e293b; border-radius: 6px; padding: 6px; }"
        )
        thought_layout = QVBoxLayout(self.thought_card)
        thought_layout.setContentsMargins(6, 6, 6, 6)
        thought_layout.setSpacing(4)

        self.thought_header = QLabel("💭 Internal Monologue", self.thought_card)
        self.thought_header.setStyleSheet("color: #64748b; font-size: 8pt; font-weight: bold;")
        self.thought_text = QPlainTextEdit(self.thought_card)
        self.thought_text.setObjectName("ThoughtText")
        self.thought_text.setReadOnly(True)
        self.thought_text.setMaximumHeight(70)
        self.thought_text.setStyleSheet(
            "color: #94a3b8; font-style: italic; font-family: 'Consolas', 'Segoe UI', monospace; "
            "font-size: 8.5pt; background: transparent; border: none;"
        )
        self.thought_text.setPlainText("Monitoring foreground UI tree...")

        thought_layout.addWidget(self.thought_header)
        thought_layout.addWidget(self.thought_text)

        if not self.config.show_thought_stream:
            self.thought_card.hide()
        card_layout.addWidget(self.thought_card)

        # -------------------------------------------------------------
        # 4. Action Telemetry Card
        # -------------------------------------------------------------
        self.telemetry_card = QFrame(self.main_card)
        self.telemetry_card.setObjectName("TelemetryCard")
        self.telemetry_card.setStyleSheet(
            "#TelemetryCard { background-color: #111827; border: 1px solid #1f2937; border-radius: 6px; padding: 6px; }"
        )
        telemetry_layout = QVBoxLayout(self.telemetry_card)
        telemetry_layout.setContentsMargins(6, 6, 6, 6)
        telemetry_layout.setSpacing(4)

        self.telemetry_label = QLabel("Target: None | Idle", self.telemetry_card)
        self.telemetry_label.setStyleSheet("color: #cbd5e1; font-size: 8.5pt;")

        progress_row = QHBoxLayout()
        self.step_label = QLabel("Step: Idle", self.telemetry_card)
        self.step_label.setStyleSheet("color: #64748b; font-size: 8pt;")
        self.step_progress = QProgressBar(self.telemetry_card)
        self.step_progress.setFixedHeight(4)
        self.step_progress.setTextVisible(False)
        self.step_progress.setRange(0, 100)
        self.step_progress.setValue(0)
        self.step_progress.setStyleSheet(
            "QProgressBar { background-color: #1e293b; border-radius: 2px; border: none; } "
            "QProgressBar::chunk { background-color: #10b981; border-radius: 2px; }"
        )
        progress_row.addWidget(self.step_label)
        progress_row.addWidget(self.step_progress)

        telemetry_layout.addWidget(self.telemetry_label)
        telemetry_layout.addLayout(progress_row)
        card_layout.addWidget(self.telemetry_card)

        # -------------------------------------------------------------
        # 5. Live Perception Preview Card
        # -------------------------------------------------------------
        self.perception_card = QFrame(self.main_card)
        self.perception_card.setObjectName("PerceptionCard")
        self.perception_card.setStyleSheet(
            "#PerceptionCard { background-color: #0b1120; border: 1px solid #1e293b; border-radius: 6px; padding: 4px; }"
        )
        perception_layout = QVBoxLayout(self.perception_card)
        perception_layout.setContentsMargins(4, 4, 4, 4)
        perception_layout.setSpacing(2)

        self.thumbnail_view = QLabel(self.perception_card)
        self.thumbnail_view.setFixedHeight(85)
        self.thumbnail_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail_view.setStyleSheet("background-color: #020617; border-radius: 4px;")
        self.thumbnail_view.setText("Live Perception Feed")

        self.grounding_badge = QLabel("Grounding: Active", self.perception_card)
        self.grounding_badge.setStyleSheet("color: #64748b; font-size: 7.5pt; padding-left: 2px;")

        perception_layout.addWidget(self.thumbnail_view)
        perception_layout.addWidget(self.grounding_badge)

        if not self.config.show_perception_preview:
            self.perception_card.hide()
        card_layout.addWidget(self.perception_card)

        # -------------------------------------------------------------
        # 6. Interactive Controls Section
        # -------------------------------------------------------------
        controls_layout = QVBoxLayout()
        controls_layout.setSpacing(6)

        # Goal Input Row
        goal_row = QHBoxLayout()
        goal_row.setSpacing(4)
        self.goal_input = QLineEdit(self.main_card)
        self.goal_input.setPlaceholderText("Give Parasite a task...")
        self.goal_input.setClearButtonEnabled(True)
        self.goal_input.setStyleSheet(
            "QLineEdit { background-color: #1e293b; color: #f8fafc; border: 1px solid #334155; "
            "border-radius: 6px; padding: 6px; font-size: 9pt; } "
            "QLineEdit:focus { border: 1px solid #00e5ff; }"
        )
        self.goal_input.returnPressed.connect(self._on_submit_goal)

        self.btn_send = QPushButton("Send", self.main_card)
        self.btn_send.setFixedWidth(54)
        self.btn_send.setStyleSheet(
            "QPushButton { background-color: #0284c7; color: white; border: none; "
            "border-radius: 6px; padding: 6px; font-weight: bold; } "
            "QPushButton:hover { background-color: #0369a1; } "
            "QPushButton:pressed { background-color: #075985; }"
        )
        self.btn_send.clicked.connect(self._on_submit_goal)

        goal_row.addWidget(self.goal_input)
        goal_row.addWidget(self.btn_send)
        controls_layout.addLayout(goal_row)

        # Primary Action Row (Pause Hands / Panic Abort)
        action_row = QHBoxLayout()
        action_row.setSpacing(6)

        self.btn_pause = QPushButton("⏸ Pause Hands", self.main_card)
        self.btn_pause.setStyleSheet(
            "QPushButton { background-color: #334155; color: #f8fafc; border: 1px solid #475569; "
            "border-radius: 6px; padding: 6px; font-weight: bold; font-size: 8.5pt; } "
            "QPushButton:hover { background-color: #475569; }"
        )
        self.btn_pause.clicked.connect(self._on_toggle_pause)

        self.btn_panic = QPushButton("⚠ PANIC ABORT", self.main_card)
        self.btn_panic.setStyleSheet(
            "QPushButton { background-color: #dc2626; color: white; border: none; "
            "border-radius: 6px; padding: 6px; font-weight: bold; font-size: 8.5pt; } "
            "QPushButton:hover { background-color: #b91c1c; } "
            "QPushButton:pressed { background-color: #991b1b; }"
        )
        self.btn_panic.clicked.connect(self._on_panic_clicked)

        action_row.addWidget(self.btn_pause)
        action_row.addWidget(self.btn_panic)
        controls_layout.addLayout(action_row)

        # Secondary Utility Row (HUD Checkbox & Brain Mode)
        utility_row = QHBoxLayout()
        utility_row.setSpacing(6)

        self.chk_hud = QCheckBox("Show HUD Tags", self.main_card)
        self.chk_hud.setChecked(True)
        self.chk_hud.setStyleSheet("QCheckBox { color: #94a3b8; font-size: 8pt; }")
        self.chk_hud.toggled.connect(self._on_toggle_hud)

        self.combo_brain_mode = QComboBox(self.main_card)
        self.combo_brain_mode.addItem("Browser Offload", "browser_offload")
        self.combo_brain_mode.addItem("Local GGUF", "local_llm")
        self.combo_brain_mode.addItem("Mock / Test", "mock")
        self.combo_brain_mode.setStyleSheet(
            "QComboBox { background-color: #1e293b; color: #cbd5e1; border: 1px solid #334155; "
            "border-radius: 4px; padding: 2px 6px; font-size: 8pt; }"
        )
        self.combo_brain_mode.currentIndexChanged.connect(self._on_brain_mode_changed)

        utility_row.addWidget(self.chk_hud)
        utility_row.addStretch()
        utility_row.addWidget(self.combo_brain_mode)
        controls_layout.addLayout(utility_row)

        card_layout.addLayout(controls_layout)
        root_layout.addWidget(self.main_card)

    def _update_card_style(self, accent_color: str) -> None:
        """Sets glowing border color on the main card."""
        self.main_card.setStyleSheet(
            f"#MainCard {{ "
            f"background-color: #0f172a; "
            f"border: 1px solid {accent_color}; "
            f"border-radius: 12px; "
            f"}}"
        )

    def _update_state_pill_style(self, state: str) -> None:
        """Updates styling and label for the state pill."""
        cfg = STATE_CONFIG.get(state, STATE_CONFIG["WATCHING"])
        self.state_pill.setText(cfg["label"])
        self.state_pill.setStyleSheet(
            f"color: {cfg['color']}; "
            f"background-color: {cfg['bg']}; "
            f"border: 1px solid {cfg['color']}; "
            f"border-radius: 10px; "
            f"padding: 2px 8px; "
            f"font-weight: bold; "
            f"font-size: 8.5pt;"
        )

    # -----------------------------------------------------------------------
    # Screen Anchoring
    # -----------------------------------------------------------------------
    def anchor_to_screen(self, screen: Optional[QScreen] = None) -> None:
        """Anchors window to screen corner respecting Windows taskbar geometry."""
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        if screen is None:
            self.move(100, 100)
            return

        screen_rect = screen.availableGeometry()
        dock_w = self.width()
        dock_h = self.height()
        mx = self.config.margin_x
        my = self.config.margin_y

        anchor = self.config.anchor
        if anchor == "bottom_right":
            x = screen_rect.x() + screen_rect.width() - dock_w - mx
            y = screen_rect.y() + screen_rect.height() - dock_h - my
        elif anchor == "bottom_left":
            x = screen_rect.x() + mx
            y = screen_rect.y() + screen_rect.height() - dock_h - my
        elif anchor == "top_right":
            x = screen_rect.x() + screen_rect.width() - dock_w - mx
            y = screen_rect.y() + my
        elif anchor == "top_left":
            x = screen_rect.x() + mx
            y = screen_rect.y() + my
        else:
            return

        self.move(x, y)

    # -----------------------------------------------------------------------
    # Click-and-Drag Repositioning
    # -----------------------------------------------------------------------
    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handles click-to-drag initiation on the header area."""
        if event.button() == Qt.MouseButton.LeftButton:
            child = self.childAt(event.pos())
            # Don't initiate drag if clicking interactive child widgets
            if child is None or not isinstance(child, (QPushButton, QComboBox, QCheckBox, QLineEdit)):
                if self.header_frame.geometry().contains(event.pos()) or event.pos().y() <= 48:
                    self._is_dragging = True
                    self._drag_start_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                    event.accept()
                    return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Drags the window keeping it within virtual desktop bounds."""
        if self._is_dragging and (event.buttons() & Qt.MouseButton.LeftButton):
            target_pos = event.globalPosition().toPoint() - self._drag_start_pos
            self.move(self._clamp_to_virtual_desktop(target_pos))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Concludes window drag."""
        self._is_dragging = False
        super().mouseReleaseEvent(event)

    def _clamp_to_virtual_desktop(self, pos: QPoint) -> QPoint:
        """Prevents window from being dragged completely off screen."""
        screen = QGuiApplication.primaryScreen()
        if not screen:
            return pos

        vgeom = screen.virtualGeometry()
        min_x = vgeom.x() - self.width() + 60
        max_x = vgeom.right() - 60
        min_y = vgeom.y()
        max_y = vgeom.bottom() - 40

        clamped_x = max(min_x, min(pos.x(), max_x))
        clamped_y = max(min_y, min(pos.y(), max_y))
        return QPoint(clamped_x, clamped_y)

    # -----------------------------------------------------------------------
    # Public Slots & Update APIs
    # -----------------------------------------------------------------------
    @pyqtSlot(str)
    @pyqtSlot(str, str)
    def update_state(self, state: str, mood: str = "Curious") -> None:
        """
        Updates the companion operational state and character mood.
        Switches accent glowing borders, pill badges, and triggers privacy masking.
        """
        state_key = state.upper()
        if state_key not in STATE_CONFIG:
            state_key = "WATCHING"

        self._current_state = state_key
        self._current_mood = mood

        # Update pill badge and glowing card border
        accent = STATE_CONFIG[state_key]["color"]
        self._update_card_style(accent)
        self._update_state_pill_style(state_key)
        self.mood_pill.setText(f"[{mood}]")

        # If protected state, automatically engage vision masking
        if state_key == "PROTECTED":
            self.set_perception_masked(True)
        elif self._is_masked:
            self.set_perception_masked(False)

        self.sig_status_changed.emit(self._current_state, self._current_mood)

    def update_status(self, state: str, mood: str = "Curious") -> None:
        """Convenience alias for update_state."""
        self.update_state(state, mood)

    @pyqtSlot(str)
    def update_speech(self, text: str, stream: bool = False) -> None:
        """Updates character speech bubble, with optional typewriter streaming."""
        if not stream:
            self._speech_stream_timer.stop()
            self._speech_stream_queue.clear()
            self.dialogue_label.setText(text)
            self.sig_speech_updated.emit(text)
        else:
            self._speech_stream_timer.stop()
            self._speech_stream_queue = list(text)
            self.dialogue_label.setText("")
            self._speech_stream_timer.start()

    def _on_typewriter_tick(self) -> None:
        """Appends next token character during streaming."""
        if not self._speech_stream_queue:
            self._speech_stream_timer.stop()
            self.sig_speech_updated.emit(self.dialogue_label.text())
            return
        next_char = self._speech_stream_queue.pop(0)
        self.dialogue_label.setText(self.dialogue_label.text() + next_char)

    @pyqtSlot(str)
    def update_thought(self, text: str) -> None:
        """Appends to the internal monologue and scrolls into view."""
        self.thought_text.appendPlainText(text)
        self.thought_text.ensureCursorVisible()
        self.sig_thought_updated.emit(text)

    @pyqtSlot(str)
    @pyqtSlot(str, int, int)
    def update_telemetry(self, text: str, current_step: int = 0, total_steps: int = 0) -> None:
        """Updates action telemetry and step progress bar."""
        self.telemetry_label.setText(text)
        if total_steps > 0:
            self.step_label.setText(f"Step: {current_step}/{total_steps}")
            pct = round((current_step * 100) / total_steps)
            self.step_progress.setValue(min(100, max(0, pct)))
        else:
            self.step_label.setText("Step: Idle")
            self.step_progress.setValue(0)
        self.sig_telemetry_updated.emit(text)

    @pyqtSlot(object)
    @pyqtSlot(object, list)
    def update_perception_preview(self, frame_data: Any, elements: Optional[List[Any]] = None) -> None:
        """
        Updates the downscaled desktop perception thumbnail.
        If privacy masked, renders blackout shield instead.
        """
        if self._is_masked:
            self._render_privacy_blackout()
            return

        pixmap: Optional[QPixmap] = None
        if isinstance(frame_data, QPixmap):
            pixmap = frame_data
        elif isinstance(frame_data, QImage):
            pixmap = QPixmap.fromImage(frame_data)
        elif hasattr(frame_data, "shape") and len(frame_data.shape) >= 2:
            qimg = ndarray_to_qimage(frame_data)
            if not qimg.isNull():
                pixmap = QPixmap.fromImage(qimg)

        if pixmap and not pixmap.isNull():
            scaled = pixmap.scaled(
                self.thumbnail_view.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.thumbnail_view.setPixmap(scaled)
        else:
            self.thumbnail_view.setText("No Frame Available")

        if elements is not None:
            self.grounding_badge.setText(f"Grounding: {len(elements)} Targets Active")

        self.sig_perception_updated.emit(frame_data)

    @pyqtSlot(bool)
    def set_perception_masked(self, is_masked: bool) -> None:
        """Toggles privacy blackout mask over the perception preview."""
        self._is_masked = is_masked
        if is_masked:
            self._render_privacy_blackout()
        else:
            self.thumbnail_view.setText("Live Perception Feed")

    def _render_privacy_blackout(self) -> None:
        """Renders privacy blackout mask in the thumbnail viewport."""
        w = max(100, self.thumbnail_view.width())
        h = max(50, self.thumbnail_view.height())
        blackout = QPixmap(w, h)
        blackout.fill(QColor("#000000"))

        with QPainter(blackout) as painter:
            painter.setPen(QColor("#ef4444"))
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.drawText(
                QRect(0, 0, w, h),
                Qt.AlignmentFlag.AlignCenter,
                "🔒 SENSITIVE WINDOW ACTIVE\nVISION MASKED",
            )
        self.thumbnail_view.setPixmap(blackout)
        self.grounding_badge.setText("Grounding: [PAUSED — SENSITIVE]")

    @pyqtSlot(bool)
    def set_hands_paused(self, is_paused: bool) -> None:
        """Updates Pause Hands button label and state."""
        self._is_paused = is_paused
        if is_paused:
            self.btn_pause.setText("▶ Resume Hands")
            self.btn_pause.setStyleSheet(
                "QPushButton { background-color: #059669; color: white; border: none; "
                "border-radius: 6px; padding: 6px; font-weight: bold; font-size: 8.5pt; } "
                "QPushButton:hover { background-color: #047857; }"
            )
        else:
            self.btn_pause.setText("⏸ Pause Hands")
            self.btn_pause.setStyleSheet(
                "QPushButton { background-color: #334155; color: #f8fafc; border: 1px solid #475569; "
                "border-radius: 6px; padding: 6px; font-weight: bold; font-size: 8.5pt; } "
                "QPushButton:hover { background-color: #475569; }"
            )

    # -----------------------------------------------------------------------
    # Interactive Button / Event Triggers
    # -----------------------------------------------------------------------
    def _poll_external_foreground_window(self) -> None:
        """Tracks the last active non-Parasite window HWND so goal submission can relinquish focus."""
        try:
            import ctypes
            user32 = ctypes.windll.user32
            fg = user32.GetForegroundWindow()
            if not fg:
                return
            own_hwnd = int(self.winId()) if self.winId() else 0
            if fg == own_hwnd:
                return
            buf = ctypes.create_unicode_buffer(128)
            user32.GetClassNameW(fg, buf, 128)
            if buf.value in ("CompanionDock", "GhostHUD"):
                return
            self._last_external_hwnd = int(fg)
        except Exception:
            pass

    def _restore_external_focus(self) -> None:
        """Relinquishes keyboard focus from CompanionDock back to the last active desktop window."""
        try:
            self.goal_input.clearFocus()
            self.clearFocus()
            import ctypes
            user32 = ctypes.windll.user32
            target_hwnd = self._last_external_hwnd
            if not target_hwnd or not user32.IsWindow(target_hwnd) or not user32.IsWindowVisible(target_hwnd):
                target_hwnd = user32.GetShellWindow()
            if target_hwnd:
                user32.SetForegroundWindow(target_hwnd)
        except Exception:
            pass

    def _on_submit_goal(self) -> None:
        """Submits goal text from QLineEdit and relinquishes keyboard focus back to desktop."""
        text = self.goal_input.text().strip()
        if text:
            self.goal_input.clear()
            self._restore_external_focus()
            self.sig_goal_submitted.emit(text)

    def _on_toggle_pause(self) -> None:
        """Toggles hands pause status and emits signal."""
        new_state = not self._is_paused
        self.set_hands_paused(new_state)
        self.sig_pause_toggled.emit(new_state)

    def _on_panic_clicked(self) -> None:
        """Emits emergency panic trigger."""
        logger.warning("Emergency PANIC button clicked on CompanionDock.")
        self.sig_panic_triggered.emit()

    def _on_toggle_hud(self, checked: bool) -> None:
        """Emits HUD overlay visibility toggle."""
        self.sig_hud_toggled.emit(checked)

    def _on_brain_mode_changed(self, index: int) -> None:
        """Emits brain mode selection."""
        mode_data = self.combo_brain_mode.itemData(index) or self.combo_brain_mode.currentText()
        self.sig_brain_mode_changed.emit(str(mode_data))

    # -----------------------------------------------------------------------
    # Bridge Connection Helper
    # -----------------------------------------------------------------------
    def _connect_bridge(self, bridge: Any) -> None:
        """Wires Qt bridge signals to dock slots and dock signals to bridge."""
        try:
            bridge.sig_state_changed.connect(self.update_state, Qt.ConnectionType.QueuedConnection)
            bridge.sig_thought_updated.connect(self.update_thought, Qt.ConnectionType.QueuedConnection)
            bridge.sig_speech_updated.connect(self.update_speech, Qt.ConnectionType.QueuedConnection)
            try:
                bridge.sig_telemetry_updated[str].connect(self.update_telemetry, Qt.ConnectionType.QueuedConnection)
                bridge.sig_telemetry_updated[str, int, int].connect(self.update_telemetry, Qt.ConnectionType.QueuedConnection)
            except (KeyError, TypeError):
                bridge.sig_telemetry_updated.connect(self.update_telemetry, Qt.ConnectionType.QueuedConnection)
            bridge.sig_perception_updated.connect(self.update_perception_preview, Qt.ConnectionType.QueuedConnection)

            self.sig_goal_submitted.connect(bridge.sig_goal_submitted)
            self.sig_pause_toggled.connect(bridge.sig_pause_toggled)
            self.sig_panic_triggered.connect(bridge.sig_panic_triggered)
            self.sig_hud_toggled.connect(bridge.sig_hud_toggled)
            self.sig_brain_mode_changed.connect(bridge.sig_brain_mode_changed)
        except Exception as e:
            logger.warning(f"Failed to wire bridge to CompanionDock: {e}")
