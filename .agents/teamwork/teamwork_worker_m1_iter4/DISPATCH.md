## 2026-10-29T12:26:48Z
You are teamwork_worker_m1_iter4.
Working Directory: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_worker_m1_iter4\
Original Request: g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md
Project Spec: g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md

Plans to Implement:
- Explorer 1 Plan: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m1_iter4_1\plan.md
- Explorer 2 Plan: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m1_iter4_2\plan.md
- Explorer 3 Plan: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m1_iter4_3\plan.md

Exclusive File Ownership:
- parasite_ai/mind/brain_manager.py

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Mission:
1. In `parasite_ai/mind/brain_manager.py`:
   - Add early chunk-loop abort if `real_total > 0 and bytes_downloaded > real_total:` to break early on oversized stream overflow.
   - Update line 777 check from `< real_total` to strict two-sided equality `!= real_total` (along with `real_total <= 0` or `temp_size != real_total` or `temp_size == 0`).
   - Clean up `temp_path`, transition state to `BrainState.DOWNLOAD_FAILED`, and set progress status to `"failed"`.
2. Run `uv run pytest -v` and verify that ALL 178 tests pass with exit code 0.
3. Write handoff report to `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_worker_m1_iter4\handoff.md`.
4. Message parent upon completion.
