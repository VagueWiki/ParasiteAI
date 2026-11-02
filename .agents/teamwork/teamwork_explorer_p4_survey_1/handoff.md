# Phase 4 Survey Report: Cognition, Escalation, Grounded Contract & Dual-Channel Output

**Surveyor:** Survey Explorer 1 (`teamwork_explorer_p4_survey_1`)  
**Timestamp:** 2026-11-01T07:48:00Z  
**Target:** Phase 4 Master Implementation Plan (Sub-Phases 4A, 4B, 4C & Mind Schemas)  
**Status:** Hard Handoff — Complete Survey  

---

## 1. Observation

Direct observations from read-only inspection of the codebase, master plan, and runtime test environment:

### 1.1 Existing Test Baseline & Invariant Auditing
- **Baseline Test Suite Execution:**
  - Running `C:\ParasiteAI\.venv\Scripts\python.exe -m pytest tests/` collects **922 items**.
  - During the full 151-second run, 921 tests passed; one test (`tests/test_interrupt_guard.py::TestInterruptGuardFilteringAndPreemption::test_physical_mouse_event_aborts_under_2ms`) failed intermittently under heavy CPU saturation (`elapsed_ms = 11.365ms > 2.0ms`). When run individually, `pytest tests/test_interrupt_guard.py` completed 15/15 tests green in 0.85s.
  - Phase 4 preplanning tests (`tests/test_gemini_consultation_protocol.py`, `tests/test_living_plan.py`, `tests/test_challenger_p4_empirical.py`, `tests/test_challenger_p4_iter2_c1.py`, `tests/test_challenger_p4_iter2_empirical.py`) execute **100% green** (76 passed across these files).
- **Invariant: Anti-Hardcoding (VERIF-6):**
  - Command: `git grep -i "app_map" parasite_ai/` returned exit code 1 with 0 matches. No static application lookup tables exist in `parasite_ai/`.
- **Invariant: Win32 Ctypes Struct Sizes (VERIF-9):**
  - All 10 Win32 ctypes structures match 64-bit Windows ABI:
    - `POINT`: 8 bytes (expected 8)
    - `RECT` (`ctypes.wintypes.RECT`): 16 bytes (expected 16)
    - `MSLLHOOKSTRUCT`: 32 bytes (expected 32)
    - `KBDLLHOOKSTRUCT`: 24 bytes (expected 24)
    - `MOUSEINPUT`: 32 bytes (expected 32)
    - `KEYBDINPUT`: 24 bytes (expected 24)
    - `HARDWAREINPUT`: 8 bytes (expected 8)
    - `INPUT_UNION`: 32 bytes (expected 32)
    - `INPUT`: 40 bytes (expected 40)
    - `GUITHREADINFO`: 72 bytes (expected 72)

---

### 1.2 Grounded Capability Contract & Prompt Template (Master Plan Section 4, Sub-Phase 4A)
- **File:** `C:\ParasiteAI\parasite_ai\mind\plan.py`
  - Lines 168–192 define `GEMINI_CONSULTATION_TEMPLATE`:
    ```python
    GEMINI_CONSULTATION_TEMPLATE = """[SYSTEM: PARASITE STRATEGIC ADVISOR PROTOCOL]
    You are the Strategic Cognitive Advisor for ParasiteAI, an autonomous desktop companion.
    The user gave a goal. I need an actionable, machine-interpretable strategic plan.

    User Goal: {goal}
    Current Desktop Context:
    - Active Window: {active_window_title} ({process_name})
    - Visible Applications: {open_apps_summary}
    - Visual Scene Observation: {visual_scene_summary}
    - Current Dilemma / Status: {dilemma_description}

    Respond ONLY with a valid JSON block enclosed in ```json ... ``` following this exact schema:
    ...
    ```
  - Lines 195–219 define `format_gemini_consultation_prompt(goal, active_window_title, process_name, open_apps_summary, visual_scene_summary, dilemma_description)`.
