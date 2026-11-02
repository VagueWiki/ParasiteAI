# DISPATCH — Reviewer 1 (Milestone 4F: Win32 Ctypes & Schema Mapping)

## Mission
Review and verify Win32 ctypes struct sizes, alignments, and field offsets matching 64-bit Windows ABI (VERIF-9).

## Key Context & Paths
- Master Plan: `c:\Users\Suici\.gemini\antigravity\brain\464b4ef0-398b-45b1-94dc-857256a38046\phase_4_master_plan.md` (§9.2, §10 Sub-Phase 4F, §12 VERIF-9)
- Original Request: `C:\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md`
- Scope: `C:\ParasiteAI\.agents\teamwork\orchestrator_4\SCOPE.md`
- Worker Handoff: `C:\ParasiteAI\.agents\teamwork\teamwork_worker_m4f\handoff.md`
- Your Workspace: `C:\ParasiteAI\.agents\teamwork\reviewer_m4f_1\`

## Target Review Areas
1. Inspect `parasite_ai/input/types.py`, `parasite_ai/safety/interrupt_guard.py`, `parasite_ai/safety/window_guard.py`, `parasite_ai/hands/keyboard.py`, `parasite_ai/mind/dual_mind.py`.
2. Verify all 10 structs match exact 64-bit sizes:
   - `POINT`: 8 bytes
   - `RECT`: 16 bytes
   - `MSLLHOOKSTRUCT`: 32 bytes
   - `KBDLLHOOKSTRUCT`: 24 bytes
   - `MOUSEINPUT`: 32 bytes
   - `KEYBDINPUT`: 24 bytes
   - `HARDWAREINPUT`: 8 bytes
   - `INPUT_UNION`: 32 bytes
   - `INPUT`: 40 bytes
   - `GUITHREADINFO`: 72 bytes
3. Inspect `tests/test_schema_mapping.py` and run via `.\.venv\Scripts\python.exe -m pytest tests/test_schema_mapping.py -v`.
4. Check anti-hardcoding invariant: `git grep -i "app_map" parasite_ai/` -> 0 matches.
5. Write `handoff.md` in `C:\ParasiteAI\.agents\teamwork\reviewer_m4f_1\` with explicit verdict `APPROVE` or `REQUEST_CHANGES` and notify orchestrator.


## 2026-11-01T13:43:28Z
You are Reviewer 1 for Milestone 4F (Win32 Ctypes & Schema Mapping).
Your working directory is C:\ParasiteAI\.agents\teamwork\reviewer_m4f_1\.
Read your instructions in C:\ParasiteAI\.agents\teamwork\reviewer_m4f_1\DISPATCH.md.
Also read ORIGINAL_REQUEST.md at C:\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md, SCOPE.md at C:\ParasiteAI\.agents\teamwork\orchestrator_4\SCOPE.md, and the worker handoff at C:\ParasiteAI\.agents\teamwork\teamwork_worker_m4f\handoff.md.
Review Win32 ctypes struct sizes and field offsets matching 64-bit ABI (POINT=8, RECT=16, MSLLHOOKSTRUCT=32, KBDLLHOOKSTRUCT=24, MOUSEINPUT=32, KEYBDINPUT=24, HARDWAREINPUT=8, INPUT_UNION=32, INPUT=40, GUITHREADINFO=72).
Run tests via .\.venv\Scripts\python.exe -m pytest tests/test_schema_mapping.py -v.
Verify anti-hardcoding invariant (git grep -i "app_map" parasite_ai/).
Write handoff.md in C:\ParasiteAI\.agents\teamwork\reviewer_m4f_1\ with explicit verdict APPROVE or REQUEST_CHANGES and send message back to orchestrator.
