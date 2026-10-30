# Implementation Plan: Milestone M5 Entry Points (`main.py`, `launch_parasite.bat`)

## Overview
This plan specifies the implementation for Features 16 & 17 of ParasiteAI, delivering the primary desktop application bootstrapper, Qt lifecycle coordinator, cross-thread cognitive daemon synchronization, Win32 clean exit handlers, CLI interface, Windows batch launcher, and automated entry point test suite.

---

## Architecture Specification

### 1. File Structure & Placement
```
g:\__Docs\ParasiteAI\
├── main.py                          # Root entry point delegating to parasite_ai.main:main
├── launch_parasite.bat              # Windows batch launcher (uv verification, sync & execution)
├── parasite_ai/
│   ├── main.py                      # Core application controller & ParasiteApp lifecycle class
│   └── ui/
│       ├── dpi.py                   # Add alias init_dpi_awareness = init_high_dpi_awareness
│       └── __init__.py              # Export init_dpi_awareness
└── tests/
    └── test_entrypoints.py          # Comprehensive pytest suite for CLI, lifecycle & shutdown
```

---

### 2. Component Details

#### A. DPI Awareness Bootstrapping (`parasite_ai/ui/dpi.py` & `parasite_ai/ui/__init__.py`)
- **Requirement**: Must be invoked before `QApplication` instantiation to ensure 1:1 coordinate parity between physical desktop pixels, Win32 UI Automation bounding boxes, `mss` screen captures, and transparent PyQt6 overlays.
- **Change**:
  - In `parasite_ai/ui/dpi.py`: Add `init_dpi_awareness = init_high_dpi_awareness` (alias for DISPATCH contract compliance).
  - In `parasite_ai/ui/__init__.py`: Export `init_dpi_awareness`.

#### B. CLI Interface (`parasite_ai/main.py:parse_args`)
- Supported Arguments:
  - `-c`, `--config`: Path to custom configuration YAML (defaults to `config.yaml` / zero-config auto-generation).
  - `--headless`: Enables offscreen execution (`QT_QPA_PLATFORM=offscreen`) and simulation mode for mouse/keyboard drivers.
  - `--dry-run`: Instantiates all subsystems, verifies integrity, self-tests, and cleanly exits with status code 0.
  - `--no-hud`: Suppresses the fullscreen transparent GhostHUD overlay window, running only the companion dock.
  - `--brain-mode`: Choice of `["local_llm", "browser_offload", "hybrid", "mock"]`, overriding `config.yaml`.
  - `--goal`: Initial natural language goal queued immediately on boot.
  - `--log-level`: Choice of `["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]`.
  - `--version`: Displays version (`parasite 0.1.0`) and exits.

#### C. Application Lifecycle Controller (`parasite_ai/main.py:ParasiteApp`)
- **Initialization Order**:
  1. Parse CLI arguments and configure logging level and format.
  2. Bootstrap High-DPI awareness via `init_dpi_awareness()`.
  3. Set `QT_QPA_PLATFORM=offscreen` if `--headless` or offscreen environment is detected.
  4. Instantiate or retrieve `QApplication(sys.argv)`.
  5. Load configuration via `load_config(config_path)` and apply CLI overrides (`brain_mode`, `log_level`, `no_hud`).
  6. Instantiate `UIBridge` signal hub.
  7. Instantiate safety guards:
     - `InterruptGuard(safety_config=config.safety, on_interrupt=..., on_panic=...)`
     - `WindowGuard(config=config.safety)`
  8. Instantiate physical input drivers:
     - `MouseDriver(config=config.hands.mouse, reticle_callback=bridge.show_reticle, simulation_mode=is_headless)`
     - `KeyboardDriver(config=config.hands.keyboard)`
  9. Instantiate vision components:
     - `ScreenCapture(backend=config.vision.capture_backend)`
     - `ScreenGrounder(config=config.vision, capturer=screen_capture)`
  10. Instantiate cognitive mind pipeline:
     - `BrowserOffloader(config=config.brain.offload, keyboard_driver=keyboard_driver, mouse_driver=mouse_driver, bridge=bridge)`
     - `LocalBrainManager(config=config, offloader=offloader)`
     - `EpisodicMemory()`
     - `DualMindPipeline(brain_manager=..., memory=..., mouse_driver=..., keyboard_driver=..., screen_grounder=..., capturer=..., interrupt_guard=..., window_guard=..., bridge=bridge, offloader=offloader, config=config)`
  11. Instantiate GUI widgets:
     - `CompanionDock(config=config.ui.dock, bridge=bridge)`
     - `GhostHUD(config=config.ui.hud, bridge=bridge, enable_win32_styles=not is_headless)` (if HUD enabled and not `--no-hud`)
  12. Set up clean exit hooks:
     - `app.aboutToQuit.connect(self.shutdown)`
     - Windows `SIGINT` / `SIGTERM` handlers paired with a 200ms `QTimer` heartbeat to wake the Python interpreter.
     - `bridge.sig_panic_triggered.connect(self._on_panic_abort)`
     - `bridge.sig_hud_toggled.connect(self._on_hud_toggled)`

