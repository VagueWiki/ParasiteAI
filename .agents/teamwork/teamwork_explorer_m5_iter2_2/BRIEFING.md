# BRIEFING — 2026-10-29T21:53:00Z

## Mission
Investigate and formulate concrete, verified implementation strategies for Pre-Live Desktop Hardening:
1. Multi-monitor edge clamping in `parasite_ai/hands/mouse.py` & `parasite_ai/hands/kinematics.py`
2. Grounded Chrome selectors in `parasite_ai/mind/browser_offload.py` / `parasite_ai/mind/offloader.py`
3. 64-bit Win32 styles in `parasite_ai/ui/win32_styles.py`

## 🔒 My Identity
- Archetype: Explorer
- Roles: Read-only investigation, evidence-based synthesis, drop-in code fix proposals
- Working directory: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m5_iter2_2
- Original parent: e41fc20b-5cde-4ee6-9f1f-2a9a3b7515e4
- Milestone: Milestone 5 Iteration 2 (Pre-Live Desktop Hardening)

## 🔒 Key Constraints
- Read-only investigation — do NOT implement or modify project code or tests
- Live interactive tests (Notepad task, Gemini offload) are NOT authorized
- Absolutely NO live mouse or keyboard control. Simulated/dry-run/offscreen modes only
- Only write progress.md, BRIEFING.md, and handoff.md in working directory
- Provide exact line locations, proposed drop-in replacements, and verification commands

## Current Parent
- Conversation ID: e41fc20b-5cde-4ee6-9f1f-2a9a3b7515e4
- Updated: 2026-10-29T21:53:00Z

## Investigation State
- **Explored paths**:
  - `parasite_ai/hands/mouse.py` (lines 410-449)
  - `parasite_ai/hands/kinematics.py` (lines 100-239)
  - `parasite_ai/mind/offloader.py` (lines 1-526)
  - `parasite_ai/vision/grounding.py` (lines 1-350)
  - `parasite_ai/runtime.py` (lines 85-115)
  - `parasite_ai/ui/win32_styles.py` (lines 1-82)
  - `parasite_ai/ui/ghost_hud.py` (lines 1-205)
  - `tests/test_mouse_driver.py`, `tests/test_kinematics.py`, `tests/test_browser_offloader.py`, `tests/test_ghost_hud.py`, `tests/test_ghost_hud_adversarial.py`
- **Key findings**:
  1. Multi-monitor coordinate calculation in `mouse.py` produces negative values or values > 65535 when unconstrained, causing Win32 cursor wrapping. `kinematics.py:222-225` overshoots past screen edges (`min_x = -5`), and clamping `p_over` to `p_target` requires handling `d_corr < 1.0` to avoid a critical `ZeroDivisionError` at line 140.
  2. `BrowserOffloader` can accept `grounder: Optional[Any] = None` (connected in `runtime.py` from `self.screen_grounder`), using `_find_prompt_target` and `_find_copy_button` while preserving 100% backward-compatible fallback heuristic for mock window backends.
  3. `win32_styles.py` can be upgraded to 64-bit `GetWindowLongPtrW` / `SetWindowLongPtrW` with `argtypes`/`restype = ctypes.c_ssize_t` and `SetWindowPos.argtypes`, with mock-aware fallback ensuring zero regressions on existing unit tests.
- **Unexplored areas**: None. All 3 target domains have been explored and verified via local Python dry-runs and pytest executions.

## Key Decisions Made
- Formulate complete drop-in code snippets for implementer.
- Include unit test additions and updates to ensure 100% test pass rate upon implementation.

## Artifact Index
- DISPATCH.md — Dispatch instructions from orchestrator
- BRIEFING.md — Working memory and status
- progress.md — Liveness heartbeat and milestone tracker
- handoff.md — Final 5-component handoff report
