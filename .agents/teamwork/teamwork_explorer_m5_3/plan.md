# Implementation Plan: Feature 18 — E2E Test Suite & Acceptance Verification (`tests/test_e2e_integration.py`)

## 1. Executive Summary & Problem Boundary
The purpose of Milestone M5 Explorer 3 is to architect the comprehensive end-to-end (E2E) integration test suite for ParasiteAI (`tests/test_e2e_integration.py`). This suite serves as the definitive verification gate proving that all system components (UI, Safety, Physical Input, Perception, Working Memory, Dual-Mind Cognition, and Browser Offload) satisfy every requirement in `ORIGINAL_REQUEST.md` (R1–R5) and `PROJECT.md` Feature 18, under both nominal operation and Tier 5 adversarial stress.

All tests are engineered to execute deterministically under `uv run pytest tests/test_e2e_integration.py` in headless CI without requiring physical human hands, active GPU VRAM, or real external display hardware.

---

## 2. Deterministic Headless Test Harness Architecture

To achieve 100% test reliability and sub-second execution across CI environments, the E2E test harness leverages built-in polymorphic mock backends and offscreen Qt execution:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        E2E Integration Test Suite                       │
│                     tests/test_e2e_integration.py                      │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
          ┌─────────────────────────┴─────────────────────────┐
          ▼                                                   ▼
┌───────────────────────────┐                       ┌───────────────────┐
│     PyQt6 Offscreen       │                       │  Mock Subsystems  │
│ - QT_QPA_PLATFORM=offscreen│                       │ - MockInputBackend│
│ - qtbot signal blockers   │                       │ - Sim MouseDriver │
│ - Real CompanionDock      │                       │ - MockClipboard   │
│ - Real GhostHUD (no Win32)│                       │ - MockBrowserWin  │
└─────────────┬─────────────┘                       └─────────┬─────────┘
              │                                               │
              └─────────────────────┬─────────────────────────┘
                                    │
                                    ▼
       ┌─────────────────────────────────────────────────────────┐
       │                Integrated Runtime Pipeline               │
       │  UIBridge ◄──► DualMindPipeline ◄──► EpisodicMemory    │
       │       ▲                 ▲                   ▲           │
       │       │                 │                   │           │
       │  WindowGuard     InterruptGuard       LocalBrainManager │
       └─────────────────────────────────────────────────────────┘
