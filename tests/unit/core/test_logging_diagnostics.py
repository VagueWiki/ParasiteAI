"""
tests/test_logging_diagnostics.py - Verification for Diagnostics, Monologue Auto-scroll, and OCR.
"""
from __future__ import annotations

import logging
from pathlib import Path
import pytest
from PyQt6.QtGui import QTextCursor

from parasite_ai.config import AppConfig, CompanionDockConfig
from parasite_ai.main import parse_args, setup_logging
from parasite_ai.ui.companion_dock import CompanionDock
from parasite_ai.vision.grounding import ScreenGrounder


def test_cli_debug_flag_parsing():
    args = parse_args(["--debug", "--log-file", "logs/custom_test.log"])
    assert args.debug is True
    assert args.log_file == "logs/custom_test.log"


def test_setup_logging_creates_rotating_file(tmp_path: Path):
    config = AppConfig()
    custom_log = tmp_path / "subdir" / "test_debug.log"
    returned_path = setup_logging(config=config, debug=True, log_file_override=str(custom_log))

    assert returned_path.resolve() == custom_log.resolve()
    assert custom_log.exists()

    logger = logging.getLogger("test_logger")
    logger.debug("Diagnostic trace message 12345")

    content = custom_log.read_text(encoding="utf-8")
    assert "=== ParasiteAI Logger Initialized ===" in content
    assert "Diagnostic trace message 12345" in content
    assert "[DEBUG  ]" in content


def test_monologue_auto_scrolls_to_newest_line(qtbot):
    dock = CompanionDock(config=CompanionDockConfig())
    qtbot.addWidget(dock)

    # Initial state
    assert dock.thought_text.textCursor().atEnd()

    # Append thoughts
    dock.update_thought("First observation")
    assert dock.thought_text.textCursor().atEnd()

    dock.update_thought("Second observation: button located")
    assert dock.thought_text.textCursor().atEnd()

    dock.update_thought("Third observation: newest thought visible")
    assert dock.thought_text.textCursor().atEnd()

    # Verify vertical scrollbar is at the maximum (bottom)
    sb = dock.thought_text.verticalScrollBar()
    assert sb.value() == sb.maximum()


def test_ocr_engine_available_and_instantiable():
    from rapidocr_onnxruntime import RapidOCR
    engine = RapidOCR()
    assert engine is not None

    grounder = ScreenGrounder(ocr_engine=engine)
    assert grounder._get_ocr_engine() is engine

