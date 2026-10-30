# Task Assignment: Milestone M3 Iteration 2 Explorer 2 (Telemetry Step Float Precision)

**Recipient**: `teamwork_explorer_m3_iter2_2`
**Role**: `teamwork_explorer`
**Working Directory**: `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m3_iter2_2\`
**Assigned Milestone**: Milestone M3 — Desktop Companion Dock & Ghost-Hand Overlay (Iteration 2)

---

## Previous Failure Output & Context
In Milestone M3 Iteration 1 Gate Evaluation, Challenger 1 uncovered the following defect:
- **Defect 2**: IEEE 754 Floating-Point Truncation in Telemetry Step Progress
- **Location**: `parasite_ai/ui/companion_dock.py` line 589
- **Symptom**: `pct = int((current_step / total_steps) * 100)`. In Python floating point arithmetic, `(29 / 100) * 100` evaluates to `28.999999999999996`. Calling `int(...)` truncates to `28%` instead of `29%`. Similar truncation occurs at steps 57 and 58.
- **Failing Test**: `tests/test_companion_dock_adversarial.py::TestCompanionDockAdversarial::test_telemetry_step_precision_calculation`

---

## Instructions
1. Read `g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md`.
2. Read `g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md`.
3. Read `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_challenger_m3_1\handoff.md`.
4. Inspect `parasite_ai/ui/companion_dock.py` around line 589.
5. Formulate an exact fix strategy and plan for the implementation worker:
   - Analyze `pct = round((current_step / total_steps) * 100)` vs integer division `(current_step * 100) // total_steps` vs clamping `max(0, min(100, ...))`.
   - Ensure edge cases (0 total steps, negative steps, current_step > total_steps) are safely handled.
6. Write your plan in `plan.md` and handoff in `handoff.md`. Do NOT modify code directly.
7. Notify the orchestrator via `send_message`.

## 2026-10-29T16:19:39Z
You are assigned as Milestone M3 Iteration 2 Explorer 2 (`teamwork_explorer_m3_iter2_2`).
Working directory: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m3_iter2_2\
Scope: Defect 2 (IEEE 754 floating-point truncation bug in CompanionDock.update_telemetry).
