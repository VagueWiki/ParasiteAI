# Task Assignment: Milestone M3 Code Reviewer 1 (Companion Dock & Bridge)

**Recipient**: `teamwork_reviewer_m3_1`
**Role**: `teamwork_reviewer`
**Working Directory**: `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_reviewer_m3_1\`
**Assigned Milestone**: Milestone M3 — Desktop Companion Dock & Ghost-Hand Overlay

---

## Mandatory Instructions
1. Read `g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md`.
2. Read `g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md`.
3. Read `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_worker_m3\handoff.md`.
4. Inspect and review the source code for:
   - `parasite_ai/ui/companion_dock.py`
   - `parasite_ai/ui/bridge.py`
   - `parasite_ai/ui/types.py`
   - `tests/test_companion_dock.py`
   - `tests/test_ui_bridge.py`
5. Verify:
   - Code cleanliness, typing, and docstrings.
   - Frameless always-on-top window styling and boundary clamping.
   - 6 glowing visual states (`WATCHING`, `THINKING`, `DRIVING`, `USER_OVERRIDE`, `OFFLOADING`, `PROTECTED`) and mood badges.
   - Dual speech card (with typewriter effect) vs dark monospace thought stream.
   - Action telemetry and downscaled perception thumbnail with privacy blackout masking in `PROTECTED` state.
   - Thread safety: `UIBridge` queued connections and goal queue.
6. Run the test suite:
   - `uv run pytest tests/test_companion_dock.py tests/test_ui_bridge.py -v`
   - `uv run pytest -v` (full project test suite)
7. Produce `handoff.md` with:
   - Observation, Logic Chain, Caveats, Conclusion, Verification Method.
   - Clear Gate Verdict: **APPROVE** or **REQUEST_CHANGES**.
8. Notify the orchestrator via `send_message`.
