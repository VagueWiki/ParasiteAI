# Task Assignment: Milestone M3 Implementation (Companion Dock & Ghost-Hand Overlay)

**Recipient**: `teamwork_worker_m3`
**Role**: `teamwork_worker`
**Working Directory**: `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_worker_m3\`
**Assigned Milestone**: Milestone M3 — Desktop Companion Dock & Ghost-Hand Overlay

---

## Mandatory Integrity Warning
> DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

---

## Objective
Implement the complete production UI subsystem for ParasiteAI, consisting of:
1. `parasite_ai/ui/types.py`: UI element schemas (`UIElement`, `TargetElement`), state/mood enums, and color palettes.
2. `parasite_ai/ui/dpi.py`: High-DPI Per-Monitor v2 awareness bootstrap with idempotent error handling.
3. `parasite_ai/ui/win32_styles.py`: Safe Win32 extended style applicator (`IsWindow` guard) for click-through and non-focus-stealing windows.
4. `parasite_ai/ui/bridge.py`: Cross-thread Qt signal/slot bridge (`UIBridge`) using queued connections and thread-safe goal queue.
5. `parasite_ai/ui/companion_dock.py`: Always-on-top frameless Companion Dock with 6 glowing states, dialogue/thought split, action telemetry, perception thumbnail with privacy blackout masking, and interactive controls.
6. `parasite_ai/ui/ghost_hud.py`: Fullscreen transparent click-through Ghost-Hand HUD overlay spanning virtual desktop geometry, Set-of-Mark box/badge rendering, and animated 300ms pre-click reticle with Bézier trajectory path.
7. `parasite_ai/ui/__init__.py`: Clean package exports.
8. Comprehensive test suites in `tests/`:
   - `tests/test_companion_dock.py`
   - `tests/test_ghost_hud.py`
   - `tests/test_ui_bridge.py`
   - `tests/test_dpi.py`

---

## Inputs to Study
- `g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md`
- `g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md`
- `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m3_1\plan.md`
- `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m3_1\handoff.md`
- `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m3_2\plan.md`
- `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m3_2\handoff.md`
- `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m3_3\plan.md`
- `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m3_3\handoff.md`

---

## Exclusive File Ownership
You exclusively own and may create or modify:
- `parasite_ai/ui/__init__.py`
- `parasite_ai/ui/types.py`
- `parasite_ai/ui/dpi.py`
- `parasite_ai/ui/win32_styles.py`
- `parasite_ai/ui/bridge.py`
- `parasite_ai/ui/companion_dock.py`
- `parasite_ai/ui/ghost_hud.py`
- `tests/test_companion_dock.py`
- `tests/test_ghost_hud.py`
- `tests/test_ui_bridge.py`
- `tests/test_dpi.py`

DO NOT modify files outside this list unless necessary (e.g. if `parasite_ai/config.py` needs an import or typing touch-up, document it clearly).

---

## Verification Requirements
1. Run `uv run pytest tests/test_companion_dock.py tests/test_ghost_hud.py tests/test_ui_bridge.py tests/test_dpi.py -v`
2. Run full test suite: `uv run pytest -v` (must pass 100% of existing 321 tests + all new M3 tests with zero regressions).
3. Record commands and test results in `handoff.md`.
