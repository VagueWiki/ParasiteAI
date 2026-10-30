# Handoff Report: Milestone M5 Explorer 3 (Feature 18 — E2E Test Suite Architecture)

**Author**: `teamwork_explorer_m5_3`  
**Role**: Explorer / Synthesizer  
**Target Milestone**: Milestone M5 — Integration, Entry Points & E2E Acceptance  
**Working Directory**: `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m5_3\`  

---

## 1. Observation

1. **System & Acceptance Requirements**:
   - `ORIGINAL_REQUEST.md` (lines 31–46): Requires automated verification via `uv run pytest`, verifying:
     - Synthetic input (`LLMHF_INJECTED = 1`) ignored, physical touch (`LLMHF_INJECTED = 0`) aborts in `< 2ms`.
     - Hybrid screen grounding locates elements with coordinates.
     - Episodic memory detects consecutive action failure loops.
     - Sentinel clipboard verification saves, validates response text, and restores original clipboard.
   - `PROJECT.md` Feature 18 (lines 49–51): Mandates complete E2E test suite under `tests/test_e2e_integration.py` and Tier 5 adversarial coverage hardening.

2. **Existing Subsystem Testability & Polymorphic Hooks**:
   - `parasite_ai/safety/interrupt_guard.py` (lines 482–516):
     ```python
     def simulate_event(
         self,
         event_type: str,
         flags: int = 0,
         vk_code: int = 0,
         pt: Tuple[int, int] = (0, 0),
         w_param: Optional[int] = None,
     ) -> None:
     ```
     Enables software-driven deterministic injection of both physical (`flags = 0`) and synthetic (`flags = LLMHF_INJECTED / LLKHF_INJECTED`) input events directly to hook procedures without human hands.
   - `parasite_ai/safety/window_guard.py` (lines 129–166):
     ```python
     def evaluate_sensitivity(
         self,
         title: str,
         process_name: str,
         hwnd: int = 1,
         can_open_process: bool = True,
     ) -> Tuple[bool, str]:
     ```
     Provides pure, deterministic sensitivity classification with built-in fail-safes for `hwnd == 0` (desktop switch / lock screen) and `can_open_process == False` (elevated UAC prompts).
   - `parasite_ai/hands/mouse.py` (lines 98–121):
     `MouseDriver` exposes `simulation_mode=True`, `reticle_callback`, and `speed_factor`, tracking `simulation_history` and checking `cancellation_token` at 120Hz.
   - `parasite_ai/hands/keyboard.py` (lines 253–275):
     Exposes `MockInputBackend` recording virtual key events with per-keystroke interrupt cancellation.
   - `parasite_ai/ui/ghost_hud.py` (lines 126–133):
     `GhostHUD` exposes `enable_win32_styles=False`, allowing safe execution in headless / offscreen Qt environments without Win32 display dependencies.
   - `parasite_ai/ui/bridge.py` (lines 27–44, 47):
     `UIBridge` exposes `_goal_queue` and signals (`sig_state_changed`, `sig_thought_updated`, `sig_speech_updated`, `sig_telemetry_updated`, `sig_perception_updated`, `sig_targets_updated`, `sig_reticle_requested`).
   - `parasite_ai/mind/dual_mind.py` (lines 536–735):
     `DualMindPipeline.step()` encapsulates the entire closed-loop cycle: safety checks -> perception -> Pass 1 Persona monologue -> Pass 2 action plan -> physical execution -> settling -> visual diff -> episodic memory record -> telemetry update.
   - `parasite_ai/mind/offloader.py` (lines 101–123, 245–275, 280–350):
     Exposes `MockClipboardBackend`, `MockBrowserWindowBackend`, and `SentinelClipboardVerifier` guaranteeing original clipboard restoration in a `finally:` block.

3. **Current Test Execution Baseline**:
   - `uv run pytest tests/test_interrupt_guard.py tests/test_browser_offloader.py -v` executes 27 unit tests with 100% pass rate in 7.61s.
   - `pytest-qt` (version 4.5.0) is present and verified active in the virtual environment.

---

## 2. Logic Chain

1. **Deterministic Testability Without Hardware Peripherals**:
   - Based on Observations 2.1 through 2.6, all subsystems already contain pure Python abstractions, simulation modes, and software event simulators.
   - Therefore, all 6 E2E integration scenarios can be tested completely in memory and offscreen via `pytest-qt` (`qtbot`) without requiring physical displays, physical mice/keyboards, or active GPU VRAM.

2. **Scenario 1 (Clean Startup & Zero-Config Boot)**:
   - Driven by `main.py --dry-run` and `load_config()`.
   - By executing a subprocess invocation of `main.py --dry-run` and an in-process initialization of all 12 core components, the test proves that zero-config defaults load cleanly, components initialize without unhandled exceptions, and teardown releases all hooks/timers without lingering resources.

3. **Scenario 2 (End-to-End Goal Execution Cycle)**:
   - Driven by `UIBridge`, `CompanionDock`, `GhostHUD`, `ScreenGrounder`, and `DualMindPipeline`.
   - By feeding a goal through `bridge.sig_goal_submitted`, the test traces every step: goal dequeuing -> `THINKING` state -> Set-of-Mark visual bounding on HUD -> Pass 1 monologue -> Pass 2 `CLICK` action -> `DRIVING` state -> 300ms reticle countdown -> Bézier mouse glide -> click dispatch -> visual diff computation -> `EpisodicMemory` record -> step telemetry -> `DONE` completion -> HUD target clear.

4. **Scenario 3 (Physical Hardware Touch Interruption <2ms)**:
   - Driven by `InterruptGuard.simulate_event()` and `MouseDriver.move_to()`.
   - Injected synthetic events (`LLMHF_INJECTED = 1`) do not trip interrupt.
   - Physical events (`flags = 0`) set `cancellation_token` in `< 0.002s` (verified with `time.perf_counter()`).
   - Active mouse movements abort, held buttons are released, HUD reticle is cancelled, and dock transitions to `USER_OVERRIDE`.

5. **Scenario 4 (Sensitive Window Detection & Privacy Blackout)**:
   - Driven by `WindowGuard` and `DualMindPipeline`.
   - Activating a sensitive window (e.g. `bitwarden.exe`, `taskmgr.exe`, `hwnd == 0`) returns `is_safe_to_operate() == False`.
   - Dock transitions to `PROTECTED` (`🔒 PROTECTED`), perception preview is masked with privacy blackout overlay, HUD targets are cleared, and `DualMindPipeline` safely halts action dispatch.

6. **Scenario 5 (3-Strike Failure Loop Emergency Reset)**:
   - Driven by `EpisodicMemory` zero-diff tracking (`diff <= 0.005`).
   - Strike 1 logs initial failure; Strike 2 shifts dock mood to `Cautious`; Strike 3 trips `memory.is_in_loop() == True`.
   - `DualMindPipeline` overrides planned action to `ActionType.PANIC`, emits `sig_panic_triggered`, sets dock mood to `Panic-Averted`, and executes emergency key/button release. Positive diff cleanly resets strikes to 0.

7. **Scenario 6 (Zero-VRAM Visible Browser Brain Offload)**:
   - Driven by `BrowserOffloader` and `SentinelClipboardVerifier`.
   - Traverses visible browser window discovery and state machine (`LOCATING_BROWSER` through `COMPLETED`).
   - Generates unique UUID sentinel token, injects token into clipboard, executes harvest, accepts non-sentinel response, and verifies 100% guaranteed restoration of the user's pre-existing clipboard text in all execution paths (success, harvest error, and cancellation preemption).

---

## 3. Caveats

1. **Qt Platform in CI**: In purely headless Linux CI (if ever ported), `QT_QPA_PLATFORM=offscreen` is mandatory. On Windows, `enable_win32_styles=False` in `GhostHUD` ensures the overlay does not attempt Win32 `SetWindowLongW` calls on dummy test windows.
2. **Main.py Concurrency Model**: Explorer 1 is designing `main.py` entrypoint arguments (`--dry-run`, `--headless`). The test harness in `tests/test_e2e_integration.py` tests both CLI execution and in-process component wiring, ensuring compatibility regardless of whether CLI flags are parsed via `argparse` or `sys.argv`.
3. **No Caveats Regarding Subsystem Mockability**: Every required mock and simulation hook already exists in the production codebase.

---

## 4. Conclusion

The E2E test suite architecture is fully defined and documented in `plan.md`. The design covers all 6 required integration scenarios with exact assertions, sub-2ms timing guarantees, signal sequences, and Tier 5 adversarial coverage hardening. Implementing `tests/test_e2e_integration.py` according to this architecture will provide 100% acceptance verification for Milestone M5 and satisfy all criteria in `ORIGINAL_REQUEST.md` (R1–R5).

---

## 5. Verification Method

To independently verify this plan and execute the resulting E2E test suite:

1. **Inspect Artifacts**:
   - Plan: `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m5_3\plan.md`
   - Briefing: `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m5_3\BRIEFING.md`
2. **Execute Pytest Verification Command**:
   ```powershell
   uv run pytest tests/test_e2e_integration.py -v
   ```
3. **Invalidation Conditions**:
   - Any test failure in `test_e2e_integration.py`.
   - Hardware touch preemption latency exceeding 2.0ms.
   - User clipboard text corrupted or modified after browser offload harvest.
   - Unhandled exception during `--dry-run` bootstrapper execution.
