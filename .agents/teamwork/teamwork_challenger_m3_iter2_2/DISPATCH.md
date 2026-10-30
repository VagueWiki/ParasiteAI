# Task Assignment: Milestone M3 Iteration 2 Challenger 2 (Full System Cross-Subsystem Adversarial Stress)

**Recipient**: `teamwork_challenger_m3_iter2_2`
**Role**: `teamwork_challenger`
**Working Directory**: `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_challenger_m3_iter2_2\`
**Assigned Milestone**: Milestone M3 — Desktop Companion Dock & Ghost-Hand Overlay (Iteration 2 Gate)

---

## Instructions
1. Read `g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md`.
2. Read `g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md`.
3. Read `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_worker_m3_iter2\handoff.md`.
4. Adversarially challenge the entire UI subsystem (`parasite_ai/ui/`):
   - Re-execute and stress `tests/test_ghost_hud_adversarial.py` (33 tests) and `tests/test_companion_dock_adversarial.py` (14 tests).
   - Test cross-subsystem interactions between `CompanionDock` (telemetry/status/goal queue) and `GhostHUD` (Set-of-Mark/reticle) under concurrent execution.
   - Test simultaneous rapid reticle preview triggering alongside heavy telemetry flooding.
5. Execute:
   - `uv run pytest tests/test_ghost_hud_adversarial.py tests/test_companion_dock_adversarial.py -v`
   - `uv run pytest -v` (full project test suite)
6. Produce `handoff.md` with:
   - Observation, Logic Chain, Caveats, Conclusion, Verification Method.
   - Clear Gate Verdict: **APPROVE** or **REQUEST_CHANGES**.
7. Notify the orchestrator via `send_message`.


## 2026-10-29T16:36:13Z
You are assigned as Milestone M3 Iteration 2 Challenger 2 (`teamwork_challenger_m3_iter2_2`).

Your working directory is:
`g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_challenger_m3_iter2_2\`

Read your dispatch assignment:
`g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_challenger_m3_iter2_2\DISPATCH.md`

MANDATORY FIRST ACTIONS:
1. Initialize your `BRIEFING.md` and `progress.md` in your working directory.
2. Read `g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md`.
3. Read `g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md`.
4. Read `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_worker_m3_iter2\handoff.md`.

CHALLENGER SCOPE:
- Adversarially challenge the entire UI subsystem (`parasite_ai/ui/`):
  - Re-execute and stress `tests/test_ghost_hud_adversarial.py` (33 tests) and `tests/test_companion_dock_adversarial.py` (14 tests).
  - Test cross-subsystem interactions between `CompanionDock` (telemetry/status/goal queue) and `GhostHUD` (Set-of-Mark/reticle) under concurrent execution.
- Execute:
  `uv run pytest tests/test_ghost_hud_adversarial.py tests/test_companion_dock_adversarial.py -v`
  `uv run pytest -v` (full project test suite)
- Compile `handoff.md` with gate verdict: **APPROVE** or **REQUEST_CHANGES**.
- Notify the orchestrator via `send_message`.