#### D. Cross-Thread Cognitive Worker Thread (`CognitiveDaemon`)
- **Execution Pattern**:
  - The Qt main thread executes `app.exec()` processing GUI painting, mouse clicks, and window dragging.
  - A background daemon thread runs `_run_cognitive_loop()`:
    1. Sets initial UI state: `bridge.notify_state("WATCHING", "Curious")` and welcome speech.
    2. If `--goal` was passed on CLI, emits `bridge.sig_goal_submitted.emit(goal)`.
    3. Loop until `self.stop_event.is_set()`:
       - **Pause check**: If `self._is_paused`, sleep 100ms.
       - **Physical interrupt check**: If `interrupt_guard.is_interrupted()`, sleep 100ms.
       - **Window guard check**: If active foreground window is protected/sensitive, emit `bridge.notify_state("PROTECTED", "Cautious")` and mask perception.
       - **Goal polling**: Poll `bridge.get_next_goal(timeout_sec=0.25)`.
         - When a goal arrives, execute iterative closed-loop steps via `pipeline.step(user_goal=goal)`.
         - On completion (`ActionType.DONE`), notify speech and return to idle.
         - On 3 repeated failures (`memory.is_in_loop()`), alert user and pause hands to prevent loops.
       - **Idle perception**: Every 1.5s during idle observation, capture screen thumbnail and emit `bridge.notify_perception()`.

#### E. Graceful Shutdown & Resource Cleanup (`shutdown()`)
- Guaranteed atomic and idempotent via `threading.Lock`:
  1. `self.stop_event.set()` to signal the cognitive worker thread.
  2. Join daemon thread with 2.0s timeout.
  3. Stop `interrupt_guard` to unhook Win32 `WH_MOUSE_LL` and `WH_KEYBOARD_LL` hooks via `UnhookWindowsHookEx`.
  4. Release any held mouse buttons (`mouse_driver.release_all_buttons()`).
  5. Emergency release any held keyboard keys (`keyboard_driver.emergency_release_keys()` / `release_all_keys()`).
  6. Close screen capture handle (`screen_capture.close()`).
  7. Clear targets and close `GhostHUD` overlay window.
  8. Close `CompanionDock` widget.

#### F. Windows Launcher Batch Script (`launch_parasite.bat`)
- Implementation requirements:
  - Set working directory to project root via `cd /d "%~dp0"`.
  - Validate Windows environment and search for `uv.exe` in `PATH`, `%USERPROFILE%\.cargo\bin\uv.exe`, and `%LOCALAPPDATA%\bin\uv.exe`.
  - Execute `uv sync` to ensure project virtual environment is synced.
  - Execute `uv run python main.py %*` forwarding all command-line arguments.
  - Preserve and return exit code via `exit /b %ERRORLEVEL%`.

---

## Proposed Code Structure

### 1. `parasite_ai/ui/dpi.py` Addition
```python
# Alias for backwards and interface compliance
init_dpi_awareness = init_high_dpi_awareness
```

