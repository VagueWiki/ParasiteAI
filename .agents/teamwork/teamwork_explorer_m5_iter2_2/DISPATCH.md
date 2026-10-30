# Dispatch: Explorer 2 (Milestone 5 Iteration 2 - Pre-Live Desktop Hardening)

## Mission
Investigate and formulate concrete, verified implementation strategies for Pre-Live Desktop Hardening:
1. Multi-monitor edge clamping in `parasite_ai/hands/mouse.py` and `parasite_ai/hands/kinematics.py`: add virtual screen boundary clamping `max(vx, min(pt[0], vx + vcx - 1))` before normalizing to `[0, 65535]` to prevent cursor border wrapping or warping.
2. Grounded Chrome selectors in `parasite_ai/mind/browser_offload.py` / `parasite_ai/mind/offloader.py`: integrate `ScreenGrounder` / UIA selectors for Chrome's prompt box and copy button instead of blind relative coordinate clicks.
3. 64-bit Win32 styles in `parasite_ai/ui/win32_styles.py` (`GetWindowLongPtrW`/`SetWindowLongPtrW`).

## Context & Inputs
- `g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md`
- `g:\__Docs\ParasiteAI\PROJECT.md`
- `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_discrepancy\handoff.md`
- `parasite_ai/hands/mouse.py`
- `parasite_ai/hands/kinematics.py`
- `parasite_ai/mind/offloader.py`
- `parasite_ai/vision/grounding.py`
- `parasite_ai/ui/win32_styles.py`
- Existing test suites: `tests/test_mouse_driver.py`, `tests/test_browser_offloader.py`, `tests/test_ghost_hud.py`.

## Instructions
1. Analyze the exact code locations and failure modes identified in the Discrepancy Analysis report.
2. Formulate exact implementations:
   - In `mouse.py`, virtual desktop coordinate clamping `max(vx, min(pt[0], vx + vcx - 1))` and `max(vy, min(pt[1], vy + vcy - 1))` before normalizing to `[0, 65535]`.
   - In `offloader.py`, integration with `ScreenGrounder` or UI Automation element finding for Chrome prompt box and copy button, with fallback heuristics if UIA tree is empty/mocked, ensuring existing tests remain 100% passing.
   - In `win32_styles.py`, 64-bit ctypes safety with `GetWindowLongPtrW` and `SetWindowLongPtrW`.
3. Provide step-by-step code modification proposals with exact line ranges and drop-in replacements.
4. Output your complete report to `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m5_iter2_2\handoff.md`.
