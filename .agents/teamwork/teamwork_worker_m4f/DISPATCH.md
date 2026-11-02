# DISPATCH — Worker (Milestone 4F: System Integration, Ctypes Verification & Full Regression Gate)

## Mission
Implement and certify Milestone 4F:
1. Author `tests/test_schema_mapping.py` verifying all 10 Win32 ctypes struct sizes and field offsets match 64-bit Windows ABI (VERIF-9).
2. Apply Polish & Edge-Case Remediations identified by Reviewers & Challengers in Milestone 4E:
   - Trailing non-word character boundary matching in `PrecisionAppMatcher.score_match` (e.g. `notepad++`, `c++`, `c#`) so Level 3 matches boundary cleanly without dropping to 0.0 in non-prefix positions.
   - Natural language extraction in `UniversalAppResolver.extract_target_app`: allow attached commas/punctuation directly adjacent to target words (e.g. `open visual studio code, then write code`).
   - Defensive check in `UniversalAppResolver.resolve_launch_action`: guard against `target_app=None` safely returning `ActionPlan(action=ActionType.WAIT)`.
   - `LivingPlan` contingency active pointer: when `check_and_insert_contingencies` inserts a prerequisite contingency step, update `plan.current_step_id` to that contingency step so remediation runs first.
3. Victory Verification Matrix Certification (VERIF-1 through VERIF-11).
4. Run full repository regression suite ensuring 100% passing tests.

## Key Constraints & Mandatory Warnings
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.
Strict anti-hardcoding invariant: `git grep -i "app_map" parasite_ai/` must return 0 matches.

## Key Context & Paths
- Master Plan: `c:\Users\Suici\.gemini\antigravity\brain\464b4ef0-398b-45b1-94dc-857256a38046\phase_4_master_plan.md` (§9.2, §10 Sub-Phase 4F, §12 VERIF-1..11)
- Original Request: `C:\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md`
- Scope: `C:\ParasiteAI\.agents\teamwork\orchestrator_4\SCOPE.md`
- Your Workspace: `C:\ParasiteAI\.agents\teamwork\teamwork_worker_m4f\`

## Target Deliverables
1. `tests/test_schema_mapping.py`:
   - Import all 10 structs from `parasite_ai/input/types.py` (or Win32 modules):
     `POINT`, `RECT`, `MSLLHOOKSTRUCT`, `KBDLLHOOKSTRUCT`, `MOUSEINPUT`, `KEYBDINPUT`, `HARDWAREINPUT`, `INPUT_UNION`, `INPUT`, `GUITHREADINFO`.
   - Test `ctypes.sizeof()` matches:
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
   - Test field offsets for 64-bit ABI alignment.
2. Polish in `parasite_ai/mind/resolver.py` and `parasite_ai/mind/plan.py`.
3. Author verification tests for edge-case polish in `tests/test_phase4_final_integration.py`.
4. Run tests:
   - `.\.venv\Scripts\python.exe -m pytest tests/test_schema_mapping.py -v`
   - `.\.venv\Scripts\python.exe -m pytest tests/test_phase4_final_integration.py -v`
   - `.\.venv\Scripts\python.exe -m pytest tests/ -q`
5. Anti-hardcoding check:
   - `git grep -i "app_map" parasite_ai/` -> 0 matches.

## Output
Write `handoff.md` in `C:\ParasiteAI\.agents\teamwork\teamwork_worker_m4f\` with your complete implementation details, test outputs, and notify orchestrator.
