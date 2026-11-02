# Auditor Dispatch: Milestone 4A — Forensic Auditor

## Role
teamwork_auditor

## Working Directory
C:\ParasiteAI\.agents\teamwork\teamwork_auditor_m4a\

## Target Deliverable Audited
Milestone 4A implementation:
- `parasite_ai/config.py`
- `parasite_ai/mind/plan.py`
- `parasite_ai/mind/memory.py`
- `tests/test_scene_serialization.py`

## Reference Documents
- Original Request: C:\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md
- Scope Document: C:\ParasiteAI\.agents\teamwork\orchestrator_4\SCOPE.md
- Master Plan: c:\Users\Suici\.gemini\antigravity\brain\464b4ef0-398b-45b1-94dc-857256a38046\phase_4_master_plan.md
- Worker Handoff: C:\ParasiteAI\.agents\teamwork\teamwork_worker_m4a\handoff.md

## Forensic Audit Protocol
Execute independent forensic integrity checks:
1. Anti-Cheat & Authenticity: Verify no test result hardcoding, fake/mock facades, or circumvention in `parasite_ai/config.py`, `parasite_ai/mind/plan.py`, or `parasite_ai/mind/memory.py`.
2. Anti-Hardcoding Invariant: Run `git grep -i "app_map" parasite_ai/` and confirm 0 matches.
3. Zero Silent Cloud Exfiltration Invariant: Confirm `BrainConfig.mode` defaults to `"local_llm"` and cannot silently mutate to cloud offload.
4. Win32 Struct 64-bit ABI Sizing: Run ctypes reflection check on `POINT`, `RECT`, `MSLLHOOKSTRUCT`, `KBDLLHOOKSTRUCT`, `MOUSEINPUT`, `KEYBDINPUT`, `HARDWAREINPUT`, `INPUT_UNION`, `INPUT`, `GUITHREADINFO` to confirm byte sizes and field offsets.
5. Code Health & Test Gate: Run AST syntax validation and `pytest tests/test_scene_serialization.py`.
6. Deliver binary verdict: `CLEAN` or `INTEGRITY VIOLATION` in `handoff.md`.


## 2026-11-01T08:05:55Z
You are Forensic Auditor for Milestone 4A of ParasiteAI.
Working directory: C:\ParasiteAI\.agents\teamwork\teamwork_auditor_m4a\
Original request path: C:\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md
Scope document path: C:\ParasiteAI\.agents\teamwork\orchestrator_4\SCOPE.md
Master plan path: c:\Users\Suici\.gemini\antigravity\brain\464b4ef0-398b-45b1-94dc-857256a38046\phase_4_master_plan.md
Worker handoff path: C:\ParasiteAI\.agents\teamwork\teamwork_worker_m4a\handoff.md

Read DISPATCH.md in your working directory.
Audit the Milestone 4A work products:
1. Anti-cheat & authenticity check in parasite_ai/config.py, parasite_ai/mind/plan.py, parasite_ai/mind/memory.py.
2. Anti-hardcoding check: git grep -i "app_map" parasite_ai/ (must be 0 matches).
3. Zero silent exfiltration check: BrainConfig().mode == "local_llm".
4. Win32 Struct 64-bit ABI Sizing ctypes reflection check across all 10 structures.
5. Code health: AST syntax validation and pytest tests/test_scene_serialization.py.
Write your audit script in your working directory, run it, document results and state your binary verdict (CLEAN or INTEGRITY VIOLATION) in handoff.md, then notify the orchestrator via send_message.