```

### Key Fixtures:
1. `qapp_offscreen` / `qtbot`: Instantiates `QApplication` with `QT_QPA_PLATFORM=offscreen` (or leverages `pytest-qt`).
2. `e2e_bridge`: Real `UIBridge` instance managing cross-thread signal emission and `_goal_queue`.
3. `e2e_dock`: Real `CompanionDock` widget connected to `UIBridge`.
4. `e2e_hud`: Real `GhostHUD` overlay configured with `enable_win32_styles=False` for headless safety.
5. `e2e_mouse`: `MouseDriver(simulation_mode=True, speed_factor=10.0, preview_reticle_ms=50)` capturing full movement history and reticle callbacks.
6. `e2e_keyboard`: `KeyboardDriver(backend=MockInputBackend())` recording dispatched key packets.
7. `e2e_interrupt_guard`: Real `InterruptGuard` with software injection harness `simulate_event()`.
8. `e2e_window_guard`: `WindowGuard` instance with controllable foreground window simulation.
9. `e2e_brain`: `LocalBrainManager(mode=BrainMode.MOCK)` programmed with deterministic monologue and action sequences.
10. `e2e_memory`: Real `EpisodicMemory(strike_limit=3)`.
11. `e2e_pipeline`: Real `DualMindPipeline` wiring all the above subsystems together.

---

## 3. The 6 E2E Integration Scenarios

### Scenario 1: Clean Startup & Zero-Config Default Boot
**Goal**: Verify application bootstrap under zero-config default settings, both via CLI arguments (`--dry-run`, `--headless`) and programmatic bootstrapper invocation.

- **Execution Flow**:
  1. CLI Subprocess Test: Execute `python main.py --dry-run` via `subprocess.run` with a 10-second timeout.
  2. Verify process returns exit code `0`.
  3. Verify standard output contains confirmation: `"Clean dry-run initialization completed successfully"`.
  4. Programmatic Bootstrapper Test: Invoke startup lifecycle in-process:
     - Initialize High-DPI awareness (`init_high_dpi_awareness()`).
     - Load config via `load_config(None)`: verifies that missing `config.yaml` automatically generates default file with Pydantic validation.
     - Instantiate all 12 core subsystems: `UIBridge`, `InterruptGuard`, `WindowGuard`, `MouseDriver`, `KeyboardDriver`, `ScreenCapture`, `ScreenGrounder`, `LocalBrainManager`, `EpisodicMemory`, `DualMindPipeline`, `CompanionDock`, `GhostHUD`.
     - Execute component health checks.
     - Perform clean teardown: stop hooks, cancel timers, restore `timeEndPeriod(1)`, verify no dangling threads.
- **Pass Criteria**:
  - `main.py --dry-run` exits cleanly with code 0 in < 3s.
  - Zero unhandled exceptions or crashes.
  - All 12 subsystems report healthy initialized status.

---

### Scenario 2: End-to-End Goal Execution Cycle (Closed-Loop Goal Execution)
**Goal**: Verify the complete closed-loop cycle from user goal entry to Set-of-Mark visual grounding, character monologue, targeting reticle, kinematic movement, click dispatch, visual screen diff verification, episodic memory logging, and UI telemetry.

- **Execution Flow**:
  1. Goal Input: Emit `bridge.sig_goal_submitted.emit("Click the Submit button")` or type into `CompanionDock` goal input.
  2. Goal Retrieval: Runtime worker dequeues goal from `UIBridge._goal_queue`.
  3. Thinking State: `CompanionDock` state transitions to `THINKING`, mood to `Focused`.
  4. Screen Grounding & Perception: Grounder receives synthetic desktop image (1920x1080) with a known button at `(500, 400, 100, 40)`. Grounder assigns 1-based Set-of-Mark ID `[#1]`, label `"Submit"`, role `"Button"`.
  5. HUD Set-of-Mark Display: `bridge.set_hud_targets()` publishes targets to `GhostHUD`. HUD renders numbered bounding box `[#1]`.
  6. Dock Perception Preview: `bridge.notify_perception()` updates companion dock thumbnail preview.
  7. Pass 1 Persona Monologue: `PersonaEngine` produces monologue dialogue (`"I will click the Submit button now."`) and internal thoughts (`"Targeting element #1 at center (550, 420)"`).
  8. Pass 2 Action Planning: Dispatcher receives `ActionPlan(action=ActionType.CLICK, target_id=1)`.
  9. Targeting Reticle Display: Target coordinates resolved to element center `(550, 420)`. `bridge.show_reticle(550, 420, duration_ms=300)` is invoked on `GhostHUD`, triggering the 300ms pre-click reticle countdown.
  10. Driving State & Kinematic Mouse Movement: Dock state transitions to `DRIVING`. `MouseDriver.move_to(550, 420)` executes human curved trajectory:
      - Trajectory follows Cubic Bézier path with non-zero curvature.
      - Kinematic points verify smooth Min-Jerk velocity profile, micro-jitter, and terminal overshoot.
  11. Physical Click Dispatch: Mouse left-click is dispatched at `(550, 420)`.
  12. Visual Screen Diff Calculation: Post-action frame captures depressed button / visual state change. `compute_pixel_diff(pre_frame, post_frame)` computes difference (`diff = 0.08 > 0.05`).
  13. Episodic Memory Record: `EpisodicMemory.record_step(...)` appends `StepRecord(step_id=1, action=CLICK, success=True, screen_diff=0.08)`.
  14. Telemetry Update: Progress bar on `CompanionDock` updates to step 1/1.
  15. Completion: Next action plan is `ActionType.DONE`. Dock state transitions to `WATCHING`, mood `Amused`. `GhostHUD.clear_targets()` removes all Set-of-Mark overlays.
- **Pass Criteria**:
  - Full signal sequence verified in exact chronological order via `qtbot.waitSignal`.
  - Mouse coordinates arrive exactly within target element bounding box.
  - Screen diff recorded > 0.0, step recorded as `success=True`.
  - HUD overlay cleanly cleared upon task completion.

---

### Scenario 3: Physical Hardware Touch Interruption in <2ms
**Goal**: Verify that low-level hardware hooks filter synthetic vs physical events, and any physical human input immediately (<2ms) aborts active synthetic movements, releases held inputs, and switches the UI to `USER_OVERRIDE`.

- **Execution Flow**:
  1. Synthetic Injected Input Filtering:
     - Dispatch synthetic mouse and keyboard events marked with `LLMHF_INJECTED (0x01)` and `LLKHF_INJECTED (0x10)`.
     - Verify `interrupt_guard.is_interrupted()` remains `False` and `cancellation_token.is_set()` remains `False`.
  2. Physical Hardware Touch Simulation:
     - Start a long continuous synthetic mouse movement (e.g. from `(100, 100)` to `(1800, 900)`).
     - Inject physical hardware touch: `interrupt_guard.simulate_event("mouse", flags=0, pt=(400, 400))`.
  3. Preemption Latency Benchmark (<2ms):
     - Measure time between hook invocation and `cancellation_token.is_set()`.
     - Assert measured latency is strictly `< 0.002` seconds (typically < 0.0003s).
  4. Immediate Action Abort & Resource Release:
     - Active `MouseDriver.move_to` immediately aborts and returns `False`.
     - `release_all_buttons()` is invoked, ensuring zero stuck mouse buttons.
     - Active targeting reticle on `GhostHUD` is aborted via `bridge.clear_reticle()`.
     - `CompanionDock` immediately transitions to `USER_OVERRIDE` state, mood `Curious`.
     - `DualMindPipeline.step()` records `interrupted=True`, `error_message="User override active"`.
  5. Sliding Cooldown & Rearm:
     - Verify further action attempts are blocked while cooldown is active.
     - Advance time / fire rearm: verify system automatically rearms, clears token, and allows actions to resume.
- **Pass Criteria**:
  - Physical touch abort latency strictly `< 2ms`.
  - Synthetic events never trigger preemption.
  - Held buttons/keys released immediately.
  - Dock switches to `USER_OVERRIDE`.

---

### Scenario 4: Sensitive Window Detection & Privacy Blackout
**Goal**: Verify that `WindowGuard` detects sensitive applications (password managers, admin consoles, UAC prompts, lock screen), immediately blacking out perception feeds, clearing HUD overlays, and halting actions in `PROTECTED` state.

- **Execution Flow**:
  1. Baseline Safe Window:
     - Set active foreground window to `notepad.exe` ("Untitled - Notepad").
     - Verify `window_guard.is_safe_to_operate()` is `True`.
     - Dock operates in normal state.
  2. Sensitive Window Activation:
     - Simulate foreground window switch to password manager (e.g. `bitwarden.exe`, `1password.exe`, `keepass.exe`, `taskmgr.exe`, `regedit.exe`, or title `"Bitwarden"`, `"Administrator: Command Prompt"`).
     - Also verify fail-safe edge cases: `hwnd == 0` (lock screen) and `can_open_process == False` (elevated UAC prompt).
  3. Privacy Protection Enforcement:
     - `window_guard.is_safe_to_operate()` returns `False`.
     - `CompanionDock` transitions to `PROTECTED` state, displaying badge `🔒 PROTECTED`, mood `Cautious`.
     - Perception thumbnail is masked with privacy blackout overlay (`[PRIVACY MASK / BLACKOUT]`), ensuring zero private credentials appear in memory or logs.
     - `GhostHUD.clear_targets()` removes all Set-of-Mark tags so no numbered boxes hover over password fields.
     - `DualMindPipeline.step()` refuses to drive hands, recording a safe `WAIT` action with `error_message="Sensitive window detected; pausing actions"`.
  4. Safe Window Restoration:
     - Switch foreground back to safe window (`notepad.exe`).
     - `window_guard.is_safe_to_operate()` returns `True`.
     - Dock exits `PROTECTED` state; normal observation and driving resume.
- **Pass Criteria**:
  - `is_safe_to_operate()` returns `False` for all blacklisted processes and titles.
  - Zero synthetic keystrokes or mouse clicks dispatched while protected.
  - Privacy blackout verified on dock perception preview.

---

### Scenario 5: 3-Strike Failure Loop Emergency Reset
**Goal**: Verify that episodic memory detects consecutive action failures or zero-diff actions (3 strikes), transitions mood to `Cautious`, and triggers an emergency PANIC strategy reset.

- **Execution Flow**:
  1. Strike 1: Action executes, but post-action visual diff is `0.001 <= 0.005` (no visual change).
     - Memory logs strike 1. Dock mood remains `Focused`.
  2. Strike 2: Second consecutive attempt produces zero screen diff (`diff <= 0.005`).
     - Memory logs strike 2.
     - `PersonaEngine.derive_mood` detects 2 strikes -> transitions dock mood to `Cautious`.
  3. Strike 3 (Loop Detection Trigger): Third consecutive attempt produces zero screen diff.
     - Memory logs strike 3.
     - `memory.is_in_loop()` returns `True`!
  4. Emergency PANIC Action Override:
     - In `DualMindPipeline.step()`, loop detection intercepts the cycle and overrides the planned action with `ActionPlan(action=ActionType.PANIC, reasoning="Detected 3-strike failure loop. Initiating panic/strategy reset.")`.
     - `bridge.sig_panic_triggered.emit()` is fired.
     - Dock mood transitions to `Panic-Averted`.
     - Emergency release of all held buttons/keys is triggered (`_release_all()`).
  5. Recovery / Loop Break:
     - A corrective action (e.g. OCR fallback or window reposition) produces positive screen diff (`diff = 0.12 > 0.05`).
     - Strikes counter resets to 0.
     - `memory.is_in_loop()` returns `False`.
     - Normal operation resumes.
- **Pass Criteria**:
  - `memory.is_in_loop()` is `False` at strike 2, and `True` at strike 3.
  - Action plan automatically overridden to `PANIC` on 3rd strike.
  - `sig_panic_triggered` emitted.
  - Strikes cleanly reset upon subsequent positive diff.

---

### Scenario 6: Zero-VRAM Visible Browser Brain Offload
**Goal**: Verify that in zero-VRAM browser offload mode, the system operates with 100% visible desktop browser automation (zero headless browsers, zero invisible scrapers) and executes the Sentinel Clipboard Verification protocol with guaranteed user clipboard restoration.

- **Execution Flow**:
  1. Configuration:
     - Configure `brain_mode = BrainMode.BROWSER_OFFLOAD` in `LocalBrainManager`.
     - Use `MockClipboardBackend(initial_text="Sensitive User Work Document")` and `MockBrowserWindowBackend()`.
  2. Browser Discovery & Focus:
     - System calls `find_browser_window("chrome")`.
     - If not running, launches browser with web AI URL (`https://chatgpt.com`).
     - Calls `focus_window(hwnd)` to ensure visible foreground operation.
  3. State Machine & Dock Telemetry:
     - State machine steps through: `LOCATING_BROWSER` -> `FOCUSING_WINDOW` -> `NAVIGATING_URL` -> `WAITING_PAGE_READY` -> `FOCUSING_PROMPT` -> `TYPING_PROMPT` -> `WAITING_RESPONSE` -> `HARVESTING_RESPONSE` -> `COMPLETED`.
     - Companion dock updates state to `OFFLOADING`, mood `Focused`.
  4. Sentinel Clipboard Protocol Verification:
     - User's initial clipboard text is backed up: `"Sensitive User Work Document"`.
     - Unique 128-bit UUID sentinel token injected: `__PARASITE_SENTINEL__<uuid4>`.
     - Trigger copy action (simulating Ctrl+C on web AI answer): clipboard changes to `"Here is the web AI model answer."`.
     - Verifier polls clipboard, verifies response is NOT the sentinel token, and accepts answer.
     - In `finally:` block, original user clipboard content `"Sensitive User Work Document"` is GUARANTEED to be restored.
  5. Fault Tolerance & Cancellation:
     - Simulate copy timeout / harvest failure: raises `OffloadHarvestError`, but original user clipboard is STILL 100% restored!
     - Simulate cancellation token trip during prompt typing: offloader aborts in < 2ms, restores user clipboard, and sets dock to `USER_OVERRIDE`.
- **Pass Criteria**:
  - Offloader cycles through all visible state machine states.
  - Harvested answer matches expected text.
  - User clipboard identical before and after test in all scenarios (success, failure, and cancellation).

---

## 4. Test Matrix & Acceptance Mapping

| Test Class & Method | Focus Requirement | Subsystems Verified | Key Assertion |
|---|---|---|---|
| `TestScenario1CleanStartup.test_dry_run_cli` | R1, R5 | `main.py`, CLI | Exit code 0, clean output in <3s |
| `TestScenario1CleanStartup.test_headless_bootstrap` | R1, R5 | All 12 subsystems | Zero exceptions, clean state, clean teardown |
| `TestScenario1CleanStartup.test_missing_config_autogen` | R1, R5 | `config.py` | Auto-generates valid `config.yaml` |
| `TestScenario2GoalCycle.test_full_goal_to_telemetry_flow` | R2, R4 | UIBridge, Dock, HUD, DualMind | End-to-end signal sequence, step telemetry |
| `TestScenario2GoalCycle.test_som_grounding_and_hud` | R2, R4 | Grounder, GhostHUD | Numbered SoM boxes rendered on HUD |
| `TestScenario2GoalCycle.test_targeting_reticle_preview` | R2, R3 | MouseDriver, GhostHUD | 300ms reticle countdown prior to click |
| `TestScenario2GoalCycle.test_kinematic_mouse_trajectory` | R3 | MouseDriver, Kinematics | Curved Bézier path, jitter, overshoot |
| `TestScenario2GoalCycle.test_screen_diff_and_memory` | R4 | EpisodicMemory, Vision | Diff > 0 recorded, ring buffer updated |
| `TestScenario3HardwareInterrupt.test_synthetic_filtering` | R3 | InterruptGuard | Injected events do not trip interrupt |
| `TestScenario3HardwareInterrupt.test_preemption_under_2ms` | R3 | InterruptGuard, Token | Preemption latency strictly < 2ms |
| `TestScenario3HardwareInterrupt.test_abort_active_actions` | R3 | MouseDriver, KeyboardDriver | In-flight action immediately returns False |
| `TestScenario3HardwareInterrupt.test_dock_user_override` | R2, R3 | CompanionDock, Bridge | State transitions to `USER_OVERRIDE` |
| `TestScenario4SensitiveWindow.test_process_and_title_shield` | R3 | WindowGuard | Password manager detected, returns False |
| `TestScenario4SensitiveWindow.test_privacy_blackout_and_hud` | R2, R3 | CompanionDock, GhostHUD | Dock shows `PROTECTED`, HUD cleared |
| `TestScenario4SensitiveWindow.test_actions_blocked` | R3, R4 | DualMindPipeline | Pipeline pauses, logs safe WAIT step |
| `TestScenario5ThreeStrikes.test_strike_accumulation` | R4 | EpisodicMemory | Strikes increment on diff <= 0.005 |
| `TestScenario5ThreeStrikes.test_mood_cautious_transition` | R2, R4 | PersonaEngine, Dock | Mood switches to Cautious at strike 2 |
| `TestScenario5ThreeStrikes.test_panic_recovery_on_strike_3` | R3, R4 | DualMindPipeline, Memory | Loop trips PANIC override, emits signal |
| `TestScenario6BrowserOffload.test_visible_state_machine` | R4 | BrowserOffloader | Visible window focused, states traversed |
| `TestScenario6BrowserOffload.test_sentinel_clipboard_restore` | R4 | SentinelVerifier | Original user clipboard guaranteed restored |
| `TestScenario6BrowserOffload.test_harvest_failure_guarantee` | R4 | SentinelVerifier | Clipboard restored even on harvest error |

---

## 5. File Layout & Deliverable Specification

The complete test suite will reside in:
`tests/test_e2e_integration.py`

Dependencies:
- `pytest`, `pytest-qt`
- `parasite_ai.config`
- `parasite_ai.ui.bridge.UIBridge`
- `parasite_ai.ui.companion_dock.CompanionDock`
- `parasite_ai.ui.ghost_hud.GhostHUD`
- `parasite_ai.safety.interrupt_guard.InterruptGuard`
- `parasite_ai.safety.window_guard.WindowGuard`
- `parasite_ai.hands.mouse.MouseDriver`
- `parasite_ai.hands.keyboard.KeyboardDriver`, `MockInputBackend`
- `parasite_ai.mind.dual_mind.DualMindPipeline`
- `parasite_ai.mind.brain_manager.LocalBrainManager`
- `parasite_ai.mind.memory.EpisodicMemory`
- `parasite_ai.mind.offloader.BrowserOffloader`, `SentinelClipboardVerifier`, `MockClipboardBackend`, `MockBrowserWindowBackend`

---

## 6. Verification Method

To verify the test suite once implemented:
```powershell
uv run pytest tests/test_e2e_integration.py -v
```
All scenarios must pass cleanly with 100% success rate in headless mode.
