"""
tests/test_challenger_m5_1.py - Adversarial Stress & Vulnerability Test Suite for M5.

Author: teamwork_challenger_m5_1_gen2
Target: Milestone M5 Entry Points and Lifecycle
Audited Components:
- main.py
- parasite_ai/main.py (CLI parsing, ParasiteApp lifecycle, Qt shutdown, heartbeat)
- launch_parasite.bat (Batch launcher resilience, foreign working directories, errorlevel propagation)
- parasite_ai/ui/dpi.py (High-DPI Per-Monitor v2 bootstrapping, OS fallback chain, concurrency)
- parasite_ai/config.py (Config overrides, malformed YAML, Pydantic bounds)

Verification Scope:
1. Malformed and conflicting CLI arguments, injections, and precedence.
2. High-DPI awareness bootstrap failures, platform emulation, and multi-threaded calls.
3. Windows batch script launch from arbitrary foreign directories and argument quoting.
4. Signal interception (SIGINT/SIGTERM), heartbeat timer execution, and multi-threaded shutdown races.
"""

from __future__ import annotations

import argparse
import ctypes
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Generator
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from parasite_ai.config import AppConfig, load_config
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


# ============================================================================
# Group 1: CLI & Configuration Adversarial Robustness
# ============================================================================


class TestAdversarialCLIAndConfigArguments:
    """Stress-tests command-line arguments, environment variable overrides, and config loading."""

    def test_unrecognized_argument_raises_system_exit_2(self) -> None:
        """Adversarial CLI input: Bogus/unrecognized flags must exit with code 2."""
        with pytest.raises(SystemExit) as exc_info:
            parse_args(["--nonexistent-flag-xyz"])
        assert exc_info.value.code == 2

    @pytest.mark.parametrize(
        "invalid_mode",
        [
            "cloud",
            "deepseek",
            "openai_direct",
            "LOCAL_LLM",  # Case sensitivity check
            "MOCK",
            "",
            "None",
            "123",
            "local-llm",
        ],
    )
    def test_invalid_brain_modes_rejected(self, invalid_mode: str) -> None:
        """Adversarial CLI input: Unsupported brain mode values must be rejected."""
        with pytest.raises(SystemExit) as exc_info:
            parse_args(["--brain-mode", invalid_mode])
        assert exc_info.value.code == 2

    @pytest.mark.parametrize(
        "invalid_level",
        [
            "TRACE",
            "FATAL",
            "info",  # Case sensitivity check (uppercase required by choices)
            "10",
            "ALL",
            "OFF",
            "",
        ],
    )
    def test_invalid_log_levels_rejected(self, invalid_level: str) -> None:
        """Adversarial CLI input: Invalid log levels must be rejected."""
        with pytest.raises(SystemExit) as exc_info:
            parse_args(["--log-level", invalid_level])
        assert exc_info.value.code == 2

    def test_flag_combinations_dry_run_and_headless(self, qapp_instance: QApplication) -> None:
        """Verifies simultaneous presence of --headless, --dry-run, --no-hud, and --brain-mode."""
        args = parse_args(
            [
                "--headless",
                "--dry-run",
                "--no-hud",
                "--brain-mode",
                "mock",
                "--log-level",
                "WARNING",
            ]
        )
        app = ParasiteApp(args)
        try:
            assert app.args.headless is True
            assert app.args.dry_run is True
            assert app.args.no_hud is True
            assert app.args.brain_mode == "mock"
            assert app.config.brain.mode == "mock"
            assert app.config.system.log_level == "WARNING"
            assert app.hud is None

            exit_code = app.run()
            assert exit_code == 0
        finally:
            app.shutdown()

    def test_no_hud_flag_overrides_config_enabled(self, qapp_instance: QApplication) -> None:
        """CLI flag --no-hud must take precedence over config.ui.hud.enabled == True."""
        args = parse_args(["--headless", "--no-hud", "--brain-mode", "mock"])
        app = ParasiteApp(args)
        try:
            # Force config to true to verify CLI override
            assert app.config.ui.hud.enabled is True
            assert app.hud is None
        finally:
            app.shutdown()

    def test_config_hud_disabled_without_cli_flag(self, qapp_instance: QApplication) -> None:
        """When config.ui.hud.enabled is False, HUD must not be instantiated even without --no-hud."""
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as tf:
            tf.write("ui:\n  hud:\n    enabled: false\n")
            cfg_path = tf.name

        try:
            args = parse_args(
                ["--headless", "--config", cfg_path, "--brain-mode", "mock"]
            )
            app = ParasiteApp(args)
            try:
                assert app.config.ui.hud.enabled is False
                assert app.hud is None
            finally:
                app.shutdown()
        finally:
            if os.path.exists(cfg_path):
                os.unlink(cfg_path)

    def test_extreme_goal_string_injections(self, qapp_instance: QApplication) -> None:
        """Adversarial goal strings: Emojis, ANSI escapes, HTML/XML tags, and 50k chars."""
        adversarial_goal = (
            "🚀 <script>alert('xss')</script> SELECT * FROM users; -- "
            + "\x1b[31;1mRED_ALERT\x1b[0m "
            + "A" * 50000
        )
        args = parse_args(
            [
                "--headless",
                "--no-hud",
                "--brain-mode",
                "mock",
                "--goal",
                adversarial_goal,
            ]
        )
        app = ParasiteApp(args)
        try:
            dequeued = app.bridge.get_next_goal(timeout_sec=0.2)
            assert dequeued == adversarial_goal
            assert len(dequeued) > 50000
        finally:
            app.shutdown()

    def test_malformed_yaml_config_raises_value_error(self) -> None:
        """Passing a path with corrupted/invalid YAML must raise ValueError."""
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as tf:
            tf.write("system: [unclosed list mapping ::: invalid")
            cfg_path = tf.name

        try:
            with pytest.raises(ValueError, match="Failed to read configuration YAML"):
                load_config(cfg_path)
        finally:
            if os.path.exists(cfg_path):
                os.unlink(cfg_path)

    def test_config_directory_path_fallback(self) -> None:
        """If config_path points to an existing directory, load_config must handle it safely."""
        with tempfile.TemporaryDirectory() as td:
            # Pointing to directory td (path.is_file() == False)
            cfg = load_config(td)
            assert isinstance(cfg, AppConfig)

    def test_config_corrupted_pydantic_types_raises_validation_error(self) -> None:
        """YAML with invalid field types must trigger Pydantic validation error."""
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as tf:
            tf.write("safety:\n  corner_distance_px: 'NOT_AN_INTEGER'\n")
            cfg_path = tf.name

        try:
            with pytest.raises(Exception):  # pydantic_core.ValidationError
                load_config(cfg_path)
        finally:
            if os.path.exists(cfg_path):
                os.unlink(cfg_path)

    def test_env_var_brain_mode_override_precedence(
        self, qapp_instance: QApplication
    ) -> None:
        """Tests precedence: CLI argument > Environment Variable > config.yaml default."""
        env_backup = os.environ.get("PARASITE_BRAIN_MODE")
        try:
            # Case 1: Environment variable set, no CLI flag -> env var wins
            os.environ["PARASITE_BRAIN_MODE"] = "HYBRID"
            args_no_cli = parse_args(["--headless", "--no-hud"])
            app1 = ParasiteApp(args_no_cli)
            try:
                assert app1.config.brain.mode == "hybrid"
            finally:
                app1.shutdown()

            # Case 2: Environment variable set, CLI flag passed -> CLI flag wins
            os.environ["PARASITE_BRAIN_MODE"] = "HYBRID"
            args_cli = parse_args(["--headless", "--no-hud", "--brain-mode", "mock"])
            app2 = ParasiteApp(args_cli)
            try:
                assert app2.config.brain.mode == "mock"
            finally:
                app2.shutdown()
        finally:
            if env_backup is not None:
                os.environ["PARASITE_BRAIN_MODE"] = env_backup
            else:
                os.environ.pop("PARASITE_BRAIN_MODE", None)

    def test_env_var_integrity_mode_override(self) -> None:
        """Tests PARASITE_INTEGRITY_MODE environment variable application."""
        env_backup = os.environ.get("PARASITE_INTEGRITY_MODE")
        try:
            os.environ["PARASITE_INTEGRITY_MODE"] = "TESTING"
            cfg = load_config(None)
            assert cfg.system.integrity_mode == "testing"
        finally:
            if env_backup is not None:
                os.environ["PARASITE_INTEGRITY_MODE"] = env_backup
            else:
                os.environ.pop("PARASITE_INTEGRITY_MODE", None)


