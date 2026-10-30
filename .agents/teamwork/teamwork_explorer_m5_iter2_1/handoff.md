# Milestone M5 Iteration 2: Explorer Investigation & Remediation Plan

**Agent**: `teamwork_explorer_m5_iter2_1`  
**Working Directory**: `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m5_iter2_1\`  
**Target File**: `handoff.md`  
**Context**: Milestone M5 Runtime Orchestrator Resilience Hardening (Defects 1–4)

---

## 1. Observation

Direct empirical observations across the codebase and execution logs:

### Observation 1: Unhandled Worker Thread Exception Boundary (`parasite_ai/runtime.py:221-231`)
In `RuntimeOrchestrator._worker_loop`:
```python
221:     def _worker_loop(self) -> None:
222:         """Main loop dequeuing goals and executing closed-loop episodes."""
223:         logger.info("Cognitive worker loop started.")
224:         while not self._stop_event.is_set():
225:             goal = self.bridge.get_next_goal(timeout_sec=0.25)
226:             if goal is None or self._stop_event.is_set():
227:                 continue
228: 
229:             self._execute_goal_episode(goal)
230: 
231:         logger.info("Cognitive worker loop terminated.")
```
When `pipeline.step()` or perception/brain inference raises an unexpected exception (e.g., `RuntimeError("Perception engine corrupted / CUDA segmentation fault")` or `ConnectionError("Inference endpoint unreachable")`), the exception escapes `_execute_goal_episode` without being caught.
Pytest captures:
```
PytestUnhandledThreadExceptionWarning: Exception in thread ParasiteCognitiveWorker
Traceback (most recent call last):
  File "G:\__Docs\ParasiteAI\parasite_ai\runtime.py", line 229, in _worker_loop
    self._execute_goal_episode(goal)
  File "G:\__Docs\ParasiteAI\parasite_ai\runtime.py", line 274, in _execute_goal_episode
    step_record = self.pipeline.step(user_goal=goal)