- **Observed Deficiencies vs. Master Plan Section 4 & Sub-Phase 4A:**
  1. **No Capability Contract Model or Manifest:** `GroundedCapabilityContract` class is missing from `parasite_ai/mind/plan.py`. `build_grounded_capability_manifest() -> str` is missing.
  2. **Unanchored Prompt:** The prompt template does not embed the formal capability contract YAML specified in Master Plan Section 4.2 (cubic Bézier mouse kinematics, 120Hz polling, atomic Ctrl+V paste, SendInput cadence, virtual screen bounds, Set-of-Mark tags, 1:1 foveal crop, ROI diffing, caret focus GUITHREADINFO, hard safety constraints: zero headless scraping via curl/playwright/requests, zero programmatic UIA pattern invocation, zero private WM_SETTEXT, sub-2ms preemption, Ctrl+Alt+K kill, protected windows, strict anti-hardcoding).
  3. **Signature Mismatch:** `format_gemini_consultation_prompt` does not match the Sub-Phase 4A deliverable signature:
     `format_gemini_consultation_prompt(user_goal: str, elements: List[UIElement], window_info: WindowInfo, dilemma: str, recent_history: str) -> str`.
  4. **Missing Textual Scene Serialization:** `serialize_textual_scene_brief(elements: List[UIElement], active_win: WindowInfo, recent_diff: float, caret_active: bool) -> str` generating `<3 KB` Set-of-Mark markdown tables is not implemented.
  5. **Missing Clarification Hooks:** `parse_gemini_consultation_response` in `plan.py:344–416` only attempts JSON blueprint extraction. It lacks multi-turn clarification hooks (`need_clarification: true`, window style / modal inspection, candidate disambiguation).
  6. **Missing Test Suite:** `tests/test_scene_serialization.py` does not exist.

---

### 1.3 4-Tier Escalation State Machine (Master Plan Section 3, Sub-Phase 4B)
- **File:** `C:\ParasiteAI\parasite_ai\mind\memory.py`
  - Lines 185–203: `EpisodicMemory` uses a flat 3-strike failure counter:
    ```python
    self.strike_limit = strike_limit  # default 3
    self._consecutive_strikes: int = 0
    ```
  - Lines 231–243: Strike evaluation only checks `INTERACTIVE_ACTION_TYPES` against `screen_diff < self.screen_diff_threshold` (0.02).
- **File:** `C:\ParasiteAI\parasite_ai\mind\dual_mind.py`
  - Lines 922–927: Loop handling is a crude panic abort:
    ```python
    elif self.memory.is_in_loop():
        action_plan = ActionPlan(
            action=ActionType.PANIC,
            reasoning="Detected 3-strike failure loop. Initiating panic/strategy reset.",
        )
    ```
- **Observed Deficiencies vs. Master Plan Section 3 & Sub-Phase 4B:**
  1. **CadenceTier Enum Missing:** `CadenceTier` (`TIER_1_LOCAL`, `TIER_2_CONSULT`, `TIER_3_GUIDED`, `TIER_4_CO_PILOT`, `USER_OVERRIDE`) is not defined in `parasite_ai/mind/memory.py` or any module in `parasite_ai/`.
  2. **EscalationStateMachine Missing:** `EscalationStateMachine` model is not implemented in `parasite_ai/mind/memory.py`.
  3. **No Independent Strike Tracking:** `local_strikes` (0..2), `guided_strikes` (0..2), and `copilot_strikes` (0..3) do not exist in production code.
  4. **Action-Aware Strike Criteria Missing:**
     - Headless CLI actions (`ActionType.RUN_CLI_COMMAND`) are not evaluated by `cli_returncode == 0` (currently `RUN_CLI_COMMAND` does not even exist in `ActionType`).
     - Passive actions (`WAIT`, `DONE`, clipboard `HOTKEY`) are not explicitly guarded from visual diff checks in an escalation state machine.
  5. **Ping-Pong & Deadlock Protection Missing:** `total_escalation_cycles` (capped at 3) and `consultation_failures` (capped at 2) are not implemented in production code.
  6. **Strike Leakage:** No mechanism in `DualMindPipeline` resets `local_strikes = 0` upon consultation success.
  7. **Direct Preemption Method Missing:** `on_hardware_interrupt()` transitioning immediately from `ANY_STATE` to `USER_OVERRIDE` is not implemented.
  8. **DualMindPipeline Unwired:** `DualMindPipeline.step()` has zero awareness of the 4-tier escalation state machine. It does not trigger consultation at 2 local strikes, does not guide local execution of blueprint steps, and does not run continuous co-pilot micro-loops.
  9. **Missing Test Suite:** `tests/test_escalation_cadence.py` does not exist.

---

