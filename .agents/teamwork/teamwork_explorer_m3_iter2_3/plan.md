# Implementation Plan: Defect 3 — UIBridge Telemetry Step Progress

**Assigned Explorer**: `teamwork_explorer_m3_iter2_3`  
**Target Defect**: Defect 3 — `UIBridge.notify_telemetry` cannot transmit step progress  
**Target Files**:
1. `parasite_ai/ui/bridge.py` (lines 31, 72-74)
2. `parasite_ai/ui/companion_dock.py` (lines 583-584, 712)
**Target Test**: `tests/test_companion_dock_adversarial.py::TestCompanionDockAdversarial::test_ui_bridge_telemetry_step_progress_parameters`  
**Preserved Baseline Tests**:
- `tests/test_ui_bridge.py::TestUIBridge::test_ui_bridge_cross_thread_telemetry_notification`
- `tests/test_companion_dock.py::TestCompanionDock::test_dock_telemetry_feed`
- `tests/test_companion_dock.py::TestCompanionDock::test_bridge_integration_wiring`
- `tests/test_companion_dock_adversarial.py::TestCompanionDockAdversarial::test_concurrent_signal_emission_multithreaded_flood`

---

## 1. Problem Analysis & Root Cause

### 1.1 The Symptom
In `tests/test_companion_dock_adversarial.py:203-226`:
```python
bridge.notify_telemetry("Executing action #3", current_step=3, total_steps=10)
```
fails with:
```
TypeError: UIBridge.notify_telemetry() got an unexpected keyword argument 'current_step'
```

### 1.2 The Root Causes
1. **Method Signature**: `UIBridge.notify_telemetry` is defined as:
   ```python
   def notify_telemetry(self, telemetry: str) -> None:
       self.sig_telemetry_updated.emit(telemetry)
   ```
   It accepts only a single parameter `telemetry: str`.
2. **Signal Signature**: `UIBridge.sig_telemetry_updated` is defined as:
   ```python
   sig_telemetry_updated = pyqtSignal(str)
   ```
   It only carries a string payload.
3. **Slot Signature in `CompanionDock`**: `CompanionDock.update_telemetry` is declared with:
   ```python
   @pyqtSlot(str)
   def update_telemetry(self, text: str, current_step: int = 0, total_steps: int = 0) -> None:
   ```
   Even though Python allows default arguments, Qt's meta-object system uses `@pyqtSlot` decorators to determine signal-slot compatibility across threads. When an overloaded or multi-argument signal is delivered across threads via `Qt.ConnectionType.QueuedConnection`, Qt matches the slot signature. If only `@pyqtSlot(str)` is declared, Qt drops the extra arguments, setting `current_step = 0, total_steps = 0`.
4. **Bridge Connection in `CompanionDock._connect_bridge`**:
   ```python
   bridge.sig_telemetry_updated.connect(self.update_telemetry, Qt.ConnectionType.QueuedConnection)
   ```
   In PyQt6, when a signal is overloaded via `pyqtSignal([str], [str, int, int])`, calling `bridge.sig_telemetry_updated.connect(...)` without index brackets defaults strictly to the first overload `sig_telemetry_updated[str]`. The 3-argument overload `sig_telemetry_updated[str, int, int]` remains completely unconnected!

### 1.3 Why a Naive `pyqtSignal(str, int, int)` Breaks Existing Tests
A naive change replacing `sig_telemetry_updated = pyqtSignal(str)` with `sig_telemetry_updated = pyqtSignal(str, int, int)` causes **critical regression** in `tests/test_ui_bridge.py:45-52`:
```python
with qtbot.waitSignal(bridge.sig_telemetry_updated, timeout=1000) as blocker:
    threading.Thread(target=lambda: bridge.notify_telemetry("Target: [#2] Edit 'Search'"), daemon=True).start()
assert blocker.args == ["Target: [#2] Edit 'Search'"]
```
If `sig_telemetry_updated` is `pyqtSignal(str, int, int)`, emitting with defaults `(telemetry, 0, 0)` produces:
```python
blocker.args == ["Target: [#2] Edit 'Search'", 0, 0]
```
which immediately fails `assert blocker.args == ["Target: [#2] Edit 'Search'"]`!

Therefore, `sig_telemetry_updated` **must be an overloaded signal** `pyqtSignal([str], [str, int, int])`.

---

## 2. Proposed Architecture & Code Changes

### 2.1 File: `parasite_ai/ui/bridge.py`

#### Change 1: Overloaded Signal Definition
At line 31:
```python
<<<<
    sig_telemetry_updated = pyqtSignal(str)              # action telemetry string
====
    sig_telemetry_updated = pyqtSignal([str], [str, int, int])  # (telemetry: str) or (telemetry: str, current_step: int, total_steps: int)
>>>>
```

#### Change 2: `notify_telemetry` Method Signature and Emission
At lines 72-74:
```python
<<<<
    def notify_telemetry(self, telemetry: str) -> None:
        """Update pending action telemetry."""
        self.sig_telemetry_updated.emit(telemetry)
====
    def notify_telemetry(
        self,
        telemetry: str,
        current_step: int = 0,
        total_steps: int = 0,
    ) -> None:
        """
        Update pending action telemetry and optional step progress.
        Emits 3-arg signal when step progress is provided, or 1-arg string signal for idle/simple updates.
        """
        if current_step != 0 or total_steps != 0:
            self.sig_telemetry_updated[str, int, int].emit(telemetry, current_step, total_steps)
        else:
            self.sig_telemetry_updated[str].emit(telemetry)
>>>>
```

