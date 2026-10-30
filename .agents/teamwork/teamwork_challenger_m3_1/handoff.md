# Milestone M3 Challenger 1 Handoff Report

**Agent**: `teamwork_challenger_m3_1`  
**Milestone**: Milestone M3 — Desktop Companion Dock & Ghost-Hand Overlay  
**Handoff Type**: Hard (Adversarial Assessment Complete)  
**Gate Verdict**: **REQUEST_CHANGES**  
**Date**: 2026-10-29  

---

## 1. Observation

An adversarial stress test suite containing 14 rigorous test scenarios was created in `tests/test_companion_dock_adversarial.py` and executed against `parasite_ai/ui/companion_dock.py`, `parasite_ai/ui/bridge.py`, and `parasite_ai/ui/types.py`.

### Robust Subsystems Verified (11 Tests Passing)
1. **Multi-Threaded Signal Flooding**: 8 concurrent background worker threads emitting 400 signals per channel (1600 total updates: states, speech, thoughts, telemetry) into `UIBridge` wired to `CompanionDock` operated without deadlocks, memory corruption, or race conditions (`test_concurrent_signal_emission_multithreaded_flood`).
2. **Rapid 6-State Cycling**: 300 rapid state transitions across `WATCHING`, `THINKING`, `DRIVING`, `USER_OVERRIDE`, `OFFLOADING`, and `PROTECTED` reliably applied correct hex accent border colors, state pill text labels, and privacy masking toggles (`test_rapid_state_cycling_all_six_states`).
3. **Invalid & Adversarial State Inputs**: Passing empty strings, unknown states, and lowercase names normalized cleanly to `WATCHING` / uppercase states without raising exceptions (`test_invalid_and_adversarial_state_inputs`).
4. **Telemetry Out-of-Bounds Clamping**: Clamped oversized steps (500/100 -> 100%), negative steps (-20 -> 0%), zero total steps, and negative total steps safely without division-by-zero crashes (`test_telemetry_burst_and_progress_clamping`).
5. **Perception Privacy Blackout & Zero Pixel Leakage**:
   - Initialized thumbnail with pure bright green frame (`#00FF00`).
   - Transitioned to `PROTECTED` state. Pixel-by-pixel inspection confirmed **0 green pixels** leaked (black background `#000000`, red text `#ef4444`).
   - Attempted to update perception preview with bright yellow frame (`#FFFF00`) while in `PROTECTED` state. Pixel audit confirmed **0 yellow pixels** leaked.
   - Returning to `WATCHING` replaced blackout shield with `"Live Perception Feed"`, preventing stale thumbnail leakage (`test_perception_privacy_blackout_zero_pixel_leakage`).
6. **Malformed Perception Frames**: Gracefully handled `None`, null `QPixmap`, and `QImage` objects (`test_perception_preview_malformed_inputs`).
7. **Goal Queue Thread Contention**: 8 concurrent producer threads and 3 consumer threads submitted and retrieved 400 goals without message loss or ordering corruption (`test_goal_submission_queue_thread_competition`).
8. **Goal Input Payload Boundaries**: Rejected empty and whitespace-only strings; successfully submitted 15 KB prompt payloads and unicode emojis (`test_goal_input_payload_boundaries`).
9. **Header Drag Coordinate Clamping**: Clamped negative coordinates (-99999, -99999), positive offscreen bounds (+999999, +999999), and negative virtual screen origins (-1920) within screen bounds (`test_header_drag_coordinate_clamping_extremes`).
10. **Interactive Child Widget Pass-Through**: Click-and-drag initiates on header labels (`avatar_icon`, `title_label`, `state_pill`, `header_frame`), but does **not** initiate on interactive controls (`goal_input`, `btn_send`, `btn_pause`, `btn_panic`, `chk_hud`, `combo_brain_mode`), and ignores right/middle clicks (`test_header_drag_interactive_widget_passthrough`).
11. **UIElement Schema Validation & Immutability**: Validated Pydantic constraints (`id >= 1`, `width >= 0`, `height >= 0`, `frozen=True`) (`test_ui_element_adversarial_validation_invariants`).

