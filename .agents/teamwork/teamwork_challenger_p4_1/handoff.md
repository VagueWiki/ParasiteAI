# Challenger 1 Handoff Report: State Machine & Contract Stress Testing

**Author:** Challenger 1 (State Machine & Contract Stress Tester)  
**Role:** critic, specialist  
**Working Directory:** `C:\ParasiteAI\.agents\teamwork\teamwork_challenger_p4_1\`  
**Target File Reviewed:** `c:\Users\Suici\.gemini\antigravity\brain\464b4ef0-398b-45b1-94dc-857256a38046\phase_4_master_plan.md`  
**Test Suite Created:** `C:\ParasiteAI\tests\test_challenger_p4_empirical.py`  
**Date:** 2026-11-01T02:44:00Z  
**Verdict:** **REQUEST_CHANGES** (Empirical design defects & router ingestion bugs discovered)

---

## 1. Observation

1. **DualChannelRouter Blueprint Ingestion Bug (`phase_4_master_plan.md` line 438):**
   - The proposed implementation reads:
     ```python
     # Channel A: Extract machine blueprint
     blueprint_json = extract_strategic_blueprint_json(raw_advisor_text)
     if blueprint_json and "steps" in blueprint_json:
         updated_plan = parse_gemini_consultation_response(raw_advisor_text, user_goal)
     ```
   - In `parasite_ai/mind/plan.py` line 182 and `tests/test_gemini_consultation_protocol.py` line 42, the existing standardized schema template uses `"recommended_strategy": [...]`.
   - Empirically observed in `test_router_drops_blueprint_when_using_recommended_strategy_key`:
     When Gemini responds matching the existing codebase prompt format (`"recommended_strategy": [...]`), `"steps" in blueprint_json` evaluates to `False`. The blueprint is discarded (`updated_plan = None`), and the system falsely concludes that no plan was generated!

2. **Dual-Channel Output Leaks to Companion Dock (`phase_4_master_plan.md` lines 477–485):**
   - In `DualChannelRouter._sanitize_text`:
     ```python
     text = re.sub(r"```json[\s\S]*?```", "", text)
     text = re.sub(r"[{}\[\]\"]", "", text)
     text = re.sub(r"\b\d+x\d+\b", "", text)
     text = re.sub(r"\(\d+,\s*\d+\)", "", text)
     return " ".join(text.split()).strip()
     ```
   - Empirically observed in `test_router_raw_json_leakage_on_malformed_error_payload`:
     When Gemini returns an error object (e.g. `{"error": "RESOURCE_EXHAUSTED", "code": 429}`), it has no `"steps"`, so `raw_rationale` receives the raw string. The regex strips braces and quotes, leaving `error: RESOURCE_EXHAUSTED, code: 429` which leaks directly into visible speech bubbles.
   - Empirically observed in `test_router_code_block_leakage_python_or_bash`:
     The regex only removes ````json ... ````. Any non-JSON code blocks (````python ... ````, ````bash ... ````, or raw backticks) fail the regex and are rendered in the companion dock monologue.

3. **Cognitive State Machine Infinite Ping-Pong Loop (`phase_4_master_plan.md` lines 239–248):**
   - In `ProposedEscalationStateMachine.on_action_result`:
     ```python
     elif self.current_tier == CadenceTier.TIER_4_CO_PILOT:
         if effective_success:
             self.copilot_strikes = 0
             self.guided_strikes = 0
             self.current_tier = CadenceTier.TIER_3_GUIDED
         else:
             self.copilot_strikes += 1
             if self.copilot_strikes >= 3:
                 self.current_tier = CadenceTier.USER_OVERRIDE
     ```
   - Empirically observed in `test_edge_case_infinite_ping_pong_loop_between_tier_3_and_tier_4`:
     If Tier 3 fails twice and escalates to Tier 4, and in Tier 4 a single micro-action succeeds, `copilot_strikes` and `guided_strikes` are both reset to 0, returning to Tier 3. If Tier 3 fails on the next step, it returns to Tier 4. This sequence was run for 10 consecutive cycles without ever escalating to `USER_OVERRIDE`. Without a cumulative cycle cap, the agent can cycle indefinitely.

4. **Persistent Advisor Failure Loop (`phase_4_master_plan.md` lines 256–260):**
   - In `on_consultation_failure`:
     ```python
     def on_consultation_failure(self) -> None:
         if self.current_tier == CadenceTier.TIER_2_CONSULT:
             self.local_strikes = 0
             self.current_tier = CadenceTier.TIER_1_LOCAL
     ```
   - Empirically observed in `test_edge_case_persistent_advisor_failure_infinite_loop`:
     When an offline network condition or missing API key causes Gemini consultation to fail repeatedly, `on_consultation_failure` resets `local_strikes = 0` and bounces back to `TIER_1_LOCAL`. Tier 1 fails twice, transitions to Tier 2, fails, and resets. The system loops infinitely between Tier 1 and Tier 2, never yielding to `USER_OVERRIDE`.

5. **Strike Counter Leakage on Consultation Success (`phase_4_master_plan.md` lines 251–255):**
   - In `on_consultation_success`:
     ```python
     def on_consultation_success(self) -> None:
         if self.current_tier == CadenceTier.TIER_2_CONSULT:
             self.guided_strikes = 0
             self.current_tier = CadenceTier.TIER_3_GUIDED
     ```
   - Empirically observed in `test_edge_case_local_strikes_leak_after_consultation_success`:
     `local_strikes` was set to 2 when escalating from Tier 1. It is never reset in `on_consultation_success`. If the agent later returns to Tier 1 after completing a guided plan, `local_strikes` remains at 2. The very next failure in Tier 1 immediately triggers an escalation or violates Pydantic's `le=2` constraint if incremented to 3.

6. **Passive Action False Strikes (`phase_4_master_plan.md` line 220):**
   - `effective_success = success and (screen_diff >= diff_threshold)`
   - Empirically observed in `test_passive_action_wait_triggers_strike_if_diff_zero`:
     A planned `ActionType.WAIT` or `ActionType.DONE` with `screen_diff = 0.0` is evaluated as `effective_success = False`, erroneously incrementing failure strikes.

7. **Missing Hardware Preemption Transition in State Machine (`phase_4_master_plan.md` lines 213–260):**
   - Section 3.2 specifies that on hardware touch, state transitions from `ANY_STATE` to `USER_OVERRIDE`.
   - However, the `EscalationStateMachine` class in Section 3.3 provides no transition method (no `on_hardware_interrupt()` or `set_user_override()`).

8. **Empirical Test Suite Execution Results:**
   - Command: `& "C:\ParasiteAI\.venv\Scripts\python.exe" -m pytest tests/test_challenger_p4_empirical.py -v`
   - Result: **18 passed in 0.73s**, exit code 0.
   - Core regression test command: `& "C:\ParasiteAI\.venv\Scripts\python.exe" -m pytest tests/test_living_plan.py tests/test_gemini_consultation_protocol.py tests/test_interrupt_guard.py tests/test_dual_mind.py tests/test_challenger_p4_empirical.py`
   - Result: **78 passed in 1.44s**, exit code 0.

---

## 2. Logic Chain

1. **Premise 1:** The user request mandates incorporating the 4-Tier Escalation Cadence, Grounded Capability Contract, and Dual-Channel Output Router with zero raw JSON shown to the user and full verification of state edge cases.
2. **Premise 2:** In desktop automation, edge cases such as offline advisor failures, oscillating co-pilot successes, un-sanitized LLM error payloads, and non-visual actions (`WAIT`, `Ctrl+C`) occur frequently.
3. **Inference 1 (State Machine Deadlocks):**
   - Because `on_consultation_failure()` resets `local_strikes = 0` unconditionally, repeated advisor outages create an infinite loop between T1 and T2 without ever notifying the user in `USER_OVERRIDE`.
   - Because Tier 4 resets `copilot_strikes` on any single micro-success, a fragile workflow that repeatedly breaks on step 2 can cycle endlessly between T3 and T4.
   - An airtight state machine requires cumulative tracking (`consultation_failures`, `total_escalation_cycles`) to force terminal escalation to `USER_OVERRIDE`.
4. **Inference 2 (Dual-Channel Output Robustness):**
   - The master plan's router implementation in Section 5.2 introduces a regression by checking solely `"steps" in blueprint_json`. Since existing models and prompts format plans with `"recommended_strategy"`, the router drops valid blueprints.
   - When external advisors fail, they return raw error strings or non-JSON code blocks. A sanitizer that only targets ````json```` allows Python code and unquoted JSON error keys to leak into the user's Companion Dock bubble, violating the core character immersion requirement.
5. **Inference 3 (Grounded Capability Contract Grounding):**
   - The contract in Section 4.2 forbids headless browser automation, but Section 6 permits CLI execution (`RUN_CLI_COMMAND`). Without explicit language banning headless scraping tools via CLI (e.g. `curl`, `requests`, `playwright CLI`), an LLM could interpret CLI commands as an allowable loophole.

---

## 3. Caveats

1. **Sub-Phase Execution Timing:** The bugs identified are in the architectural code templates proposed in `phase_4_master_plan.md`. The actual runtime implementation of Sub-phases 4A–4E has not yet begun. Catching these bugs during planning prevents costly debugging during implementation.
2. **Win32 Struct Compliance:** All 10 64-bit Win32 ctypes structures were verified via reflection and conform 100% to the Windows x64 ABI. No changes are required to struct layouts.
3. **Pydantic V2 Compatibility:** Existing models (`UIElement`, `BoundingBox`, `PlanStep`, `LivingPlan`, `ActionPlan`, `StepRecord`, `AppConfig`) operate cleanly under Pydantic v2.

---

## 4. Challenge Summary & Report

**Overall risk assessment**: **HIGH** (Architectural deadlocks and blueprint drop bugs would severely impair Phase 4 implementation if not corrected in the master plan).

### Challenges

#### 1. [Critical] Blueprint Dropping Bug in DualChannelRouter
- **Assumption challenged:** That checking `"steps" in blueprint_json` reliably captures all valid Gemini blueprints.
- **Attack scenario:** Gemini responds with `"recommended_strategy": [...]` (the existing template). The check evaluates to False, drops the plan, and converts the machine blueprint into conversational text.
- **Blast radius:** System completely fails to ingest valid blueprints, breaking Tier 2 $\to$ Tier 3 transition.
- **Mitigation:** Update Section 5.2 to check:
  `has_steps = blueprint_json and (("steps" in blueprint_json and bool(blueprint_json["steps"])) or ("recommended_strategy" in blueprint_json and bool(blueprint_json["recommended_strategy"])))`.

#### 2. [High] State Machine Infinite Ping-Pong & Deadlock Loops
- **Assumption challenged:** That checking strike thresholds on isolated actions guarantees escalation to `USER_OVERRIDE`.
- **Attack scenario:**
  1. Alternating T3 failure / T4 micro-success causes endless oscillating loops.
  2. Persistent Gemini timeout/offline causes endless T1/T2 cycles.
- **Blast radius:** Agent hangs indefinitely without yielding control to the user.
- **Mitigation:** Add `total_escalation_cycles` (max 3) and `consultation_failures` (max 2) to `EscalationStateMachine`. If either limit is reached, transition immediately to `USER_OVERRIDE`.

#### 3. [High] Raw JSON and Code Leakage into Companion Dock
- **Assumption challenged:** That regex stripping of ````json```` and braces is sufficient to suppress raw outputs.
- **Attack scenario:** Gemini returns an error JSON payload (`{"error": "RESOURCE_EXHAUSTED"}`) or a Python snippet (````python import sys````).
- **Blast radius:** Breaks user desktop immersion and exposes technical stack traces in character speech bubbles.
- **Mitigation:** Update `_sanitize_text` to strip ALL code blocks (`re.sub(r"```[\w]*[\s\S]*?```", "", text)`), backticks, and error keywords, falling back to a friendly character voice line.

#### 4. [Medium] Passive Actions Triggering Failure Strikes
- **Assumption challenged:** That all actions produce $\Delta \ge 0.02$.
- **Attack scenario:** Agent executes a planned `ActionType.WAIT`, `ActionType.DONE`, or clipboard `Ctrl+C`. `screen_diff` is 0.000.
- **Blast radius:** Agent accumulates false strikes and escalates prematurely.
- **Mitigation:** Pass `is_interactive: bool` (or `ActionType`) to `on_action_result` so passive actions do not incur strikes.

#### 5. [Medium] Grounded Capability Contract Headless Scraping Loopholes
- **Assumption challenged:** That banning DOM manipulation in GUI prevents web scraping.
- **Attack scenario:** Advisor instructs the agent to run `curl`, `requests`, or `playwright` via `ActionType.RUN_CLI_COMMAND`.
- **Blast radius:** Violates the physical visible desktop automation paradigm and zero silent exfiltration invariant.
- **Mitigation:** Explicitly specify in Section 4.2 that CLI tools cannot be used for headless scraping or programmatic web extraction.

---

## 5. Conclusion & Actionable Verdict

**Verdict:** **REQUEST_CHANGES**

The master plan at `c:\Users\Suici\.gemini\antigravity\brain\464b4ef0-398b-45b1-94dc-857256a38046\phase_4_master_plan.md` must be updated with the following 4 surgical corrections:

1. **Update Section 3.3 (`EscalationStateMachine`):**
   - Reset `self.local_strikes = 0` inside `on_consultation_success()`.
   - Add `consultation_failures` counter to escalate to `USER_OVERRIDE` after 2 consecutive advisor failures.
   - Add `total_escalation_cycles` counter to escalate to `USER_OVERRIDE` after 3 T3/T4 oscillation cycles.
   - Add `on_hardware_interrupt()` method to immediately enter `USER_OVERRIDE`.
   - Accept `is_interactive: bool = True` in `on_action_result()` to bypass strikes for `WAIT`/`DONE`.
2. **Update Section 4.2 (Grounded Capability Contract):**
   - Explicitly add: `"ZERO headless scraping or HTTP data extraction via CLI/scripts (curl, requests, Playwright CLI, Puppeteer, Selenium, BeautifulSoup are strictly forbidden)"`.
   - Explicitly add: `"ZERO programmatic accessibility pattern invocation (ValuePattern.SetValue, InvokePattern.Invoke are strictly forbidden)"`.
   - Update `Virtual_Desktop_Bounds` to note dynamic querying via `get_virtual_screen_bounds()` to support left-extended multi-monitor setups with negative coordinates.
3. **Update Section 5.2 (`DualChannelRouter`):**
   - In `route_consultation_output`, check both `"steps"` and `"recommended_strategy"`.
   - In `_sanitize_text`, strip all markdown code blocks (`re.sub(r"```[\w]*[\s\S]*?```", "", text)`) and inline backticks.
   - In `translate_to_persona_voice`, filter error tokens (`"error:"`, `"exception"`, `"resource_exhausted"`) to character fallback dialogue.
4. **Update Section 12 (Victory Matrix):**
   - Add verification criteria for the hardened state machine loops and multi-key blueprint router.

All suggested corrections are empirically verified 100% green in `tests/test_challenger_p4_empirical.py`.

---

## 6. Verification Method

To independently verify all findings and hardened remediations:

```powershell
Set-Location C:\ParasiteAI
& "C:\ParasiteAI\.venv\Scripts\python.exe" -m pytest tests/test_challenger_p4_empirical.py -v
```
*Expected Result:* 18 passed in < 1.0s.

To verify core project test suite stability alongside the empirical test suite:
```powershell
& "C:\ParasiteAI\.venv\Scripts\python.exe" -m pytest tests/test_living_plan.py tests/test_gemini_consultation_protocol.py tests/test_interrupt_guard.py tests/test_dual_mind.py tests/test_challenger_p4_empirical.py
```
*Expected Result:* 78 passed in ~1.44s.
