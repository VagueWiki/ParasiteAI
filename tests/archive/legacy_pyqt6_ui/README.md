# Legacy PyQt6 UI Test Archive

## Contents
This directory contains archived pytest test suites for PyQt6 UI widgets retired in Stint P4.3:
- `test_companion_dock.py`: 21 tests
- `test_companion_dock_adversarial.py`: 17 tests
- `test_ghost_hud.py`: 14 tests
- `test_ghost_hud_adversarial.py`: 34 tests
Total: 86 tests.

## Status
These tests are excluded from standard pytest discovery (`tests/archive` path) because PyQt6 and pytest-qt have been decommissioned in favor of a headless pure-Python core and Discord C2.

See `archive/legacy_pyqt6_ui/README.md` for full architectural rationale and rollback procedures.