### 2. `parasite_ai/main.py`
```python
"""
parasite_ai/main.py - Application Entry Point and Subsystem Coordinator.
Manages DPI awareness, Qt application lifecycle, cross-thread cognitive daemon,
clean Win32 exit handlers, and CLI options.
"""
from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Any, List, Optional

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import QApplication

from parasite_ai.config import AppConfig, load_config
from parasite_ai.hands.keyboard import KeyboardDriver
from parasite_ai.hands.mouse import MouseDriver
from parasite_ai.mind.brain_manager import LocalBrainManager
from parasite_ai.mind.dual_mind import DualMindPipeline
from parasite_ai.mind.memory import ActionType, EpisodicMemory
from parasite_ai.mind.offloader import BrowserOffloader
from parasite_ai.safety.interrupt_guard import InterruptGuard
from parasite_ai.safety.window_guard import WindowGuard
from parasite_ai.ui.bridge import UIBridge
from parasite_ai.ui.companion_dock import CompanionDock
from parasite_ai.ui.dpi import init_high_dpi_awareness
from parasite_ai.ui.ghost_hud import GhostHUD
from parasite_ai.vision.capture import ScreenCapture
from parasite_ai.vision.grounding import ScreenGrounder

logger = logging.getLogger("parasite_ai.main")

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="parasite",
        description="ParasiteAI - 100% visible, desktop-native local AI assistant operating on physical Windows desktop.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-c", "--config", dest="config_path", type=str, default=None, help="Path to config.yaml")
    parser.add_argument("--headless", action="store_true", default=False, help="Run in headless/offscreen mode.")
    parser.add_argument("--dry-run", action="store_true", default=False, help="Initialize subsystems, validate self-test, and exit 0.")
    parser.add_argument("--no-hud", action="store_true", default=False, help="Disable transparent GhostHUD overlay.")
    parser.add_argument("--brain-mode", choices=["local_llm", "browser_offload", "hybrid", "mock"], default=None, help="Override brain mode.")
    parser.add_argument("--goal", type=str, default=None, help="Initial goal to queue at startup.")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], default=None, help="Logging verbosity.")
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")
    return parser.parse_args(argv)

class ParasiteApp:
    ...
```

### 3. Root `main.py`
```python
"""
ParasiteAI - Top-level Application Entry Point.
"""
from __future__ import annotations

import sys
from parasite_ai.main import main

if __name__ == "__main__":
    sys.exit(main())
```

### 4. `launch_parasite.bat`
```batch
@echo off
setlocal EnableDelayedExpansion
title ParasiteAI Launcher

cd /d "%~dp0"

set "UV_EXE="
where uv >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    set "UV_EXE=uv"
) else if exist "%USERPROFILE%\.cargo\bin\uv.exe" (
    set "UV_EXE=%USERPROFILE%\.cargo\bin\uv.exe"
) else if exist "%LOCALAPPDATA%\bin\uv.exe" (
    set "UV_EXE=%LOCALAPPDATA%\bin\uv.exe"
)

if "!UV_EXE!"=="" (
    echo [ERROR] uv package manager was not found on PATH or standard install directories.
    echo Please install uv from: https://astral.sh/uv
    exit /b 1
)

echo [ParasiteAI] Synchronizing virtual environment...
"!UV_EXE!" sync
if !ERRORLEVEL! NEQ 0 (
    echo [ERROR] uv sync failed with exit code !ERRORLEVEL!.
    exit /b !ERRORLEVEL!
)

echo [ParasiteAI] Launching desktop assistant...
"!UV_EXE!" run python main.py %*
set "EXIT_CODE=!ERRORLEVEL!"
exit /b !EXIT_CODE!
```

---

## Test Plan (`tests/test_entrypoints.py`)
1. **CLI Parsing**:
   - `test_cli_defaults`: Default values matching specification.
   - `test_cli_custom_flags`: Correct parsing of `--config`, `--headless`, `--dry-run`, `--no-hud`, `--brain-mode`, `--goal`.
2. **DPI Initialization**:
   - `test_dpi_awareness_alias`: Verifies `init_dpi_awareness` matches `init_high_dpi_awareness`.
3. **Headless Application Lifecycle**:
   - `test_parasite_app_instantiation_headless`: Initializes in headless mode; checks all component references.
   - `test_parasite_app_dry_run`: Executes `--dry-run --headless`, asserting exit code 0 and complete resource cleanup.
   - `test_parasite_app_no_hud_flag`: Asserts `hud is None` when `--no-hud` is passed.
4. **Daemon & Cross-Thread Synchronization**:
   - `test_cognitive_daemon_goal_execution`: Tests goal submission through bridge, pipeline step trigger, and completion notification.
   - `test_cognitive_daemon_pause_handling`: Tests pause state halts execution.
5. **Clean Exit & Signal Handling**:
   - `test_graceful_shutdown_idempotency`: Calling `shutdown()` repeatedly is safe and idempotent.
   - `test_unhook_on_shutdown`: Confirms `interrupt_guard.stop()` is invoked and screen capture closed.
6. **Batch Script Validation**:
   - `test_launch_script_structure`: Verifies `launch_parasite.bat` exists, is non-empty, checks `uv`, syncs, and forwards `%*`.
