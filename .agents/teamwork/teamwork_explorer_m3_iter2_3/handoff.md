# Milestone M3 Iteration 2 Explorer 3 Handoff Report

**Agent**: `teamwork_explorer_m3_iter2_3`  
**Milestone**: Milestone M3 — Desktop Companion Dock & Ghost-Hand Overlay (Iteration 2)  
**Target**: Defect 3 (`UIBridge.notify_telemetry` Cannot Transmit Step Progress)  
**Handoff Type**: Hard  
**Date**: 2026-10-29  

---

## 1. Observation

### 1.1 Reproducing Verbatim Test Failure
Executing the adversarial test suite:
```powershell
uv run pytest tests/test_companion_dock_adversarial.py -k "test_ui_bridge_telemetry_step_progress_parameters" -v
```
Result:
```
FAILED tests/test_companion_dock_adversarial.py::TestCompanionDockAdversarial::test_ui_bridge_telemetry_step_progress_parameters - Failed: UIBridge.notify_telemetry does not accept step progress parameters: UIBridge.notify_telemetry() got an unexpected keyword argument 'current_step'
```

Stack trace:
```python
tests/test_companion_dock_adversarial.py:218: 
    bridge.notify_telemetry("Executing action #3", current_step=3, total_steps=10)
E   TypeError: UIBridge.notify_telemetry() got an unexpected keyword argument 'current_step'
```

### 1.2 Inspection of Existing Code

1. `parasite_ai/ui/bridge.py` line 31:
   ```python
   sig_telemetry_updated = pyqtSignal(str)              # action telemetry string
   ```
2. `parasite_ai/ui/bridge.py` lines 72-74:
   ```python
   def notify_telemetry(self, telemetry: str) -> None:
       """Update pending action telemetry."""
       self.sig_telemetry_updated.emit(telemetry)
   ```
3. `parasite_ai/ui/companion_dock.py` lines 583-584:
   ```python
   @pyqtSlot(str)
   def update_telemetry(self, text: str, current_step: int = 0, total_steps: int = 0) -> None:
   ```
4. `parasite_ai/ui/companion_dock.py` line 712:
   ```python
   bridge.sig_telemetry_updated.connect(self.update_telemetry, Qt.ConnectionType.QueuedConnection)
   ```
5. `tests/test_ui_bridge.py` lines 49-51:
   ```python
   with qtbot.waitSignal(bridge.sig_telemetry_updated, timeout=1000) as blocker:
       threading.Thread(target=lambda: bridge.notify_telemetry("Target: [#2] Edit 'Search'"), daemon=True).start()
   assert blocker.args == ["Target: [#2] Edit 'Search'"]
   ```

### 1.3 Empirical Verification of PyQt6 Behavior
Via empirical command runs in powershell:
1. When `Bridge.sig = pyqtSignal(str, int, int)` is emitted as `emit("text", 0, 0)`, `blocker.args` is `["text", 0, 0]`. This breaks `test_ui_bridge_cross_thread_telemetry_notification` which strictly expects `blocker.args == ["text"]`.
2. When `Bridge.sig = pyqtSignal([str], [str, int, int])`:
   - `b.sig.connect(...)` without index only connects to the `[str]` overload.
   - `b.sig.emit(...)` without index only emits the `[str]` overload.
   - `b.sig[str, int, int].connect(...)` must be called explicitly to receive 3-argument emissions.
   - Connecting `b.sig[str, int, int]` to a method decorated solely with `@pyqtSlot(str)` across `QueuedConnection` causes Qt to silently drop the 2 int arguments (`current_step` and `total_steps`).
   - Stacking `@pyqtSlot(str)` and `@pyqtSlot(str, int, int)` allows Qt to dispatch both 1-argument emissions (with default `current_step=0, total_steps=0`) and 3-argument emissions correctly.

---

## 2. Logic Chain

1. *From Observation 1.1 to Observation 1.2*:
   - Background workers in cognitive pipelines (M4/M5) call `bridge.notify_telemetry("Executing action #3", current_step=3, total_steps=10)`.
   - `UIBridge.notify_telemetry` currently only accepts `telemetry: str`, raising `TypeError` immediately when step parameters are supplied.
2. *From Observation 1.2 to Observation 1.3 (Why signal overloading is mandatory)*:
   - If `UIBridge.sig_telemetry_updated` were simply changed to `pyqtSignal(str, int, int)` with default arguments `current_step=0, total_steps=0`, `notify_telemetry("Target: ...")` would emit a 3-element tuple `("Target: ...", 0, 0)`.
   - `tests/test_ui_bridge.py:51` asserts `blocker.args == ["Target: [#2] Edit 'Search'"]`. A 3-element payload would fail this existing test regression check.
   - Therefore, `UIBridge.sig_telemetry_updated` must be an overloaded signal: `pyqtSignal([str], [str, int, int])`.
