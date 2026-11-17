"""
parasite_ai/main.py - Application Entry Point and Pure-Python Subsystem Coordinator.

Manages High-DPI awareness bootstrap, pure-Python runtime orchestration,
Discord C2 daemon lifecycle, clean signal handlers, and CLI options with
zero PyQt6 dependencies.
"""

from __future__ import annotations

import argparse
import logging
import logging.handlers
import os
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Any, List, Optional

from parasite_ai.config import AppConfig, load_config
from parasite_ai.runtime import RuntimeOrchestrator
from parasite_ai.ui.bridge import UIBridge
from parasite_ai.ui.discord_bot import DiscordBotC2
from parasite_ai.ui.dpi import init_dpi_awareness

logger = logging.getLogger("parasite_ai.main")


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parses command-line arguments for ParasiteAI."""
    parser = argparse.ArgumentParser(
        prog="parasite",
        description="ParasiteAI - Desktop-native local AI agent operating on physical Windows desktop.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-c", "--config", dest="config_path", type=str, default=None, help="Path to config.yaml")
    parser.add_argument("--headless", action="store_true", default=False, help="Run headless without local GUI windows.")
    parser.add_argument(
        "--simulation",
        dest="simulation",
        action="store_true",
        default=False,
        help="Run in simulation mode using mock hardware input backends (for tests / CI).",
    )
    parser.add_argument("--dry-run", action="store_true", default=False, help="Initialize subsystems, validate self-test, and exit 0.")
    parser.add_argument("--discord", dest="discord", action="store_true", default=False, help="Enable Discord C2 bot listener.")
    parser.add_argument("--no-discord", dest="no_discord", action="store_true", default=False, help="Explicitly disable Discord C2 bot.")
    parser.add_argument("--no-hud", action="store_true", default=False, help="Legacy compatibility flag (ignored).")
    parser.add_argument(
        "--brain-mode",
        choices=["local_llm", "browser_offload", "hybrid", "mock"],
        default=None,
        help="Override brain mode.",
    )
    parser.add_argument("--goal", type=str, default=None, help="Initial goal to queue at startup.")
    parser.add_argument(
        "--monitor-index",
        dest="monitor_index",
        type=int,
        default=None,
        help="Target monitor index (0 = all monitors, 1 = primary/left monitor, 2 = secondary monitor).",
    )
    parser.add_argument(
        "--auto-exit-on-complete",
        dest="auto_exit_on_complete",
        action="store_true",
        default=False,
        help="Automatically exit application after completing the initial --goal episode.",
    )
    parser.add_argument(
        "--episode-report",
        dest="episode_report",
        type=str,
        default=None,
        help="Path to write machine-readable JSON episode receipt.",
    )
    parser.add_argument(
        "--max-steps",
        dest="max_steps",
        type=int,
        default=30,
        help="Maximum cognitive steps per goal episode.",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default=None,
        help="Logging verbosity.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Enable maximum debug logging verbosity (forces log-level to DEBUG).",
    )
    parser.add_argument(
        "--log-file",
        dest="log_file",
        type=str,
        default=None,
        help="Path to write rotating debug log file (defaults to logs/parasite_debug.log).",
    )
    from parasite_ai import __version__
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser.parse_args(argv)


def setup_logging(
    config: AppConfig,
    debug: bool = False,
    log_file_override: Optional[str] = None,
) -> Path:
    """
    Configures unified dual-stream logging:
    1. Console stream (StreamHandler to sys.stderr) with clean formatting.
    2. High-fidelity rotating debug log file recording line numbers, thread names,
       LLM reasoning, and diagnostic traces.
    """
    root_logger = logging.getLogger()
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    console_level = logging.DEBUG if debug else getattr(logging, config.system.log_level.upper(), logging.INFO)
    root_logger.setLevel(logging.DEBUG)

    # Suppress verbose third-party COM/HTTP debug log flooding
    for noisy_logger in ("comtypes", "comtypes._post_coinit", "urllib3", "httpx", "httpcore", "PIL", "discord"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    console_formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    log_path = Path(log_file_override) if log_file_override else config.system.log_file or Path("logs/parasite_debug.log")
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        if log_path.exists() and log_path.stat().st_size > 0:
            import datetime
            import shutil
            mtime = datetime.datetime.fromtimestamp(log_path.stat().st_mtime)
            stamp = mtime.strftime("%I%M%p").lower()
            archive_candidate = log_path.parent / f"{log_path.stem}{stamp}{log_path.suffix}"
            if archive_candidate.exists():
                stamp_sec = mtime.strftime("%I%M%S%p").lower()
                archive_candidate = log_path.parent / f"{log_path.stem}{stamp_sec}{log_path.suffix}"
            try:
                shutil.copy2(log_path, archive_candidate)
                log_path.write_text("", encoding="utf-8")
                max_archives = getattr(config.system, "max_archived_logs", 25)
                if isinstance(max_archives, int) and max_archives >= 1:
                    archived = [
                        p for p in log_path.parent.glob(f"{log_path.stem}*{log_path.suffix}")
                        if p != log_path and p.is_file()
                    ]
                    if len(archived) > max_archives:
                        archived.sort(key=lambda p: p.stat().st_mtime)
                        for stale_log in archived[: len(archived) - max_archives]:
                            try:
                                stale_log.unlink()
                            except Exception:
                                pass
            except Exception:
                pass
        file_formatter = logging.Formatter(
            fmt="%(asctime)s.%(msecs)03d [%(levelname)-7s] [%(threadName)s] [%(name)s:%(funcName)s:%(lineno)d] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler = logging.handlers.RotatingFileHandler(
            filename=str(log_path),
            maxBytes=15 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
    except Exception as exc:
        console_handler.stream.write(f"[WARNING] Could not initialize log file at {log_path}: {exc}\n")

    logger.info("=== ParasiteAI Logger Initialized ===")
    logger.info(
        "Diagnostics Active -> Console Level: %s | Debug Log File: %s",
        logging.getLevelName(console_level),
        log_path.resolve() if hasattr(log_path, "resolve") else log_path,
    )
    return log_path


class ParasiteApp:
    """
    Main application coordinator managing High-DPI bootstrapping, pure-Python runtime,
    Discord C2 daemon, and clean signal handling with zero Qt event loop dependencies.
    """

    def __init__(self, args: Optional[argparse.Namespace] = None) -> None:
        self.args = args or parse_args([])
        self._shutdown_lock = threading.Lock()
        self._is_shutdown = False
        self._stop_event = threading.Event()
        self.exit_code: int = 0

        # 1. Bootstrap High-DPI Awareness
        init_dpi_awareness()

        # 2. Load configuration & apply CLI overrides
        self.config: AppConfig = load_config(self.args.config_path)
        if self.args.headless:
            self.config.headless = True
        if self.args.brain_mode:
            self.config.brain.mode = self.args.brain_mode
        elif self.args.dry_run:
            self.config.brain.mode = "mock"
        if getattr(self.args, "monitor_index", None) is not None:
            self.config.vision.monitor_index = int(self.args.monitor_index)
        if self.args.debug:
            self.config.system.log_level = "DEBUG"
        elif self.args.log_level:
            self.config.system.log_level = self.args.log_level

        # Discord configuration overrides
        if self.args.discord:
            self.config.discord.enabled = True
        elif self.args.no_discord:
            self.config.discord.enabled = False

        # 3. Configure dual-stream logging
        self.log_path = setup_logging(
            config=self.config,
            debug=bool(self.args.debug),
            log_file_override=self.args.log_file,
        )

        # 4. Instantiate UIBridge
        self.bridge = UIBridge()

        # 5. Determine simulation mode vs headless
        # Simulation mode is used in CI/unit tests to mock hardware.
        # Headless mode on real desktop operates with real Win32 hardware drivers.
        is_simulation = bool(self.args.simulation or self.args.dry_run)

        # 6. Instantiate Runtime Orchestrator
        self.runtime = RuntimeOrchestrator(
            config=self.config,
            bridge=self.bridge,
            simulation_mode=is_simulation,
            headless=bool(self.args.headless or self.config.headless),
            episode_report_path=self.args.episode_report,
        )
        self.runtime.auto_exit_on_complete = bool(getattr(self.args, "auto_exit_on_complete", False))
        self.runtime.default_max_steps = int(getattr(self.args, "max_steps", 30))
        self.bridge.sig_close_requested.connect(self._on_close_requested)

        # 7. Instantiate Discord C2 Bot (if enabled)
        self.discord_bot: Optional[DiscordBotC2] = None
        if self.config.discord.enabled and not self.args.dry_run:
            self.discord_bot = DiscordBotC2(
                orchestrator=self.runtime,
                config=self.config,
            )

        # 8. Setup Signal Handlers
        self._setup_signal_handling()

        # 9. Submit initial goal if passed on CLI
        if self.args.goal:
            self.bridge.submit_goal(
                goal=self.args.goal,
                max_steps=self.runtime.default_max_steps,
                source="cli",
            )

    def _on_close_requested(self) -> None:
        """Handles close signal from bridge (e.g. after episode auto-exit)."""
        logger.info("Application close requested. Evaluating episode outcome...")
        if self.runtime and self.runtime.last_episode_receipt:
            receipt = self.runtime.last_episode_receipt
            if receipt.success:
                self.exit_code = 0
            elif receipt.exit_reason == "PANIC":
                self.exit_code = 2
            else:
                self.exit_code = 1
        self._stop_event.set()

    def _setup_signal_handling(self) -> None:
        """Configures clean SIGINT / SIGTERM handlers."""
        def _handle_signal(signum: int, frame: Any) -> None:
            logger.info(f"Exit signal received ({signum}). Initiating shutdown...")
            self._on_close_requested()

        try:
            signal.signal(signal.SIGINT, _handle_signal)
            signal.signal(signal.SIGTERM, _handle_signal)
        except (ValueError, AttributeError):
            pass

    def run(self) -> int:
        """Runs application in self-test mode, Discord daemon mode, or goal execution loop."""
        if self.args.dry_run:
            logger.info("Executing ParasiteAI dry-run self-test...")
            assert self.bridge is not None, "UIBridge was not initialized"
            assert self.runtime is not None, "RuntimeOrchestrator was not initialized"
            assert self.runtime.interrupt_guard is not None, "InterruptGuard was not initialized"
            assert self.runtime.window_guard is not None, "WindowGuard was not initialized"
            assert self.runtime.mouse_driver is not None, "MouseDriver was not initialized"
            assert self.runtime.keyboard_driver is not None, "KeyboardDriver was not initialized"
            assert self.runtime.screen_capture is not None, "ScreenCapture was not initialized"
            assert self.runtime.screen_grounder is not None, "ScreenGrounder was not initialized"
            assert self.runtime.brain_manager is not None, "BrainManager was not initialized"
            assert self.runtime.browser_offloader is not None, "BrowserOffloader was not initialized"
            assert self.runtime.memory is not None, "EpisodicMemory was not initialized"
            assert self.runtime.pipeline is not None, "DualMindPipeline was not initialized"

            print("Clean dry-run initialization completed successfully")
            self.shutdown()
            return 0

        # Start background runtime orchestrator
        self.runtime.start()

        # Start Discord C2 bot if configured
        if self.discord_bot:
            self.discord_bot.start()

        logger.info("ParasiteAI core running. Press Ctrl+C or issue /panic to stop.")

        try:
            while not self._stop_event.is_set():
                time.sleep(0.15)
                # If single-shot goal execution requested via CLI with auto_exit_on_complete
                if self.runtime.auto_exit_on_complete and self.runtime.last_episode_receipt:
                    receipt = self.runtime.last_episode_receipt
                    self.exit_code = 0 if receipt.success else (2 if receipt.exit_reason == "PANIC" else 1)
                    break
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt received.")
        finally:
            self.shutdown()

        return self.exit_code

    def shutdown(self) -> None:
        """Atomically shuts down all subsystems and cleans up resources."""
        with self._shutdown_lock:
            if self._is_shutdown:
                return
            self._is_shutdown = True
            logger.info("Shutting down ParasiteAI subsystems...")

            if self.discord_bot:
                try:
                    self.discord_bot.stop()
                except Exception as exc:
                    logger.debug(f"Error stopping Discord bot: {exc}")

            if hasattr(self, "runtime") and self.runtime:
                try:
                    self.runtime.stop()
                except Exception as exc:
                    logger.debug(f"Error stopping runtime orchestrator: {exc}")

            logger.info("ParasiteAI shutdown complete.")
            for handler in list(logging.getLogger().handlers):
                try:
                    handler.flush()
                except Exception:
                    pass


def main(argv: Optional[List[str]] = None) -> int:
    """Main CLI entrypoint function."""
    args = parse_args(argv)
    app = ParasiteApp(args)
    return app.run()


if __name__ == "__main__":
    sys.exit(main())
