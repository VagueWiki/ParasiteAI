"""
parasite_ai/main.py - Application Entry Point and Subsystem Coordinator.

Manages High-DPI awareness bootstrap, Qt application lifecycle, cross-thread
cognitive daemon synchronization, clean Win32 exit handlers, and CLI options.
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import threading
from pathlib import Path
from typing import Any, List, Optional

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import QApplication

from parasite_ai.config import AppConfig, load_config
from parasite_ai.runtime import RuntimeOrchestrator
from parasite_ai.ui.bridge import UIBridge
from parasite_ai.ui.companion_dock import CompanionDock
from parasite_ai.ui.dpi import init_dpi_awareness
from parasite_ai.ui.ghost_hud import GhostHUD

logger = logging.getLogger("parasite_ai.main")


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parses command-line arguments for ParasiteAI."""
    parser = argparse.ArgumentParser(
        prog="parasite",
        description="ParasiteAI - 100% visible, desktop-native local AI assistant operating on physical Windows desktop.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-c", "--config", dest="config_path", type=str, default=None, help="Path to config.yaml")
    parser.add_argument("--headless", action="store_true", default=False, help="Run in headless/offscreen mode.")
    parser.add_argument("--dry-run", action="store_true", default=False, help="Initialize subsystems, validate self-test, and exit 0.")
    parser.add_argument("--no-hud", action="store_true", default=False, help="Disable transparent GhostHUD overlay.")
    parser.add_argument(
        "--brain-mode",
        choices=["local_llm", "browser_offload", "hybrid", "mock"],
        default=None,
        help="Override brain mode.",
    )
    parser.add_argument("--goal", type=str, default=None, help="Initial goal to queue at startup.")
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default=None,
        help="Logging verbosity.",
    )
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")
    return parser.parse_args(argv)


class ParasiteApp:
    """
    Main application coordinator managing High-DPI bootstrapping, Qt lifecycle,
    GUI components, runtime orchestrator, and clean shutdown.
    """

    def __init__(self, args: Optional[argparse.Namespace] = None) -> None:
        self.args = args or parse_args([])
        self._shutdown_lock = threading.Lock()
        self._is_shutdown = False

        # 1. Bootstrap High-DPI Awareness before QApplication setup
        init_dpi_awareness()

        # 2. Configure headless offscreen platform if requested or detected
        if self.args.headless:
            os.environ["QT_QPA_PLATFORM"] = "offscreen"

        # 3. Instantiate or retrieve QApplication
        self.qapp = QApplication.instance()
        if self.qapp is None:
            self.qapp = QApplication(sys.argv)

        # 4. Load configuration & apply CLI overrides
        self.config: AppConfig = load_config(self.args.config_path)
        if self.args.brain_mode:
            self.config.brain.mode = self.args.brain_mode
        if self.args.log_level:
            self.config.system.log_level = self.args.log_level

        # 5. Configure logging
        logging.basicConfig(
            level=getattr(logging, self.config.system.log_level.upper(), logging.INFO),
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )

        # 6. Instantiate UIBridge
        self.bridge = UIBridge()

        # 7. Instantiate Runtime Orchestrator
        self.runtime = RuntimeOrchestrator(
            config=self.config,
            bridge=self.bridge,
            simulation_mode=self.args.headless,
            headless=self.args.headless,
        )

        # 8. Instantiate CompanionDock
        self.dock = CompanionDock(
            config=self.config.ui.dock,
            bridge=self.bridge,
        )
        idx = self.dock.combo_brain_mode.findData(self.config.brain.mode)
        if idx >= 0:
            self.dock.combo_brain_mode.blockSignals(True)
            self.dock.combo_brain_mode.setCurrentIndex(idx)
            self.dock.combo_brain_mode.blockSignals(False)

        # 9. Instantiate GhostHUD (unless disabled via CLI or config)
        self.hud: Optional[GhostHUD] = None
        if not self.args.no_hud and self.config.ui.hud.enabled:
            self.hud = GhostHUD(
                config=self.config.ui.hud,
                bridge=self.bridge,
                enable_win32_styles=not self.args.headless,
            )
            self.bridge.sig_hud_toggled.connect(
                lambda visible: self.hud.setVisible(visible) if self.hud else None
            )

        # 10. Wire clean shutdown hooks & Qt signal handling
        self.qapp.aboutToQuit.connect(self.shutdown)
        self._setup_signal_handling()

        # 11. Initial display setup (unless headless/dry-run)
        if not self.args.headless and not self.args.dry_run:
            self.dock.show()
            if self.hud:
                self.hud.show()

        # 12. Submit initial goal if passed on CLI
        if self.args.goal:
            self.bridge.sig_goal_submitted.emit(self.args.goal)

    def _setup_signal_handling(self) -> None:
        """Sets up 200ms heartbeat timer and SIGINT/SIGTERM handlers for clean exit."""
        self._heartbeat_timer = QTimer()
        self._heartbeat_timer.setInterval(200)
        self._heartbeat_timer.timeout.connect(lambda: None)  # Wakes Python interpreter
        self._heartbeat_timer.start()

        def _handle_signal(signum: int, frame: Any) -> None:
            logger.info("Exit signal received (%d). Shutting down...", signum)
            self.shutdown()
            if self.qapp:
                self.qapp.quit()

        try:
            signal.signal(signal.SIGINT, _handle_signal)
            signal.signal(signal.SIGTERM, _handle_signal)
        except (ValueError, AttributeError):
            pass

    def run(self) -> int:
        """Runs application: self-test if dry-run, or starts runtime and Qt event loop."""
        if self.args.dry_run:
            logger.info("Executing ParasiteAI dry-run self-test...")
            # Validate subsystem health
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
            assert self.dock is not None, "CompanionDock was not initialized"
            if not self.args.no_hud and self.config.ui.hud.enabled:
                assert self.hud is not None, "GhostHUD was not initialized"

            print("Clean dry-run initialization completed successfully")
            self.shutdown()
            return 0

        # Start runtime cognitive daemon and enter Qt event loop
        self.runtime.start()
        return self.qapp.exec()

    def shutdown(self) -> None:
        """Atomically shuts down all subsystems and cleans up resources."""
        with self._shutdown_lock:
            if self._is_shutdown:
                return
            self._is_shutdown = True
            logger.info("Shutting down ParasiteAI subsystems...")

            if hasattr(self, "_heartbeat_timer") and self._heartbeat_timer:
                try:
                    self._heartbeat_timer.stop()
                except Exception:
                    pass

            if hasattr(self, "runtime") and self.runtime:
                try:
                    self.runtime.stop()
                except Exception as exc:
                    logger.debug("Error stopping runtime orchestrator: %s", exc)

            if hasattr(self, "hud") and self.hud:
                try:
                    self.hud.clear_targets()
                    self.hud.close()
                except Exception:
                    pass

            if hasattr(self, "dock") and self.dock:
                try:
                    self.dock.close()
                except Exception:
                    pass

            logger.info("ParasiteAI shutdown complete.")


def main(argv: Optional[List[str]] = None) -> int:
    """Main CLI entrypoint function."""
    args = parse_args(argv)
    app = ParasiteApp(args)
    return app.run()


if __name__ == "__main__":
    sys.exit(main())