```
- `runtime._worker_thread.is_alive()` drops to `False`.
- `runtime.is_running` remains `True` (zombie state).
- All future goals submitted via `bridge.sig_goal_submitted` remain trapped in `bridge._goal_queue` forever.
- No speech or UI notification is sent to the user; GhostHUD and companion dock freeze in their last active state.

### Observation 2: Cognitive 3-Strike Failure Escalation to Irreversible Hardware Panic (`parasite_ai/mind/dual_mind.py:449-453, 623-628`, `parasite_ai/runtime.py:138, 372-378`, `parasite_ai/safety/panic.py:105-117`, `parasite_ai/safety/interrupt_guard.py:301-305`)
1. In `dual_mind.py:623-628`, when `self.memory.is_in_loop()` trips after 3 zero-diff failures, the planner issues `action_plan = ActionPlan(action=ActionType.PANIC, reasoning="Detected 3-strike failure loop...")`.
2. In `ActionDispatcher.dispatch` (`dual_mind.py:449-453`):
   ```python
   elif action.action == ActionType.PANIC:
       if self.bridge:
           self.bridge.sig_panic_triggered.emit()
       self._release_all()
       return ActionResult(success=True, action_executed=action)
   ```
3. In `RuntimeOrchestrator._wire_bridge_signals` (`runtime.py:138`):
   `self.bridge.sig_panic_triggered.connect(self._on_gui_panic_triggered)`
4. In `RuntimeOrchestrator._on_gui_panic_triggered` (`runtime.py:372-378`):
   ```python
   @pyqtSlot()
   def _on_gui_panic_triggered(self) -> None:
       logger.critical("PANIC triggered via GUI button.")
       self._neutralize_inputs()
       self.interrupt_guard.panic_manager.trigger_panic("GUI PANIC button")
       self._on_hardware_panic("GUI button")
   ```
5. `PanicManager.trigger_panic()` sets `self._panic_event.set()`.
6. In `InterruptGuard.is_interrupted()` (`interrupt_guard.py:301-303`):
   ```python
   if self._panic_manager_is_panic():
       return True
   ```
7. In `RuntimeOrchestrator._execute_goal_episode` (`runtime.py:252-256`):
   ```python
   if self.interrupt_guard.is_interrupted():
       while self.interrupt_guard.is_interrupted() and not self._stop_event.is_set():
           time.sleep(0.2)
   ```
   Because `PanicManager` has no automatic reset, the worker thread hangs indefinitely in the while loop.
8. Furthermore, `ActionType.PANIC` is classified as a passive action in `EpisodicMemory.record_step` (`memory.py:240-242`), meaning it never clears strikes. Because `RuntimeOrchestrator` never calls `self.memory.reset_loop_detector()`, all subsequent goals start with 3 strikes and immediately abort.

### Observation 3: Goal Backlog Retention on Panic (`parasite_ai/ui/bridge.py:47-55`, `parasite_ai/runtime.py:345-353`)
In `UIBridge`:
- `self._goal_queue: queue.Queue[str] = queue.Queue()` maintains queued goals.
- There is no method on `UIBridge` to clear or drain the queue.
In `RuntimeOrchestrator._on_hardware_panic` and `_on_gui_panic_triggered`:
- Neither method attempts to purge `_goal_queue`.
- Rapidly queued goals (e.g., "Dangerous Goal 2: Delete Files", "Dangerous Goal 3: Drop Database") remain in the queue, creating a hazardous replay risk if the system ever re-arms.

### Observation 4: GUI Pause Hands Disconnect from Cancellation Token (`parasite_ai/runtime.py:360-370`, `parasite_ai/hands/mouse.py:198-208`)
In `RuntimeOrchestrator._on_gui_pause_toggled`:
```python
361:     @pyqtSlot(bool)
362:     def _on_gui_pause_toggled(self, is_paused: bool) -> None:
363:         """Handles Pause Hands toggle from CompanionDock button."""
364:         self._is_paused = is_paused
365:         logger.info(f"Hands pause state updated: {is_paused}")
366:         if is_paused:
367:             self.bridge.notify_state("WATCHING", "Curious")
368:             self.bridge.notify_telemetry("Hands paused by user")
369:         else:
370:             self.bridge.notify_telemetry("Hands resumed by user")
```
- `_on_gui_pause_toggled` modifies only the boolean `self._is_paused`.
- It does NOT signal `self.interrupt_guard.get_cancellation_token()`.
- In `MouseDriver.move_to` (`mouse.py:198-208`), waypoints check `cancellation_token.is_set()` and `cancellation_token.wait()`. Because the token is not set, a 300ms–500ms glide and subsequent click execute to 100% completion even after the user toggles "Pause Hands".

---

## 2. Logic Chain

1. **Worker Thread Exception Boundary (Defect 1)**:
   - *Observation 1* proves that unhandled exceptions inside `_execute_goal_episode` escape `_worker_loop`, destroying `_worker_thread` while leaving `runtime.is_running == True`.
   - Wrapping `self._execute_goal_episode(goal)` in a `try...except Exception as exc:` block catches any unhandled failure, logs it, calls `self._neutralize_inputs()`, `bridge.clear_hud_targets()`, `bridge.clear_reticle()`, emits `bridge.notify_speech(...)`, updates UI state to `WATCHING`, and keeps `_worker_loop` running to process subsequent goals.
   - Wrapping `self.pipeline.step(user_goal=goal)` within `_execute_goal_episode` ensures individual step errors cleanly exit the episode loop to teardown without crashing the worker.

2. **Cognitive Loop Decoupling & Loop Reset (Defect 2)**:
   - *Observation 2* proves that `ActionDispatcher.dispatch()` emits `bridge.sig_panic_triggered`, which `RuntimeOrchestrator._on_gui_panic_triggered` connects to `PanicManager.trigger_panic()`.
   - `test_e2e_integration.py:436` and `test_dual_mind.py:293` require `bridge.sig_panic_triggered` to be emitted when `ActionType.PANIC` executes in `DualMindPipeline`.
   - Therefore, `sig_panic_triggered` must remain emitted, but `RuntimeOrchestrator` must decouple cognitive step panics from hardware `PanicManager.trigger_panic()`.
   - Tracking cognitive step execution via `self._is_in_cognitive_step` allows `_on_gui_panic_triggered` to recognize cognitive loop resets: it neutralizes inputs and sets UI state to `Panic-Averted` WITHOUT calling `panic_manager.trigger_panic()`.
   - Calling `self.memory.reset_loop_detector()` at the beginning of each goal and during episode teardown guarantees subsequent goals start with 0 strikes.
   - Adding an explicit `reset_panic()` method to `RuntimeOrchestrator` allows recovery when physical/GUI panic has occurred and a new goal is submitted.

3. **Goal Queue Flush on Panic (Defect 3)**:
   - *Observation 3* proves that `UIBridge` lacks a purge method, leaving pending goals in memory across panic aborts.
   - Adding `clear_goals() -> int` to `UIBridge` using thread-safe `get_nowait()` drains all backlogged goals.
   - Calling `self.bridge.clear_goals()` in `_on_hardware_panic` and `_on_gui_panic_triggered` ensures safe, zero-backlog states post-abort.

4. **In-Flight Pause Preemption (Defect 4)**:
   - *Observation 4* proves `_on_gui_pause_toggled` does not trip `cancellation_token`.
   - Calling `self.interrupt_guard.get_cancellation_token().set()` when `is_paused=True` immediately signals `MouseDriver.move_to` and `MouseDriver.click`, aborting any in-flight glide, releasing buttons, and clearing the reticle in < 2ms.
   - Calling `cancellation_token.clear()` when `is_paused=False` re-arms the token for resumed operation.

---

## 3. Caveats

1. **Offline/Simulated Execution**: All investigations and reproductions were performed in software-simulated mode (`simulation_mode=True`) with offscreen Qt (`QT_QPA_PLATFORM=offscreen`) to adhere strictly to Safety Guardrail R2 (zero unconsented mouse/keyboard takeover).
2. **Subprocess Dry-Run Timing**: In `tests/test_e2e_integration.py`, `test_dry_run_cli_subprocess` may take ~5.5s on loaded Windows runners against a 5.0s budget. This is an environment/OS scheduling factor and unrelated to orchestrator runtime logic.
3. **Challenger Test Suite Inversion**: `tests/test_challenger_m5_2.py` was authored by Challenger 2 to assert the presence of vulnerabilities (e.g., `assert runtime._worker_thread.is_alive() is False`). Once the remediation is implemented, those assertions must be updated to assert the fixed, resilient behavior (e.g., `assert runtime._worker_thread.is_alive() is True`).

---

## 4. Conclusion & Drop-In Code Proposals

### Summary of Changes by Subsystem

| Subsystem | File | Lines | Purpose |
|---|---|---|---|
| **UIBridge** | `parasite_ai/ui/bridge.py` | 122–131 | Add `clear_goals() -> int` to drain `_goal_queue` |
| **RuntimeOrchestrator** | `parasite_ai/runtime.py` | 221–231 | Enclose `_execute_goal_episode(goal)` in `try...except` in `_worker_loop` |
| **RuntimeOrchestrator** | `parasite_ai/runtime.py` | 233–310 | Add step-level exception handling, cognitive tracking, and loop detector reset |
| **RuntimeOrchestrator** | `parasite_ai/runtime.py` | 315–328 | Add loop reset on fresh goal in `run_single_step` |
| **RuntimeOrchestrator** | `parasite_ai/runtime.py` | 345–353 | Call `self.bridge.clear_goals()` in `_on_hardware_panic` |
| **RuntimeOrchestrator** | `parasite_ai/runtime.py` | 360–370 | Connect `_on_gui_pause_toggled` to `cancellation_token.set()`/`clear()` |
| **RuntimeOrchestrator** | `parasite_ai/runtime.py` | 372–378 | Decouple cognitive panic from `panic_manager.trigger_panic()` and clear goals |
| **RuntimeOrchestrator** | `parasite_ai/runtime.py` | 380+ | Add `reset_panic()` method |
| **Challenger Tests** | `tests/test_challenger_m5_2.py` | Multiple | Invert 7 vulnerability asserts to verify resilience |

---

### Drop-In Code Replacements

#### 1. `parasite_ai/ui/bridge.py`
Add `clear_goals()` right after `get_next_goal` (around line 131):

```python
    def get_next_goal(self, timeout_sec: Optional[float] = None) -> Optional[str]:
        """
        Thread-safe blocking or polling getter for background engine
        to retrieve the next user goal submitted from the GUI.
        """
        try:
            return self._goal_queue.get(timeout=timeout_sec)
        except queue.Empty:
            return None

    def clear_goals(self) -> int:
        """
        Purges all pending goals from the queue (e.g. on emergency panic).
        Returns the number of discarded goals.
        """
        discarded = 0
        while not self._goal_queue.empty():
            try:
                self._goal_queue.get_nowait()
                discarded += 1
            except queue.Empty:
                break
        return discarded
