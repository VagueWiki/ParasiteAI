# Scope: Phase 3 — Execution Loop Hardening

## Architecture
Phase 3 hardens the execution loop in ParasiteAI across three key interactions:
1. **Localized ROI Diffing (`parasite_ai/mind/dual_mind.py`)**:
   - Scope post-action visual difference verification to the target bounding box padded by 20px (`target_bbox.pad(20px)` or equivalent clamped to screen bounds) rather than full desktop diffing.
   - Prevents false positives from peripheral desktop updates (clocks, tray notifications, background animations).
2. **Win32 Caret Focus Verification (`parasite_ai/mind/dual_mind.py` or Win32 utility)**:
   - Call `GetGUIThreadInfo` to verify that `flags & GUI_CARETBLINKING` or `hwndCaret != 0` before emitting `TYPE` actions.
   - Ensures target input element actually holds keyboard focus before keystrokes are dispatched.
3. **Start Search Cadence Buffer (`parasite_ai/mind/resolver.py`)**:
   - Enforce a 250ms cadence pause in `UniversalAppResolver` between pressing the `Win` key chord and typing the application name.
   - Prevents dropped characters during Windows Search UI indexer initialization.
4. **Architectural Invariants & Regression Safety**:
   - Maintain all 797 existing tests green in `uv run pytest`.
   - Preserve sub-2ms hardware touch preemption and Ctrl+Alt+K hard kill.
   - Strict anti-hardcoding rule (zero application-specific lookup tables or branching).
   - Dual-monitor coordinate safety (3840x1080 @ 100% DPI).

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Localized ROI Diffing | Post-action visual diffing scoped to target bounding box + 20px padding clamped to screen | M1 | Phase 3A, ORIGINAL_REQUEST |
| 2 | Win32 Caret Focus Verification | Pre-TYPE check via `GetGUIThreadInfo` verifying `flags & GUI_CARETBLINKING` or `hwndCaret != 0` | M1 | Phase 3B, ORIGINAL_REQUEST |
| 3 | Start Search Cadence Buffer | 250ms pause between `Win` key chord and application typing in `UniversalAppResolver` | M1 | Phase 3C, ORIGINAL_REQUEST |
| 4 | Test Suite & Invariant Verification | Full regression check (797 tests passing) + new comprehensive unit tests with mocks | M1 | Phase 3D, ORIGINAL_REQUEST |

## Milestones
| # | Name | Scope | Dependencies | Status | Key Outputs |
|---|------|-------|-------------|--------|-------------|
| 1 | Phase 3 Execution Loop Hardening | Features 1, 2, 3, 4 | none | DONE | BoundingBox.pad(20px), Win32 GetGUIThreadInfo caret check, 250ms Start Search cadence buffer, 877/877 tests passing (100% green) |

## Code Layout
- `parasite_ai/ui/types.py`: `BoundingBox` class, `UIElement.target_bbox`, `UIElement.pad(20)`
- `parasite_ai/mind/dual_mind.py`: `extract_action_target_roi`, localized visual verification in `DualMindPipeline.step()`, `GUITHREADINFO`, `check_caret_focus`, `verify_caret_focus` before `ActionType.TYPE` in `ActionDispatcher.dispatch()`
- `parasite_ai/mind/resolver.py`: `cadence_buffer_ms = 250.0`, `_sleep_cadence_buffer` in `UniversalAppResolver.resolve_launch_action()`
- `tests/test_challenger_m4_2.py`: Line 712 target-aligned delta
- `tests/test_phase3_execution_loop.py`: 32 unit tests
- `tests/test_phase3_challenger_stress.py` & `tests/test_challenger_p3_stress.py`: 48 adversarial stress tests
