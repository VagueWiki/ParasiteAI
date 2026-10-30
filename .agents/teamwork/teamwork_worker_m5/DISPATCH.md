# Task Assignment: Milestone M5 Implementation Worker

**Recipient**: `teamwork_worker_m5`
**Role**: `teamwork_worker`
**Working Directory**: `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_worker_m5\`
**Assigned Milestone**: Milestone M5 — Integration, Entry Points & E2E Acceptance

---

## ⚠️ MANDATORY INTEGRITY WARNING (ZERO TOLERANCE)
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

---

## Required Reference Documents (READ BEFORE CODING)
1. `g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md` (Authoritative User Request)
2. `g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md` (System Architecture & Contracts)
3. Explorer Plans:
   - Explorer 1 (Entry Points): `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m5_1\plan.md`
   - Explorer 2 (Closed-Loop Runtime): `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m5_2\plan.md`
   - Explorer 3 (E2E Test Architecture): `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m5_3\plan.md`

---

## Scope & File Ownership
You have EXCLUSIVE write ownership of the following files:
1. `parasite_ai/ui/dpi.py` (add `init_dpi_awareness = init_high_dpi_awareness` alias)
2. `parasite_ai/ui/__init__.py` (export `init_dpi_awareness`)
3. `parasite_ai/ui/companion_dock.py` (add `ndarray_to_qimage` converter so numpy perception frames display cleanly)
4. `parasite_ai/runtime.py` (implement `RuntimeOrchestrator` coordinating closed-loop execution and signal wiring)
5. `parasite_ai/main.py` (implement `ParasiteApp`, CLI parser, cognitive daemon, clean shutdown)
6. `main.py` (root entrypoint delegating to `parasite_ai.main:main()`)
7. `launch_parasite.bat` (root batch script verifying `uv`, running `uv sync`, and `uv run python main.py %*`)
8. `tests/test_entrypoints.py` (CLI, dry-run, headless, and batch script tests)
9. `tests/test_e2e_integration.py` (comprehensive 6-scenario E2E acceptance suite)

---

## Detailed Implementation Requirements

### 1. UI Enhancements:
- In `parasite_ai/ui/dpi.py`: Add `init_dpi_awareness = init_high_dpi_awareness` and export it in `parasite_ai/ui/__init__.py`.
- In `parasite_ai/ui/companion_dock.py`: Update `update_perception_preview` to support `np.ndarray` input by converting to `QImage` (via `QImage(frame.data, w, h, 3*w, QImage.Format.Format_RGB888)` or `ndarray_to_qimage`), ensuring live desktop perception thumbnails render without error.

### 2. Closed-Loop Runtime Orchestrator (`parasite_ai/runtime.py`):
- Implement `RuntimeOrchestrator` class:
  - Manages background `CognitiveWorkerThread` daemon.
  - Wires all 14 signals between `UIBridge`, `CompanionDock`, `GhostHUD`, `DualMindPipeline`, `InterruptGuard`, and `WindowGuard`.
  - Coordinates closed loop:
    Goal Dequeue -> `THINKING` state -> Screen Grounding (`set_hud_targets`, `notify_perception`) -> Pass 1 Persona monologue (`notify_speech`, `notify_thought`) -> Pass 2 Action plan -> `DRIVING` state -> 300ms pre-click reticle (`show_reticle`) -> Kinematic curved mouse movement with sub-2ms hardware interrupt check -> Screen diff computation -> Episodic memory recording -> Step telemetry update (`notify_telemetry`).
  - Connects hardware interrupt callback (`on_interrupt_callback` -> clear reticle, set dock `USER_OVERRIDE`).
  - Connects sensitive window callback (`WindowGuard` -> privacy blackout masking, clear HUD targets, set dock `PROTECTED`).
  - Handles 3-strike failure loop detection (`memory.is_in_loop()` -> emergency `PANIC` reset, set dock mood `Panic-Averted`).

### 3. Application Entry Points (`parasite_ai/main.py`, root `main.py`, `launch_parasite.bat`):
- `parasite_ai/main.py`:
  - `ParasiteApp` class coordinating high-DPI bootstrap (`init_dpi_awareness()`), config loading (`load_config()`), Qt app setup, `UIBridge`, `CompanionDock`, `GhostHUD`, `RuntimeOrchestrator`, and clean shutdown.
  - CLI parser: `--config <path>`, `--headless` (sets `simulation_mode=True`, `enable_win32_styles=False`), `--dry-run` (initializes all components, verifies health, exits code 0), `--no-hud`, `--brain-mode <mode>`, `--goal <text>`, `--log-level <level>`.
  - Signal handling: 200ms `QTimer` to allow Python `SIGINT` / `Ctrl+C` handling inside Qt event loop.
  - `main(argv=None) -> int` entrypoint function.
- Root `main.py`: Top-level delegator:
  ```python
  import sys
  from parasite_ai.main import main

  if __name__ == "__main__":
      sys.exit(main())
  ```
- Root `launch_parasite.bat`: One-click Windows batch script checking `uv`, syncing virtual environment via `uv sync`, and running `uv run python main.py %*`.

### 4. Automated Verification Suites:
- `tests/test_entrypoints.py`:
  - Tests CLI argument parsing (`--config`, `--headless`, `--dry-run`, `--no-hud`, `--brain-mode`, `--goal`).
  - Tests `--dry-run` exits code 0 cleanly without hanging.
  - Tests `launch_parasite.bat` exists, contains valid Windows batch syntax, `uv sync`, and `uv run python main.py %*`.
  - Tests DPI awareness alias `init_dpi_awareness`.
- `tests/test_e2e_integration.py`:
  - Implement all 6 E2E acceptance scenarios in detail:
    1. Scenario 1: Clean Startup & Zero-Config Default Boot.
    2. Scenario 2: End-to-End Goal Execution Cycle (Goal -> Set-of-Mark -> Monologue -> Reticle -> Mouse Glide -> Diff -> Telemetry).
    3. Scenario 3: Physical Hardware Touch Interruption (<2ms preemption, atomic token set, dock transitions to `USER_OVERRIDE`).
    4. Scenario 4: Sensitive Window Detection & Privacy Blackout (`WindowGuard` detect password manager -> perception feed blacked out -> dock `PROTECTED` -> actions blocked).
    5. Scenario 5: 3-Strike Failure Loop Emergency Reset (3 no-diff actions -> `is_in_loop()` -> emergency PANIC recovery).
    6. Scenario 6: Zero-VRAM Visible Browser Brain Offload (fallback to `BrowserOffloadBackend` -> visible Chrome automation -> Sentinel Clipboard Verification with guaranteed restore).

---

## Verification Requirements
You must run the tests yourself and document results in your handoff report:
1. `uv run python main.py --dry-run --headless` (Must exit code 0)
2. `uv run pytest tests/test_entrypoints.py -v`
3. `uv run pytest tests/test_e2e_integration.py -v`
4. `uv run pytest` (Ensure 100% of all 552 existing tests pass, 0 regressions, all new tests pass)

Author `handoff.md` with: Observation, Logic Chain, Caveats, Conclusion, and Verification Method.
Notify orchestrator via `send_message` when done.


## 2026-10-29T17:40:26Z
[Message] timestamp=2026-10-29T17:40:26Z sender=9a16f679-6db4-4849-ba56-0f4856cbbf9b priority=MESSAGE_PRIORITY_HIGH
You are assigned as Milestone M5 Implementation Worker (`teamwork_worker_m5`).

Working Directory:
`g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_worker_m5\`

Read your full dispatch instructions:
`g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_worker_m5\DISPATCH.md`

MANDATORY FIRST ACTIONS:
1. Initialize your `BRIEFING.md` and `progress.md` in your working directory.
2. Read `g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md`.
3. Read `g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md`.
4. Read the three Explorer plans:
   - `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m5_1\plan.md`
   - `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m5_2\plan.md`
   - `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m5_3\plan.md`

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

SCOPE & EXCLUSIVE FILE OWNERSHIP:
1. `parasite_ai/ui/dpi.py` (add `init_dpi_awareness = init_high_dpi_awareness`)
2. `parasite_ai/ui/__init__.py` (export `init_dpi_awareness`)
3. `parasite_ai/ui/companion_dock.py` (add `ndarray_to_qimage` converter)
4. `parasite_ai/runtime.py` (implement `RuntimeOrchestrator`)
5. `parasite_ai/main.py` (implement `ParasiteApp`, CLI parser, cognitive daemon, clean shutdown)
6. `main.py` (root entrypoint delegating to `parasite_ai.main:main()`)
7. `launch_parasite.bat` (root batch script verifying `uv`, running `uv sync`, and `uv run python main.py %*`)
8. `tests/test_entrypoints.py` (CLI, dry-run, headless, and batch script tests)
9. `tests/test_e2e_integration.py` (comprehensive 6-scenario E2E acceptance suite)

Execute the full build and verification:
- `uv run python main.py --dry-run --headless`
- `uv run pytest tests/test_entrypoints.py -v`
- `uv run pytest tests/test_e2e_integration.py -v`
- `uv run pytest` (verify 100% of all 552 existing tests pass, 0 regressions, all new tests pass)

Document all commands, results, and findings in `handoff.md`.
Notify the orchestrator via `send_message` when complete.
