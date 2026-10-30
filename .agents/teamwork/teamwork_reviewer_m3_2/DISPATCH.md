# Task Assignment: Milestone M3 Code Reviewer 2 (Ghost HUD & Win32 Styles)

**Recipient**: `teamwork_reviewer_m3_2`
**Role**: `teamwork_reviewer`
**Working Directory**: `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_reviewer_m3_2\`
**Assigned Milestone**: Milestone M3 — Desktop Companion Dock & Ghost-Hand Overlay

---

## Mandatory Instructions
1. Read `g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md`.
2. Read `g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md`.
3. Read `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_worker_m3\handoff.md`.
4. Inspect and review the source code for:
   - `parasite_ai/ui/ghost_hud.py`
   - `parasite_ai/ui/win32_styles.py`
   - `parasite_ai/ui/dpi.py`
   - `tests/test_ghost_hud.py`
   - `tests/test_dpi.py`
5. Verify:
   - Win32 extended window styles: `WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW` applied safely via `user32.SetWindowLongW`.
   - Headless CI compatibility: `user32.IsWindow(hwnd)` guard preventing `1400` invalid handle errors under offscreen QPA.
   - Multi-monitor virtual desktop coverage: `screen.virtualGeometry()` handling and negative coordinate offsets.
   - Set-of-Mark box and pill badge rendering: role-based color themes and legible text tags.
   - 300ms pre-click reticle preview: animated contracting brackets, aiming badge, and Bézier path preview matching `KinematicsEngine`.
   - High-DPI awareness bootstrap: 3-tier fallback with idempotent `E_ACCESSDENIED` handling.
6. Run the test suite:
   - `uv run pytest tests/test_ghost_hud.py tests/test_dpi.py -v`
   - `uv run pytest -v` (full project test suite)
7. Produce `handoff.md` with:
   - Observation, Logic Chain, Caveats, Conclusion, Verification Method.
   - Clear Gate Verdict: **APPROVE** or **REQUEST_CHANGES**.
8. Notify the orchestrator via `send_message`.


## 2026-10-29T16:09:34Z
Sender: 9a16f679-6db4-4849-ba56-0f4856cbbf9b
Priority: MESSAGE_PRIORITY_HIGH
Content:
You are assigned as Milestone M3 Code Reviewer 2 (`teamwork_reviewer_m3_2`).

Your working directory is:
`g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_reviewer_m3_2\`

Read your dispatch assignment:
`g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_reviewer_m3_2\DISPATCH.md`

MANDATORY FIRST ACTIONS:
1. Initialize your `BRIEFING.md` and `progress.md` in your working directory.
2. Read `g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md`.
3. Read `g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md`.
4. Read `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_worker_m3\handoff.md`.

REVIEW SCOPE:
- Inspect and review:
  - `parasite_ai/ui/ghost_hud.py`
  - `parasite_ai/ui/win32_styles.py`
  - `parasite_ai/ui/dpi.py`
  - `tests/test_ghost_hud.py`
  - `tests/test_dpi.py`
- Verify Win32 extended window styles (`WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW`), headless CI compatibility (`IsWindow` check), multi-monitor virtual desktop coverage (`screen.virtualGeometry()`), Set-of-Mark box and badge rendering, 300ms pre-click reticle countdown with Bézier path preview matching `KinematicsEngine`, and high-DPI bootstrap.
- Execute test commands:
  `uv run pytest tests/test_ghost_hud.py tests/test_dpi.py -v`
  `uv run pytest -v` (full suite)
- Compile `handoff.md` with your evaluation and a clear gate verdict: **APPROVE** or **REQUEST_CHANGES**.
- Notify the orchestrator via `send_message`.
