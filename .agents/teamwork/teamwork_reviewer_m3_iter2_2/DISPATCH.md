# Task Assignment: Milestone M3 Iteration 2 Code Reviewer 2 (Ghost HUD, Win32 & DPI Integration)

**Recipient**: `teamwork_reviewer_m3_iter2_2`
**Role**: `teamwork_reviewer`
**Working Directory**: `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_reviewer_m3_iter2_2\`
**Assigned Milestone**: Milestone M3 — Desktop Companion Dock & Ghost-Hand Overlay (Iteration 2 Gate)

---

## Instructions
1. Read `g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md`.
2. Read `g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md`.
3. Read `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_worker_m3_iter2\handoff.md`.
4. Inspect the entire UI subsystem (`parasite_ai/ui/ghost_hud.py`, `win32_styles.py`, `dpi.py`, `types.py`, `bridge.py`, `companion_dock.py`).
5. Verify:
   - Zero regressions in GhostHUD, DPI awareness, and Win32 extended click-through styles.
   - Reticle preemption, virtual desktop bounds handling, Set-of-Mark box/badge rendering.
   - Interoperability between `UIBridge`, `GhostHUD`, and `CompanionDock`.
6. Run tests:
   - `uv run pytest tests/test_ghost_hud_adversarial.py tests/test_ghost_hud.py tests/test_dpi.py -v`
   - `uv run pytest -v` (full project test suite)
7. Produce `handoff.md` with:
   - Observation, Logic Chain, Caveats, Conclusion, Verification Method.
   - Clear Gate Verdict: **APPROVE** or **REQUEST_CHANGES**.
8. Notify the orchestrator via `send_message`.


## 2026-10-29T16:35:51Z
You are assigned as Milestone M3 Iteration 2 Code Reviewer 2 (`teamwork_reviewer_m3_iter2_2`).

Your working directory is:
`g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_reviewer_m3_iter2_2\`

Read your dispatch assignment:
`g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_reviewer_m3_iter2_2\DISPATCH.md`

MANDATORY FIRST ACTIONS:
1. Initialize your `BRIEFING.md` and `progress.md` in your working directory.
2. Read `g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md`.
3. Read `g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md`.
4. Read `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_worker_m3_iter2\handoff.md`.

REVIEW SCOPE:
- Inspect `parasite_ai/ui/ghost_hud.py`, `win32_styles.py`, `dpi.py`, `types.py`, `bridge.py`, `companion_dock.py`.
- Verify zero regressions across GhostHUD, Win32 styles, and DPI bootstrap.
- Execute tests:
  `uv run pytest tests/test_ghost_hud_adversarial.py tests/test_ghost_hud.py tests/test_dpi.py -v`
  `uv run pytest -v` (full project test suite)
- Compile `handoff.md` with gate verdict: **APPROVE** or **REQUEST_CHANGES**.
- Notify the orchestrator via `send_message`.
