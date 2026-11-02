# Handoff Report — Milestone 4B Reviewer 1 (Quality & Adversarial Review)

## 1. Observation

### 1.1 Direct Code Observations
1. **Legacy 3-Strike Panic Abort in `DualMindPipeline`**:
   In `parasite_ai/mind/dual_mind.py` lines 1042-1047:
   ```python
   elif self.memory.is_in_loop():
       # Detected cognitive failure loop! Trigger emergency strategy switch
       action_plan = ActionPlan(
           action=ActionType.PANIC,
           reasoning="Detected 3-strike failure loop. Initiating panic/strategy reset.",
       )
   ```
2. **Strike Leakage across Tiers in `EpisodicMemory`**:
   In `parasite_ai/mind/memory.py` lines 393-406:
   ```python
   # Strike evaluation
   is_strike = False
   if parsed_action.action in INTERACTIVE_ACTION_TYPES:
       if not success or screen_diff < self.screen_diff_threshold:
           is_strike = True
           self._consecutive_strikes += 1
       else:
           self._consecutive_strikes = 0
   ```
   When `on_consultation_success()` is called (`memory.py` line 216), `self.local_strikes` is reset to 0 in `EscalationStateMachine`, but `self._consecutive_strikes` in `EpisodicMemory` is **never reset** and remains at 2.
3. **Infinite Loop when `offloader is None`**:
   In `parasite_ai/mind/dual_mind.py` lines 912-916:
   ```python
   if self.escalation_sm.current_tier == CadenceTier.TIER_2_CONSULT:
       if self.offloader is None:
           logger.info("No offloader configured for Tier 2 consultation; falling back to local execution.")
           self.escalation_sm.local_strikes = 0
           self.escalation_sm.current_tier = CadenceTier.TIER_1_LOCAL
   ```
   `self.escalation_sm.on_consultation_failure()` is **never called** when `offloader is None`. `self.escalation_sm.consultation_failures` remains 0 indefinitely, bypassing `max_consultation_failures = 2` loop termination and cycling T1 <-> T2 forever.
4. **Isolated Test Coverage**:
   In `tests/test_escalation_cadence.py` (lines 332-449), tests for `DualMindPipeline` test single-step actions with manually injected tiers, and never execute a natural sequential step progression across Tier 1 -> Tier 2 -> Tier 3.

### 1.2 Verbatim Test & Reproduction Outputs
1. **Reproduction of Critical Strike Leakage & Premature Panic**:
   Command:
   ```powershell
   C:\ParasiteAI\.venv\Scripts\python.exe -c "import json; from unittest.mock import MagicMock; from parasite_ai.mind.dual_mind import DualMindPipeline; from parasite_ai.mind.memory import ActionType, CadenceTier; bm = MagicMock(); bm.generate_thought.return_value = 't'; bm.generate_action.return_value = {'action': 'CLICK'}; off = MagicMock(); off.query_web_ai.return_value = json.dumps({'steps': [{'step_id': 1, 'intent': 'NAVIGATE', 'description': 'test'}]}); p = DualMindPipeline(brain_manager=bm, offloader=off); p.step(user_goal='test'); p.step(user_goal='test'); p.step(user_goal='test'); rec4 = p.step(user_goal='test'); rec5 = p.step(user_goal='test'); print('Rec5 Action:', rec5.action.action); assert rec5.action.action == ActionType.PANIC"
   ```
   Output:
   ```
   Rec5 Action: ActionType.PANIC
   ```
   On Step 4 (the first guided action in Tier 3), execution failed. On Step 5 (the second guided action in Tier 3), instead of allowing the second guided attempt or escalating to Tier 4, `DualMindPipeline` emitted `ActionType.PANIC`.
