# Worker Dispatch: Milestone M2 — Safety & Physical Input Layer

Working Directory: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_worker_m2\
Original Request: g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md
Master Project Spec: g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md
Explorer 1 Plan: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m2_1\plan.md
Explorer 1 Handoff: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m2_1\handoff.md
Explorer 2 Plan: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m2_2\plan.md
Explorer 2 Handoff: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m2_2\handoff.md
Explorer 3 Plan: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m2_3\plan.md
Explorer 3 Handoff: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m2_3\handoff.md

## Exclusive File Ownership
You own and must implement the following files:
1. `parasite_ai/safety/__init__.py`
2. `parasite_ai/safety/interrupt_guard.py`
3. `parasite_ai/safety/window_guard.py`
4. `parasite_ai/safety/panic.py`
5. `parasite_ai/hands/__init__.py`
6. `parasite_ai/hands/kinematics.py`
7. `parasite_ai/hands/mouse.py`
8. `parasite_ai/hands/keyboard.py`
9. `tests/test_interrupt_guard.py`
10. `tests/test_window_guard.py`
11. `tests/test_kinematics.py`
12. `tests/test_mouse_driver.py`
13. `tests/test_keyboard_driver.py`
14. `tests/test_panic.py`

## Mandatory Verification Command
You must run:
`uv run pytest`
And verify that all M1 tests (189 existing tests) PLUS all new M2 tests pass with 0 failures.

## Mandatory Integrity Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.


## 2026-10-29T12:48:41Z
Received dispatch from 9a16f679-6db4-4849-ba56-0f4856cbbf9b:
Implement ParasiteAI Milestone M2: Safety & Physical Input Layer.
Own and implement:
- parasite_ai/safety/__init__.py
- parasite_ai/safety/interrupt_guard.py
- parasite_ai/safety/window_guard.py
- parasite_ai/safety/panic.py
- parasite_ai/hands/__init__.py
- parasite_ai/hands/kinematics.py
- parasite_ai/hands/mouse.py
- parasite_ai/hands/keyboard.py
- tests/test_interrupt_guard.py
- tests/test_window_guard.py
- tests/test_kinematics.py
- tests/test_mouse_driver.py
- tests/test_keyboard_driver.py
- tests/test_panic.py
Run uv run pytest (189 existing tests + all new tests passing).
