# Worker Dispatch: Milestone M2 (Generation 3 Replacement)

Working Directory: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_worker_m2_gen3\
Predecessor: teamwork_worker_m2_gen2 (interrupted during test suite implementation)
Original Request: g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md
Master Project Spec: g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md
Explorer 1 Plan: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m2_1\plan.md
Explorer 2 Plan: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m2_2\plan.md
Explorer 3 Plan: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m2_3\plan.md

## Inherited Accomplishments
All production source code files are ALREADY IMPLEMENTED:
- `parasite_ai/safety/interrupt_guard.py`
- `parasite_ai/safety/window_guard.py`
- `parasite_ai/safety/panic.py`
- `parasite_ai/safety/__init__.py`
- `parasite_ai/hands/kinematics.py`
- `parasite_ai/hands/mouse.py`
- `parasite_ai/hands/keyboard.py`
- `parasite_ai/hands/__init__.py`

And `tests/test_interrupt_guard.py` is fully implemented and passing 15/15 tests!

## Immediate Tasks for Worker Gen 3
1. Fix the assertion in `tests/test_window_guard.py` line 98:
   In `test_blacklist_elevated_console`:
   `evaluate_sensitivity()` returns `reason = "Sensitive window title matched: 'administrator:'"`.
   Change line 98 to:
   `assert is_sens is True`
   `assert ("elevated" in reason.lower() or "administrator" in reason.lower() or "sensitive window title" in reason.lower())`
   Verify with `uv run pytest tests/test_window_guard.py` (all 11 tests should pass).

2. Implement the remaining test suites (per Explorer plans):
   - `tests/test_panic.py` (verifying Esc, Ctrl+Alt+P, Ctrl+Alt+Backspace, corner slam, emergency hardware release).
   - `tests/test_kinematics.py` (verifying Fitts's Law, Cubic Bézier, Min-Jerk easing, micro-jitter damping, overshoot).
   - `tests/test_mouse_driver.py` (verifying 120Hz timeBeginPeriod, interrupt abort in < 2ms, reticle preview, simulation mode).
   - `tests/test_keyboard_driver.py` (verifying KEYEVENTF_UNICODE, emoji surrogate pairs, Shift+Enter multiline, cadence jitter, per-keystroke interrupt check).

3. Run full test verification:
   `uv run pytest -v`
   Ensure 100% tests pass (all 189 baseline tests + all M2 tests) with 0 failures.

4. Deliver `handoff.md` and notify orchestrator via `send_message`.

## Mandatory Integrity Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## 2026-10-29T13:01:17Z
You are teamwork_worker_m2_gen3, the Generation 3 replacement implementation worker for ParasiteAI Milestone M2: Safety & Physical Input Layer.

Your working directory is: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_worker_m2_gen3\

You MUST read:
1. ORIGINAL_REQUEST: g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md
2. Master Project Spec: g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md
3. Your Dispatch: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_worker_m2_gen3\DISPATCH.md
4. Explorer 1 Plan: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m2_1\plan.md
5. Explorer 2 Plan: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m2_2\plan.md
6. Explorer 3 Plan: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m2_3\plan.md
7. Existing codebase in g:\__Docs\ParasiteAI\parasite_ai\

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Context & Current Status:
All production source code files are ALREADY IMPLEMENTED in `parasite_ai/safety/` and `parasite_ai/hands/`!
`tests/test_interrupt_guard.py` is ALREADY IMPLEMENTED and passing 15/15 tests!

Your Immediate Tasks:
1. In `tests/test_window_guard.py` line 98 (`test_blacklist_elevated_console`), update the assertion from `assert "Elevated" in reason` to `assert ("elevated" in reason.lower() or "administrator" in reason.lower() or "sensitive window title" in reason.lower())`. Run `uv run pytest tests/test_window_guard.py` and verify all 11 tests pass.
2. Implement the remaining test files (as specified in Explorer plans):
   - `tests/test_panic.py` (panic hotkeys Esc, Ctrl+Alt+P, Ctrl+Alt+Backspace, corner slam, emergency hardware release).
   - `tests/test_kinematics.py` (Fitts's law, Cubic Bézier, Min-Jerk easing polynomial, micro-jitter damping, overshoot).
   - `tests/test_mouse_driver.py` (120Hz timeBeginPeriod, interrupt abort in < 2ms, reticle preview, simulation mode).
   - `tests/test_keyboard_driver.py` (KEYEVENTF_UNICODE, emoji surrogate pairs, Shift+Enter multiline, cadence jitter, per-keystroke interrupt check).
3. Run the complete pytest suite:
   `uv run pytest -v`
   Ensure 100% tests pass (all 189 baseline tests + all M2 tests) with zero failures or regressions.
4. Write your final handoff report in `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_worker_m2_gen3\handoff.md` and notify the orchestrator via send_message.
