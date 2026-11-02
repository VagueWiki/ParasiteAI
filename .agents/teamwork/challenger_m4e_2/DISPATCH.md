# DISPATCH — Challenger 2 (Milestone 4E)

## Mission
Adversarially stress-test `UniversalAppResolver` state transitions, attempt counters, rapid target app switching, Tier 2 -> Tier 3 -> Exhaustion progression, cancellation token responsiveness, and `verify_step_completion` across all 8 `StepIntent` types.

## Key Context & Paths
- Master Plan: `c:\Users\Suici\.gemini\antigravity\brain\464b4ef0-398b-45b1-94dc-857256a38046\phase_4_master_plan.md` (§8, §10 Sub-Phase 4E, §12 VERIF-11)
- Original Request: `C:\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md`
- Scope: `C:\ParasiteAI\.agents\teamwork\orchestrator_4\SCOPE.md`
- Worker Handoff: `C:\ParasiteAI\.agents\teamwork\teamwork_worker_m4e\handoff.md`
- Your Workspace: `C:\ParasiteAI\.agents\teamwork\challenger_m4e_2\`

## Target Adversarial Areas
1. `UniversalAppResolver` State Transitions & Loop Prevention:
   - Verify that when no SOM elements match:
     - Call 1: Hotkey ["win"] (Start chord)
     - Call 2: Type f"{app}\n" (Submit search, `_start_search_attempts=1`)
     - Call 3: Hotkey ["win", "r"] (Run dialog fallback chord)
     - Call 4: Type f"{app}\n" (Submit run dialog, `_run_dialog_attempts=1`)
     - Call 5+: ActionType.WAIT (Exhaustion — cleanly escalates to replan, NEVER loops back to Win)
   - Rapid app switching: switching `target_app` from "notepad" to "calculator" resets attempt counters immediately.
   - Non-blocking cadence buffer wait: verify that a cancelled `threading.Event` breaks out of the cadence wait in <20ms rather than blocking for full duration.
2. `verify_step_completion` & Contingency Insertion:
   - Stress-test all 8 `StepIntent` types (`LAUNCH_OR_ACTIVATE`, `NAVIGATE`, `INPUT_DATA`, `SELECT_OPTION`, `VERIFY_STATE`, `DISMISS_DIALOG`, `CONSULT_ADVISOR`, `CONCLUDE`).
   - Verify visual stagnation contingency (`screen_diff < threshold`) triggers `insert_stagnation_contingency`.
   - Verify missing caret contingency (`caret_active=False` on typing) triggers `insert_caret_contingency`.
   - Verify modal dialog detection triggers `insert_modal_dialog_contingency`.
3. Deliverable:
   - Author empirical test suite `tests/test_challenger_m4e_resolver_state.py`.
   - Run tests using `.\.venv\Scripts\python.exe -m pytest tests/test_challenger_m4e_resolver_state.py -v`.
   - Write `handoff.md` in `C:\ParasiteAI\.agents\teamwork\challenger_m4e_2\` with explicit verdict (`APPROVE` or `REQUEST_CHANGES`) and notify orchestrator.

## 2026-11-01T13:22:09Z
You are Challenger 2 for Milestone 4E (UniversalAppResolver State & Contingency Stress Testing).
Your working directory is C:\ParasiteAI\.agents\teamwork\challenger_m4e_2\.
Read your instructions in C:\ParasiteAI\.agents\teamwork\challenger_m4e_2\DISPATCH.md.
Also read ORIGINAL_REQUEST.md at C:\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md, SCOPE.md at C:\ParasiteAI\.agents\teamwork\orchestrator_4\SCOPE.md, and the worker handoff at C:\ParasiteAI\.agents\teamwork\teamwork_worker_m4e\handoff.md.
Adversarially stress-test UniversalAppResolver state transitions, attempt counters, rapid app switching, Tier 2 -> Tier 3 -> Exhaustion (WAIT) progression, non-blocking cadence wait responsiveness, and verify_step_completion across all 8 StepIntent types with automated contingency insertion.
Author tests/test_challenger_m4e_resolver_state.py and run via .\.venv\Scripts\python.exe -m pytest tests/test_challenger_m4e_resolver_state.py -v.
Write handoff.md in C:\ParasiteAI\.agents\teamwork\challenger_m4e_2\ with explicit verdict APPROVE or REQUEST_CHANGES and send message back to orchestrator.
