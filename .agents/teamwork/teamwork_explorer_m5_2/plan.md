# Implementation Plan: End-to-End Subsystem Wiring & Closed-Loop Integration

**Author**: `teamwork_explorer_m5_2`  
**Milestone**: Milestone M5 — Integration, Entry Points & E2E Acceptance  
**Target Module**: `parasite_ai/runtime.py`  
**Scope**: End-to-End closed-loop orchestration, signal hub wiring, lifecycle management, and safety synchronization.

---

## 1. Executive Summary & Architectural Overview

ParasiteAI requires a dedicated runtime orchestrator that bridges the PyQt6 GUI layer (`CompanionDock`, `GhostHUD`, `UIBridge`) on the main thread and the physical execution / cognitive pipeline (`DualMindPipeline`, `InterruptGuard`, `WindowGuard`, `MouseDriver`, `KeyboardDriver`, `ScreenCapture`, `ScreenGrounder`, `EpisodicMemory`, `LocalBrainManager`) on a background worker thread.

Prior to Milestone M5, all individual subsystems (M1 foundation, M2 safety & physical hands, M3 visible UI widgets, M4 cognition/memory/perception) were implemented and verified with 552 unit/adversarial tests passing. However, no centralized orchestrator class existed to manage the background thread lifecycle, dequeue submitted goals, execute multi-step episodes, synchronize hardware interrupts with UI state badges, coordinate window guard privacy blackouts, and trigger 3-strike loop recoveries.

This plan defines the architecture for `parasite_ai/runtime.py` (`RuntimeOrchestrator`), mapping all cross-thread signals, callbacks, and data transformations into a unified, thread-safe closed loop.

---

## 2. Comprehensive Subsystem Signal & Callback Matrix

