# Task Assignment: Milestone M3 Forensic Integrity Auditor

**Recipient**: `teamwork_auditor_m3`
**Role**: `teamwork_auditor`
**Working Directory**: `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_auditor_m3\`
**Assigned Milestone**: Milestone M3 — Desktop Companion Dock & Ghost-Hand Overlay

---

## Mandatory Instructions
1. Read `g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md`.
2. Read `g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md`.
3. Read `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_worker_m3\handoff.md`.
4. Perform comprehensive forensic audit across all Milestone M3 files:
   - `parasite_ai/ui/types.py`
   - `parasite_ai/ui/dpi.py`
   - `parasite_ai/ui/win32_styles.py`
   - `parasite_ai/ui/bridge.py`
   - `parasite_ai/ui/companion_dock.py`
   - `parasite_ai/ui/ghost_hud.py`
   - `parasite_ai/ui/__init__.py`
   - `tests/test_companion_dock.py`
   - `tests/test_ghost_hud.py`
   - `tests/test_ui_bridge.py`
   - `tests/test_dpi.py`
5. Integrity Checks to Execute:
   - **Check 1: Facade and Dummy Detection**: Check whether `CompanionDock`, `GhostHUD`, and `UIBridge` implement authentic Qt widget hierarchies, genuine state transitions, genuine paint events, and real queueing, rather than mocked stubs.
   - **Check 2: Tautological and Mock Bypass Testing**: Audit all test cases in `tests/test_*.py`. Verify tests do not assert `True == True`, mock out the entire implementation under test, or pass unconditionally.
   - **Check 3: Hardcoded Value Detection**: Inspect source code and tests for hardcoded fixture matches designed solely to pass specific test cases.
   - **Check 4: Real Win32 Style & DPI Verification**: Verify `WS_EX_TRANSPARENT (0x00000020)`, `WS_EX_NOACTIVATE (0x08000000)`, `WS_EX_LAYERED (0x00080000)`, `WS_EX_TOPMOST (0x00000008)`, and DPI awareness calls (`SetProcessDpiAwarenessContext`, `SetProcessDpiAwareness`) are authentic ctypes calls with genuine bitmasks and proper error handling.
   - **Check 5: True Kinematic Path Rendering**: Verify `GhostHUD` draws Bézier curves using genuine cubic equations matching `KinematicsEngine`.
   - **Check 6: Privacy Blackout Verification**: Verify that in `PROTECTED` state, the perception preview genuinely blanks out the thumbnail and does not leak underlying desktop pixels.
6. Run the test suite:
   - `uv run pytest tests/test_companion_dock.py tests/test_ghost_hud.py tests/test_ui_bridge.py tests/test_dpi.py -v`
   - `uv run pytest -v` (full project test suite)
7. Produce `handoff.md` with:
   - Observation, Logic Chain, Caveats, Conclusion, Verification Method.
   - Clear Gate Verdict: **CLEAN** (if 100% genuine) or **INTEGRITY VIOLATION** (if cheating detected).
8. Notify the orchestrator via `send_message`.

## 2026-10-29T16:09:58Z
You are assigned as the Milestone M3 Forensic Integrity Auditor (`teamwork_auditor_m3`).

Your working directory is:
`g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_auditor_m3\`

Read your dispatch assignment:
`g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_auditor_m3\DISPATCH.md`

MANDATORY FIRST ACTIONS:
1. Initialize your `BRIEFING.md` and `progress.md` in your working directory.
2. Read `g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md`.
3. Read `g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md`.
4. Read `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_worker_m3\handoff.md`.

AUDIT SCOPE:
- Perform forensic integrity checks on all Milestone M3 files:
  - `parasite_ai/ui/types.py`
  - `parasite_ai/ui/dpi.py`
  - `parasite_ai/ui/win32_styles.py`
  - `parasite_ai/ui/bridge.py`
  - `parasite_ai/ui/companion_dock.py`
  - `parasite_ai/ui/ghost_hud.py`
  - `parasite_ai/ui/__init__.py`
  - `tests/test_companion_dock.py`
  - `tests/test_ghost_hud.py`
  - `tests/test_ui_bridge.py`
  - `tests/test_dpi.py`
- Run 6 systematic integrity checks:
  1. Facade and Dummy Detection (genuine Qt widgets, genuine state management, real paint events).
  2. Tautological and Mock Bypass Testing (zero `assert True == True`, zero unconditional bypasses).
  3. Hardcoded Value Detection (zero hardcoded strings or test-specific branches).
  4. Real Win32 Style & DPI Verification (authentic bitmasks: `WS_EX_TRANSPARENT 0x20`, `WS_EX_NOACTIVATE 0x08000000`, `WS_EX_LAYERED 0x80000`, `WS_EX_TOPMOST 0x08`, `WS_EX_TOOLWINDOW 0x80`, authentic ctypes DPI APIs).
  5. True Kinematic Path Rendering (real cubic Bézier math matching `KinematicsEngine`).
  6. Privacy Blackout Verification (genuine blanking of perception preview in `PROTECTED` state).
- Run test commands:
  `uv run pytest tests/test_companion_dock.py tests/test_ghost_hud.py tests/test_ui_bridge.py tests/test_dpi.py -v`
  `uv run pytest -v` (full project test suite)
- Compile `handoff.md` with your audit evidence and a clear gate verdict: **CLEAN** or **INTEGRITY VIOLATION**.
- Notify the orchestrator via `send_message`.
