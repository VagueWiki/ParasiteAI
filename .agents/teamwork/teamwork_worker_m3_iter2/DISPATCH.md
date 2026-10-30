# Task Assignment: Milestone M3 Iteration 2 Remediation Worker

**Recipient**: `teamwork_worker_m3_iter2`
**Role**: `teamwork_worker`
**Working Directory**: `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_worker_m3_iter2\`
**Assigned Milestone**: Milestone M3 — Desktop Companion Dock & Ghost-Hand Overlay (Iteration 2)

---

## Mandatory Integrity Warning
> DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

---

## Objective
Remediate the 3 defects uncovered during Milestone M3 Iteration 1 Gate Evaluation by Challenger 1, following the precise plans formulated by the 3 Iteration 2 Explorers:

1. **Defect 1**: Stack `@pyqtSlot(object, list)` alongside `@pyqtSlot(object)` on `CompanionDock.update_perception_preview` in `parasite_ai/ui/companion_dock.py:596`.
   - See `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m3_iter2_1\plan.md` and `handoff.md`.
2. **Defect 2**: Replace `pct = int((current_step / total_steps) * 100)` with `pct = round((current_step * 100) / total_steps)` (with `max(0, min(100, pct))` clamping) in `parasite_ai/ui/companion_dock.py:589`.
   - See `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m3_iter2_2\plan.md` and `handoff.md`.
3. **Defect 3**:
   - In `parasite_ai/ui/bridge.py:31`, overload `sig_telemetry_updated = pyqtSignal([str], [str, int, int])`.
   - In `parasite_ai/ui/bridge.py:72`, update `notify_telemetry(self, telemetry: str, current_step: int = 0, total_steps: int = 0) -> None` to emit the 3-arg overload if steps are supplied and 1-arg overload otherwise.
   - In `parasite_ai/ui/companion_dock.py:583`, decorate `update_telemetry` with both `@pyqtSlot(str)` and `@pyqtSlot(str, int, int)`.
   - In `parasite_ai/ui/companion_dock.py:712` (`_connect_bridge`), connect both overloads to `self.update_telemetry`.
   - See `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m3_iter2_3\plan.md` and `handoff.md`.

---

## Files Owned
- `parasite_ai/ui/companion_dock.py`
- `parasite_ai/ui/bridge.py`

---

## Verification Requirements
1. Run `uv run pytest tests/test_companion_dock_adversarial.py -v` (must pass 14/14 tests).
2. Run `uv run pytest tests/test_ghost_hud_adversarial.py -v` (must pass 33/33 tests).
3. Run `uv run pytest tests/test_companion_dock.py tests/test_ghost_hud.py tests/test_ui_bridge.py tests/test_dpi.py -v` (must pass 44/44 tests).
4. Run full repository test suite: `uv run pytest -v` (must pass 412/412 tests with zero failures and zero regressions).
5. Document all results and commands in `handoff.md` and notify the orchestrator via `send_message`.


## 2026-10-29T16:29:30Z
[Message] timestamp=2026-10-29T16:29:30Z sender=9a16f679-6db4-4849-ba56-0f4856cbbf9b priority=MESSAGE_PRIORITY_HIGH
Objective: Remediate the 3 defects uncovered during Milestone M3 Iteration 1 Gate Evaluation by Challenger 1, following the precise plans formulated by the 3 Iteration 2 Explorers.
