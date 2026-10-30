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
from parasite_ai.ui.companion_dock import ndarray_to_qimage
from parasite_ai.ui.types import UIElement
from parasite_ai.vision.capture import ScreenCapture
from parasite_ai.vision.grounding import ScreenGrounder

logger = logging.getLogger("parasite_ai.runtime")


class RuntimeOrchestrator(QObject):
    """
    Master Runtime Orchestrator binding all ParasiteAI subsystems into a closed loop.
    Coordinates GUI events, background cognition, physical input dispatch, and
    Win32 hardware hook safety.
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
        self._is_running: bool = False
        self._is_paused: bool = False
        self._is_in_cognitive_step: bool = False
        self._last_single_step_goal: Optional[str] = None
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None

        # 1. Instantiate Safety Guards
        self.interrupt_guard = InterruptGuard(
            cooldown_seconds=self.config.safety.override_pause_duration_sec,
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
        self.screen_capture = ScreenCapture(backend=self.config.vision.capture_backend)
        self.screen_grounder = ScreenGrounder(
            config=self.config.vision,
            capturer=self.screen_capture,
        )

        # 4. Instantiate Cognition Subsystems
        self.browser_offloader = BrowserOffloader(
            config=self.config.brain.offload,
            bridge=self.bridge,
            mouse_driver=self.mouse_driver,
            keyboard_driver=self.keyboard_driver,
            grounder=self.screen_grounder,
        )
        self.brain_manager = LocalBrainManager(
            config=self.config,
            offloader=self.browser_offloader,
        )
        # 5. Instantiate Dual-Mind Pipeline & bind EpisodicMemory
        self.pipeline = DualMindPipeline(
            brain_manager=self.brain_manager,
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
        self.memory = self.pipeline.memory

        # 6. Wire Bridge Signal Listeners
        self._wire_bridge_signals()

    @property
    def is_running(self) -> bool:
        """Returns True if background worker thread is active."""
        return self._is_running

    @property
    def is_paused(self) -> bool:
        """Returns True if actions are currently paused by the user."""
        return self._is_paused

    def _wire_bridge_signals(self) -> None:
        """Connects signals emitted from GUI controls to runtime handlers."""
        self.bridge.sig_pause_toggled.connect(self._on_gui_pause_toggled)
        self.bridge.sig_panic_triggered.connect(self._on_gui_panic_triggered)
        self.bridge.sig_brain_mode_changed.connect(self._on_gui_brain_mode_changed)

    # -----------------------------------------------------------------------
    # Lifecycle Management
    # -----------------------------------------------------------------------

    def start(self) -> None:
        """Starts background worker thread and low-level hardware hooks."""
        if self._is_running:
            return
        self._is_running = True
        self._stop_event.clear()

        # Start low-level hook thread (unless simulated in CI / headless)
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

    def stop(self, timeout_sec: float = 6.0) -> None:
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

        # Close screen capture resources
        try:
            self.screen_capture.close()
        except Exception:
            pass

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
        last_idle_scan = 0.0
        while not self._stop_event.is_set():
            goal = self.bridge.get_next_goal(timeout_sec=0.25)
            if goal is None or self._stop_event.is_set():
                if (
                    not self.simulation_mode
                    and not self.headless
                    and not self._is_paused
                    and not self._stop_event.is_set()
                    and (time.time() - last_idle_scan) >= 1.0
                ):
                    last_idle_scan = time.time()
                    try:
                        if not self.window_guard.is_safe_to_operate():
                            self.bridge.notify_state("PROTECTED", "Cautious")
                            self.bridge.clear_hud_targets()
                        else:
                            frame = self.screen_capture.capture_screen()
                            elems = self.screen_grounder.ground(image_override=frame)
                            self.bridge.notify_perception(frame, elems)
                            self.bridge.set_hud_targets(elems)
                    except Exception as exc:
                        logger.debug("Idle perception refresh skipped: %s", exc)
                continue

            try:
                self.memory.reset_loop_detector()
                self._execute_goal_episode(goal)
            except Exception as exc:
                logger.critical(
                    f"Unhandled exception during goal episode '{goal}': {exc}",
                    exc_info=True,
                )
                self._neutralize_inputs()
                self.bridge.clear_hud_targets()
                self.bridge.clear_reticle()
                self.bridge.notify_speech(f"An internal error occurred: {exc}")
                self.bridge.notify_state("WATCHING", "Curious")
                self.bridge.notify_telemetry(f"Episode aborted due to internal error: {exc}")

        logger.info("Cognitive worker loop terminated.")

    def _execute_goal_episode(self, goal: str, max_steps: int = 15) -> None:
        """Executes a multi-step goal until completion, panic, loop, or max steps."""
        logger.info(f"Beginning goal episode: '{goal}'")

        # 0. If recovering from previous hardware/GUI panic, re-arm on new goal
        if self.interrupt_guard.is_panic():
            logger.info("New goal received post-panic; auto re-arming system.")
            self.reset_panic()

        self.bridge.notify_state("THINKING", "Focused")
        self.bridge.notify_telemetry(f"Starting goal: {goal}", 0, max_steps)
        was_panic_or_loop = False

        for step_idx in range(1, max_steps + 1):
            if self._stop_event.is_set():
                break

            # 1. Handle Paused State
            while self._is_paused and not self._stop_event.is_set():
                self.bridge.notify_telemetry("Hands paused by user", step_idx, max_steps)
                time.sleep(0.2)

            if self._stop_event.is_set():
                break

            # 2. Handle Hardware Override State
            if self.interrupt_guard.is_interrupted():
                logger.info("Hardware touch active, waiting for cooldown...")
                self.bridge.notify_state("USER_OVERRIDE", "Curious")
                while self.interrupt_guard.is_interrupted() and not self._stop_event.is_set():
                    time.sleep(0.2)
                if self._stop_event.is_set():
                    break
                self.bridge.notify_state("THINKING", "Focused")

            # 3. Handle Sensitive Window Protection
            if not self.window_guard.is_safe_to_operate():
                logger.warning("Active window is sensitive/protected. Pausing observation.")
                self.bridge.notify_state("PROTECTED", "Cautious")
                self.bridge.clear_hud_targets()
                while not self.window_guard.is_safe_to_operate() and not self._stop_event.is_set():
                    time.sleep(0.5)
                if self._stop_event.is_set():
                    break
                self.bridge.notify_state("THINKING", "Focused")

            # 4. Execute Atomic Cognitive Step with Error Boundary
            self.bridge.notify_telemetry(f"Step {step_idx}/{max_steps}: Perceiving & Reasoning", step_idx, max_steps)
            self._is_in_cognitive_step = True
            try:
                step_record = self.pipeline.step(user_goal=goal)
            except Exception as exc:
                logger.error(f"Step {step_idx} failed with unhandled exception: {exc}", exc_info=True)
                self.bridge.notify_speech(f"An internal error occurred: {exc}")
                self.bridge.notify_state("WATCHING", "Curious")
                self.bridge.notify_telemetry(f"Step error: {exc}", step_idx, max_steps)
                break
            finally:
                self._is_in_cognitive_step = False

            action_type = step_record.action.action
            logger.info(f"Step {step_idx} executed: {action_type} (success={step_record.success})")

            # Terminal / Special States:
            # Done Condition
            if action_type == ActionType.DONE:
                self.bridge.notify_speech("I've completed your goal!")
                self.bridge.notify_state("WATCHING", "Amused")
                self.bridge.notify_telemetry("Goal completed successfully!", max_steps, max_steps)
                break

            # Panic Condition
            if action_type == ActionType.PANIC or self.interrupt_guard.is_panic():
                was_panic_or_loop = True
                self.bridge.notify_speech("Emergency abort triggered! Backing off.")
                self.bridge.notify_state("WATCHING", "Panic-Averted")
                self.bridge.notify_telemetry("Goal aborted by emergency panic", step_idx, max_steps)
                break

            # Cognitive Loop Detection (3-strike failure loop)
            if self.memory.is_in_loop():
                was_panic_or_loop = True
                self.bridge.notify_speech("I noticed we're repeating actions without screen change. Pausing.")
                self.bridge.notify_state("WATCHING", "Panic-Averted")
                self.bridge.notify_telemetry("Paused: 3 consecutive failure strikes detected", step_idx, max_steps)
                break

            # Settle delay between steps
            time.sleep(0.1)

        # Episode Teardown & Reset Loop Detector
        self.memory.reset_loop_detector()
        self.bridge.clear_hud_targets()
        self.bridge.clear_reticle()
        if not self._stop_event.is_set() and not self.interrupt_guard.is_panic() and not was_panic_or_loop:
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
        if hasattr(self, "_last_single_step_goal") and self._last_single_step_goal != goal:
            self.memory.reset_loop_detector()
        self._last_single_step_goal = goal

        self._is_in_cognitive_step = True
        try:
            return self.pipeline.step(
                user_goal=goal,
                screen_frame=screen_frame,
                grounded_elements=grounded_elements,
                override_action=override_action,
            )
        finally:
            self._is_in_cognitive_step = False

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
        self.bridge.clear_goals()
        self.bridge.clear_reticle()
        self.bridge.clear_hud_targets()
        self.bridge.notify_state("WATCHING", "Panic-Averted")
        self.bridge.notify_telemetry(f"EMERGENCY PANIC: {reason}")

    def reset_panic(self) -> None:
        """Resets emergency panic state, clears tokens, and re-arms interrupt guard."""
        logger.info("Resetting emergency panic state and re-arming.")
        self.interrupt_guard.reset_interrupt()
        self.memory.reset_loop_detector()
        self.bridge.notify_state("WATCHING", "Curious")
        self.bridge.notify_telemetry("Re-armed: Ready for goals")

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
        token = self.interrupt_guard.get_cancellation_token()
        if is_paused:
            token.set()
            self._neutralize_inputs()
            self.bridge.clear_reticle()
            self.bridge.notify_state("WATCHING", "Curious")
            self.bridge.notify_telemetry("Hands paused by user")
        else:
            token.clear()
            self.bridge.notify_telemetry("Hands resumed by user")

    @pyqtSlot()
    def _on_gui_panic_triggered(self) -> None:
        """Handles PANIC signal from GUI button or cognitive pipeline."""
        if getattr(self, "_is_in_cognitive_step", False):
            # Cognitive loop panic: Decoupled from hardware PanicManager!
            logger.warning("Cognitive strategy reset triggered by 3-strike loop.")
            self._neutralize_inputs()
            self.bridge.clear_reticle()
            self.bridge.clear_hud_targets()
            self.bridge.notify_state("WATCHING", "Panic-Averted")
            self.bridge.notify_telemetry("Cognitive loop: strategy reset")
            return

        logger.critical("PANIC triggered via GUI button.")
        self.bridge.clear_goals()
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
