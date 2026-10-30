# Implementation Plan: Fix Qt Slot Overload for Perception Preview (Defect 1)

**Target Worker**: `teamwork_worker_m3`  
**Author**: `teamwork_explorer_m3_iter2_1`  
**Milestone**: Milestone M3 (Iteration 2)  
**Target File**: `parasite_ai/ui/companion_dock.py`  
**Target Function**: `CompanionDock.update_perception_preview` (lines 596-626)  

---

## 1. Executive Summary & Root Cause Analysis

### Symptom
When `UIBridge.notify_perception(frame, elements)` emits across threads via Qt queued connection, `CompanionDock.update_perception_preview` receives `frame_data` as expected, but the `elements` argument is completely dropped and defaults to `None`.
Consequently:
- The target grounding badge never updates with the number of grounded targets.
- The badge remains statically frozen at `"Grounding: Active"` instead of displaying `"Grounding: N Targets Active"`.
- Adversarial test `tests/test_companion_dock_adversarial.py::TestCompanionDockAdversarial::test_ui_bridge_perception_elements_slot_signature` fails with:
  ```
  AssertionError: Missing @pyqtSlot(object, list) on CompanionDock.update_perception_preview!
  Grounding badge text is 'Grounding: Active', elements argument was dropped.
  assert 'Grounding: Active' == 'Grounding: 2 Targets Active'
  ```

### Deep-Dive Root Cause
1. **Signal Signature**: In `parasite_ai/ui/bridge.py` line 32:
   ```python
   sig_perception_updated = pyqtSignal(object, list)
   ```
   In Qt's C++ meta-object system, `pyqtSignal(object, list)` normalizes to `sig_perception_updated(PyQt_PyObject, QVariantList)`.
2. **Current Slot Signature**: In `parasite_ai/ui/companion_dock.py` line 596:
   ```python
   @pyqtSlot(object)
   def update_perception_preview(self, frame_data: Any, elements: Optional[List[Any]] = None) -> None:
   ```
   This registers ONLY `update_perception_preview(PyQt_PyObject)`.
3. **Connection Wiring**: In `parasite_ai/ui/companion_dock.py` line 713:
   ```python
   bridge.sig_perception_updated.connect(self.update_perception_preview, Qt.ConnectionType.QueuedConnection)
   ```
