# Task Assignment: Milestone M3 Iteration 2 Explorer 1 (Perception Slot Overload)

**Recipient**: `teamwork_explorer_m3_iter2_1`
**Role**: `teamwork_explorer`
**Working Directory**: `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m3_iter2_1\`
**Assigned Milestone**: Milestone M3 — Desktop Companion Dock & Ghost-Hand Overlay (Iteration 2)

---

## Previous Failure Output & Context
In Milestone M3 Iteration 1 Gate Evaluation, Challenger 1 uncovered the following defect:
- **Defect 1**: Grounding Targets Dropped via `UIBridge`
- **Location**: `parasite_ai/ui/companion_dock.py` line 596
- **Symptom**: `CompanionDock.update_perception_preview` only decorates `@pyqtSlot(object)`. When `UIBridge.sig_perception_updated = pyqtSignal(object, list)` emits across threads via queued connection, Qt drops the `list` (elements) argument. Consequently, `elements` is always `None`, and the grounding badge text never updates to `Grounding: N Targets Active`.
- **Failing Test**: `tests/test_companion_dock_adversarial.py::TestCompanionDockAdversarial::test_ui_bridge_perception_elements_slot_signature`

---

## Instructions
1. Read `g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md`.
2. Read `g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md`.
3. Read `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_challenger_m3_1\handoff.md`.
4. Inspect `parasite_ai/ui/companion_dock.py` and `parasite_ai/ui/bridge.py`.
5. Formulate an exact fix strategy and plan for the implementation worker:
   - How to decorate `update_perception_preview` with overloaded `@pyqtSlot` signatures (`@pyqtSlot(object)` and `@pyqtSlot(object, list)` or `object, object`) so Qt queued connections preserve both arguments.
   - Verify compatibility when called directly vs via Qt signal.
6. Write your plan in `plan.md` and handoff in `handoff.md`. Do NOT modify code directly.
7. Notify the orchestrator via `send_message`.