| Signal / Callback Source | Destination Slot / Handler | Mechanism | Thread Boundary | Payload & Purpose |
|---|---|---|---|---|
| `CompanionDock.sig_goal_submitted` | `UIBridge.sig_goal_submitted` -> `_goal_queue.put` | Qt Signal -> Python Queue | GUI -> Thread-Safe Queue | User goal text string (`str`) |
| `UIBridge._goal_queue` | `RuntimeOrchestrator._worker_loop` | `bridge.get_next_goal(timeout)` | Worker Thread Dequeue | `str` goal dequeued for execution |
| `RuntimeOrchestrator` / `DualMindPipeline` | `UIBridge.notify_state` | Direct method call | Worker -> Bridge | `(state: str, mood: str)` |
| `UIBridge.sig_state_changed` | `CompanionDock.update_state` | Qt `QueuedConnection` | Worker -> GUI Thread | Accent glowing border, state badge (`WATCHING`, `THINKING`, `DRIVING`, `USER_OVERRIDE`, `PROTECTED`, `OFFLOADING`), mood badge |
| `PersonaEngine` (Pass 1) | `UIBridge.notify_thought` | Direct method call | Worker -> Bridge | Internal reasoning monologue string |
| `UIBridge.sig_thought_updated` | `CompanionDock.update_thought` | Qt `QueuedConnection` | Worker -> GUI Thread | Appends to scrollable thought stream |
| `PersonaEngine` (Pass 1) | `UIBridge.notify_speech` | Direct method call | Worker -> Bridge | Character dialogue speech string |
| `UIBridge.sig_speech_updated` | `CompanionDock.update_speech` | Qt `QueuedConnection` | Worker -> GUI Thread | Typewriter dialogue stream |
| `RuntimeOrchestrator` / `ActionDispatcher` | `UIBridge.notify_telemetry` | Direct method call | Worker -> Bridge | `(telemetry: str, current_step: int, total_steps: int)` |
| `UIBridge.sig_telemetry_updated` | `CompanionDock.update_telemetry` | Qt `QueuedConnection` | Worker -> GUI Thread | Step progress bar (% value) and active action label |
| `ScreenGrounder` / `DualMindPipeline` | `UIBridge.set_hud_targets` | Direct method call | Worker -> Bridge | `List[UIElement]` grounded Set-of-Mark items |
| `UIBridge.sig_targets_updated` | `GhostHUD.set_targets` | Qt `QueuedConnection` | Worker -> GUI Thread | Transparent numbered bounding boxes [#1..#N] |
| `ScreenCapture` / `DualMindPipeline` | `UIBridge.notify_perception` | Direct method call | Worker -> Bridge | Downscaled desktop screenshot + target list |
| `UIBridge.sig_perception_updated` | `CompanionDock.update_perception_preview` | Qt `QueuedConnection` | Worker -> GUI Thread | Desktop thumbnail or privacy blackout shield |
| `MouseDriver.click()` | `MouseDriver.reticle_callback` -> `bridge.show_reticle` | Callback function | Worker -> Bridge | `(x: int, y: int, duration_ms: int)` |
| `UIBridge.sig_reticle_requested` | `GhostHUD.show_reticle` | Qt `QueuedConnection` | Worker -> GUI Thread | Initiates 300ms animated targeting preview reticle |
| `InterruptGuard` (low-level hook) | `_on_interrupt_callback` | Function Callback | Win32 Hook Thread -> Worker/Bridge | Physical touch detected (`LLMHF_INJECTED=0` / `LLKHF_INJECTED=0`) |
| `RuntimeOrchestrator._on_interrupt` | `UIBridge.clear_reticle` & `notify_state` | Direct method call | Worker -> Bridge -> GUI | Instantly cancels GhostHUD reticle and sets dock to `USER_OVERRIDE` |
| `InterruptGuard` (panic manager) | `_on_panic_callback` | Function Callback | Win32 Hook Thread -> Worker/Bridge | Panic key (`Esc`, `Ctrl+Alt+P`, Corner Slam) tripped |
| `RuntimeOrchestrator._on_panic` | `panic()` & `bridge.notify_state` | Direct method call | Hook -> Worker -> GUI | Neutralizes hardware inputs, halts episode, sets `Panic-Averted` |
| `WindowGuard.is_safe_to_operate()` | `DualMindPipeline.step()` | Direct method call | Worker Thread Check | Returns `False` on sensitive window (password manager, admin console) |
| `DualMindPipeline` | `UIBridge.notify_state("PROTECTED", ...)` | Direct method call | Worker -> Bridge -> GUI | Triggers dock automatic privacy blackout and clears HUD targets |
| `CompanionDock.sig_pause_toggled` | `UIBridge.sig_pause_toggled` -> `RuntimeOrchestrator._on_pause_toggled` | Qt Signal -> Slot | GUI -> Worker | Toggles pause flag (`_is_paused: bool`) |
| `CompanionDock.sig_panic_triggered`| `UIBridge.sig_panic_triggered` -> `RuntimeOrchestrator._on_gui_panic` | Qt Signal -> Slot | GUI -> Worker | Triggers immediate abort and resets memory loop detector |
| `CompanionDock.sig_hud_toggled` | `UIBridge.sig_hud_toggled` -> `GhostHUD.setVisible` | Qt `QueuedConnection` | GUI -> GUI | Shows / hides fullscreen transparent HUD overlay |
| `CompanionDock.sig_brain_mode_changed`| `UIBridge.sig_brain_mode_changed` -> `RuntimeOrchestrator._on_brain_mode_changed` | Qt Signal -> Slot | GUI -> Worker | Switches `LocalBrainManager` between local GGUF, browser offload, and mock |

---

## 3. Detailed Trace of the 12 Closed-Loop Execution Stages

1. **Stage 1: Goal Submission & Enqueuing**
   - User types prompt in `CompanionDock`'s `goal_input` (e.g., "Search for weather") and presses Enter or clicks Send.
   - `CompanionDock._on_submit_goal()` emits `sig_goal_submitted(text)`.
   - `UIBridge._on_internal_goal_submitted(goal)` handles this slot on the Qt main thread and puts the goal into `self._goal_queue` (`queue.Queue[str]`).
   - `CompanionDock.goal_input` is cleared immediately, ready for subsequent input.

2. **Stage 2: Background Worker Dequeue & State Transition**
   - The background worker thread (`CognitiveWorkerThread`) polls `bridge.get_next_goal(timeout_sec=0.25)`.
   - When a goal arrives:
     - Worker sets active episode state: `bridge.notify_state("THINKING", "Focused")`.
     - Worker resets loop detector if starting a fresh goal: `memory.reset_loop_detector()`.
     - `CompanionDock` receives `sig_state_changed`, switching its pill badge to amber `● THINKING` with `[Focused]` mood.

3. **Stage 3: Perception & Hybrid Screen Grounding**
   - In `DualMindPipeline.step()`:
     - Captures desktop: `frame = capturer.capture_screen()` (MSS or PIL fallback).
     - Resolves interactive elements: `elements = screen_grounder.ground(image_override=frame)`.
     - Dispatches perception to UI:
       - `bridge.set_hud_targets(elements)` -> `GhostHUD` receives `sig_targets_updated` and schedules paint event, drawing neon Set-of-Mark boxes [#1..#N].
       - `bridge.notify_perception(frame, elements)` -> `CompanionDock` receives `sig_perception_updated` and updates the downscaled desktop thumbnail with target count.

4. **Stage 4: Pass 1 Persona Monologue Generation**
   - `PersonaEngine.generate_monologue(user_goal, scene_summary, memory_context)` is invoked.
   - Character thought and speech are derived from model output or structured template.
   - `bridge.notify_thought(thought)` emits `sig_thought_updated` -> appended to `thought_text` in CompanionDock.
   - `bridge.notify_speech(speech)` emits `sig_speech_updated` -> displayed in `dialogue_label` (with typewriter animation if `stream=True`).

5. **Stage 5: Pass 2 Action Planning & State Transition**
   - If `memory.is_in_loop()` is False:
     - Action Planner generates structured JSON action (`CLICK`, `TYPE`, `HOTKEY`, `WAIT`, `OFFLOAD_WEB_AI`, `DONE`).
     - Action is validated via Pydantic `ActionPlan`.
   - Driving state is resolved:
     - If action is `CLICK` / `TYPE` / `HOTKEY`: state = `DRIVING`, mood = `Focused`.
     - If action is `OFFLOAD_WEB_AI`: state = `OFFLOADING`, mood = `Focused`.
     - If action is `WAIT` / `DONE`: state = `WATCHING`, mood = `Amused`.
   - `bridge.notify_state(state, mood)` updates CompanionDock card accent and glowing border to crimson `● DRIVING`.

6. **Stage 6: Target Resolution & 300ms Pre-Click Reticle on GhostHUD**
   - For coordinate-targeted actions (`CLICK`, `DOUBLE_CLICK`, `RIGHT_CLICK`, `CLICK_AND_TYPE`):
     - `ActionDispatcher.resolve_target(action, elements)` matches `target_id` against grounded element list to find `(center_x, center_y)`.
     - Validates coordinates against virtual desktop bounds.
   - `MouseDriver.click()` is invoked with `cancellation_token=token`.
   - Because `MouseDriver` is initialized with `reticle_callback=bridge.show_reticle`:
     - Calls `self.reticle_callback(target_x, target_y, 300)`.
     - Emits `bridge.sig_reticle_requested(target_x, target_y, 300, target_id, label)`.
     - `GhostHUD.show_reticle()` starts 60 FPS animation timer, painting bracket corners, crosshairs, and countdown banner `Aiming: Click in 300ms`.

7. **Stage 7: Sub-2ms Hardware Interrupt Check & Kinematic Mouse Movement**
   - `MouseDriver` waits `preview_reticle_ms` (300ms) interruptibly using `cancellation_token.wait(timeout=0.3)`.
   - If no physical touch occurs:
     - Generates 120Hz trajectory using `KinematicsEngine.generate_trajectory()` (Cubic Bézier, Min-Jerk velocity profile, micro-jitter, terminal overshoot).
     - Traverses waypoints with 1ms high-resolution timer (`timeBeginPeriod(1)`).
     - At every single waypoint step, tests `cancellation_token.is_set()`.
     - Upon landing at target, performs `mouse_down` -> 40ms dwell -> `mouse_up`.

8. **Stage 8: Settling, Screen Diff & Episodic Memory Recording**
   - Post-action settling delay (50ms).
   - Post-action screen capture: `post_frame = capturer.capture_screen()`.
   - Screen difference computed:
     - Pixel diff ratio: `compute_pixel_diff(frame, post_frame)`.
     - Perceptual hash: `compute_dhash(post_frame)`.
   - Recorded into `EpisodicMemory`:
     - `step_record = memory.record_step(action, success, screen_diff, ...)`
     - Evaluates strike: If interactive action had `success=False` OR `screen_diff < 0.02`, increments `_consecutive_strikes`. Otherwise resets strikes to 0.

9. **Stage 9: Step Telemetry & Progress Bar Update**
   - Telemetry string formatted: e.g., `"Step 2/10: Executing CLICK [#3] 'Submit'"`.
   - `bridge.notify_telemetry(telemetry_str, current_step=2, total_steps=10)` emitted.
   - `CompanionDock.update_telemetry` updates `step_label` ("Step: 2/10") and `step_progress` (20%).

10. **Stage 10: 3-Strike Failure Loop Emergency Reset**
    - If `memory.is_in_loop()` reaches True (`consecutive_strikes >= 3`):
      - In next step, `DualMindPipeline.step()` automatically overrides action with `ActionType.PANIC`.
      - `ActionDispatcher` triggers `bridge.sig_panic_triggered.emit()`.
      - Character mood derives `"Panic-Averted"`.
      - Companion monologue announces loop detection and pauses for guidance.
      - Reticle and targets cleared on `GhostHUD`.

11. **Stage 11: Physical Hardware Touch Interruption (< 2ms)**
    - If user touches physical mouse or keyboard during synthetic action:
      - Win32 low-level hook (`WH_MOUSE_LL` / `WH_KEYBOARD_LL`) inspects flags: `LLMHF_INJECTED == 0` or `LLKHF_INJECTED == 0`.
      - `InterruptGuard` immediately sets atomic `_cancellation_token`.
      - Active `MouseDriver` or `KeyboardDriver` loop aborts in < 2ms, calling `release_all_buttons()`.
      - `InterruptGuard` invokes `on_interrupt_callback`.
      - Orchestrator signals `bridge.clear_reticle()` and `bridge.notify_state("USER_OVERRIDE", "Curious")`.
      - CompanionDock turns cyan `● OVERRIDE`.
      - Sliding cooldown timer (10s) starts. When expired, re-arms system to `WATCHING`.

12. **Stage 12: Sensitive Window Detection & Privacy Blackout**
    - `WindowGuard.is_safe_to_operate()` queries active foreground window.
    - If process is in blacklist (`bitwarden.exe`, `1password.exe`, `taskmgr.exe`, `consent.exe`) or title is sensitive or process is elevated admin:
      - Returns `False`.
      - `DualMindPipeline.step()` skips perception inspection and hands invocation.
      - Sets state `bridge.notify_state("PROTECTED", "Cautious")`.
      - `CompanionDock` automatically engages privacy blackout shield:
        Renders solid black rectangle with `"🔒 SENSITIVE WINDOW ACTIVE\nVISION MASKED"` and sets grounding badge to `[PAUSED — SENSITIVE]`.
      - `bridge.clear_hud_targets()` clears GhostHUD so no overlay elements appear over the sensitive application.

---

## 4. Class Design: `RuntimeOrchestrator` (`parasite_ai/runtime.py`)

```python
"""
parasite_ai/runtime.py - Central Runtime Orchestrator & Closed-Loop Runner.

Coordinates the lifecycle and cross-thread communications between:
1. PyQt6 UI Layer (CompanionDock, GhostHUD, UIBridge) on the GUI thread.
2. Cognitive & Hand Execution (DualMindPipeline, Hand Drivers, Screen Grounding,
   LocalBrainManager, EpisodicMemory) on a dedicated background worker thread.
3. Win32 Low-Level Safety Guards (InterruptGuard, WindowGuard) on native hook threads.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np
from PyQt6.QtCore import QObject, Qt, pyqtSlot
from PyQt6.QtGui import QImage

from parasite_ai.config import AppConfig
from parasite_ai.hands.keyboard import KeyboardDriver, MockInputBackend
from parasite_ai.hands.mouse import MouseDriver
from parasite_ai.mind.brain_manager import BrainMode, LocalBrainManager
from parasite_ai.mind.dual_mind import DualMindPipeline
from parasite_ai.mind.memory import ActionPlan, ActionType, EpisodicMemory, StepRecord
from parasite_ai.mind.offloader import BrowserOffloader
from parasite_ai.safety.interrupt_guard import InterruptGuard
from parasite_ai.safety.window_guard import WindowGuard
from parasite_ai.ui.bridge import UIBridge
from parasite_ai.ui.types import UIElement
from parasite_ai.vision.capture import ScreenCapture
from parasite_ai.vision.grounding import ScreenGrounder

logger = logging.getLogger("parasite_ai.runtime")


def ndarray_to_qimage(frame: Optional[np.ndarray]) -> QImage:
    """Safely converts a numpy image array (H, W, 3) to a detached PyQt6 QImage."""
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


class RuntimeOrchestrator(QObject):
    """
    Master Runtime Orchestrator binding all ParasiteAI subsystems into a closed loop.
    """

    def __init__(
        self,
        config: Optional[AppConfig] = None,
        bridge: Optional[UIBridge] = None,
        simulation_mode: bool = False,
        headless: bool = False,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self.config = config or AppConfig()
        self.bridge = bridge or UIBridge()
        self.simulation_mode = simulation_mode
        self.headless = headless

        # Operational Flags
        self._is_running = False
        self._is_paused = False
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None

        # 1. Instantiate Safety Guards
        self.interrupt_guard = InterruptGuard(
            cooldown_seconds=self.config.safety.interrupt_cooldown_seconds,
            corner_panic_enabled=self.config.safety.corner_panic_enabled,
            corner_distance_px=self.config.safety.corner_distance_px,
            on_interrupt_callback=self._on_hardware_interrupt,
            on_panic_callback=self._on_hardware_panic,
            on_rearm_callback=self._on_hardware_rearm,
        )
        self.window_guard = WindowGuard(config=self.config.safety)

        # 2. Instantiate Hand Drivers
        self.mouse_driver = MouseDriver(
            config=self.config.hands.mouse,
            reticle_callback=self._on_reticle_requested,
            simulation_mode=self.simulation_mode,
        )
        self.keyboard_driver = KeyboardDriver(
            config=self.config.hands.keyboard,
            backend=MockInputBackend() if self.simulation_mode else None,
        )

        # 3. Instantiate Perception Subsystems
        self.screen_capture = ScreenCapture()
        self.screen_grounder = ScreenGrounder(config=self.config.vision)

        # 4. Instantiate Cognition Subsystems
        self.brain_manager = LocalBrainManager(config=self.config)
        self.browser_offloader = BrowserOffloader(
            config=self.config.brain.browser_offload,
            bridge=self.bridge,
            mouse_driver=self.mouse_driver,
            keyboard_driver=self.keyboard_driver,
        )
        self.memory = EpisodicMemory(
            capacity=self.config.memory.ring_buffer_capacity if hasattr(self.config, "memory") else 20,
            strike_limit=3,
        )

        # 5. Instantiate Dual-Mind Pipeline
        self.pipeline = DualMindPipeline(
            brain_manager=self.brain_manager,
            memory=self.memory,
            mouse_driver=self.mouse_driver,
            keyboard_driver=self.keyboard_driver,
            screen_grounder=self.screen_grounder,
            capturer=self.screen_capture,
            interrupt_guard=self.interrupt_guard,
            window_guard=self.window_guard,
            bridge=self.bridge,
            offloader=self.browser_offloader,
            config=self.config,
        )

        # 6. Wire GUI Bridge Signal Listeners
        self._wire_bridge_signals()

    def _wire_bridge_signals(self) -> None:
        """Connects signals emitted from GUI controls to runtime handlers."""
        self.bridge.sig_pause_toggled.connect(self._on_gui_pause_toggled)
        self.bridge.sig_panic_triggered.connect(self._on_gui_panic_triggered)
        self.bridge.sig_brain_mode_changed.connect(self._on_gui_brain_mode_changed)

    # -----------------------------------------------------------------------
    # Lifecycle Management
    # -----------------------------------------------------------------------

    def start(self) -> None:
        """Starts background worker thread and hooks."""
        if self._is_running:
            return
        self._is_running = True
        self._stop_event.clear()

        # Start low-level hook thread (unless simulated in CI)
        if not self.simulation_mode and not self.headless:
            try:
                self.interrupt_guard.start()
            except Exception as exc:
                logger.warning(f"Could not start native Win32 hardware hooks: {exc}")

        # Start Cognitive Worker Thread
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            name="ParasiteCognitiveWorker",
            daemon=True,
        )
        self._worker_thread.start()

        # Notify initial GUI state
        self.bridge.notify_state("WATCHING", "Curious")
        self.bridge.notify_telemetry("Ready for user goal")

    def stop(self, timeout_sec: float = 2.0) -> None:
        """Gracefully halts worker thread, unhooks Win32 hooks, and neutralizes hands."""
        if not self._is_running:
            return
        self._is_running = False
        self._stop_event.set()

        # Signal cancellation token to wake up any sleeping or moving drivers
        token = self.interrupt_guard.get_cancellation_token()
        token.set()

        # Stop interrupt guard
        try:
            self.interrupt_guard.stop()
        except Exception:
            pass

        # Neutralize any pressed buttons/keys
        self._neutralize_inputs()

        # Clear HUD overlay
        self.bridge.clear_reticle()
        self.bridge.clear_hud_targets()

        # Join worker thread
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=timeout_sec)
            self._worker_thread = None

    def _neutralize_inputs(self) -> None:
        """Releases all mouse buttons and keys."""
        try:
            self.mouse_driver.release_all_buttons()
        except Exception:
            pass
        try:
            self.keyboard_driver.emergency_release_keys()
        except Exception:
            pass

    # -----------------------------------------------------------------------
    # Background Cognitive Worker Loop
    # -----------------------------------------------------------------------

    def _worker_loop(self) -> None:
        """Main loop dequeuing goals and executing closed-loop episodes."""
        logger.info("Cognitive worker loop started.")
        while not self._stop_event.is_set():
            goal = self.bridge.get_next_goal(timeout_sec=0.25)
            if goal is None or self._stop_event.is_set():
                continue

            self._execute_goal_episode(goal)

        logger.info("Cognitive worker loop terminated.")

    def _execute_goal_episode(self, goal: str, max_steps: int = 15) -> None:
        """Executes a multi-step goal until completion, panic, loop, or max steps."""
        logger.info(f"Beginning goal episode: '{goal}'")
        self.bridge.notify_state("THINKING", "Focused")
        self.bridge.notify_telemetry(f"Starting goal: {goal}", 0, max_steps)

        for step_idx in range(1, max_steps + 1):
            if self._stop_event.is_set():
                break

            # Handle Paused State
            while self._is_paused and not self._stop_event.is_set():
                self.bridge.notify_telemetry("Hands paused by user", step_idx, max_steps)
                time.sleep(0.2)

            if self._stop_event.is_set():
                break

            # Handle Hardware Override State
            if self.interrupt_guard.is_interrupted():
                logger.info("Hardware touch active, waiting for cooldown...")
                self.bridge.notify_state("USER_OVERRIDE", "Curious")
                while self.interrupt_guard.is_interrupted() and not self._stop_event.is_set():
                    time.sleep(0.2)
                if self._stop_event.is_set():
                    break
                self.bridge.notify_state("THINKING", "Focused")

            # Handle Sensitive Window Protection
            if not self.window_guard.is_safe_to_operate():
                logger.warning("Active window is sensitive/protected. Pausing observation.")
                self.bridge.notify_state("PROTECTED", "Cautious")
                self.bridge.clear_hud_targets()
                while not self.window_guard.is_safe_to_operate() and not self._stop_event.is_set():
                    time.sleep(0.5)
                if self._stop_event.is_set():
                    break
                self.bridge.notify_state("THINKING", "Focused")

            # Execute Atomic Cognitive Step
            self.bridge.notify_telemetry(f"Step {step_idx}/{max_steps}: Perceiving & Reasoning", step_idx, max_steps)
            step_record = self.pipeline.step(user_goal=goal)

            action_type = step_record.action.action
            logger.info(f"Step {step_idx} executed: {action_type} (success={step_record.success})")

            # 1. Done Condition
            if action_type == ActionType.DONE:
                self.bridge.notify_speech("I've completed your goal!")
                self.bridge.notify_state("WATCHING", "Amused")
                self.bridge.notify_telemetry("Goal completed successfully!", max_steps, max_steps)
                break

            # 2. Panic Condition
            if action_type == ActionType.PANIC or self.interrupt_guard.is_panic():
                self.bridge.notify_speech("Emergency abort triggered! Backing off.")
                self.bridge.notify_state("WATCHING", "Panic-Averted")
                self.bridge.notify_telemetry("Goal aborted by emergency panic", step_idx, max_steps)
                break

            # 3. Cognitive Loop Detection
            if self.memory.is_in_loop():
                self.bridge.notify_speech("I noticed we're repeating actions without screen change. Pausing.")
                self.bridge.notify_state("WATCHING", "Panic-Averted")
                self.bridge.notify_telemetry("Paused: 3 consecutive failure strikes detected", step_idx, max_steps)
                break

            # Settle delay between steps
            time.sleep(0.1)

        # Episode Teardown & Return to Watching
        self.bridge.clear_hud_targets()
        self.bridge.clear_reticle()
        if not self._stop_event.is_set() and not self.interrupt_guard.is_panic():
            self.bridge.notify_state("WATCHING", "Curious")
            self.bridge.notify_telemetry("Ready for next goal")

    # -----------------------------------------------------------------------
    # Synchronous Step Execution (Unit & Integration Testing API)
    # -----------------------------------------------------------------------

    def run_single_step(
        self,
        goal: str,
        screen_frame: Optional[np.ndarray] = None,
        grounded_elements: Optional[List[UIElement]] = None,
        override_action: Optional[ActionPlan] = None,
    ) -> StepRecord:
        """Executes one deterministic closed-loop step synchronously."""
        return self.pipeline.step(
            user_goal=goal,
            screen_frame=screen_frame,
            grounded_elements=grounded_elements,
            override_action=override_action,
        )

    # -----------------------------------------------------------------------
    # Callbacks & Signal Handlers
    # -----------------------------------------------------------------------

    def _on_reticle_requested(self, x: int, y: int, duration_ms: int) -> None:
        """Dispatches pre-click reticle request to GhostHUD via UIBridge."""
        self.bridge.show_reticle(x, y, duration_ms)

    def _on_hardware_interrupt(self, reason: str) -> None:
        """Invoked when physical human touch preempts synthetic movement."""
        logger.warning(f"Hardware interrupt detected: {reason}")
        self.bridge.clear_reticle()
        self.bridge.notify_state("USER_OVERRIDE", "Curious")
        self.bridge.notify_telemetry(f"Physical touch override: {reason}")

    def _on_hardware_panic(self, reason: str) -> None:
        """Invoked when emergency panic hotkey/trigger trips."""
        logger.critical(f"Global panic abort detected: {reason}")
        self._neutralize_inputs()
        self.bridge.clear_reticle()
        self.bridge.clear_hud_targets()
        self.bridge.notify_state("WATCHING", "Panic-Averted")
        self.bridge.notify_telemetry(f"EMERGENCY PANIC: {reason}")

    def _on_hardware_rearm(self) -> None:
        """Invoked when hardware interrupt cooldown expires."""
        logger.info("Hardware interrupt cooldown elapsed. System re-armed.")
        self.bridge.notify_state("WATCHING", "Curious")
        self.bridge.notify_telemetry("Re-armed: Ready for goals")

    @pyqtSlot(bool)
    def _on_gui_pause_toggled(self, is_paused: bool) -> None:
        """Handles Pause Hands toggle from CompanionDock button."""
        self._is_paused = is_paused
        logger.info(f"Hands pause state updated: {is_paused}")
        if is_paused:
            self.bridge.notify_state("WATCHING", "Curious")
            self.bridge.notify_telemetry("Hands paused by user")
        else:
            self.bridge.notify_telemetry("Hands resumed by user")

    @pyqtSlot()
    def _on_gui_panic_triggered(self) -> None:
        """Handles PANIC click from CompanionDock."""
        logger.critical("PANIC triggered via GUI button.")
        self._neutralize_inputs()
        self.interrupt_guard.panic_manager.trigger_panic("GUI PANIC button")
        self._on_hardware_panic("GUI button")

    @pyqtSlot(str)
    def _on_gui_brain_mode_changed(self, mode: str) -> None:
        """Handles Brain Mode selection change from CompanionDock ComboBox."""
        logger.info(f"Brain mode selection updated: {mode}")
        clean_mode = mode.lower()
        if "browser" in clean_mode:
            self.brain_manager.toggle_browser_only_mode(True)
        elif "local" in clean_mode:
            self.brain_manager.toggle_browser_only_mode(False)
        elif "mock" in clean_mode:
            self.brain_manager.mode = BrainMode.MOCK
```

---

## 5. Perception Preview NumPy Compatibility Enhancement

In `parasite_ai/ui/companion_dock.py`:
Currently, `update_perception_preview(frame_data, elements)` checks:
```python
if isinstance(frame_data, QPixmap):
    pixmap = frame_data
elif isinstance(frame_data, QImage):
    pixmap = QPixmap.fromImage(frame_data)
```
When `ScreenCapture.capture_screen()` returns a `np.ndarray`, `pixmap` evaluates to `None`, displaying "No Frame Available".
The worker should enrich `update_perception_preview` to support `np.ndarray` input directly:
```python
elif hasattr(frame_data, "shape") and len(frame_data.shape) >= 2:
    qimg = ndarray_to_qimage(frame_data)
    if not qimg.isNull():
        pixmap = QPixmap.fromImage(qimg)
```
This ensures zero friction whether callers pass `QPixmap`, `QImage`, or raw `np.ndarray`.

---

## 6. Verification and Acceptance Criteria

1. **Unit & Cross-Thread Integration Verification**:
   - `uv run pytest tests/test_ui_bridge.py` passes 100%.
   - `uv run pytest tests/test_dual_mind.py` passes 100%.
   - New `tests/test_runtime.py` verifies:
     - Startup & shutdown lifecycle (worker thread joins cleanly, hooks unhook).
     - Goal submission -> dequeue -> step execution -> telemetry update -> loop completion.
     - Physical hardware touch interrupt -> cancellation token set in <2ms -> dock transitions to `USER_OVERRIDE` -> reticle cleared.
     - Sensitive window foreground -> WindowGuard flags unsafe -> dock transitions to `PROTECTED` -> perception masked -> actions paused.
     - 3-strike failure loop -> loop detector flags loop -> PANIC action override -> dock transitions to `Panic-Averted`.
     - Pause Hands toggle -> background execution suspended.
     - Brain mode change -> delegates to `LocalBrainManager`.
2. **Full Regression Suite**:
   - `uv run pytest` runs with 0 failures across all 552+ tests.