2. **Reproduction of Infinite Loop when `offloader is None`**:
   Command:
   ```powershell
   C:\ParasiteAI\.venv\Scripts\python.exe -c "from unittest.mock import MagicMock; from parasite_ai.mind.dual_mind import DualMindPipeline; from parasite_ai.mind.memory import CadenceTier; bm = MagicMock(); bm.generate_thought.return_value = 't'; bm.generate_action.return_value = {'action': 'CLICK'}; p = DualMindPipeline(brain_manager=bm, offloader=None); [p.step(user_goal='test') for _ in range(10)]; print('Current Tier:', p.escalation_sm.current_tier); print('Consultation Failures:', p.escalation_sm.consultation_failures)"
   ```
   Output:
   ```
   Current Tier: CadenceTier.TIER_1_LOCAL
   Consultation Failures: 0
   ```
   After 10 continuous failure steps, the state machine cycled indefinitely between T1 and T2 without ever transitioning to `USER_OVERRIDE`.

---

## 2. Logic Chain

1. **Phase 4 Architectural Invariant (Master Plan Section 3 & VERIF-1)**:
   - Master Plan Section 3 explicitly mandates:
     *"4-Tier Escalation Cadence: Replaces simplistic panic aborts with a graceful, structured escalation state machine: 2 local attempts -> deep strategic Gemini consultation -> 2 guided local attempts with Gemini blueprint -> continuous visual co-pilot handholding -> user override."*
   - VERIF-1 mandates:
     *"Tier 1 advances to Tier 2 on 2 local strikes; Tier 3 advances to Tier 4 on 2 guided strikes; Tier 4 transitions to USER_OVERRIDE on 3 strikes. Persistent advisor failure transitions to USER_OVERRIDE after 2 failures... Invalidation Condition: Strike counter fails to transition, cycles indefinitely between T3/T4 or T1/T2, leaks strikes across tiers..."*
2. **Strike Leakage Mechanism**:
   - In Step 1 & 2 (Tier 1), 2 interactive failures increment both `self.escalation_sm.local_strikes` (2) and `self.memory._consecutive_strikes` (2).
   - In Step 3 (Tier 2 consultation), consultation succeeds via `self.escalation_sm.on_consultation_success()`. While `self.escalation_sm.local_strikes` is reset to 0, `self.memory._consecutive_strikes` remains untouched at 2.
   - In Step 4 (Tier 3 guided attempt 1), the interactive action fails. `self.escalation_sm.guided_strikes` becomes 1. However, `self.memory._consecutive_strikes` increments from 2 to 3.
   - In Step 5 (Tier 3 guided attempt 2), `self.memory.is_in_loop()` returns `True` (`_consecutive_strikes >= 3`). Line 1042 of `dual_mind.py` intercepts action generation and emits `ActionType.PANIC`.
   - Therefore, Tier 3 guided attempt 2 is never executed, and Tier 4 (Continuous Co-Pilot) is completely unreachable from a normal execution sequence.
3. **Infinite Loop Mechanism (`offloader is None`)**:
   - Master Plan Section 3.1 states:
     *"If offline (`brain.mode: 'local_llm'` without web credentials) or the query times out: consultation_failures increments by 1. If consultation_failures >= 2, the system immediately transitions to USER_OVERRIDE, preventing infinite deadlocks between Tier 1 and Tier 2."*
   - In `dual_mind.py` lines 913-916, when `self.offloader is None`, `self.escalation_sm.on_consultation_failure()` is bypassed. Instead, `local_strikes` is reset to 0 directly, and `consultation_failures` remains 0 forever.
   - Consequently, in standard local/offline mode, ParasiteAI enters an infinite cycle of 2 local failures -> consult reset -> 2 local failures, violating the loop termination invariant.

---

## 3. Caveats

- The worker correctly implemented the isolated Pydantic model `EscalationStateMachine` in `memory.py` according to Section 3.3.
- All 43 isolated unit tests in `test_escalation_cadence.py` and 53 regression tests pass.
- No integrity violations or cheating patterns (hardcoded test strings or dummy mocks) were found; the issues are pure system integration and state leakage defects between `DualMindPipeline` and `EpisodicMemory`.

---

## 4. Conclusion

**Verdict: REQUEST_CHANGES**