**Rationale**:
- If `current_step != 0 or total_steps != 0`, step progress is present (including step 0 of 5, where `total_steps == 5`). The 3-argument overload `sig_telemetry_updated[str, int, int]` is emitted.
- If `current_step == 0 and total_steps == 0` (or omitted), only `telemetry` is emitted via `sig_telemetry_updated[str]`.
- This preserves 100% backward compatibility with `test_ui_bridge_cross_thread_telemetry_notification` where `blocker.args == [telemetry]`.

---

### 2.2 File: `parasite_ai/ui/companion_dock.py`

#### Change 1: Overloaded Slot Decorator on `update_telemetry`
At line 583:
```python
<<<<
    @pyqtSlot(str)
    def update_telemetry(self, text: str, current_step: int = 0, total_steps: int = 0) -> None:
====
    @pyqtSlot(str)
    @pyqtSlot(str, int, int)
    def update_telemetry(self, text: str, current_step: int = 0, total_steps: int = 0) -> None:
>>>>
```

**Rationale**:
- In PyQt6, stacking `@pyqtSlot(str)` and `@pyqtSlot(str, int, int)` registers both C++/Qt slot signatures in the Qt meta-object table.
- When `sig_telemetry_updated[str]` arrives across threads via `QueuedConnection`, Qt matches `@pyqtSlot(str)` and calls `update_telemetry(text, 0, 0)`.
- When `sig_telemetry_updated[str, int, int]` arrives across threads via `QueuedConnection`, Qt matches `@pyqtSlot(str, int, int)` and calls `update_telemetry(text, current_step, total_steps)`.

#### Change 2: Connect Both Signal Overloads in `_connect_bridge`
At line 712:
```python
<<<<
            bridge.sig_telemetry_updated.connect(self.update_telemetry, Qt.ConnectionType.QueuedConnection)
====
            try:
                bridge.sig_telemetry_updated[str].connect(self.update_telemetry, Qt.ConnectionType.QueuedConnection)
                bridge.sig_telemetry_updated[str, int, int].connect(self.update_telemetry, Qt.ConnectionType.QueuedConnection)
            except (KeyError, TypeError):
                bridge.sig_telemetry_updated.connect(self.update_telemetry, Qt.ConnectionType.QueuedConnection)
>>>>
```

**Rationale**:
- Connecting `bridge.sig_telemetry_updated[str]` ensures 1-argument emissions route to `self.update_telemetry`.
- Connecting `bridge.sig_telemetry_updated[str, int, int]` ensures 3-argument emissions route to `self.update_telemetry`.
- The `try ... except (KeyError, TypeError)` fallback guarantees that if `bridge` is a mock object or legacy bridge without `[str, int, int]` indexing, standard connection still succeeds without raising unhandled exceptions.

---

## 3. Implementation Steps for the Worker

1. **Edit `parasite_ai/ui/bridge.py`**:
   - Change `sig_telemetry_updated = pyqtSignal(str)` to `sig_telemetry_updated = pyqtSignal([str], [str, int, int])`.
   - Update `notify_telemetry(self, telemetry: str, current_step: int = 0, total_steps: int = 0) -> None`:
     - If `current_step != 0 or total_steps != 0`, emit `self.sig_telemetry_updated[str, int, int].emit(telemetry, current_step, total_steps)`.
     - Else emit `self.sig_telemetry_updated[str].emit(telemetry)`.

2. **Edit `parasite_ai/ui/companion_dock.py`**:
   - Above `update_telemetry`, add `@pyqtSlot(str, int, int)` alongside `@pyqtSlot(str)`.
   - In `_connect_bridge`, connect both `bridge.sig_telemetry_updated[str]` and `bridge.sig_telemetry_updated[str, int, int]` to `self.update_telemetry`, wrapped in `try/except (KeyError, TypeError)`.

3. **Coordinate with Other Explorer Fixes**:
   - Note that Explorer 1 handles Defect 1 (`update_perception_preview` slot overload `@pyqtSlot(object, list)`).
   - Note that Explorer 2 handles Defect 2 (`round(...)` precision in `update_telemetry`).
   - The worker will apply all three fixes cohesively.

---

## 4. Verification Plan

Execute the following commands in powershell:

1. **Verify Adversarial Defect 3 Test**:
   ```powershell
   uv run pytest tests/test_companion_dock_adversarial.py -k "test_ui_bridge_telemetry_step_progress_parameters" -v
   ```
   *Expected*: PASSED.

2. **Verify UIBridge Unit Tests**:
   ```powershell
   uv run pytest tests/test_ui_bridge.py -v
   ```
   *Expected*: 7 passed in <1s. Specifically `test_ui_bridge_cross_thread_telemetry_notification` passes.

3. **Verify CompanionDock Unit Tests**:
   ```powershell
   uv run pytest tests/test_companion_dock.py -v
   ```
   *Expected*: 17 passed in <2s. Specifically `test_dock_telemetry_feed` and `test_bridge_integration_wiring` pass.

4. **Verify All Adversarial Tests**:
   ```powershell
   uv run pytest tests/test_companion_dock_adversarial.py -v
   ```
   *Expected*: 14 passed in ~5s (when combined with Defect 1 and Defect 2 fixes).

5. **Verify Full Suite**:
   ```powershell
   uv run pytest
   ```
   *Expected*: 412 passed in ~25s with 0 failures and 0 warnings.