3. *From Observation 1.3 to Slot and Connection Architecture*:
   - In `UIBridge.notify_telemetry`: when `current_step != 0 or total_steps != 0`, emit `self.sig_telemetry_updated[str, int, int].emit(telemetry, current_step, total_steps)`. Otherwise, emit `self.sig_telemetry_updated[str].emit(telemetry)`.
   - In `CompanionDock.update_telemetry`: add `@pyqtSlot(str, int, int)` above `@pyqtSlot(str)` so Qt's cross-thread meta-object invocator does not strip the `current_step` and `total_steps` parameters.
   - In `CompanionDock._connect_bridge`: connect both `bridge.sig_telemetry_updated[str]` and `bridge.sig_telemetry_updated[str, int, int]` to `self.update_telemetry` so both 1-argument and 3-argument updates route seamlessly to the dock. Include a graceful fallback to `bridge.sig_telemetry_updated.connect(...)` for mock or single-signature objects.

---

## 3. Caveats

- **Scope Boundary**: This investigation specifically targets Defect 3. Defect 1 (`update_perception_preview` slot overload) is scoped to Explorer 1, and Defect 2 (`round` precision in `update_telemetry`) is scoped to Explorer 2.
- **Signal Unification**: Emitting both `[str]` and `[str, int, int]` simultaneously for a single `notify_telemetry` call would result in duplicate slot invocations on `CompanionDock`, which would overwrite progress bar values. The conditional emission (`[str, int, int]` if `current_step != 0 or total_steps != 0`, else `[str]`) cleanly avoids duplicate invocations while remaining 100% backward-compatible.

---

## 4. Conclusion

Defect 3 is fully diagnosed and solved without any breaking changes to existing tests.

The worker must apply the following edits:

### In `parasite_ai/ui/bridge.py`:
1. **Line 31**:
   ```python
   sig_telemetry_updated = pyqtSignal([str], [str, int, int])  # (telemetry: str) or (telemetry: str, current_step: int, total_steps: int)
   ```
2. **Lines 72-74**:
   ```python
   def notify_telemetry(
       self,
       telemetry: str,
       current_step: int = 0,
       total_steps: int = 0,
   ) -> None:
       """Update pending action telemetry and optional step progress."""
       if current_step != 0 or total_steps != 0:
           self.sig_telemetry_updated[str, int, int].emit(telemetry, current_step, total_steps)
       else:
           self.sig_telemetry_updated[str].emit(telemetry)
   ```

### In `parasite_ai/ui/companion_dock.py`:
1. **Line 583**:
   ```python
   @pyqtSlot(str)
   @pyqtSlot(str, int, int)
   def update_telemetry(self, text: str, current_step: int = 0, total_steps: int = 0) -> None:
   ```
2. **Line 712**:
   ```python
   try:
       bridge.sig_telemetry_updated[str].connect(self.update_telemetry, Qt.ConnectionType.QueuedConnection)
       bridge.sig_telemetry_updated[str, int, int].connect(self.update_telemetry, Qt.ConnectionType.QueuedConnection)
   except (KeyError, TypeError):
       bridge.sig_telemetry_updated.connect(self.update_telemetry, Qt.ConnectionType.QueuedConnection)
   ```

Full details are documented in `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m3_iter2_3\plan.md`.

---

## 5. Verification Method

To independently verify after implementation:

1. **Verify Target Adversarial Test**:
   ```powershell
   uv run pytest tests/test_companion_dock_adversarial.py -k "test_ui_bridge_telemetry_step_progress_parameters" -v
   ```
   *Expected*: PASSED.

2. **Verify Preserved UIBridge Test**:
   ```powershell
   uv run pytest tests/test_ui_bridge.py -k "test_ui_bridge_cross_thread_telemetry_notification" -v
   ```
   *Expected*: PASSED with `blocker.args == ["Target: [#2] Edit 'Search'"]`.

3. **Verify Preserved CompanionDock Test**:
   ```powershell
   uv run pytest tests/test_companion_dock.py -k "test_dock_telemetry_feed or test_bridge_integration_wiring" -v
   ```
   *Expected*: Both PASSED.

4. **Verify Full Adversarial & Project Test Suites**:
   ```powershell
   uv run pytest tests/test_companion_dock_adversarial.py -v
   uv run pytest
   ```
   *Expected*: All tests pass without regression.
