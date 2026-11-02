# DISPATCH — Reviewer 2 (Milestone 4F: Final System Integration & Polish)

## Mission
Review and verify edge-case remediations, LivingPlan dynamic contingency scheduling, and end-to-end integration across all Phase 4 modules.

## Key Context & Paths
- Master Plan: `c:\Users\Suici\.gemini\antigravity\brain\464b4ef0-398b-45b1-94dc-857256a38046\phase_4_master_plan.md` (§9, §10 Sub-Phase 4F, §12)
- Original Request: `C:\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md`
- Scope: `C:\ParasiteAI\.agents\teamwork\orchestrator_4\SCOPE.md`
- Worker Handoff: `C:\ParasiteAI\.agents\teamwork\teamwork_worker_m4f\handoff.md`
- Your Workspace: `C:\ParasiteAI\.agents\teamwork\reviewer_m4f_2\`

## Target Review Areas
1. `PrecisionAppMatcher.score_match`: Trailing non-word boundary matching (e.g. `notepad++`, `c++`, `c#`) in non-prefix positions.
2. `UniversalAppResolver.extract_target_app`: Attached punctuation parsing (e.g. `open visual studio code, then write code`).
3. `UniversalAppResolver.resolve_launch_action`: Defensive None/empty check.
4. `LivingPlan` contingency pointer advancement: Updating `plan.current_step_id` to prerequisite contingency step in `check_and_insert_contingencies`.
5. Run tests:
   - `.\.venv\Scripts\python.exe -m pytest tests/test_phase4_final_integration.py -v`
   - `.\.venv\Scripts\python.exe -m pytest tests/test_resolver_precision.py tests/test_schema_mapping.py -v`
6. Check anti-hardcoding invariant: `git grep -i "app_map" parasite_ai/` -> 0 matches.
7. Write `handoff.md` in `C:\ParasiteAI\.agents\teamwork\reviewer_m4f_2\` with explicit verdict `APPROVE` or `REQUEST_CHANGES` and notify orchestrator.


## 2026-11-01T13:43:33Z
You are Reviewer 2 for Milestone 4F (Final System Integration & Polish).
Your working directory is C:\ParasiteAI\.agents\teamwork\reviewer_m4f_2\.
Read your instructions in C:\ParasiteAI\.agents\teamwork\reviewer_m4f_2\DISPATCH.md.
Also read ORIGINAL_REQUEST.md at C:\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md, SCOPE.md at C:\ParasiteAI\.agents\teamwork\orchestrator_4\SCOPE.md, and the worker handoff at C:\ParasiteAI\.agents\teamwork\teamwork_worker_m4f\handoff.md.
Review edge-case polish: trailing non-word boundary matching in PrecisionAppMatcher, attached punctuation delimiter parsing in extract_target_app, defensive None handling, and LivingPlan prerequisite contingency pointer advancement.
Run tests via .\.venv\Scripts\python.exe -m pytest tests/test_phase4_final_integration.py tests/test_resolver_precision.py tests/test_schema_mapping.py -v.
Verify anti-hardcoding invariant (git grep -i "app_map" parasite_ai/).
Write handoff.md in C:\ParasiteAI\.agents\teamwork\reviewer_m4f_2\ with explicit verdict APPROVE or REQUEST_CHANGES and send message back to orchestrator.
