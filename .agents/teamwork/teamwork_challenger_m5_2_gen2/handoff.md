# Milestone M5 Adversarial Challenge & Stress Report

**Agent**: `teamwork_challenger_m5_2_gen2`  
**Working Directory**: `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_challenger_m5_2_gen2`  
**Verdict**: **REQUEST_CHANGES**  

---

## 1. Observation

Direct empirical observations across `parasite_ai/runtime.py`, `parasite_ai/ui/bridge.py`, `parasite_ai/mind/dual_mind.py`, and `parasite_ai/safety/interrupt_guard.py`:

### Observation 1: Unhandled Worker Thread Exception Boundary (`parasite_ai/runtime.py:221-231`)
In `RuntimeOrchestrator._worker_loop`:
```python
    def _worker_loop(self) -> None:
        """Main loop dequeuing goals and executing closed-loop episodes."""
        logger.info("Cognitive worker loop started.")
        while not self._stop_event.is_set():
            goal = self.bridge.get_next_goal(timeout_sec=0.25)
            if goal is None or self._stop_event.is_set():
                continue

            self._execute_goal_episode(goal)

        logger.info("Cognitive worker loop terminated.")
```
There is no `try...except` block enclosing `self._execute_goal_episode(goal)`.
When an unexpected exception occurs inside `pipeline.step()` (such as `RuntimeError` or `ConnectionError`), pytest reported:
```
PytestUnhandledThreadExceptionWarning: Exception in thread ParasiteCognitiveWorker
Traceback (most recent call last):
  File "G:\__Docs\ParasiteAI\parasite_ai\runtime.py", line 229, in _worker_loop
    self._execute_goal_episode(goal)
  File "G:\__Docs\ParasiteAI\parasite_ai\runtime.py", line 274, in _execute_goal_episode
    step_record = self.pipeline.step(user_goal=goal)
```
Upon thread crash:
- `runtime._worker_thread.is_alive()` becomes `False`.
- `runtime.is_running` remains `True` (zombie state).
- Subsequent goals submitted via `bridge.sig_goal_submitted` remain trapped in `bridge._goal_queue` forever.

### Observation 2: Escalation of Cognitive Failure Loop to Irreversible Hardware Emergency Panic (`parasite_ai/mind/dual_mind.py:450-453`, `parasite_ai/runtime.py:372-378`, `parasite_ai/safety/interrupt_guard.py:300-305`)
In `ActionDispatcher.dispatch`:
```python
            elif action.action == ActionType.PANIC:
                if self.bridge:
                    self.bridge.sig_panic_triggered.emit()
                self._release_all()
                return ActionResult(success=True, action_executed=action)
```
In `RuntimeOrchestrator._on_gui_panic_triggered`:
```python
    @pyqtSlot()
    def _on_gui_panic_triggered(self) -> None:
        logger.critical("PANIC triggered via GUI button.")
        self._neutralize_inputs()
        self.interrupt_guard.panic_manager.trigger_panic("GUI PANIC button")
        self._on_hardware_panic("GUI button")
```
When `EpisodicMemory.is_in_loop()` trips after 3 failed actions:
1. `DualMindPipeline.step()` automatically overrides the next action with `ActionType.PANIC`.
2. `ActionDispatcher.dispatch()` emits `sig_panic_triggered`.
3. `RuntimeOrchestrator._on_gui_panic_triggered()` invokes `interrupt_guard.panic_manager.trigger_panic(...)`.
4. `PanicManager.trigger_panic()` permanently sets `_is_panic = True`.
5. In `InterruptGuard.is_interrupted()`:
   ```python
   if self._panic_manager_is_panic():
       return True
   ```
6. In `RuntimeOrchestrator._execute_goal_episode`:
   ```python
   if self.interrupt_guard.is_interrupted():
       while self.interrupt_guard.is_interrupted() and not self._stop_event.is_set():
           time.sleep(0.2)
   ```