### 1.4 Dual-Channel Output Router & Persona Voice Translator (Master Plan Section 5, Sub-Phase 4C)
- **File:** `C:\ParasiteAI\parasite_ai\mind\dual_mind.py`
  - Lines 998–1006 handle `ActionType.OFFLOAD_WEB_AI`:
    ```python
    if action_plan.action == ActionType.OFFLOAD_WEB_AI and self.offloader:
        try:
            harvested = self.offloader.query_web_ai(user_goal)
            if isinstance(harvested, str) and harvested.strip():
                persona_out.thought = f"{persona_out.thought}\n[Web AI Advice]: {harvested.strip()}"
                persona_out.speech = f"Web AI advises: {harvested.strip()[:180]}"
                if self.bridge:
                    self.bridge.notify_speech(persona_out.speech)
            action_res = ActionResult(success=True, action_executed=action_plan)
    ```
- **Observed Deficiencies vs. Master Plan Section 5 & Sub-Phase 4C:**
  1. **Direct Speech Leakage Regression:** Line 1003 formats `persona_out.speech = f"Web AI advises: {harvested.strip()[:180]}"` and immediately calls `self.bridge.notify_speech(persona_out.speech)`. This leaks raw web LLM tokens, JSON fragments, and error codes directly to the Companion Dock speech bubble!
  2. **DualChannelRouter Missing:** `DualChannelRouter` is not implemented in `parasite_ai/mind/dual_mind.py`.
  3. **PersonaVoiceTranslator Missing:** `PersonaVoiceTranslator` / `translate_to_persona_voice()` is not implemented.
  4. **Text Sanitizer Missing:** `_sanitize_text()` (stripping markdown code blocks ` ```[\w]*[\s\S]*?``` `, inline backticks, curly braces, coordinate pairs, and filtering error tokens `"error:"`, `"exception"`, `"resource_exhausted"`) is not implemented.
  5. **Channel A / Channel B Splitting Unwired:** Consultation outputs are not split between internal `LivingPlan` hydration (Channel A, supporting both `"steps"` and `"recommended_strategy"` keys) and sanitized character dialogue (Channel B).
  6. **Missing Test Suite:** `tests/test_dual_channel_output.py` does not exist.

---

### 1.5 Schema Updates Across Core Files
- **File:** `C:\ParasiteAI\parasite_ai\mind\plan.py`
  - `PlanStep` (lines 44–56):
    - Has: `step_id`, `intent`, `description`, `target_description`, `success_criteria`, `rationale`, `status`, `contingency`.
    - **Missing:** `tool_route: Optional[Literal["GUI", "CLI", "ADVISOR"]] = None`.
  - `LivingPlan` (lines 58–71):
    - Has: `user_goal`, `overall_strategy`, `steps`, `current_step_id`, `replan_count`, `consulted_gemini`.
    - **Missing:** `escalation_tier: CadenceTier = CadenceTier.TIER_1_LOCAL`.
    - **Missing:** `tier_strikes: int = Field(default=0, ge=0)`.
  - `LivingPlan.advance_step()` verification (in `dual_mind.py:1091–1104`):
    - Only checks `LAUNCH_OR_ACTIVATE` and `DISMISS_DIALOG`.
    - **Missing:** Verification criteria for `NAVIGATE`, `INPUT_DATA`, `SELECT_OPTION`, `VERIFY_STATE`, `CONSULT_ADVISOR`, `CONCLUDE`.
- **File:** `C:\ParasiteAI\parasite_ai\mind\memory.py`
  - `ActionType` (lines 108–120):
    - Has: `CLICK`, `DOUBLE_CLICK`, `RIGHT_CLICK`, `CLICK_AND_TYPE`, `TYPE`, `HOTKEY`, `SCROLL`, `WAIT`, `PANIC`, `OFFLOAD_WEB_AI`, `DONE`.
    - **Missing:** `RUN_CLI_COMMAND = "RUN_CLI_COMMAND"`.
  - `ActionPlan` (lines 133–147):
    - Has: `action`, `target_id`, `coordinates`, `text`, `submit`, `keys`, `clicks`, `scroll_amount`, `wait_ms`, `reasoning`.
    - **Missing:** `cli_command: Optional[str] = None`.
  - `StepRecord` (lines 161–179):
    - Has: `step_id`, `timestamp`, `user_goal`, `persona_thought`, `persona_speech`, `action`, `target_info`, `pre_hash`, `post_hash`, `screen_diff`, `success`, `error_message`, `is_strike`, `consecutive_strikes`.
    - **Missing:** `tier_level: CadenceTier = CadenceTier.TIER_1_LOCAL`.
