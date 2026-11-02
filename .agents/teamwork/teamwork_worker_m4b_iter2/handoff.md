# Handoff Report — Milestone 4B Iteration 2 (Remediation of Strike Leakage & Offloader Fallback)

## 1. Observation

### 1.1 Defects Reported by Reviewer 1 & Reproduced
1. **Premature PANIC Abort via Strike Leakage in Tier 3**:
   - `parasite_ai/mind/dual_mind.py:1042`: The condition `elif self.memory.is_in_loop():` unconditionally triggered `ActionPlan(action=ActionType.PANIC)` whenever `EpisodicMemory._consecutive_strikes >= 3`.
   - In Step 1 & 2 (Tier 1), two zero-diff failures accumulated 2 strikes in `_consecutive_strikes`.
   - In Step 3 (Tier 2 consultation), consultation succeeded and advanced to Tier 3, but `_consecutive_strikes` in `EpisodicMemory` remained at 2.
   - On Step 4 (Tier 3 guided attempt 1), interactive failure incremented `_consecutive_strikes` to 3.
   - On Step 5 (Tier 3 guided attempt 2), `self.memory.is_in_loop()` returned `True`, aborting with `ActionType.PANIC` before the second guided attempt or escalation to Tier 4 co-pilot could occur.
   - Verbatim reproduction output: `Rec5 Action: ActionType.PANIC`.

2. **Infinite Deadlock Loop when `offloader is None`**:
   - `parasite_ai/mind/dual_mind.py:912-916`: In Tier 2 consultation branch, when `self.offloader is None`, the code directly set `local_strikes = 0` and reset `current_tier = CadenceTier.TIER_1_LOCAL` without calling `self.escalation_sm.on_consultation_failure()`.
   - `self.escalation_sm.consultation_failures` remained 0 indefinitely, cycling endlessly between Tier 1 (2 failures) and Tier 2 fallback without ever terminating to `USER_OVERRIDE`.
   - Verbatim reproduction output after 10 failure cycles: `Current Tier: CadenceTier.TIER_1_LOCAL`, `Consultation Failures: 0`.

3. **Loop Detector Reset Coupling**:
   - `parasite_ai/mind/memory.py:439-444`: `reset_loop_detector()` previously called `self.escalation_sm.reset()`, resetting the state machine to `TIER_1_LOCAL` and clearing all cadence progress whenever called.

### 1.2 Remediations Implemented
1. **`parasite_ai/mind/memory.py`**:
   - Updated `reset_loop_detector(self, reset_escalation: bool = False) -> None` so clearing loop detector failure strikes (`self._consecutive_strikes = 0`) does not unintentionally wipe out the active escalation cadence tier unless `reset_escalation=True` is explicitly specified.
2. **`parasite_ai/mind/dual_mind.py`**:
   - In Tier 2 consultation branch (`dual_mind.py:912-935`): When `self.offloader is None`, `self.escalation_sm.on_consultation_failure()` and `self.memory.reset_loop_detector()` are invoked. If `consultation_failures >= max_consultation_failures` (reaching `USER_OVERRIDE`), it notifies the UI bridge and returns a safe `WAIT` step. Otherwise, it updates `active_plan` tier tracking and allows clean local fallback execution.
   - In Tier 2 consultation success/failure branches (`dual_mind.py:985-995`): Added `self.memory.reset_loop_detector()` on both consultation success and consultation query failure, eliminating cross-tier strike leakage.
   - In Step 4 action planning (`dual_mind.py:1085`): Restricted legacy loop panic to `elif self.escalation_sm.current_tier == CadenceTier.TIER_1_LOCAL and self.memory.is_in_loop():`, preventing legacy panic from hijacking Tier 3 guided execution or Tier 4 visual co-pilot.
3. **`parasite_ai/runtime.py`**:
   - Maintained full episode boundary isolation by passing `reset_escalation=True` to `reset_loop_detector()` in `_execute_goal_episode`, episode teardown, `run_single_step` goal changes, and `reset_panic()`.
4. **`tests/test_escalation_cadence.py`**:
   - Added `test_sequential_full_cadence_progression_no_premature_panic`: Validates end-to-end multi-turn execution traversing T1 (2 strikes) -> T2 (Gemini consult success) -> T3 (2 guided strikes, with step 5 generating `CLICK` instead of `PANIC`) -> T4 (3 co-pilot strikes) -> `USER_OVERRIDE` (safely yielding `WAIT`).
   - Added `test_sequential_offloader_none_loop_termination`: Validates that offline mode with `offloader=None` increments `consultation_failures` on each Tier 2 visit and cleanly terminates into `USER_OVERRIDE` on the second failure without infinite looping.

---

## 2. Logic Chain

1. **Phase 4 Invariant Compliance**:
   - Master Plan Section 3 dictates that the 4-tier escalation state machine replaces simplistic panic aborts with a progressive ladder: 2 local attempts -> strategic Gemini consultation -> 2 guided attempts -> continuous visual co-pilot -> user override.
   - Restricting `memory.is_in_loop()` panic abort in `DualMindPipeline.step()` exclusively to `TIER_1_LOCAL` guarantees that once Tier 2 consultation has occurred, execution in Tier 3 and Tier 4 is governed solely by `EscalationStateMachine` strike counters (`guided_strikes` and `copilot_strikes`).