### Findings Summary
1. **Critical Finding 1 (Strike Leakage & Premature Panic Abort)**:
   - Location: `parasite_ai/mind/dual_mind.py:1042` and `parasite_ai/mind/memory.py:363,393`
   - Problem: `EpisodicMemory._consecutive_strikes` leaks strikes across tiers, causing `self.memory.is_in_loop()` to trigger `ActionType.PANIC` on the first Tier 3 failure, bypassing Tier 3 guided attempt 2 and blocking Tier 4 co-pilot entirely.
   - Suggested Fix:
     - In `DualMindPipeline.step()`, when in Tier 3 or Tier 4, the legacy `self.memory.is_in_loop()` panic abort must either be deactivated or synchronized with `self.escalation_sm`.
     - In `DualMindPipeline`, when `on_consultation_success()` or `on_consultation_failure()` is called, reset `self.memory._consecutive_strikes = 0` (or call `self.memory.reset_loop_detector()`).
     - Alternatively, replace `self.memory.is_in_loop()` in `DualMindPipeline.step()` with `self.escalation_sm.current_tier == CadenceTier.USER_OVERRIDE` or coordinate them cleanly so panic does not override the 4-tier state machine.
2. **Critical Finding 2 (Infinite Loop when `offloader is None`)**:
   - Location: `parasite_ai/mind/dual_mind.py:912-916`
   - Problem: When `offloader is None`, `local_strikes` is reset without calling `on_consultation_failure()`, preventing `consultation_failures` from incrementing and circumventing `max_consultation_failures = 2` termination.
   - Suggested Fix:
     - Call `self.escalation_sm.on_consultation_failure()` when `self.offloader is None`.
     - If `self.escalation_sm.current_tier == CadenceTier.USER_OVERRIDE`, notify the bridge and return a `WAIT` step.
     - Otherwise, allow local replan / fallback execution.
3. **Major Finding 3 (Missing Multi-Step Pipeline Integration Test)**:
   - Location: `tests/test_escalation_cadence.py`
   - Problem: No test exercised multi-turn consecutive stepping through `DualMindPipeline` across Tier 1 -> Tier 2 -> Tier 3 -> Tier 4.
   - Suggested Fix: Add an end-to-end integration test in `test_escalation_cadence.py` that runs consecutive pipeline steps from Tier 1 failure (2 strikes) -> Tier 2 consult -> Tier 3 failures (2 strikes) -> Tier 4 co-pilot (3 strikes) -> `USER_OVERRIDE`.

---

## 5. Verification Method

1. Verify reproduction of Premature Panic in Tier 3:
   ```powershell
   C:\ParasiteAI\.venv\Scripts\python.exe -c "import json; from unittest.mock import MagicMock; from parasite_ai.mind.dual_mind import DualMindPipeline; from parasite_ai.mind.memory import ActionType, CadenceTier; bm = MagicMock(); bm.generate_thought.return_value = 't'; bm.generate_action.return_value = {'action': 'CLICK'}; off = MagicMock(); off.query_web_ai.return_value = json.dumps({'steps': [{'step_id': 1, 'intent': 'NAVIGATE', 'description': 'test'}]}); p = DualMindPipeline(brain_manager=bm, offloader=off); p.step(user_goal='test'); p.step(user_goal='test'); p.step(user_goal='test'); rec4 = p.step(user_goal='test'); rec5 = p.step(user_goal='test'); print('Rec5 Action:', rec5.action.action); assert rec5.action.action != ActionType.PANIC, 'FAIL: Premature PANIC aborted Tier 3'"
   ```
2. Verify reproduction of Infinite Loop when `offloader is None`:
   ```powershell
   C:\ParasiteAI\.venv\Scripts\python.exe -c "from unittest.mock import MagicMock; from parasite_ai.mind.dual_mind import DualMindPipeline; from parasite_ai.mind.memory import CadenceTier; bm = MagicMock(); bm.generate_thought.return_value = 't'; bm.generate_action.return_value = {'action': 'CLICK'}; p = DualMindPipeline(brain_manager=bm, offloader=None); [p.step(user_goal='test') for _ in range(10)]; assert p.escalation_sm.current_tier == CadenceTier.USER_OVERRIDE, 'FAIL: Did not reach USER_OVERRIDE after repeated offline advisor failures'"
   ```
3. Full test pass after remediation:
   ```powershell
   C:\ParasiteAI\.venv\Scripts\python.exe -m pytest tests/test_escalation_cadence.py tests/test_challenger_p4_empirical.py -v
   ```
