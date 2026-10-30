"""
tests/test_entrypoints.py - Entry Points, CLI, and Launcher Test Suite.

Verifies:
1. CLI argument parsing across all valid flags and options.
2. High-DPI awareness bootstrap and interface alias parity.
3. Headless ParasiteApp lifecycle, self-tests, and dry-run execution.
4. Clean shutdown idempotency and resource unhooking.
5. Windows batch launcher (launch_parasite.bat) syntax and synchronization commands.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Generator

import pytest
from PyQt6.QtWidgets import QApplication

from parasite_ai.main import ParasiteApp, main, parse_args
from parasite_ai.ui.dpi import init_dpi_awareness, init_high_dpi_awareness


@pytest.fixture(scope="module")
def qapp_instance() -> Generator[QApplication, None, None]:
    """Ensures a QApplication instance exists with offscreen platform."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


class TestCLIArgumentParsing:
    """Tests command-line interface argument parser options and defaults."""

    def test_cli_defaults(self) -> None:
        args = parse_args([])
        assert args.config_path is None
        assert args.headless is False
        assert args.dry_run is False
        assert args.no_hud is False
        assert args.brain_mode is None
        assert args.goal is None
        assert args.log_level is None

    def test_cli_custom_flags(self) -> None:
        argv = [
            "--config", "custom_config.yaml",
            "--headless",
            "--dry-run",
            "--no-hud",
            "--brain-mode", "mock",
            "--goal", "Open calculator and compute 42",
            "--log-level", "DEBUG",
        ]
        args = parse_args(argv)
        assert args.config_path == "custom_config.yaml"
        assert args.headless is True
        assert args.dry_run is True
        assert args.no_hud is True
        assert args.brain_mode == "mock"
        assert args.goal == "Open calculator and compute 42"
        assert args.log_level == "DEBUG"

    def test_cli_short_config_flag(self) -> None:
        args = parse_args(["-c", "test.yaml"])
        assert args.config_path == "test.yaml"

    def test_cli_invalid_brain_mode_raises(self) -> None:
        with pytest.raises(SystemExit):
            parse_args(["--brain-mode", "invalid_brain"])

    def test_cli_version_flag(self, capsys: pytest.CaptureFixture) -> None:
        with pytest.raises(SystemExit) as exc_info:
            parse_args(["--version"])
        assert exc_info.value.code == 0


class TestDPIAwareness:
    """Tests High-DPI awareness bootstrap and alias interface."""

    def test_dpi_awareness_alias_identity(self) -> None:
        assert init_dpi_awareness is init_high_dpi_awareness

    def test_dpi_awareness_invocation_safe(self) -> None:
        result = init_dpi_awareness()
        assert isinstance(result, bool)


class TestParasiteAppLifecycle:
    """Tests ParasiteApp instantiation, dry-run, and graceful termination."""

    def test_parasite_app_instantiation_headless(self, qapp_instance: QApplication) -> None:
        args = parse_args(["--headless", "--no-hud", "--brain-mode", "mock"])
        app = ParasiteApp(args)
        try:
            assert app.bridge is not None
            assert app.runtime is not None
            assert app.runtime.simulation_mode is True
            assert app.runtime.headless is True
            assert app.dock is not None
            assert app.hud is None
            assert app.config.brain.mode == "mock"
        finally:
            app.shutdown()

    def test_parasite_app_dry_run_exit_code_zero(self, qapp_instance: QApplication, capsys: pytest.CaptureFixture) -> None:
        args = parse_args(["--dry-run", "--headless", "--brain-mode", "mock"])
        app = ParasiteApp(args)
        exit_code = app.run()
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Clean dry-run initialization completed successfully" in captured.out

    def test_parasite_app_hud_enabled_by_default(self, qapp_instance: QApplication) -> None:
        args = parse_args(["--headless", "--brain-mode", "mock"])
        app = ParasiteApp(args)
        try:
            assert app.hud is not None
        finally:
            app.shutdown()

    def test_parasite_app_initial_goal_queued(self, qapp_instance: QApplication) -> None:
        goal_text = "Test goal injection at boot"
        args = parse_args(["--headless", "--no-hud", "--brain-mode", "mock", "--goal", goal_text])
        app = ParasiteApp(args)
        try:
            dequeued = app.bridge.get_next_goal(timeout_sec=0.1)
            assert dequeued == goal_text
        finally:
            app.shutdown()

    def test_parasite_app_shutdown_idempotent(self, qapp_instance: QApplication) -> None:
        args = parse_args(["--headless", "--no-hud", "--brain-mode", "mock"])
        app = ParasiteApp(args)
        # Calling shutdown multiple times must be completely safe
        app.shutdown()
        app.shutdown()
        app.shutdown()
        assert app._is_shutdown is True


class TestSubprocessEntryPoints:
    """Tests running the entry points as isolated subprocesses."""

    def test_main_py_dry_run_subprocess(self) -> None:
        result = subprocess.run(
            [sys.executable, "main.py", "--dry-run", "--headless"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 0
        assert "Clean dry-run initialization completed successfully" in result.stdout

    def test_parasite_ai_main_dry_run_subprocess(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "parasite_ai.main", "--dry-run", "--headless"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 0
        assert "Clean dry-run initialization completed successfully" in result.stdout


class TestBatchScriptValidation:
    """Tests launch_parasite.bat existence and contents."""

    def test_batch_script_exists_and_content(self) -> None:
        batch_path = Path("launch_parasite.bat")
        assert batch_path.exists(), "launch_parasite.bat must exist in project root"
        content = batch_path.read_text(encoding="utf-8")
        assert len(content.strip()) > 50
        assert "uv sync" in content
        assert "uv run python main.py %*" in content
        assert "setlocal EnableDelayedExpansion" in content
        assert "exit /b" in content