2. **Strike Leakage Eradication**:
   - When strategic consultation succeeds or fails, invoking `self.memory.reset_loop_detector()` resets `self._consecutive_strikes` in `EpisodicMemory` to 0.
   - Because `reset_loop_detector()` preserves `self.escalation_sm` by default, `current_tier` correctly advances to `TIER_3_GUIDED` on success (or evaluates `consultation_failures` on failure) while resetting physical strike accumulators.
   - Consequently, in Step 5 (guided attempt 2), `_consecutive_strikes` is only 1, ensuring neither the legacy detector nor the state machine triggers a premature abort.
3. **Loop Termination Guarantee (`offloader is None`)**:
   - When offline without an offloader, entering Tier 2 directly records a consultation failure via `on_consultation_failure()`.
   - On consultation failure 1 (`consultation_failures == 1`), the state machine allows a second attempt cycle in Tier 1.
   - On consultation failure 2 (`consultation_failures == 2 >= max_consultation_failures`), the state machine deterministically transitions to `USER_OVERRIDE`.
   - The pipeline recognizes `current_tier == USER_OVERRIDE`, notifies the bridge, and yields a `WAIT` action, preventing infinite deadlocks.

---

## 3. Caveats

- In headless test environments where no display is connected and `ScreenCapture` yields synthetic uniform frames, interactive GUI actions (such as `CLICK`) produce a calculated `screen_diff` of `0.0`. Under `on_action_result()`, visual actions with `screen_diff < diff_threshold` are categorized as effective strikes as designed by the strike evaluation contract.
- Actions with `ActionType.WAIT` or `ActionType.DONE` remain exempt from strike accumulation.

---

## 4. Conclusion

All reported defects and requested remediations have been implemented and verified:
1. `self.memory.reset_loop_detector()` is called on consultation success, consultation query failure, and `offloader is None`.
2. `DualMindPipeline.step()` panic abort check is restricted strictly to `TIER_1_LOCAL`.
3. When `self.offloader is None`, `self.escalation_sm.on_consultation_failure()` is invoked, terminating into `USER_OVERRIDE` after 2 failures.
4. Comprehensive multi-step sequential integration tests were added in `tests/test_escalation_cadence.py` and pass with 100% green status.
5. All 58 tests across `test_escalation_cadence.py`, `test_challenger_m5_2.py`, and `test_challenger_p4_empirical.py` pass cleanly.

---

## 5. Verification Method

To independently verify the fixes:

1. **Verify Premature Panic in Tier 3 is Fixed**:
   ```powershell
   C:\ParasiteAI\.venv\Scripts\python.exe -c "import json; from unittest.mock import MagicMock; from parasite_ai.mind.dual_mind import DualMindPipeline; from parasite_ai.mind.memory import ActionType, CadenceTier; bm = MagicMock(); bm.generate_thought.return_value = 't'; bm.generate_action.return_value = {'action': 'CLICK'}; off = MagicMock(); off.query_web_ai.return_value = json.dumps({'steps': [{'step_id': 1, 'intent': 'NAVIGATE', 'description': 'test'}]}); p = DualMindPipeline(brain_manager=bm, offloader=off); p.step(user_goal='test'); p.step(user_goal='test'); p.step(user_goal='test'); rec4 = p.step(user_goal='test'); rec5 = p.step(user_goal='test'); print('Rec5 Action:', rec5.action.action); assert rec5.action.action != ActionType.PANIC, 'FAIL: Premature PANIC aborted Tier 3'"
   ```
   *Expected Output*: `Rec5 Action: ActionType.CLICK` (exit code 0).

2. **Verify `offloader is None` Loop Termination**:
   ```powershell
   C:\ParasiteAI\.venv\Scripts\python.exe -c "from unittest.mock import MagicMock; from parasite_ai.mind.dual_mind import DualMindPipeline; from parasite_ai.mind.memory import CadenceTier; bm = MagicMock(); bm.generate_thought.return_value = 't'; bm.generate_action.return_value = {'action': 'CLICK'}; p = DualMindPipeline(brain_manager=bm, offloader=None); [p.step(user_goal='test') for _ in range(10)]; assert p.escalation_sm.current_tier == CadenceTier.USER_OVERRIDE, 'FAIL: Did not reach USER_OVERRIDE after repeated offline advisor failures'"
   ```
   *Expected Output*: Clean exit code 0.

3. **Run Cadence and Empirical Regression Test Suites**:
   ```powershell
   C:\ParasiteAI\.venv\Scripts\python.exe -m pytest tests/test_escalation_cadence.py tests/test_challenger_p4_empirical.py tests/test_challenger_m5_2.py -v
   ```
   *Expected Output*: 58 passed in ~6.5s.
