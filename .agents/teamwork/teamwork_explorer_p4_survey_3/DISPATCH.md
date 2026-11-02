# Dispatch: Survey Explorer 3 (UniversalAppResolver, Ctypes Structs, Anti-Hardcoding & Tests)

## Role
teamwork_explorer

## Working Directory
C:\ParasiteAI\.agents\teamwork\teamwork_explorer_p4_survey_3\

## Mission
Survey the current codebase against Phase 4 Master Plan requirements for:
1. UniversalAppResolver Hardening & PrecisionAppMatcher (Master Plan Section 8, Sub-Phase 4E, VERIF-11)
2. Win32 Ctypes Structs 64-bit ABI sizing (Master Plan Section 9.2, Sub-Phase 4F, VERIF-9)
3. Anti-Hardcoding Invariant audit (`git grep -i "app_map"` check, Master Plan Section 8, VERIF-6)
4. Existing baseline tests (877 tests) status and Phase 4 test suites status (`tests/test_escalation_cadence.py`, `tests/test_dual_channel_output.py`, `tests/test_tool_aware_reasoning.py`, `tests/test_scene_serialization.py`, `tests/test_cli_sandbox.py`, `tests/test_resolver_precision.py`).

## Instructions
- Read `C:\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md`.
- Read Master Plan: `c:\Users\Suici\.gemini\antigravity\brain\464b4ef0-398b-45b1-94dc-857256a38046\phase_4_master_plan.md` (Sections 8, 9.2, 10, 11, 12).
- Inspect `parasite_ai/mind/resolver.py`, `parasite_ai/safety/`, `parasite_ai/hands/`, and `tests/`.
- Verify what structs exist, what resolver logic exists, what tests exist, and check the status of all test files.
- Write a detailed structured survey report to `C:\ParasiteAI\.agents\teamwork\teamwork_explorer_p4_survey_3\handoff.md`.
- Send a completion message when done.


## 2026-11-01T07:40:14Z
You are Survey Explorer 3 for Phase 4 of ParasiteAI.
Working directory: C:\ParasiteAI\.agents\teamwork\teamwork_explorer_p4_survey_3\
Original request path: C:\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md
Master plan path: c:\Users\Suici\.gemini\antigravity\brain\464b4ef0-398b-45b1-94dc-857256a38046\phase_4_master_plan.md

Your mission:
Survey the current codebase against Phase 4 Master Plan requirements for:
1. UniversalAppResolver Hardening & PrecisionAppMatcher (Master Plan Section 8, Sub-Phase 4E, VERIF-11)
2. Win32 Ctypes Structs 64-bit ABI sizing (Master Plan Section 9.2, Sub-Phase 4F, VERIF-9)
3. Anti-Hardcoding Invariant audit (git grep -i "app_map" check, Master Plan Section 8, VERIF-6)
4. Existing baseline tests (877 tests) status and Phase 4 test suites status (tests/test_escalation_cadence.py, tests/test_dual_channel_output.py, tests/test_tool_aware_reasoning.py, tests/test_scene_serialization.py, tests/test_cli_sandbox.py, tests/test_resolver_precision.py, etc.).
