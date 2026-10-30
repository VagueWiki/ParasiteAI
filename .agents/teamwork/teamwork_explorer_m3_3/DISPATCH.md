# Dispatch for Explorer M3 (3/3)

Working Directory: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m3_3\
Original Request: g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md
Project Spec: g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md
Survey 3 Report: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_survey_3\survey_report.md
Existing Config: g:\__Docs\ParasiteAI\parasite_ai\config.py

Milestone: M3 — Desktop Companion Dock & Ghost-Hand Overlay
Focus: UI Integration, Thread Bridges, Package Exports (`parasite_ai/ui/__init__.py`) and Test Architecture (`tests/test_companion_dock.py`, `tests/test_ghost_hud.py`)
Requirements:
1. Thread-safe communication bridge:
   - Background worker threads (Engine, Safety, Offloader) cannot directly touch Qt widgets (crashes Qt event loop).
   - Qt signals and queued connections (`Qt.ConnectionType.QueuedConnection`) bridging cross-thread updates to GUI widgets.
2. Per-Monitor High-DPI Awareness initialization:
   - `ctypes.windll.shcore.SetProcessDpiAwareness(2)` (Per-Monitor v2) or fallback.
3. Headless CI environment compatibility:
   - Running `pytest` on Windows runners where display may be headless (`QT_QPA_PLATFORM=offscreen` or `windows`).
   - Using `pytest-qt` fixtures (`qtbot`) without hanging, crashing, or blocking the test runner.
4. UI element data contracts:
   - Define or import `UIElement` / `TargetElement` representation (`id`, `bbox`, `label`, `control_type`, `center`).
5. Specification of complete test suites:
   - `tests/test_companion_dock.py`: state changes, speech streaming, thought updates, goal submission, pause/panic button signals, perception thumbnail updates.
   - `tests/test_ghost_hud.py`: click-through extended window styles, Set-of-Mark bounding box geometry, reticle timer countdown, path curve calculation, element clearing.

Deliverable:
Technical implementation plan in `plan.md` and structured `handoff.md`.


## 2026-10-29T15:47:58Z
You are teamwork_explorer_m3_3, Explorer 3 for Milestone M3: Desktop Companion Dock & Ghost-Hand Overlay.
Working Directory: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m3_3\
Focus: UI Integration, Thread Bridges, Package Exports (`parasite_ai/ui/__init__.py`) and Test Architecture (`tests/test_companion_dock.py`, `tests/test_ghost_hud.py`)