4. **Qt Discard Rule**: Under Qt's signal-to-slot argument matching rules:
   - A signal carrying $N$ arguments can connect to a slot accepting $M \le N$ arguments (dropping trailing arguments from the right).
   - Because `CompanionDock` only published a 1-parameter slot `(PyQt_PyObject)`, Qt's connection engine discarded the second argument (`QVariantList`).
   - During queued marshalling across thread boundaries, Qt marshals a meta-call with only 1 argument.
   - When the slot executes on the main Qt GUI thread, Python supplies `elements = None` (the parameter's default value).
   - In `update_perception_preview` lines 622-623:
     ```python
     if elements is not None:
         self.grounding_badge.setText(f"Grounding: {len(elements)} Targets Active")
     ```
     Because `elements is None`, the badge text update never executes!

---

## 2. Precise Solution & Code Changes

### Step 1: Decorate `update_perception_preview` with Overloaded `@pyqtSlot`
In `parasite_ai/ui/companion_dock.py`, stack `@pyqtSlot(object)` and `@pyqtSlot(object, list)` directly above `def update_perception_preview(...)`.

This matches the existing, proven pattern in `CompanionDock.update_state` (lines 521-523):
```python
    @pyqtSlot(str)
    @pyqtSlot(str, str)
    def update_state(self, state: str, mood: str = "Curious") -> None:
```

#### Exact Diff in `parasite_ai/ui/companion_dock.py`:

```diff
--- a/parasite_ai/ui/companion_dock.py
+++ b/parasite_ai/ui/companion_dock.py
@@ -596,2 +596,3 @@
     @pyqtSlot(object)
+    @pyqtSlot(object, list)
     def update_perception_preview(self, frame_data: Any, elements: Optional[List[Any]] = None) -> None:
```

### Step 2: Verification of Connection Wiring in `_connect_bridge`
In `parasite_ai/ui/companion_dock.py` lines 706-714:
```python
    def _connect_bridge(self, bridge: Any) -> None:
        """Wires Qt bridge signals to dock slots and dock signals to bridge."""
        try:
            bridge.sig_state_changed.connect(self.update_state, Qt.ConnectionType.QueuedConnection)
            bridge.sig_thought_updated.connect(self.update_thought, Qt.ConnectionType.QueuedConnection)
            bridge.sig_speech_updated.connect(self.update_speech, Qt.ConnectionType.QueuedConnection)
            bridge.sig_telemetry_updated.connect(self.update_telemetry, Qt.ConnectionType.QueuedConnection)
            bridge.sig_perception_updated.connect(self.update_perception_preview, Qt.ConnectionType.QueuedConnection)
```
**CRITICAL NOTE FOR WORKER**:
Do **NOT** alter line 713 to `self.update_perception_preview[object, list]`. In PyQt6, bound methods on QWidget are not subscriptable (doing so raises `TypeError: 'method' object is not subscriptable`).
Passing `self.update_perception_preview` directly enables PyQt6's C++ connection resolver to automatically match the exact 2-argument signature `(PyQt_PyObject, QVariantList)`.

---

## 3. Behavioral Verification Matrix

| Call Pathway | Signature Invoked | Arguments Received | Resulting Badge Text |
| :--- | :--- | :--- | :--- |
| `bridge.notify_perception(frame, [elem1, elem2])` | `(PyQt_PyObject, QVariantList)` | `frame_data=frame`, `elements=[elem1, elem2]` | `"Grounding: 2 Targets Active"` |
| `bridge.notify_perception(frame)` | `(PyQt_PyObject, QVariantList)` (via `elements or []`) | `frame_data=frame`, `elements=[]` | `"Grounding: 0 Targets Active"` |
| Direct Python call `dock.update_perception_preview(frame)` | Python direct invocation | `frame_data=frame`, `elements=None` | Unchanged (`"Grounding: Active"`) |
| Direct Python call `dock.update_perception_preview(frame, [elem1])` | Python direct invocation | `frame_data=frame`, `elements=[elem1]` | `"Grounding: 1 Targets Active"` |
| 1-arg Qt Signal `sig = pyqtSignal(object)` connected to slot | `(PyQt_PyObject)` | `frame_data=frame`, `elements=None` | Unchanged (`"Grounding: Active"`) |
| Masked state (`self._is_masked = True`) | Either | Returns early via `_render_privacy_blackout()` | `"Grounding: [PAUSED — SENSITIVE]"` |

---

## 4. Step-by-Step Instructions for Worker

1. Open `parasite_ai/ui/companion_dock.py`.
2. Locate line 596:
   ```python
   @pyqtSlot(object)
   def update_perception_preview(self, frame_data: Any, elements: Optional[List[Any]] = None) -> None:
   ```
3. Add `@pyqtSlot(object, list)` directly below `@pyqtSlot(object)`:
   ```python
   @pyqtSlot(object)
   @pyqtSlot(object, list)
   def update_perception_preview(self, frame_data: Any, elements: Optional[List[Any]] = None) -> None:
   ```
4. Save the file.
5. Execute targeted test verification:
   ```powershell
   uv run pytest tests/test_companion_dock_adversarial.py -k test_ui_bridge_perception_elements_slot_signature -v
   ```
   *Expected Result*: `1 passed in ~1.3s`.
6. Execute companion dock unit tests to ensure no regressions:
   ```powershell
   uv run pytest tests/test_companion_dock.py -v
   ```
   *Expected Result*: `17 passed in ~1.3s`.

---

## 5. Risk Assessment & Invariant Checks

- **Zero Breaking Changes**: Existing callers calling `update_perception_preview(pixmap)` directly in Python or via 1-argument signals are preserved because `@pyqtSlot(object)` remains registered.
- **QVariantList Marshalling**: PyQt6 natively serializes Python lists of `UIElement` Pydantic models across threads via `QVariantList` with zero serialization failures or reference leaks.
- **Privacy Mask Invariant**: If `CompanionDock` is in `PROTECTED` state (`self._is_masked = True`), lines 602-604 continue to intercept execution before badge modification, ensuring zero pixel or metadata leakage during sensitive window focus.
