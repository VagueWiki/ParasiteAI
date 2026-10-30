# Worker Dispatch: Milestone M2 (Generation 2 Replacement)

Working Directory: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_worker_m2_gen2\
Predecessor: teamwork_worker_m2 (interrupted mid-implementation by platform code 400)
Original Request: g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md
Master Project Spec: g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md
Explorer 1 Plan: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m2_1\plan.md
Explorer 1 Handoff: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m2_1\handoff.md
Explorer 2 Plan: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m2_2\plan.md
Explorer 2 Handoff: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m2_2\handoff.md
Explorer 3 Plan: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m2_3\plan.md
Explorer 3 Handoff: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m2_3\handoff.md

## Current Progress Inherited
Predecessor already created:
- `parasite_ai/safety/interrupt_guard.py` (complete Win32 low-level hooks, cancellation token, sliding cooldown, simulation harness)
- `parasite_ai/safety/window_guard.py` (complete foreground window query, sensitive process/title blacklist, fail-safe on hwnd == 0)
- `parasite_ai/safety/panic.py` (complete panic triggers and emergency hardware release)
- `parasite_ai/safety/__init__.py`
- `parasite_ai/hands/kinematics.py` (complete Fitts's law, Cubic Bézier, Min-Jerk easing, micro-jitter, overshoot)
- `parasite_ai/hands/mouse.py` (complete MouseDriver with 120Hz timeBeginPeriod, 300ms reticle hook, SendInput, simulation backend)

## Remaining Work Items
1. Review and verify existing safety and hands files for correctness against explorer plans.
2. Implement `parasite_ai/hands/keyboard.py`:
   - `KeyboardDriver` with `IInputBackend` / `Win32InputBackend` / `MockInputBackend`.
   - `KEYEVENTF_UNICODE (0x0004)` typing with exact 64-bit aligned `INPUT` structure (40 bytes, offset 8).
   - Astral plane emoji surrogate pairs ($W_1$ and $W_2$ for codepoints $> 0xFFFF$).
   - Multiline safety: `Shift+Enter` for intermediate newlines vs `Enter` for prompt submission.
   - Natural human cadence jitter (log-normal intervals 25-75ms, punctuation 80-150ms, paragraph 150-300ms).
   - Sub-2ms per-keystroke interrupt check via cancellation token with stuck-key release.
   - Atomic `click_and_type` with click, caret settle delay (60-90ms), and per-keystroke interrupt checks.
3. Implement `parasite_ai/hands/__init__.py` exporting `KinematicsEngine`, `KinematicConfig`, `MouseDriver`, `KeyboardDriver`.
4. Implement test suites under `tests/`:
   - `tests/test_interrupt_guard.py`
   - `tests/test_window_guard.py`
   - `tests/test_panic.py`
   - `tests/test_kinematics.py`
   - `tests/test_mouse_driver.py`
   - `tests/test_keyboard_driver.py`
5. Run full test verification:
   `uv run pytest`
   Ensure 100% tests pass (all 189 baseline tests + all new M2 tests) with zero failures or regressions.

## Mandatory Integrity Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.