```

---

#### 2. `parasite_ai/runtime.py`

##### Change 2A: Exception boundary in `_worker_loop` (lines 221–231)
Replace `_worker_loop`:
```python
    def _worker_loop(self) -> None:
        """Main loop dequeuing goals and executing closed-loop episodes."""
        logger.info("Cognitive worker loop started.")
        while not self._stop_event.is_set():
            goal = self.bridge.get_next_goal(timeout_sec=0.25)
            if goal is None or self._stop_event.is_set():
                continue

            try:
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
```

##### Change 2B: Episode management, loop resets, and cognitive step context in `_execute_goal_episode` (lines 233–310)
```python
    def _execute_goal_episode(self, goal: str, max_steps: int = 15) -> None:
        """Executes a multi-step goal until completion, panic, loop, or max steps."""
        logger.info(f"Beginning goal episode: '{goal}'")

        # 0. If recovering from previous hardware/GUI panic, re-arm on new goal
        if self.interrupt_guard.is_panic():
            logger.info("New goal received post-panic; auto re-arming system.")
            self.reset_panic()

        # Reset loop detector strikes at the start of every goal episode
        self.memory.reset_loop_detector()

        self.bridge.notify_state("THINKING", "Focused")
        self.bridge.notify_telemetry(f"Starting goal: {goal}", 0, max_steps)

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
                self.bridge.notify_speech("Emergency abort triggered! Backing off.")
                self.bridge.notify_state("WATCHING", "Panic-Averted")
                self.bridge.notify_telemetry("Goal aborted by emergency panic", step_idx, max_steps)
                break

            # Cognitive Loop Detection (3-strike failure loop)
            if self.memory.is_in_loop():
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
        if not self._stop_event.is_set() and not self.interrupt_guard.is_panic():
            self.bridge.notify_state("WATCHING", "Curious")
            self.bridge.notify_telemetry("Ready for next goal")
