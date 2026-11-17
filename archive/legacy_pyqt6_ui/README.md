# Legacy PyQt6 UI Archive

## Purpose & Decommissioning Rationale (Stint P4.3)
This directory archives the legacy PyQt6 desktop overlay modules:
- `companion_dock.py`: Floating Qt widget showing monologue, status, and input controls.
- `ghost_hud.py`: Transparent full-screen overlay rendering bounding box visualizers.
- `win32_styles.py`: Win32 style utilities (layered windows, click-through, capture exclusion).
- `ui_bridge_qt.py`: Pre-P4.3 Qt `QObject` signal/slot bridge.

### Why Retired:
1. **Self-Occlusion & OCR/VLM Contamination**: The companion dock covered screen regions, requiring complex and fragile dock-evasion logic (`_evade_companion_dock_if_needed`).
2. **Compositing & Refresh Latency**: Windows layered window compositing introduced capture delays and rendering artifacts on high-DPI monitors.
3. **Event Loop Lockups**: Requiring a running Qt event loop (`QApplication`) coupled background agent orchestration to GUI thread scheduling.
4. **Decoupled Architecture**: Superseded by a pure-Python headless daemon core and Discord C2 bot (`parasite_ai/ui/discord_bot.py`).

## Git Baseline & Dependencies
- **Baseline Git Commit:** `b033e76` (Stint P4.2 completion)
- **Required Python Packages:**
  ```toml
  "PyQt6>=6.7.0"
  "pytest-qt>=4.4.0" # in dev dependencies
  ```

## Emergency Rollback Procedure
If emergency restoration of the PyQt6 overlays is required:
1. Re-add `"PyQt6>=6.7.0"` and `"pytest-qt>=4.4.0"` to `pyproject.toml`.
2. Run `uv sync`.
3. Copy `companion_dock.py`, `ghost_hud.py`, and `win32_styles.py` back to `parasite_ai/ui/`.
4. Restore `ui_bridge_qt.py` to `parasite_ai/ui/bridge.py`.
5. Restore test files from `tests/archive/legacy_pyqt6_ui/` to `tests/unit/ui/`.
6. Restore git commit `b033e76` if full repository state revert is desired.
