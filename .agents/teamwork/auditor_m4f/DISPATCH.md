# DISPATCH — Forensic Auditor (Milestone 4F: Final Victory Verification & Full Regression Audit)

## Mission
Perform comprehensive forensic integrity audit for Milestone 4F and certify full compliance with the Victory Verification Matrix (VERIF-1 through VERIF-11).

## Key Context & Paths
- Master Plan: `c:\Users\Suici\.gemini\antigravity\brain\464b4ef0-398b-45b1-94dc-857256a38046\phase_4_master_plan.md` (§12 Victory Verification Matrix)
- Original Request: `C:\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md`
- Scope: `C:\ParasiteAI\.agents\teamwork\orchestrator_4\SCOPE.md`
- Worker Handoff: `C:\ParasiteAI\.agents\teamwork\teamwork_worker_m4f\handoff.md`
- Your Workspace: `C:\ParasiteAI\.agents\teamwork\auditor_m4f\`

## Mandatory Forensic Integrity Checks
1. Victory Verification Matrix (VERIF-1 through VERIF-11):
   - VERIF-1: 4-Tier Escalation State Machine (T1 -> T2 -> T3 -> T4 -> USER_OVERRIDE).
   - VERIF-2: Dual-Channel Output Router & Persona Voice (Channel A JSON vs Channel B speech monologue).
   - VERIF-3: Action-Aware Strike Evaluation (CLI returncode, GUI localized ROI diff >= 0.02, passive actions exempt).
   - VERIF-4: Tool-Aware Affordance (PHYSICAL_GUI vs LOCAL_DEVELOPER_TOOL vs STRATEGIC_ADVISOR).
   - VERIF-5: CLI Sandbox security (whitelist, scraping prohibition, 30s timeout, process tree kill order).
   - VERIF-6: Sub-2ms low-level Win32 hardware touch preemption (`LLMHF_INJECTED`, `LLKHF_INJECTED`).
   - VERIF-7: Instant hard kill (`Ctrl+Alt+K`, `taskkill /F /T /PID` in <5ms).
   - VERIF-8: `brain.mode: "local_llm"` default (zero silent cloud exfiltration).
   - VERIF-9: 10 Win32 ctypes struct sizes match 64-bit ABI (`POINT`=8, `RECT`=16, `MSLLHOOKSTRUCT`=32, `KBDLLHOOKSTRUCT`=24, `MOUSEINPUT`=32, `KEYBDINPUT`=24, `HARDWAREINPUT`=8, `INPUT_UNION`=32, `INPUT`=40, `GUITHREADINFO`=72).
   - VERIF-10: Grounded Capability Contract (<3 KB Set-of-Mark table + active window brief).
   - VERIF-11: Strict anti-hardcoding rule (`git grep -i "app_map" parasite_ai/` = 0) & Precision Matching.
2. Anti-Hardcoding Invariant Check:
   - `git grep -i "app_map" parasite_ai/` -> Must be 0 matches.
   - `git grep -i "app_lookup" parasite_ai/` -> Must be 0 matches.
3. Test Suite & Full Regression Gate:
   - Execute target tests: `tests/test_schema_mapping.py`, `tests/test_phase4_final_integration.py`.
   - Execute full repository regression: `pytest tests/ -q`.
4. Verdict:
   - `CLEAN` or `INTEGRITY VIOLATION`.
   - Write `handoff.md` in `C:\ParasiteAI\.agents\teamwork\auditor_m4f\` and send message back to orchestrator.


## 2026-11-01T13:43:47Z
You are the Forensic Auditor for Milestone 4F (Final Victory Verification & Full Regression Audit).
Your working directory is C:\ParasiteAI\.agents\teamwork\auditor_m4f\.
Read your instructions in C:\ParasiteAI\.agents\teamwork\auditor_m4f\DISPATCH.md.
Also read ORIGINAL_REQUEST.md at C:\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md, SCOPE.md at C:\ParasiteAI\.agents\teamwork\orchestrator_4\SCOPE.md, and the worker handoff at C:\ParasiteAI\.agents\teamwork\teamwork_worker_m4f\handoff.md.
Perform comprehensive forensic integrity audit across all Phase 4 deliverables:
1. Verify complete Victory Verification Matrix VERIF-1 through VERIF-11.
2. Verify strict anti-hardcoding invariant: git grep -i "app_map" parasite_ai/ (0 matches). git grep -i "app_lookup" parasite_ai/ (0 matches).
3. Verify test authenticity and execute target tests: tests/test_schema_mapping.py, tests/test_phase4_final_integration.py.
4. Run full repository regression suite: .\.venv\Scripts\python.exe -m pytest tests/ -q.
Write handoff.md in C:\ParasiteAI\.agents\teamwork\auditor_m4f\ with explicit verdict CLEAN or INTEGRITY VIOLATION and send message back to orchestrator.