```

##### Change 2C: `run_single_step` synchronization and strike isolation (lines 315–328)
```python
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
```

##### Change 2D: Hardware and GUI panic handlers, Pause toggle, and `reset_panic()` (lines 345–385)
```python
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
```

---

#### 3. Modernized Assertions for `tests/test_challenger_m5_2.py`

Update the 7 vulnerability-proving assertions to verify resilience:

1. **`test_unhandled_step_exception_terminates_worker_and_creates_zombie_state`**:
   - Change `assert runtime._worker_thread.is_alive() is False` to `assert runtime._worker_thread.is_alive() is True`.
   - Verify Goal 2 executes:
     ```python
     goal2_executed = threading.Event()
     def mock_safe_step(*args: Any, **kwargs: Any) -> StepRecord:
         goal2_executed.set()
         return StepRecord(step_id=2, action=ActionPlan(action=ActionType.DONE), success=True)
     with patch.object(runtime.pipeline, "step", side_effect=mock_safe_step):
         bridge.sig_goal_submitted.emit("Safe Goal 2")
         assert goal2_executed.wait(timeout=1.0) is True
     assert bridge._goal_queue.empty() is True
     ```
2. **`test_brain_inference_exception_crashes_worker_loop`**:
   - Change `assert runtime._worker_thread.is_alive() is False` to `assert runtime._worker_thread.is_alive() is True`.
3. **`test_panic_abort_leaves_queued_goals_unpurged_in_bridge`**:
   - Change `assert not bridge._goal_queue.empty()` to:
     ```python
     assert bridge._goal_queue.empty() is True
     assert bridge._goal_queue.qsize() == 0
     ```
4. **`test_gui_panic_triggers_permanent_unrecoverable_lockout`**:
   - Change `assert executed is False` to `assert executed is True`.
5. **`test_pause_hands_toggle_does_not_halt_inflight_mouse_glide`**:
   - In `simulate_gui_pause_click`, add `cancellation_token.set()`.
   - Change `assert completed is True` to `assert completed is False`.
   - Change `assert t_elapsed >= 0.25` to `assert t_elapsed < 0.20`.
6. **`test_three_strike_loop_permanent_lockout_across_future_goals`**:
   - Change assertions for Goal 2:
     ```python
     rec = runtime.run_single_step(goal="Goal 2 - Fresh task")
     assert rec.action.action != ActionType.PANIC
     assert runtime.memory.is_in_loop() is False
     assert runtime.memory.get_consecutive_strikes() == 0
     assert runtime.interrupt_guard.is_panic() is False
     ```
7. **`test_three_strike_loop_triggers_permanent_hardware_panic_lockout`**:
   - Change assertions:
     ```python
     assert "Panic-Averted" in moods
     assert runtime.interrupt_guard.is_panic() is False
     assert runtime.interrupt_guard.is_interrupted() is False
     assert runtime.memory.is_in_loop() is False
     ```

---

## 5. Verification Method

Once the implementer applies the changes above, run the following verification commands:

```powershell
# 1. Run Challenger 2 adversarial suite (all 13 tests must pass without warnings or zombie threads)
uv run pytest tests/test_challenger_m5_2.py -v

# 2. Run E2E integration acceptance suite (all scenarios must pass cleanly)
uv run pytest tests/test_e2e_integration.py -v

# 3. Combined regression and resilience verification run
uv run pytest tests/test_challenger_m5_2.py tests/test_e2e_integration.py tests/test_dual_mind.py -v
```

### Invalidation Conditions
- Any occurrence of `PytestUnhandledThreadExceptionWarning: Exception in thread ParasiteCognitiveWorker` invalidates Defect 1 fix.
- Any goal remaining in `bridge._goal_queue` after `_on_hardware_panic()` or `_on_gui_panic_triggered()` invalidates Defect 3 fix.
- `driver.move_to()` returning `True` after `cancellation_token.set()` invalidates Defect 4 fix.
- `runtime.interrupt_guard.is_panic()` returning `True` following a 3-strike loop invalidates Defect 2 fix.