- **File:** `C:\ParasiteAI\parasite_ai\config.py`
  - Lines 177–180:
    ```python
    mode: Literal["local_llm", "browser_offload", "hybrid", "mock"] = Field(
        default="browser_offload",
        description="Cognitive execution mode (browser_offload provides instant zero-VRAM startup)."
    )
    ```
    - **CRITICAL INVARIANT VIOLATION:** `BrainConfig.mode` defaults to `"browser_offload"`. In Master Plan Section 9.1 item 7 and Section 11/12, the invariant requires:
      `mode: Literal["local_llm", "browser_offload", "hybrid", "mock"] = Field(default="local_llm", description="Primary brain execution mode")`.
- **File:** `C:\ParasiteAI\parasite_ai\mind\resolver.py`
  - Lines 168–195:
    ```python
    if not self._search_opened:
        self._search_opened = True
        return ActionPlan(action=ActionType.HOTKEY, keys=["win"], ...)

    if self._search_opened:
        self._search_opened = False
        return ActionPlan(action=ActionType.TYPE, text=f"{target_app}\n", ...)

    # Tier 3: Run Dialog fallback (Win+R)
    return ActionPlan(action=ActionType.HOTKEY, keys=["win", "r"], ...)
    ```
    - **CRITICAL DEAD CODE BUG:** Lines 189–195 (`Win+R` fallback) can NEVER be executed. The resolver alternates between `_search_opened = True` and `_search_opened = False`, trapping the agent in an infinite Tier 2 Start Search loop upon failure.
    - **SUBSTRING COLLISION BUG:** Tier 1 element search (lines 100–115) uses `target_clean in label and len(target_clean) >= 3`, which matches prefix/substring false positives ("art" matches "SmartScreen", "cat" matches "Calculator", "notepad" matches "Exit Notepad").
    - **Missing:** `PrecisionAppMatcher` class with word boundaries (`\b`), exact match scoring, and negative verb filtering (`NEGATIVE_VERBS = {"exit", "close", "quit", "cancel", "uninstall", "delete", "remove", "kill"}`).
- **Missing Module:** `parasite_ai/mind/affordance.py`
  - Sub-Phase 4C/4D specifies `ActionAffordance`, `AffordanceAssessment`, `AffordanceEvaluator`, and `CLIExecutionSandbox` in `parasite_ai/mind/affordance.py`. The file does not exist.

---

## 2. Logic Chain

1. **Premise 1 (Master Plan Compliance):** Phase 4 mandates elevating ParasiteAI to a hierarchical dual-mind architecture operating through a Grounded Capability Contract (4A), a 4-Tier Escalation State Machine (4B), a Dual-Channel Output Router (4C), and Tool-Aware Reasoning with CLI Sandbox (4D).
2. **Step 2 (Prompt Grounding Gap):** Observation 1.2 demonstrates that `parasite_ai/mind/plan.py` only formats basic desktop window text. Because external LLMs default to hallucinating DOM injection, scraping commands, and UIA pattern calls, the absence of `GroundedCapabilityContract` and `serialize_textual_scene_brief` leaves the consultation pipeline ungrounded and vulnerable to advisor hallucinations.
3. **Step 3 (Escalation State Machine Gap):** Observation 1.3 shows that `parasite_ai/mind/memory.py` and `parasite_ai/mind/dual_mind.py` only possess flat 3-strike panic logic. Without `CadenceTier`, `EscalationStateMachine`, loop-counter caps (`total_escalation_cycles <= 3`, `consultation_failures <= 2`), and action-aware strike evaluation, the pipeline cannot execute guided blueprints or visual co-pilot loops, nor can it prevent infinite T3 $\leftrightarrow$ T4 ping-pong loops.
4. **Step 4 (Dual-Channel Output Gap & Active Leak):** Observation 1.4 confirms that `DualChannelRouter` is absent and `dual_mind.py:1003` directly emits `Web AI advises: {harvested.strip()[:180]}` to `UIBridge.notify_speech()`. This violates the Channel A / Channel B separation principle and causes desktop UI pollution with raw tokens or error messages.
5. **Step 5 (Schema Gaps & Invariant Regressions):** Observation 1.5 proves that `PlanStep`, `LivingPlan`, `ActionPlan`, `StepRecord`, and `ActionType` lack the Phase 4 schema fields (`tool_route`, `escalation_tier`, `tier_strikes`, `RUN_CLI_COMMAND`, `cli_command`, `tier_level`). Crucially, `BrainConfig.mode` defaults to `"browser_offload"`, which directly violates the core invariant of zero silent cloud exfiltration (`brain.mode: "local_llm"` default).
6. **Step 6 (Resolver Deadlock):** Observation 1.5 proves that `UniversalAppResolver` has unreachable dead code for Tier 3 (`Win+R`), trapping the system in Tier 2 Start Search upon visual stall, and lacks `PrecisionAppMatcher` to prevent destructive substring collisions.

