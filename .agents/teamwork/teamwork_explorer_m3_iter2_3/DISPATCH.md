# Task Assignment: Milestone M3 Iteration 2 Explorer 3 (UIBridge Telemetry Step Progress)

**Recipient**: `teamwork_explorer_m3_iter2_3`
**Role**: `teamwork_explorer`
**Working Directory**: `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m3_iter2_3\`
**Assigned Milestone**: Milestone M3 — Desktop Companion Dock & Ghost-Hand Overlay (Iteration 2)

---

## Previous Failure Output & Context
In Milestone M3 Iteration 1 Gate Evaluation, Challenger 1 uncovered the following defect:
- **Defect 3**: `UIBridge.notify_telemetry` Cannot Transmit Step Progress
- **Location**: `parasite_ai/ui/bridge.py` lines 31 & 72, and `parasite_ai/ui/companion_dock.py` lines 712-713
- **Symptom**: `UIBridge.sig_telemetry_updated = pyqtSignal(str)` and `notify_telemetry(self, telemetry: str)` only accept a single string, whereas `CompanionDock.update_telemetry` accepts `(text: str, current_step: int = 0, total_steps: int = 0)`. Background workers in cognitive pipelines (M4/M5) cannot report step progress via `UIBridge`, and calling `notify_telemetry(text)` resets existing step progress to 0.
- **Failing Test**: `tests/test_companion_dock_adversarial.py::TestCompanionDockAdversarial::test_ui_bridge_telemetry_step_progress_parameters`

---

## Instructions
1. Read `g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md`.
2. Read `g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md`.
3. Read `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_challenger_m3_1\handoff.md`.
4. Inspect `parasite_ai/ui/bridge.py` and `parasite_ai/ui/companion_dock.py`.
5. Formulate an exact fix strategy and plan for the implementation worker:
   - Overloading or signature extension of `sig_telemetry_updated` (e.g. `pyqtSignal([str], [str, int, int])` or `pyqtSignal(str, int, int)` with default parameters in `notify_telemetry`).
   - Signature in `UIBridge.notify_telemetry(self, telemetry: str, current_step: int = 0, total_steps: int = 0) -> None`.
   - Wiring in `CompanionDock._connect_bridge` to ensure both 1-argument and 3-argument emissions route properly to `update_telemetry`.
   - Ensure existing unit tests in `tests/test_ui_bridge.py` and `tests/test_companion_dock.py` remain 100% passing.
6. Write your plan in `plan.md` and handoff in `handoff.md`. Do NOT modify code directly.
7. Notify the orchestrator via `send_message`.


## 2026-10-29T16:19:45Z
You are assigned as Milestone M3 Iteration 2 Explorer 3 (`teamwork_explorer_m3_iter2_3`).

Your working directory is:
`g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m3_iter2_3\`

Read your dispatch assignment:
`g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m3_iter2_3\DISPATCH.md`

MANDATORY FIRST ACTIONS:
1. Initialize your `BRIEFING.md` and `progress.md` in your working directory.
2. Read `g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md`.
3. Read `g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md`.
4. Read `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_challenger_m3_1\handoff.md`.

EXPLORER SCOPE:
- Analyze Defect 3: Extending `UIBridge.sig_telemetry_updated` and `UIBridge.notify_telemetry(telemetry, current_step, total_steps)` while preserving backward compatibility and updating dock connection in `CompanionDock._connect_bridge`.
- Inspect `parasite_ai/ui/bridge.py` and `parasite_ai/ui/companion_dock.py`.
- Formulate precise implementation plan and fix strategy for the worker.
- Document in `plan.md` and `handoff.md`. Do NOT modify code directly.
- Notify the orchestrator via `send_message`.