---

### Confirmed Defects (3 Tests Failing)

#### Defect 1: Grounding Targets Dropped via `UIBridge` (Missing `@pyqtSlot(object, list)` in `CompanionDock`)
- **File**: `parasite_ai/ui/companion_dock.py` line 596
- **Verbatim Error**:
  ```
  FAILED tests/test_companion_dock_adversarial.py::TestCompanionDockAdversarial::test_ui_bridge_perception_elements_slot_signature
  AssertionError: Missing @pyqtSlot(object, list) on CompanionDock.update_perception_preview! Grounding badge text is 'Grounding: Active', elements argument was dropped.
  assert 'Grounding: Active' == 'Grounding: 2 Targets Active'
  ```
- **Code Quote** (`parasite_ai/ui/companion_dock.py:596-597`):
  ```python
  @pyqtSlot(object)
  def update_perception_preview(self, frame_data: Any, elements: Optional[List[Any]] = None) -> None:
  ```
  And `parasite_ai/ui/bridge.py:32`:
  ```python
  sig_perception_updated = pyqtSignal(object, list)
  ```
- **Direct Cause**: `CompanionDock.update_perception_preview` only decorates `@pyqtSlot(object)`. When `UIBridge.sig_perception_updated` emits `(frame_data, elements)` across threads via `QueuedConnection`, Qt resolves the slot to the 1-argument signature and drops `elements`. Consequently, `elements` is always `None` when dispatched via `UIBridge`, and lines 622-623 (`self.grounding_badge.setText(f"Grounding: {len(elements)} Targets Active")`) never execute.

#### Defect 2: IEEE 754 Floating-Point Truncation in Telemetry Step Progress
- **File**: `parasite_ai/ui/companion_dock.py` line 589
- **Verbatim Error**:
  ```
  FAILED tests/test_companion_dock_adversarial.py::TestCompanionDockAdversarial::test_telemetry_step_precision_calculation
  AssertionError: Step progress truncation bug: expected 29% but got 28%
  assert 28 == 29
  ```
- **Code Quote** (`parasite_ai/ui/companion_dock.py:589`):
  ```python
  pct = int((current_step / total_steps) * 100)
  ```
- **Direct Cause**: In Python / IEEE 754 floating point arithmetic, `(29 / 100) * 100` evaluates to `28.999999999999996`. Calling `int(...)` truncates the decimal towards zero, setting `pct = 28` instead of 29. The same occurs at step 57 (`56.99999999999999` -> 56) and step 58 (`57.99999999999999` -> 57).

#### Defect 3: `UIBridge.notify_telemetry` Cannot Transmit Step Progress
- **File**: `parasite_ai/ui/bridge.py` lines 31 & 72
- **Verbatim Error**:
  ```
  FAILED tests/test_companion_dock_adversarial.py::TestCompanionDockAdversarial::test_ui_bridge_telemetry_step_progress_parameters
  Failed: UIBridge.notify_telemetry does not accept step progress parameters: UIBridge.notify_telemetry() got an unexpected keyword argument 'current_step'
  ```
- **Code Quote** (`parasite_ai/ui/bridge.py:31, 72-74`):
  ```python
  sig_telemetry_updated = pyqtSignal(str)              # action telemetry string
  ...
  def notify_telemetry(self, telemetry: str) -> None:
      """Update pending action telemetry."""
      self.sig_telemetry_updated.emit(telemetry)
  ```
- **Direct Cause**: `CompanionDock.update_telemetry` accepts `(text: str, current_step: int = 0, total_steps: int = 0)`. However, `UIBridge.sig_telemetry_updated` only carries a single `str`, and `notify_telemetry` takes only `telemetry: str`. Background workers executing multi-step action plans have no way to notify progress via `UIBridge`. Moreover, whenever `bridge.notify_telemetry(text)` is called, it triggers `update_telemetry(text, 0, 0)`, which resets the step progress bar to 0 and the step label to `"Step: Idle"`.