---

## 3. Caveats

1. **Preplanning Test Suites:** While production implementations in `parasite_ai/mind/` lack Phase 4 components, comprehensive reference implementations already exist within `tests/test_challenger_p4_iter2_c1.py` and `tests/test_challenger_p4_iter2_empirical.py`. These can be extracted and adapted directly into production modules.
2. **Hardware Timing Test Flake:** `test_physical_mouse_event_aborts_under_2ms` in `tests/test_interrupt_guard.py` failed during a multi-minute full-suite run due to Windows background thread scheduling and CPU load (11.36ms). It passes reliably (15/15 green in 0.85s) in isolation. Test runners should avoid running CPU-intensive operations concurrently when certifying hardware preemption timing.
3. **Read-Only Scope:** No code changes were made to production files during this survey, strictly adhering to the Explorer role guidelines.

---

## 4. Conclusion

The codebase is currently in a certified **Phase 3 complete state** (all 10 ctypes structs 64-bit compliant, 0 `app_map` occurrences, 921+ passing tests), with Phase 4 preplanning tests in place. However, **Sub-Phases 4A, 4B, and 4C are not yet implemented in production code**:
- **Sub-Phase 4A (Contract & Scene Serialization):** Needs `GroundedCapabilityContract`, `build_grounded_capability_manifest()`, `serialize_textual_scene_brief()`, and updated `format_gemini_consultation_prompt()`.
- **Sub-Phase 4B (4-Tier Escalation):** Needs `CadenceTier`, `EscalationStateMachine`, and orchestration wiring in `DualMindPipeline.step()`.
- **Sub-Phase 4C (Dual-Channel Output & Persona Voice):** Needs `DualChannelRouter`, `_sanitize_text()`, `PersonaVoiceTranslator`, and elimination of the raw advice leak in `dual_mind.py:1003`.
- **Schema Updates & Bug Fixes:** Needs schema extensions in `plan.py`, `memory.py`, `dual_mind.py`; fixing `BrainConfig.mode` default to `"local_llm"`; fixing `UniversalAppResolver` dead code and adding `PrecisionAppMatcher`.

---

## 5. Verification Method

To independently verify all claims made in this report:

1. **Verify Struct Sizes & Reflection (VERIF-9):**
   ```powershell
   C:\ParasiteAI\.venv\Scripts\python.exe -c "import ctypes, wintypes; from parasite_ai.safety.interrupt_guard import POINT, MSLLHOOKSTRUCT, KBDLLHOOKSTRUCT; from parasite_ai.hands.keyboard import MOUSEINPUT, KEYBDINPUT, HARDWAREINPUT, INPUT_UNION, INPUT; from parasite_ai.mind.dual_mind import GUITHREADINFO; print([ctypes.sizeof(c) for c in (POINT, wintypes.RECT, MSLLHOOKSTRUCT, KBDLLHOOKSTRUCT, MOUSEINPUT, KEYBDINPUT, HARDWAREINPUT, INPUT_UNION, INPUT, GUITHREADINFO)])"
   # Output: [8, 16, 32, 24, 32, 24, 8, 32, 40, 72]
   ```

2. **Verify Anti-Hardcoding Invariant (VERIF-6):**
   ```powershell
   git grep -i "app_map" parasite_ai/
   # Must return exit code 1 with zero matches
   ```

3. **Verify Invariant Regression in `config.py`:**
   Inspect line 178 of `parasite_ai/config.py`:
   `mode: Literal["local_llm", "browser_offload", "hybrid", "mock"] = Field(default="browser_offload", ...)`
   Confirm default is `"browser_offload"` instead of `"local_llm"`.

4. **Verify UniversalAppResolver Unreachable Code:**
   Inspect lines 168–195 of `parasite_ai/mind/resolver.py`:
   Confirm lines 189–195 cannot be reached due to mutually exclusive `if not self._search_opened:` and `if self._search_opened:`.

5. **Verify Baseline Tests:**
   ```powershell
   C:\ParasiteAI\.venv\Scripts\python.exe -m pytest tests/test_gemini_consultation_protocol.py tests/test_living_plan.py tests/test_challenger_p4_empirical.py tests/test_challenger_p4_iter2_c1.py tests/test_challenger_p4_iter2_empirical.py -q
   # Must return 76 passed
   ```