7. Because no reset handler resets `PanicManager`, the system enters an infinite wait loop (`while self.interrupt_guard.is_interrupted()`).
8. If stepped directly, `DualMindPipeline` line 554 permanently returns `ActionType.WAIT` with `"User override active"`. All future user goals are permanently locked out.

### Observation 3: Goal Queue Backlog Retention on Emergency Panic (`parasite_ai/ui/bridge.py:47-55`, `parasite_ai/runtime.py:345-353`)
In `UIBridge`:
`_goal_queue: queue.Queue[str] = queue.Queue()` has no method to flush or purge pending goals.
In `RuntimeOrchestrator._on_hardware_panic()`:
When panic aborts the active episode, `bridge._goal_queue` is never drained. Pending goals submitted prior to panic remain in queue and will execute if the system re-arms.

### Observation 4: In-Flight Mouse Movement Pause Disconnect (`parasite_ai/runtime.py:360-370`, `parasite_ai/hands/mouse.py:198-208`)
In `RuntimeOrchestrator._on_gui_pause_toggled`:
```python
    @pyqtSlot(bool)
    def _on_gui_pause_toggled(self, is_paused: bool) -> None:
        self._is_paused = is_paused
```
It sets `self._is_paused = True`, but does NOT signal `self.interrupt_guard.get_cancellation_token()`.
In `MouseDriver.move_to`, `cancellation_token` is checked at each trajectory step, but since `cancellation_token.is_set()` is `False`, in-flight mouse movement and pre-click reticle run to 100% completion despite the user having toggled "Pause Hands".

---

## 2. Logic Chain

1. **Premise 1 (Resilience)**: As a desktop assistant running an autonomous closed loop, unexpected perception or inference exceptions must be caught at the episode boundary, notifying the user via speech and resetting UI state to `WATCHING`, rather than terminating the background worker thread.
   - *Supported by Observation 1*: `_worker_loop` currently lacks `try...except`, causing thread termination and a zombie state where `runtime.is_running == True` but no goals are ever dequeued.
2. **Premise 2 (State Consistency)**: Cognitive loop detection (3 consecutive actions without screen diff) is a software planning fallback designed to switch strategy, not a physical hardware emergency. Escalating a cognitive 3-strike loop to `sig_panic_triggered` invokes `PanicManager.trigger_panic()`, which latches hardware panic forever without recovery.
   - *Supported by Observation 2*: A 3-strike failure loop on Goal 1 permanently bricks Goal 2, 3, and all future goals into `ActionType.WAIT` / `USER_OVERRIDE` or hangs the worker thread in `while is_interrupted()`.
3. **Premise 3 (Safety Clean-Slate)**: When emergency panic is triggered, all queued intentions must be discarded to prevent queued hazardous operations (e.g., delete files) from executing after panic.
   - *Supported by Observation 3*: `UIBridge._goal_queue` is not purged upon panic.
4. **Premise 4 (Immediate Input Preemption)**: When a user clicks "Pause Hands", any in-flight mouse movement should halt immediately, not finish its trajectory.
   - *Supported by Observation 4*: `_on_gui_pause_toggled` updates a boolean flag only inspected between steps, allowing in-flight moves to complete.

---

## 3. Caveats

- Tests were executed with Win32 hardware hooks in software-simulated mode (`simulation_mode=True`) and offscreen Qt platform (`QT_QPA_PLATFORM=offscreen`) as mandated by Safety Guardrail R2 (zero mouse/keyboard takeover without explicit user consent).
- Live physical mouse movement with hardware `WH_MOUSE_LL` hooks on a multi-monitor setup was not physically tested without user consent, but the software abstraction and concurrency layer was exhaustively stress-tested.

---

## 4. Conclusion & Required Changes

Milestone M5 Runtime Orchestrator implementation requires targeted hardening before final sign-off.

**Required Changes**:
1. **Worker Thread Exception Boundary (`parasite_ai/runtime.py`)**:
   Wrap `self._execute_goal_episode(goal)` inside `_worker_loop` in a `try...except Exception as exc:` block. On unhandled exception:
   - Log critical error with traceback.
   - Emit `bridge.notify_speech("An internal error occurred: ...")`.
   - Call `self._neutralize_inputs()`, `bridge.clear_hud_targets()`, `bridge.clear_reticle()`.
   - Reset state to `bridge.notify_state("WATCHING", "Curious")`.
   - Keep worker thread alive to service future goals.
