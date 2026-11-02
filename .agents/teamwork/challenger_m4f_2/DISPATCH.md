# DISPATCH — Challenger 2 (Milestone 4F: Final End-to-End System Integration Stress Testing)

## Mission
Adversarially challenge and stress-test the end-to-end integration across all Phase 4 modules (Tiers 1-4 escalation, dual-channel output, CLI sandbox, precision app resolver, and automated contingency branching).

## Key Context & Paths
- Master Plan: `c:\Users\Suici\.gemini\antigravity\brain\464b4ef0-398b-45b1-94dc-857256a38046\phase_4_master_plan.md` (§10 Sub-Phase 4F, §12 VERIF-1..11)
- Original Request: `C:\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md`
- Scope: `C:\ParasiteAI\.agents\teamwork\orchestrator_4\SCOPE.md`
- Worker Handoff: `C:\ParasiteAI\.agents\teamwork\teamwork_worker_m4f\handoff.md`
- Your Workspace: `C:\ParasiteAI\.agents\teamwork\challenger_m4f_2\`

## Target Adversarial Areas
1. Dynamic contingency pointer execution flow:
   - When a contingency step is inserted, verify `plan.get_current_step()` immediately returns the contingency step, and that upon completion, execution returns to the parent workflow.
2. Trailing non-word symbols and compound names:
   - "GNU / Notepad++ Editor", "Visual Studio C# Express", "Dev-C++ IDE", "C++ Builder". Verify score >= 0.80 and non-prefix match.
3. Attached punctuation and natural language commands:
   - Complex prompt variants: "open visual studio code, then write code", "please start notepad; write note".
4. Author empirical test suite `tests/test_challenger_m4f_integration.py`.
5. Run via `.\.venv\Scripts\python.exe -m pytest tests/test_challenger_m4f_integration.py -v`.
6. Write `handoff.md` in `C:\ParasiteAI\.agents\teamwork\challenger_m4f_2\` with explicit verdict `APPROVE` or `REQUEST_CHANGES` and notify orchestrator.

## 2026-11-01T13:43:42Z
You are Challenger 2 for Milestone 4F (Final System Integration Stress Testing).
Your working directory is C:\ParasiteAI\.agents\teamwork\challenger_m4f_2\.
Read your instructions in C:\ParasiteAI\.agents\teamwork\challenger_m4f_2\DISPATCH.md.
Also read ORIGINAL_REQUEST.md at C:\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md, SCOPE.md at C:\ParasiteAI\.agents\teamwork\orchestrator_4\SCOPE.md, and the worker handoff at C:\ParasiteAI\.agents\teamwork\teamwork_worker_m4f\handoff.md.
Adversarially stress-test end-to-end integration: dynamic contingency pointer advancement, trailing non-word symbol matching in non-prefix positions, attached punctuation parsing, defensive None handling, and cross-module synergy.
Author tests/test_challenger_m4f_integration.py and run via .\.venv\Scripts\python.exe -m pytest tests/test_challenger_m4f_integration.py -v.
Write handoff.md in C:\ParasiteAI\.agents\teamwork\challenger_m4f_2\ with explicit verdict APPROVE or REQUEST_CHANGES and send message back to orchestrator.

## 2026-11-01T13:51:37Z
**Context**: Milestone 4F Final Integration Stress Testing
**Content**: Note that the package name in this repo is `parasite_ai` (not `desktop_agent`). Modules under review are in `parasite_ai/mind/resolver.py`, `parasite_ai/mind/plan.py`, `parasite_ai/mind/dual_mind.py`. See `tests/test_phase4_final_integration.py` for reference implementations. Author your adversarial tests in `tests/test_challenger_m4f_integration.py` and run via `.\.venv\Scripts\python.exe -m pytest tests/test_challenger_m4f_integration.py -v`.
**Action**: Implement `tests/test_challenger_m4f_integration.py`, run pytest, and submit `handoff.md`.