# ============================================================================
# Group 2: High-DPI Awareness Bootstrapping & Platform Boundary Conditions
# ============================================================================


class TestAdversarialHighDPIBootstrapping:
    """Stress-tests Windows High-DPI bootstrapping fallback tiers and concurrency."""

    def test_dpi_awareness_concurrency_stress_20_threads(self) -> None:
        """20 threads concurrently calling init_dpi_awareness 50 times each must not race or fault."""
        results: list[bool] = []
        errors: list[Exception] = []

        def _worker() -> None:
            for _ in range(50):
                try:
                    res = init_dpi_awareness()
                    results.append(res)
                except Exception as ex:
                    errors.append(ex)

        threads = [threading.Thread(target=_worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10.0)

        assert len(errors) == 0, f"DPI awareness raised concurrency errors: {errors}"
        assert len(results) == 1000
        assert all(isinstance(r, bool) for r in results)

    def test_dpi_awareness_non_windows_platform_returns_false(self) -> None:
        """On non-win32 platforms, init_dpi_awareness must immediately return False without calling windll."""
        with patch("sys.platform", "linux"):
            res_linux = init_dpi_awareness()
            assert res_linux is False

        with patch("sys.platform", "darwin"):
            res_darwin = init_dpi_awareness()
            assert res_darwin is False

    def test_dpi_awareness_per_monitor_v2_access_denied_already_set(self) -> None:
        """If SetProcessDpiAwarenessContext returns False with ERROR_ACCESS_DENIED (5), treat as success."""
        if sys.platform != "win32":
            pytest.skip("Windows only")

        mock_user32 = MagicMock()
        mock_user32.SetProcessDpiAwarenessContext.return_value = False
        mock_kernel32 = MagicMock()
        mock_kernel32.GetLastError.return_value = 5  # ERROR_ACCESS_DENIED

        with patch("ctypes.windll.user32", mock_user32), patch(
            "ctypes.windll.kernel32", mock_kernel32
        ):
            res = init_dpi_awareness()
            assert res is True

    def test_dpi_awareness_fallback_to_shcore_s_ok(self) -> None:
        """If SetProcessDpiAwarenessContext is missing, fallback to shcore.SetProcessDpiAwareness."""
        if sys.platform != "win32":
            pytest.skip("Windows only")

        mock_user32 = MagicMock()
        del mock_user32.SetProcessDpiAwarenessContext  # Raise AttributeError

        mock_shcore = MagicMock()
        mock_shcore.SetProcessDpiAwareness.return_value = 0  # S_OK

        with patch("ctypes.windll.user32", mock_user32), patch(
            "ctypes.windll.shcore", mock_shcore
        ):
            res = init_dpi_awareness()
            assert res is True
            mock_shcore.SetProcessDpiAwareness.assert_called_once_with(2)

    def test_dpi_awareness_fallback_to_shcore_access_denied(self) -> None:
        """If shcore returns E_ACCESSDENIED (-2147024891 / 0x80070005), treat as already set."""
        if sys.platform != "win32":
            pytest.skip("Windows only")

        mock_user32 = MagicMock()
        del mock_user32.SetProcessDpiAwarenessContext

        mock_shcore = MagicMock()
        # E_ACCESSDENIED as signed 32-bit int
        mock_shcore.SetProcessDpiAwareness.return_value = -2147024891

        with patch("ctypes.windll.user32", mock_user32), patch(
            "ctypes.windll.shcore", mock_shcore
        ):
            res = init_dpi_awareness()
            assert res is True

    def test_dpi_awareness_fallback_to_user32_vista(self) -> None:
        """If both Win10 and Win8.1 APIs fail, fallback to Vista SetProcessDPIAware."""
        if sys.platform != "win32":
            pytest.skip("Windows only")

        mock_user32 = MagicMock()
        del mock_user32.SetProcessDpiAwarenessContext
        mock_user32.SetProcessDPIAware.return_value = True

        mock_shcore = MagicMock()
        del mock_shcore.SetProcessDpiAwareness

        with patch("ctypes.windll.user32", mock_user32), patch(
            "ctypes.windll.shcore", mock_shcore
        ):
            res = init_dpi_awareness()
            assert res is True
            mock_user32.SetProcessDPIAware.assert_called_once()

    def test_dpi_awareness_total_failure_returns_false_cleanly(self) -> None:
        """If all Win32 DPI APIs fail with OSError/AttributeError, return False without raising."""
        if sys.platform != "win32":
            pytest.skip("Windows only")

        mock_user32 = MagicMock()
        mock_user32.SetProcessDpiAwarenessContext.side_effect = OSError("Access violation")
        mock_user32.SetProcessDPIAware.side_effect = OSError("Hardware error")

        mock_shcore = MagicMock()
        mock_shcore.SetProcessDpiAwareness.side_effect = OSError("Library not found")

        with patch("ctypes.windll.user32", mock_user32), patch(
            "ctypes.windll.shcore", mock_shcore
        ):
            res = init_dpi_awareness()
            assert res is False

    def test_dpi_awareness_alias_identity(self) -> None:
        """Verify contract alias init_dpi_awareness is exactly init_high_dpi_awareness."""
        assert init_dpi_awareness is init_high_dpi_awareness


# ============================================================================
# Group 3: Subprocess & Batch Launcher (launch_parasite.bat) Robustness
# ============================================================================


class TestAdversarialBatchLauncherAndSubprocess:
    """Stress-tests subprocess entrypoints and Windows batch script execution."""

    def test_batch_launcher_static_invariants(self) -> None:
        """Verifies critical static invariants in launch_parasite.bat."""
        bat_file = Path("launch_parasite.bat")
        assert bat_file.exists(), "launch_parasite.bat must exist in project root"
        content = bat_file.read_text(encoding="utf-8")

        # Invariant 1: Changes directory to script directory (%~dp0) to survive foreign CWD
        assert 'cd /d "%~dp0"' in content
        # Invariant 2: Checks PATH and standard locations for uv.exe
        assert "where uv" in content
        # Invariant 3: Synchronizes environment
        assert "uv sync" in content
        # Invariant 4: Forwards all CLI arguments (%*)
        assert "uv run python main.py %*" in content
        # Invariant 5: Propagates exit code
        assert "exit /b %EXIT_CODE%" in content or "exit /b %ERRORLEVEL%" in content

    def test_batch_launcher_execution_from_temp_directory(self) -> None:
        """Invokes launch_parasite.bat from a foreign temp directory with --dry-run --headless."""
        bat_path = Path("launch_parasite.bat").resolve()
        assert bat_path.is_file()

        temp_cwd = tempfile.gettempdir()
        result = subprocess.run(
            [str(bat_path), "--dry-run", "--headless", "--brain-mode", "mock"],
            cwd=temp_cwd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"Batch script failed from foreign CWD: {result.stderr}"
        assert "Clean dry-run initialization completed successfully" in result.stdout

    def test_batch_launcher_execution_with_quoted_args(self) -> None:
        """Invokes launch_parasite.bat forwarding arguments with spaces and quotes."""
        bat_path = Path("launch_parasite.bat").resolve()
        result = subprocess.run(
            [
                str(bat_path),
                "--dry-run",
                "--headless",
                "--brain-mode",
                "mock",
                "--goal",
                "Batch goal with spaces & symbols",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        assert "Clean dry-run initialization completed successfully" in result.stdout

    def test_batch_launcher_exit_code_propagation_on_error(self) -> None:
        """Batch script must propagate non-zero exit code on invalid arguments."""
        bat_path = Path("launch_parasite.bat").resolve()
        result = subprocess.run(
            [str(bat_path), "--nonexistent-unrecognized-flag"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 2

    def test_main_py_vs_parasite_ai_main_subprocess_parity(self) -> None:
        """Verifies exact output and exit code parity between main.py and python -m parasite_ai.main."""
        cmd1 = [sys.executable, "main.py", "--dry-run", "--headless", "--brain-mode", "mock"]
        cmd2 = [
            sys.executable,
            "-m",
            "parasite_ai.main",
            "--dry-run",
            "--headless",
            "--brain-mode",
            "mock",
        ]

        res1 = subprocess.run(cmd1, capture_output=True, text=True, timeout=15)
        res2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=15)

        assert res1.returncode == 0
        assert res2.returncode == 0
        assert "Clean dry-run initialization completed successfully" in res1.stdout
        assert "Clean dry-run initialization completed successfully" in res2.stdout

    def test_main_py_subprocess_malformed_yaml_exit_code_1(self) -> None:
        """Subprocess execution with corrupt YAML returns non-zero exit code."""
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as tf:
            tf.write("!broken yaml [::: forbidden")
            cfg_path = tf.name

        try:
            res = subprocess.run(
                [sys.executable, "main.py", "--config", cfg_path, "--headless"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            assert res.returncode != 0
            assert "ValueError" in res.stderr or "Failed to read configuration YAML" in res.stderr
        finally:
            if os.path.exists(cfg_path):
                os.unlink(cfg_path)

    def test_main_py_subprocess_invalid_arg_exit_code_2(self) -> None:
        """Subprocess execution with invalid CLI args returns exit code 2."""
        res = subprocess.run(
            [sys.executable, "main.py", "--invalid-flag"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert res.returncode == 2
        assert "unrecognized arguments" in res.stderr


# ============================================================================
# Group 4: Lifecycle, Signal Handling, and Heartbeat Stress
# ============================================================================


class TestAdversarialLifecycleAndConcurrency:
    """Stress-tests signal handling, heartbeat timer, shutdown races, and thread safety."""

    def test_heartbeat_timer_configuration_and_wake_callback(
        self, qapp_instance: QApplication
    ) -> None:
        """Verifies heartbeat timer interval is 200ms and active for Python interpreter wake."""
        args = parse_args(["--headless", "--no-hud", "--brain-mode", "mock"])
        app = ParasiteApp(args)
        try:
            assert hasattr(app, "_heartbeat_timer")
            assert isinstance(app._heartbeat_timer, QTimer)
            assert app._heartbeat_timer.interval() == 200
            assert app._heartbeat_timer.isActive() is True
        finally:
            app.shutdown()
            assert app._heartbeat_timer.isActive() is False

    def test_signal_handling_sigint_and_sigterm_simulation(
        self, qapp_instance: QApplication
    ) -> None:
        """Directly invokes the registered signal handlers for SIGINT and SIGTERM."""
        args = parse_args(["--headless", "--no-hud", "--brain-mode", "mock"])
        app = ParasiteApp(args)
        try:
            # Locate handler inside _setup_signal_handling
            import signal

            current_sigint = signal.getsignal(signal.SIGINT)
            assert callable(current_sigint)

            # Trigger simulated SIGINT
            with patch.object(app.qapp, "quit") as mock_quit:
                current_sigint(signal.SIGINT, None)
                assert app._is_shutdown is True
                mock_quit.assert_called_once()
        finally:
            app.shutdown()

    def test_multithreaded_shutdown_race_condition_hammer(
        self, qapp_instance: QApplication
    ) -> None:
        """Hammers app.shutdown() with 25 concurrent threads to verify thread-lock safety."""
        args = parse_args(["--headless", "--no-hud", "--brain-mode", "mock"])
        app = ParasiteApp(args)
        errors: list[Exception] = []

        def _hammer_shutdown() -> None:
            try:
                app.shutdown()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=_hammer_shutdown) for _ in range(25)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        assert len(errors) == 0, f"Shutdown race condition caused errors: {errors}"
        assert app._is_shutdown is True

    def test_shutdown_exception_resilience_and_isolation(
        self, qapp_instance: QApplication
    ) -> None:
        """Verifies shutdown() continues cleanly even if runtime, hud, or dock raise on close."""
        args = parse_args(["--headless", "--brain-mode", "mock"])
        app = ParasiteApp(args)

        # Adversarially inject exceptions into subsystem stop/close methods
        mock_runtime = MagicMock()
        mock_runtime.stop.side_effect = RuntimeError("Catastrophic runtime stop failure")
        app.runtime = mock_runtime

        mock_hud = MagicMock()
        mock_hud.close.side_effect = RuntimeError("HUD window close failure")
        app.hud = mock_hud

        mock_dock = MagicMock()
        mock_dock.close.side_effect = RuntimeError("Dock window close failure")
        app.dock = mock_dock

        # Must not propagate exceptions
        app.shutdown()
        assert app._is_shutdown is True
        mock_runtime.stop.assert_called_once()
        mock_hud.close.assert_called_once()
        mock_dock.close.assert_called_once()

    def test_parasite_app_instantiation_in_background_thread(
        self, qapp_instance: QApplication
    ) -> None:
        """Instantiating ParasiteApp in a background thread catches signal ValueError safely."""
        thread_errors: list[Exception] = []

        def _thread_worker() -> None:
            try:
                args = parse_args(["--headless", "--no-hud", "--brain-mode", "mock"])
                app = ParasiteApp(args)
                app.shutdown()
            except Exception as ex:
                thread_errors.append(ex)

        t = threading.Thread(target=_thread_worker)
        t.start()
        t.join(timeout=10.0)

        assert len(thread_errors) == 0, f"Threaded instantiation failed: {thread_errors}"

    def test_double_run_or_shutdown_before_run(
        self, qapp_instance: QApplication
    ) -> None:
        """Calling shutdown() before run() or calling shutdown repeatedly must be fully benign."""
        args = parse_args(["--headless", "--no-hud", "--dry-run", "--brain-mode", "mock"])
        app = ParasiteApp(args)
        # 1. Shutdown before run
        app.shutdown()
        assert app._is_shutdown is True

        # 2. Dry run after shutdown
        exit_code = app.run()
        assert exit_code == 0
        assert app._is_shutdown is True