---

## 2. Logic Chain

1. *From Observation (Defect 1) to Interface Degradation*:
   - Background perception threads must call `bridge.notify_perception(frame, elements)` to inform both the thumbnail and the grounding status badge of newly detected target count.
   - Because `update_perception_preview` lacks `@pyqtSlot(object, list)`, Qt queued invocation discards `elements`. The user-facing dock badge is permanently frozen at `"Grounding: Active"` regardless of whether 0 or 50 targets are grounded.
2. *From Observation (Defect 2) to Visual Desynchronization*:
   - Telemetry step progress calculations must be mathematically exact across all 100 steps.
   - Truncating `float` to `int` causes progress bar jitter/desynchronization at steps 29, 57, and 58. Using `round((current_step / total_steps) * 100)` or `(current_step * 100) // total_steps` eliminates this bug completely.
3. *From Observation (Defect 3) to Worker Communication Gap*:
   - Milestone M4 cognitive pipelines (e.g. `ActionDispatcher` executing steps 1 of 5, 2 of 5) need to broadcast plan progress to the desktop companion GUI.
   - Without step parameters on `UIBridge.sig_telemetry_updated` and `notify_telemetry`, workers cannot report progress, and existing progress is unintentionally reset to 0 upon every action telemetry emission.
4. *From Review-Only Constraint to Gate Action*:
   - The challenger constraint strictly prohibits modifying implementation files.
   - Therefore, the 3 defects are documented empirically in `tests/test_companion_dock_adversarial.py` and submitted for remediation by `teamwork_worker_m3`.

---

## 3. Caveats

- In headless CI (`QT_QPA_PLATFORM=offscreen`), virtual desktop geometry defaults to `QRect(0, 0, 3840, 1080)`. Mock screens were used to verify negative coordinate multi-monitor geometries without relying on physical hardware displays.
- `QLineEdit.maxLength()` defaults to 32767 characters in Qt. Payloads under 32 KB pass cleanly into `goal_input`; larger payloads submitted directly via `bridge.sig_goal_submitted` have no length limitation.
- No other caveats.

---

## 4. Conclusion

**Gate Verdict**: **REQUEST_CHANGES**

Milestone M3 UI implementation is high quality, highly performant, and resilient under heavy concurrency and adversarial input attacks. However, three concrete, reproducible defects must be corrected before Milestone M3 can be approved:

1. **Fix `CompanionDock.update_perception_preview` slot overload**:
   Add `@pyqtSlot(object, list)` to `parasite_ai/ui/companion_dock.py` above line 596:
   ```python
   @pyqtSlot(object)
   @pyqtSlot(object, list)
   def update_perception_preview(self, frame_data: Any, elements: Optional[List[Any]] = None) -> None:
   ```
2. **Fix Telemetry Step Float Truncation**:
   In `parasite_ai/ui/companion_dock.py` line 589, replace `int((current_step / total_steps) * 100)` with:
   ```python
   pct = round((current_step / total_steps) * 100)
   ```
3. **Extend `UIBridge.notify_telemetry` and Signal**:
   In `parasite_ai/ui/bridge.py`:
   - Overload or extend `sig_telemetry_updated = pyqtSignal(str, int, int)` (or provide overloaded signals).
   - Update `def notify_telemetry(self, telemetry: str, current_step: int = 0, total_steps: int = 0) -> None:`.
   - Update `CompanionDock._connect_bridge` to connect the step arguments.

---

## 5. Verification Method

1. **Verify Adversarial Failures**:
   ```powershell
   uv run pytest tests/test_companion_dock_adversarial.py -v
   ```
   *Current Result*: 11 passed, 3 failed in 5.34s.
   *Target Result (after worker fixes)*: 14 passed in ~5-6s.

2. **Verify Full Project Test Suite**:
   ```powershell
   uv run pytest -v
   ```
   *Current Result*: 409 passed, 3 failed in 25.35s.
   *Target Result (after worker fixes)*: 412 passed with 0 failures and 0 regressions.
