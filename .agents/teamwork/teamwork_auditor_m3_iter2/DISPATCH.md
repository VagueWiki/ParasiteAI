# Task Assignment: Milestone M3 Iteration 2 Forensic Integrity Auditor

**Recipient**: `teamwork_auditor_m3_iter2`
**Role**: `teamwork_auditor`
**Working Directory**: `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_auditor_m3_iter2\`
**Assigned Milestone**: Milestone M3 — Desktop Companion Dock & Ghost-Hand Overlay (Iteration 2 Gate)

---

## Instructions
1. Read `g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md`.
2. Read `g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md`.
3. Read `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_worker_m3_iter2\handoff.md`.
4. Perform comprehensive forensic audit across all Milestone M3 files, specifically focusing on the remediated code:
   - `parasite_ai/ui/companion_dock.py`
   - `parasite_ai/ui/bridge.py`
   - `tests/test_companion_dock_adversarial.py`
   - All other M3 production and test files.
5. Integrity Checks to Execute:
   - Check 1: Facade and Dummy Detection (genuine slot overloads and real signal emission).
   - Check 2: Tautological and Mock Bypass Testing (verify all 14 adversarial tests in `test_companion_dock_adversarial.py` perform real assertions).
   - Check 3: Hardcoded Value Detection (verify `round((current_step * 100) / total_steps)` is a general mathematical calculation and not hardcoding step 29/57/58).
   - Check 4: Real Win32 Style & DPI Verification.
   - Check 5: True Kinematic Path Rendering.
   - Check 6: Privacy Blackout Verification.
6. Execute tests:
   - `uv run pytest tests/test_companion_dock_adversarial.py tests/test_ghost_hud_adversarial.py -v`
   - `uv run pytest -v` (full project test suite)
7. Produce `handoff.md` with:
   - Forensic evidence and clear gate verdict: **CLEAN** or **INTEGRITY VIOLATION**.
8. Notify the orchestrator via `send_message`.


## 2026-10-29T16:36:19Z
You are assigned as Milestone M3 Iteration 2 Forensic Integrity Auditor (`teamwork_auditor_m3_iter2`).

Your working directory is:
`g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_auditor_m3_iter2\`

Read your dispatch assignment:
`g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_auditor_m3_iter2\DISPATCH.md`

MANDATORY FIRST ACTIONS:
1. Initialize your `BRIEFING.md` and `progress.md` in your working directory.
2. Read `g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md`.
3. Read `g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md`.
4. Read `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_worker_m3_iter2\handoff.md`.

AUDIT SCOPE:
- Perform forensic integrity checks on the remediated code and tests:
  - `parasite_ai/ui/companion_dock.py`
  - `parasite_ai/ui/bridge.py`
  - `tests/test_companion_dock_adversarial.py`
  - All other M3 files.
- Verify 6 systematic checks:
  1. Facade and Dummy Detection (genuine slot overloads and real signal emission).
  2. Tautological and Mock Bypass Testing.
  3. Hardcoded Value Detection (verify `round((current_step * 100) / total_steps)` is a general mathematical calculation).
  4. Real Win32 Style & DPI Verification.
  5. True Kinematic Path Rendering.
  6. Privacy Blackout Verification.
- Run tests:
  `uv run pytest tests/test_companion_dock_adversarial.py tests/test_ghost_hud_adversarial.py -v`
  `uv run pytest -v` (full project test suite)
- Compile `handoff.md` with forensic evidence and clear gate verdict: **CLEAN** or **INTEGRITY VIOLATION**.
- Notify the orchestrator via `send_message`.