2. **Cognitive Loop Separation from Physical Panic (`parasite_ai/mind/dual_mind.py`, `parasite_ai/runtime.py`)**:
   Do NOT emit `bridge.sig_panic_triggered` on `ActionType.PANIC` when caused by cognitive loop detection. Instead:
   - Introduce `ActionType.STRATEGY_RESET` or handle `ActionType.PANIC` in `DualMindPipeline` as a cognitive reset without tripping `PanicManager.trigger_panic()`.
   - In `RuntimeOrchestrator._execute_goal_episode`, call `self.memory.reset_loop_detector()` upon episode completion or user goal submission so future goals start with 0 strikes.
   - Provide an explicit `reset_panic()` / `rearm()` method in `RuntimeOrchestrator` and CompanionDock to recover from user-initiated panic.
3. **Goal Queue Flush on Panic (`parasite_ai/ui/bridge.py`, `parasite_ai/runtime.py`)**:
   Add `clear_goals()` / `drain_queue()` to `UIBridge`, and call it inside `RuntimeOrchestrator._on_hardware_panic()` and `_on_gui_panic_triggered()`.
4. **In-Flight Pause Preemption (`parasite_ai/runtime.py`)**:
   When `_on_gui_pause_toggled(is_paused=True)` is called, trip an internal cancellation token or interrupt token so in-flight mouse trajectories and reticle timers abort immediately (< 2ms) rather than completing.

---

## 5. Verification Method

To independently reproduce and verify all 13 adversarial edge-case tests:

```powershell
# Run the adversarial stress suite authored for M5
uv run pytest tests/test_challenger_m5_2.py -v

# Run both challenger suite and primary E2E integration suite
uv run pytest tests/test_challenger_m5_2.py tests/test_e2e_integration.py -v
```

**Test Breakdown (`tests/test_challenger_m5_2.py`)**:
1. `TestWorkerThreadResilienceAndExceptionHandling`:
   - `test_unhandled_step_exception_terminates_worker_and_creates_zombie_state` (PASSED - confirms thread termination & zombie state)
   - `test_brain_inference_exception_crashes_worker_loop` (PASSED - confirms thread crash on LLM exception)
   - `test_runtime_start_stop_idempotence_and_thread_lifecycle` (PASSED - verifies lifecycle safety)
2. `TestGoalQueueUnderRapidFloodingAndPanicAborts`:
   - `test_rapid_burst_goal_queuing_fifo_order` (PASSED - verifies FIFO queuing)
   - `test_panic_abort_leaves_queued_goals_unpurged_in_bridge` (PASSED - confirms unpurged backlog)
   - `test_gui_panic_triggers_permanent_unrecoverable_lockout` (PASSED - confirms permanent worker lockout post-panic)
3. `TestInFlightActionRaceConditionsAndInterrupts`:
   - `test_pause_hands_toggle_does_not_halt_inflight_mouse_glide` (PASSED - confirms in-flight glide completes despite pause)
   - `test_stop_while_worker_executing_aborts_immediately` (PASSED - verifies clean stop abort)
   - `test_multithreaded_control_signals_storm` (PASSED - verifies concurrency safety under signal storm)
4. `TestThreeStrikeLoopStateConsistencyAndResets`:
   - `test_three_strike_loop_permanent_lockout_across_future_goals` (PASSED - confirms cross-goal lockout)
   - `test_three_strike_loop_triggers_permanent_hardware_panic_lockout` (PASSED - confirms cognitive loop escalates to hardware panic)
   - `test_strike_reset_semantics_interactive_vs_passive_actions` (PASSED - verifies strike boundaries)
   - `test_alternating_failure_modes_do_not_evade_strikes` (PASSED - verifies strike accumulation across failure modes)
