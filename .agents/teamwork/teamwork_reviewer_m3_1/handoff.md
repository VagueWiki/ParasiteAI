# Milestone M3 Code Review Report & Gate Verdict

**Reviewer**: `teamwork_reviewer_m3_1` (Reviewer 1)  
**Roles**: Reviewer, Adversarial Critic  
**Working Directory**: `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_reviewer_m3_1\`  
**Assigned Milestone**: Milestone M3 — Desktop Companion Dock & UI Bridge  
**Date**: 2026-10-29  
**Gate Verdict**: **APPROVE**  

---

## 1. Observation

### 1.1 Reviewed Implementation Files
1. `parasite_ai/ui/types.py` (131 lines):
   - Implements strongly typed Pydantic models `UIElement` and `TargetElement` (`ConfigDict(frozen=True)`).
   - Computes dynamic properties: `@computed_field @property def bbox` (lines 87-89), `@computed_field @property def center` (lines 93-95), and compatibility alias `control_type` (lines 98-100).
   - Factory method `UIElement.from_bbox` (lines 103-126) automatically derives coordinates and centers.
   - Defines `UIState` (`WATCHING`, `THINKING`, `DRIVING`, `USER_OVERRIDE`, `OFFLOADING`, `PROTECTED`), `UIMood`, `STATE_COLORS`, and `SOM_ROLE_COLORS`.

2. `parasite_ai/ui/bridge.py` (120 lines):
   - Implements `UIBridge(QObject)` with cross-thread pyqtSignals:
     - Worker -> GUI: `sig_state_changed`, `sig_thought_updated`, `sig_speech_updated`, `sig_telemetry_updated`, `sig_perception_updated`, `sig_targets_updated`, `sig_targets_cleared`, `sig_reticle_requested`, `sig_reticle_cleared`.
     - GUI -> Worker: `sig_goal_submitted`, `sig_pause_toggled`, `sig_panic_triggered`, `sig_hud_toggled`, `sig_brain_mode_changed`.
   - Thread-safe `_goal_queue: queue.Queue[str]` with `get_next_goal(timeout_sec)` (lines 111-119).
   - Public thread-safe helper dispatchers: `notify_state()`, `notify_thought()`, `notify_speech()`, `notify_telemetry()`, `notify_perception()`, `set_hud_targets()`, `clear_hud_targets()`, `show_reticle()`, `clear_reticle()`.

3. `parasite_ai/ui/companion_dock.py` (722 lines):
   - Implements `CompanionDock(QWidget)` with frameless always-on-top window styling (`WindowStaysOnTopHint`, `FramelessWindowHint`, `Tool`), `WA_TranslucentBackground`, configurable opacity (lines 147-159).
   - Screen anchoring respecting taskbar geometry via `screen.availableGeometry()` (lines 440-471).
   - Drag repositioning with virtual desktop boundary clamping keeping 60px visible horizontally and 40px vertically (`_clamp_to_virtual_desktop`, lines 502-516).
   - 6 glowing visual states (`WATCHING`, `THINKING`, `DRIVING`, `USER_OVERRIDE`, `OFFLOADING`, `PROTECTED`) with dynamic card border styling and state pill updates (lines 413-436, 523-548).
   - Dual speech card (dialogue label with 20ms QTimer typewriter animation queue, lines 554-575) vs dark monospace thought stream (`QPlainTextEdit` with Consolas font, lines 238-265, 577-582).
   - Action telemetry card with step counter and progress bar (lines 268-299, 584-595).
   - Perception preview thumbnail with automatic blackout privacy masking upon entering `PROTECTED` state and restoration upon exit (lines 542-546, 597-654).
   - Thread-safe queued bridge wiring (`Qt.ConnectionType.QueuedConnection`, lines 708-720).

4. `tests/test_companion_dock.py` (288 lines) & `tests/test_ui_bridge.py` (126 lines):
   - 17 unit tests in `test_companion_dock.py` covering window flags, anchoring, state transitions, mood badges, typewriter streaming, thought monologue, telemetry, perception privacy masking, goal submission, pause/panic controls, header dragging, and bridge integration.
   - 7 unit tests in `test_ui_bridge.py` covering cross-thread signal emission, target marshalling, and bi-directional goal queue.

### 1.2 Independent Test Execution
1. Command:
   ```powershell
   uv run pytest tests/test_companion_dock.py tests/test_ui_bridge.py -v
   ```
   Output:
   ```
   ============================= test session starts =============================
   collected 24 items
   tests/test_companion_dock.py::TestCompanionDock::test_dock_initialization_and_window_flags PASSED [  4%]
   tests/test_companion_dock.py::TestCompanionDock::test_dock_screen_anchoring PASSED [  8%]
   tests/test_companion_dock.py::TestCompanionDock::test_dock_state_transitions_and_pill_styles PASSED [ 12%]
   tests/test_companion_dock.py::TestCompanionDock::test_dock_mood_updates PASSED [ 16%]
   tests/test_companion_dock.py::TestCompanionDock::test_dock_speech_updates_and_streaming PASSED [ 20%]
   tests/test_companion_dock.py::TestCompanionDock::test_dock_thought_stream PASSED [ 25%]
   tests/test_companion_dock.py::TestCompanionDock::test_dock_telemetry_feed PASSED [ 29%]
   tests/test_companion_dock.py::TestCompanionDock::test_dock_perception_preview_and_privacy_masking PASSED [ 33%]
   tests/test_companion_dock.py::TestCompanionDock::test_goal_input_send_button PASSED [ 37%]
   tests/test_companion_dock.py::TestCompanionDock::test_goal_input_return_key PASSED [ 41%]
   tests/test_companion_dock.py::TestCompanionDock::test_goal_input_empty_or_whitespace_ignored PASSED [ 45%]
   tests/test_companion_dock.py::TestCompanionDock::test_pause_resume_toggle_button PASSED [ 50%]
   tests/test_companion_dock.py::TestCompanionDock::test_panic_button_signal PASSED [ 54%]
   tests/test_companion_dock.py::TestCompanionDock::test_hud_checkbox_toggle PASSED [ 58%]
   tests/test_companion_dock.py::TestCompanionDock::test_brain_mode_dropdown_selection PASSED [ 62%]
   tests/test_companion_dock.py::TestCompanionDock::test_mouse_drag_repositioning PASSED [ 66%]
   tests/test_companion_dock.py::TestCompanionDock::test_bridge_integration_wiring PASSED [ 70%]
   tests/test_ui_bridge.py::TestUIBridge::test_ui_bridge_cross_thread_state_notification PASSED [ 75%]
   tests/test_ui_bridge.py::TestUIBridge::test_ui_bridge_cross_thread_thought_and_speech PASSED [ 79%]
   tests/test_ui_bridge.py::TestUIBridge::test_ui_bridge_cross_thread_telemetry_notification PASSED [ 83%]
   tests/test_ui_bridge.py::TestUIBridge::test_ui_bridge_cross_thread_reticle_request_and_clear PASSED [ 87%]
   tests/test_ui_bridge.py::TestUIBridge::test_ui_bridge_targets_signal_marshalling PASSED [ 91%]
   tests/test_ui_bridge.py::TestUIBridge::test_ui_bridge_goal_queue_consumption PASSED [ 95%]
   tests/test_ui_bridge.py::TestUIBridge::test_ui_bridge_control_signals PASSED [100%]
   ============================= 24 passed in 1.31s ==============================
   ```

2. Command:
   ```powershell
   uv run pytest -v
   ```
   Output:
   ```
   ============================ 365 passed in 21.67s =============================
   ```
   Zero failures, zero regressions across the entire project test suite.

---

## 2. Logic Chain

1. **Integrity & Authenticity Assessment**:
   - *Observation*: Inspected `parasite_ai/ui/companion_dock.py`, `bridge.py`, `types.py`, and test files.
   - *Inference*: No hardcoded or faked test outputs exist. All UI widgets, layout hierarchies, signal connections, and geometry calculations are fully implemented with native PyQt6 primitives.
   - *Conclusion*: Zero integrity violations detected.

2. **UI Thread Safety & Cross-Thread Concurrency**:
   - *Observation*: `UIBridge` connects worker threads to `CompanionDock` using `Qt.ConnectionType.QueuedConnection` (lines 709-713). `_goal_queue` utilizes Python's thread-safe `queue.Queue`.
   - *Inference*: Worker threads emitting `bridge.notify_*()` do not directly manipulate Qt widgets, eliminating Qt thread affinity violations and fatal crashes.
   - *Conclusion*: Cross-thread communication is thread-safe and resilient.

3. **Window Positioning & Clamping**:
   - *Observation*: `anchor_to_screen()` references `screen.availableGeometry()`. `_clamp_to_virtual_desktop()` calculates min/max bounds based on `screen.virtualGeometry()` (lines 509-516).
   - *Inference*: The dock accounts for taskbars and multiple monitors with positive or negative coordinate offsets. Boundary clamping guarantees that users cannot accidentally drag the dock offscreen.
   - *Conclusion*: Screen positioning and repositioning logic is sound and robust.

4. **Privacy Shield & Vision Masking**:
   - *Observation*: `update_state()` automatically calls `set_perception_masked(True)` when `state == "PROTECTED"` (lines 542-543). `update_perception_preview()` checks `self._is_masked` before rendering any pixmap, immediately diverting to `_render_privacy_blackout()` (lines 602-604).
   - *Inference*: Sensitive application frames (e.g. password managers, admin prompts) are blocked at the render gate and replaced with a solid black shield and warning text.
   - *Conclusion*: Privacy blackout requirement is completely satisfied.

5. **Typewriter Streaming & Monologue Flow**:
   - *Observation*: In `update_speech()`, direct calls cancel running timers and reset queues; streaming calls queue characters and trigger `_speech_stream_timer` at 20ms ticks (lines 554-575).
   - *Inference*: Interrupted or newly received speech stops the active animation safely without race conditions or memory leaks.
   - *Conclusion*: Speech bubble and internal thought monologue streaming operate reliably.

---

## 3. Caveats

- **Memory Management on Long-Running Monologue Stream**: While `QPlainTextEdit` handles thousands of lines with negligible overhead, setting an explicit `thought_text.setMaximumBlockCount(1000)` would serve as an extra defense-in-depth measure against unbounded memory growth during multi-day continuous runs. (Logged as Minor suggestion).
- **Offscreen QPA vs Real Physical Desktop**: In automated headless test environments (`QT_QPA_PLATFORM=offscreen`), native Win32 window APIs (`SetWindowLongW`) are safely bypassed via `IsWindow(hwnd)` guards, while all Qt event handling, layout layouting, and rendering pipelines are fully validated.

---

## 4. Conclusion

The implementation of Milestone M3 (Desktop Companion Dock & UI Bridge) meets all architectural, functional, safety, and visual requirements specified in `ORIGINAL_REQUEST.md` and `PROJECT.md`.
- Code quality, documentation, typing, and architectural separation are exemplary.
- 100% test pass rate across 24 M3 dock/bridge tests and 365 project-wide tests.
- Zero integrity violations.

**Gate Verdict**: **APPROVE**

---

## 5. Verification Method

To independently reproduce the verification:
1. Run the M3 Companion Dock & Bridge test suite:
   ```powershell
   uv run pytest tests/test_companion_dock.py tests/test_ui_bridge.py -v
   ```
   *Expected*: 24 passed in ~1-2 seconds.

2. Run the full project test suite:
   ```powershell
   uv run pytest -v
   ```
   *Expected*: 365 passed in ~20-22 seconds with zero failures.

3. Verify Python bytecode compilation:
   ```powershell
   uv run python -m py_compile parasite_ai/ui/types.py parasite_ai/ui/bridge.py parasite_ai/ui/companion_dock.py
   ```
   *Expected*: Clean exit code 0 without errors.
