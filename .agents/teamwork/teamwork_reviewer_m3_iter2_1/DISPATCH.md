# Task Assignment: Milestone M3 Iteration 2 Code Reviewer 1 (Companion Dock & Bridge Remediation)

**Recipient**: `teamwork_reviewer_m3_iter2_1`
**Role**: `teamwork_reviewer`
**Working Directory**: `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_reviewer_m3_iter2_1\`
**Assigned Milestone**: Milestone M3 — Desktop Companion Dock & Ghost-Hand Overlay (Iteration 2 Gate)

---

## Instructions
1. Read `g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md`.
2. Read `g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md`.
3. Read `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_worker_m3_iter2\handoff.md`.
4. Inspect the remediated code in:
   - `parasite_ai/ui/companion_dock.py`
   - `parasite_ai/ui/bridge.py`
5. Verify:
   - Defect 1 fix: `@pyqtSlot(object, list)` overload correctly stacked on `update_perception_preview`.
   - Defect 2 fix: float precision rounding `pct = round((current_step * 100) / total_steps)` in `update_telemetry`.
   - Defect 3 fix: overloaded `sig_telemetry_updated = pyqtSignal([str], [str, int, int])`, `notify_telemetry` dispatcher, `@pyqtSlot` decorators on `update_telemetry`, and dual connection in `_connect_bridge`.
6. Run tests:
   - `uv run pytest tests/test_companion_dock_adversarial.py tests/test_companion_dock.py tests/test_ui_bridge.py -v`
   - `uv run pytest -v` (full project test suite)
7. Produce `handoff.md` with:
   - Observation, Logic Chain, Caveats, Conclusion, Verification Method.
   - Clear Gate Verdict: **APPROVE** or **REQUEST_CHANGES**.
8. Notify the orchestrator via `send_message`.
