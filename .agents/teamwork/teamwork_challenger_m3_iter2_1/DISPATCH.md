# Task Assignment: Milestone M3 Iteration 2 Challenger 1 (Adversarial Regression & Telemetry Re-Challenge)

**Recipient**: `teamwork_challenger_m3_iter2_1`
**Role**: `teamwork_challenger`
**Working Directory**: `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_challenger_m3_iter2_1\`
**Assigned Milestone**: Milestone M3 — Desktop Companion Dock & Ghost-Hand Overlay (Iteration 2 Gate)

---

## Instructions
1. Read `g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md`.
2. Read `g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md`.
3. Read `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_challenger_m3_1\handoff.md` (which documented the 3 original defects).
4. Read `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_worker_m3_iter2\handoff.md`.
5. Empirically re-verify all 14 adversarial test cases in `tests/test_companion_dock_adversarial.py`.
6. Add further adversarial challenges if necessary (e.g. rapid switching between 1-arg and 3-arg telemetry emissions, step overflow `current_step > total_steps`, zero total steps with non-zero current step, perception preview element list mutation).
7. Execute:
   - `uv run pytest tests/test_companion_dock_adversarial.py -v`
   - `uv run pytest -v` (full project test suite)
8. Produce `handoff.md` with:
   - Observation, Logic Chain, Caveats, Conclusion, Verification Method.
   - Clear Gate Verdict: **APPROVE** (if all defects fixed and zero new issues) or **REQUEST_CHANGES**.
9. Notify the orchestrator via `send_message`.


## 2026-10-29T16:36:06Z
Received dispatch from parent `9a16f679-6db4-4849-ba56-0f4856cbbf9b`:
MANDATORY FIRST ACTIONS:
1. Initialize your BRIEFING.md and progress.md in your working directory.
2. Read g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md.
3. Read g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md.
4. Read g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_challenger_m3_1\handoff.md.
5. Read g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_worker_m3_iter2\handoff.md.

CHALLENGER SCOPE:
- Re-execute and stress all 14 tests in tests/test_companion_dock_adversarial.py.
- Formulate additional edge-case stress challenges if any gaps exist.
- Execute:
  uv run pytest tests/test_companion_dock_adversarial.py -v
  uv run pytest -v (full project test suite)
- Compile handoff.md with gate verdict: APPROVE (if robust) or REQUEST_CHANGES.
- Notify the orchestrator via send_message.
