# Phase 4 Codebase Survey Report: Tool-Aware Reasoning, CLI Sandbox, Textual Scene Serialization & Schemas

**Author:** Survey Explorer 2 (`teamwork_explorer_p4_survey_2`)  
**Target Milestone:** Phase 4 Implementation Preparation  
**Reference Document:** `c:\Users\Suici\.gemini\antigravity\brain\464b4ef0-398b-45b1-94dc-857256a38046\phase_4_master_plan.md`  
**Working Directory:** `C:\ParasiteAI\.agents\teamwork\teamwork_explorer_p4_survey_2\`  
**Timestamp:** 2026-11-01T07:48:00Z  

---

## 1. Observation

A forensic, read-only inspection was performed across `parasite_ai/` and `tests/` targeting the requirements of Phase 4 Master Plan Sections 6, 6.4, 7, 9, 10, and 12.

### 1.1 Tool-Aware Strategic Reasoning & Affordance Evaluator (Master Plan Section 6, Sub-Phase 4D)
* **Target Module:** `parasite_ai/mind/affordance.py`
  * **Observed State:** File does **NOT** exist (`find_by_name(Pattern="*affordance*")` returned 0 results).
* **Target Classes & Enums:**
  * `ActionAffordance`: Completely absent from `parasite_ai/` and `tests/` (`grep_search` returned 0 matches).
  * `AffordanceAssessment`: Completely absent from `parasite_ai/` and `tests/`.
  * `AffordanceEvaluator`: Completely absent from `parasite_ai/` and `tests/`.
* **Pipeline Integration:**
  * In `parasite_ai/mind/dual_mind.py` lines 808–947 (`DualMindPipeline.step()`), no affordance evaluation occurs prior to Pass 2 action planning. All goals are treated generically as physical GUI manipulation or unrequested browser offload.
* **Test Suite Status:**
  * `tests/test_tool_aware_reasoning.py` (required by Master Plan Section 10 & Section 12 VERIF-4) does **NOT** exist.

### 1.2 CLI Execution Sandbox & Security Model (Master Plan Section 6.4, Sub-Phase 4D)
* **Production Module:** `CLIExecutionSandbox` is **NOT** implemented in `parasite_ai/`.
* **Test Mock Existence vs. Production Gap:**
  * A mock prototype class `MasterPlanCLIExecutionSandbox` exists only in `tests/test_challenger_p4_iter2_empirical.py` (lines 153–220). No production code exists in `parasite_ai/`.
* **Security Filter Discrepancy & Missing Scrapers:**
  * In `tests/test_challenger_p4_iter2_empirical.py:165-179`, `FORBIDDEN_PATTERNS` contains:
    ```python
    FORBIDDEN_PATTERNS: List[str] = [
        r"\bcurl\b", r"\bwget\b", r"\bplaywright\b", r"\bpuppeteer\b",
        r"\bselenium\b", r"\bscrapy\b", r"\bformat\b", r"\brmdir\s+/[sq]\b",
        r"\bdel\s+/[sqf]\b", r"\bdiskpart\b", r"\breg\s+delete\b",
        r"\bshutdown\b", r"\bstop-computer\b",
    ]
    ```
  * In `phase_4_master_plan.md` lines 740–756 (Section 6.4), the certified specification requires:
    ```python
    FORBIDDEN_PATTERNS: List[str] = [
        r"\bcurl\b", r"\bwget\b", r"\bplaywright\b", r"\bpuppeteer\b",
        r"\bselenium\b", r"\bscrapy\b", r"\bformat\b", r"\brmdir\s+/[sq]\b",
        r"\bdel\s+/[sqf]\b", r"\bdiskpart\b", r"\breg\s+delete\b",
        r"\bshutdown\b", r"\bstop-computer\b",
        r"\b(?:Invoke-WebRequest|iwr|Invoke-RestMethod|irm)\b",
        r"\brequests\b",
    ]
    ```
  * **Critical Gap:** The test mock omitted `r"\b(?:Invoke-WebRequest|iwr|Invoke-RestMethod|irm)\b"` and `r"\brequests\b"`. The production implementation must include both to satisfy the Grounded Capability Contract invariant forbidding headless scraping.
* **Preemption & Hardware Interruption:**
  * The Master Plan specifies a non-blocking 10ms polling loop (`time.sleep(0.010)`) checking `cancellation_token.is_set()`. Upon human hardware touch, `proc.kill()` and `taskkill /F /T /PID proc.pid` must terminate the subprocess tree in $< 20\text{ ms}$, returning `CLIExecutionResult(preempted=True, exit_code=-1)`. This is not implemented in production.
* **Action Dispatcher Integration:**
  * In `parasite_ai/mind/dual_mind.py` lines 453–677 (`ActionDispatcher.dispatch()`), there is zero handling for `ActionType.RUN_CLI_COMMAND`.
* **Strike Evaluation Integration:**
  * In `parasite_ai/mind/memory.py` lines 231–243 (`EpisodicMemory.record_step()`), strike evaluation is purely visual diff based (`screen_diff < self.screen_diff_threshold`). Headless CLI commands produce $\Delta = 0.000$; without action-aware strike evaluation (`returncode == 0` bypasses visual diff), CLI executions incur false strikes.
* **Test Suite Status:**
  * `tests/test_cli_sandbox.py` (required by Master Plan Section 10 & Section 12 VERIF-10) does **NOT** exist.

### 1.3 Textual Scene Serialization (Master Plan Section 7, Sub-Phase 4A/4D)
* **Target Function:** `serialize_textual_scene_brief`
  * **Observed State:** Completely absent from `parasite_ai/vision/grounding.py` and `parasite_ai/mind/plan.py` (`grep_search` returned 0 matches across the workspace).
* **SOM Table Formatting:**
  * `ScreenGrounder` in `parasite_ai/vision/grounding.py` generates `List[UIElement]`, but has no function to format the Markdown Set-of-Mark summary table (`| ID | Control Type | Label / Accessible Name | Bounding Box [x, y, w, h] | Center (x, y) | Source | Flags |`).
* **Active Window Brief:**
  * No serializer exists for the YAML `Active_Window_Brief` schema specified in Section 7.3 (`Title`, `Process_Name`, `HWND`, `Bounds`, `Monitor`, `Caret_Status`, `Recent_Diff_Ratio`, `Recent_dHash`, `Consecutive_Strikes`, `Active_Tier`).
* **Consultation Prompt Status:**
  * In `parasite_ai/mind/plan.py` lines 168–219, `GEMINI_CONSULTATION_TEMPLATE` and `format_gemini_consultation_prompt` are legacy Phase 3 implementations:
    - Signature: `format_gemini_consultation_prompt(goal, active_window_title, process_name, open_apps_summary, visual_scene_summary, dilemma_description)`
    - Does **NOT** accept `elements: List[UIElement]` or format the markdown SOM table.
    - Does **NOT** accept `window_info: WindowInfo`.
    - Does **NOT** embed the Grounded Capability Contract or the actuator/perception limits.
* **Capability Contract Manifest:**
  * `GroundedCapabilityContract` model and `build_grounded_capability_manifest()` function (Master Plan Section 10 Sub-Phase 4A) do **NOT** exist in `parasite_ai/mind/plan.py`.
* **Test Suite Status:**
  * `tests/test_scene_serialization.py` (required by Master Plan Section 10 & Section 12 VERIF-5) does **NOT** exist.

### 1.4 Schema Inventory & Delta Analysis
1. `ActionAffordance`: **MISSING** in `parasite_ai/mind/affordance.py`. (Values: `PHYSICAL_GUI`, `LOCAL_DEVELOPER_TOOL`, `STRATEGIC_ADVISOR`).
2. `AffordanceAssessment`: **MISSING** in `parasite_ai/mind/affordance.py`. (Fields: `affordance`, `confidence`, `justification`, `suggested_command`).
3. `AffordanceEvaluator`: **MISSING** in `parasite_ai/mind/affordance.py`. (Method: `evaluate(goal, active_window_title)`).
4. `CLIExecutionResult`: **MISSING** in `parasite_ai/mind/affordance.py`. (Fields: `command`, `exit_code`, `stdout`, `stderr`, `duration_ms`, `timed_out`, `preempted`).
5. `CLIExecutionSandbox`: **MISSING** in `parasite_ai/mind/affordance.py`. (Methods: `sanitize_and_tokenize`, `execute`).
6. `ActionType.RUN_CLI_COMMAND`: **MISSING** in `parasite_ai/mind/memory.py:108-120`. Currently ends at `DONE = "DONE"`.
7. `ActionPlan.cli_command`: **MISSING** in `parasite_ai/mind/memory.py:133-147`. Currently has no `cli_command: Optional[str] = None`.
8. `PlanStep.tool_route`: **MISSING** in `parasite_ai/mind/plan.py:44-56`. Currently has no `tool_route: Optional[Literal["GUI", "CLI", "ADVISOR"]] = None`.
9. `CadenceTier` & `EscalationStateMachine`: **MISSING** in `parasite_ai/mind/memory.py`.
10. `LivingPlan.escalation_tier` & `LivingPlan.tier_strikes`: **MISSING** in `parasite_ai/mind/plan.py:58-70`.
11. `StepRecord.tier_level`: **MISSING** in `parasite_ai/mind/memory.py:161-179`.
12. `BrainConfig.mode` Default Invariant Regression:
    * In `parasite_ai/config.py` line 178:
      ```python
      mode: Literal["local_llm", "browser_offload", "hybrid", "mock"] = Field(
          default="browser_offload",  # VIOLATION: Must default to "local_llm"
          description="..."
      )
      ```
    * Defaulting to `"browser_offload"` violates the Core Invariant (Zero Silent Cloud Exfiltration) and VERIF-8. In `config.yaml` it is set to `"local_llm"`, but programmatic instantiation of `BrainConfig()` defaults to `"browser_offload"`.
13. `UniversalAppResolver` Collisions & Reachability:
    * In `parasite_ai/mind/resolver.py` line 106:
      ```python
      is_match = (label == target_clean) or (target_clean in label and len(target_clean) >= 3)
      ```
      Naive substring matching causes collisions ("art" matches "SmartScreen", "cat" matches "Certificate Manager", "notepad" matches "Exit Notepad").
    * In `parasite_ai/mind/resolver.py` lines 168–195: Tier 3 (`Win+R`) is unreachable because `if not self._search_opened` and `if self._search_opened` cover all cases, preventing progression to Tier 3.
    * `PrecisionAppMatcher` is completely missing from `parasite_ai/mind/resolver.py`.

---

## 2. Logic Chain

```
[Observation 1.1: affordance.py missing; ActionAffordance / AffordanceEvaluator absent]
        │
        ▼
[Deduction: Tool-Aware Reasoning is 0% implemented in production codebase]
        │
        ▼
[Observation 1.2: CLIExecutionSandbox only in tests/test_challenger_p4_iter2_empirical.py;
 missing requests & Invoke-WebRequest in forbidden patterns; ActionDispatcher lacks RUN_CLI_COMMAND]
        │
        ▼
[Deduction: CLI Sandbox is a test-only prototype with security pattern gaps; production lacks execution & dispatcher plumbing]
        │
        ▼
[Observation 1.3: serialize_textual_scene_brief missing; GEMINI_CONSULTATION_TEMPLATE lacks contract & SOM]
        │
        ▼
[Deduction: Textual Scene Serialization is 0% implemented; consultations still use legacy Phase 3 format]
        │
        ▼
[Observation 1.4: ActionType, ActionPlan, PlanStep, LivingPlan lack Phase 4 schema fields;
 BrainConfig.mode defaults to browser_offload; UniversalAppResolver has substring collisions]
        │
        ▼
[Conclusion: Phase 4 core features require complete production implementation across affordance.py,
 memory.py, plan.py, grounding.py, dual_mind.py, resolver.py, and config.py]
```

### Step-by-Step Inference:
1. **Tool-Aware Reasoning (Sub-Phase 4D):** Because `parasite_ai/mind/affordance.py` does not exist, the cognitive loop has no heuristic to differentiate between tasks that should be performed via physical GUI interaction vs. deterministic CLI tools vs. strategic advisor consultation.
2. **CLI Sandbox (Sub-Phase 4D):** Although `MasterPlanCLIExecutionSandbox` was tested in `test_challenger_p4_iter2_empirical.py`, it was never moved to `parasite_ai/`. Furthermore, the forbidden pattern list in that test file omitted `requests` and PowerShell web request commands, meaning the prototype was less strict than the finalized Master Plan specification (lines 754–755).
3. **Textual Scene Serialization (Sub-Phase 4A/4D):** Without `serialize_textual_scene_brief`, Gemini consultations cannot receive structured Set-of-Mark tables or active window telemetry briefs. The existing `format_gemini_consultation_prompt` sends loose string descriptions without actuator constraints.
4. **Action Dispatch & Feedback Loop:** Because `ActionType.RUN_CLI_COMMAND` is missing from `ActionType` and `ActionPlan.cli_command` is missing from `ActionPlan`, `ActionDispatcher.dispatch()` cannot invoke CLI execution. Because `EpisodicMemory` only evaluates interactive visual diffs ($\Delta \ge 0.02$), a successful CLI command ($\Delta = 0.000$) would trigger an erroneous strike unless action-aware strike evaluation is added.
5. **Core Invariant Maintenance:** `BrainConfig.mode` defaulting to `"browser_offload"` in `parasite_ai/config.py` constitutes an invariant defect that must be corrected to `"local_llm"` to prevent silent exfiltration.

---

## 3. Caveats

1. **Read-Only Scope:** This survey was conducted in strict read-only mode. No production files were created or modified.
2. **Challenger Test Independence:** The existing 37 passing tests in `tests/test_challenger_p4_iter2_empirical.py` and `tests/test_challenger_p4_empirical.py` pass because they instantiate *test-internal reference implementations* defined directly within those test files. They do **not** indicate that production code in `parasite_ai/` is implemented.
3. **Sub-Phase Grouping:** Textual Scene Serialization spans Sub-Phase 4A (consultation prompt & contract) and Sub-Phase 4D (tool routing integration). The serialization logic itself belongs in `parasite_ai/vision/grounding.py` or `parasite_ai/mind/plan.py`.
4. **Environment Execution Note:** Tests must be executed using Python 3.12 at `C:\ParasiteAI\.venv\Scripts\python.exe`. The global Python at `C:\Users\Suici\AppData\Local\Programs\Python\Python38\python.exe` is Python 3.8 and lacks dependencies (`pydantic`, `numpy`, `PyQt6`).

---

## 4. Conclusion

### Component Status Summary

| Item / Deliverable | Master Plan Reference | Current State | Required Work |
| :--- | :--- | :--- | :--- |
| **`parasite_ai/mind/affordance.py`** | Section 6, 6.4, 10 (4D) | **MISSING** | Create new module containing `ActionAffordance`, `AffordanceAssessment`, `AffordanceEvaluator`, `CLIExecutionResult`, `CLIExecutionSandbox`. |
| **`ActionAffordance`** | Section 6.3, 9.1 | **MISSING** | Define enum with `PHYSICAL_GUI`, `LOCAL_DEVELOPER_TOOL`, `STRATEGIC_ADVISOR`. |
| **`AffordanceAssessment`** | Section 6.3, 9.1 | **MISSING** | Define Pydantic model (`affordance`, `confidence`, `justification`, `suggested_command`). |
| **`AffordanceEvaluator`** | Section 6.3, 10 (4D) | **MISSING** | Implement 3-priority-rule classifier (Canvas -> GUI, App Launch -> GUI, Code/Tests -> CLI, Default -> GUI). |
| **`CLIExecutionSandbox`** | Section 6.4, 10 (4D) | **MISSING (in production)** | Implement whitelist, forbidden regexes (including `requests` and `Invoke-WebRequest`), 30s timeout, and 10ms cancellation token preemption with `taskkill /F /T /PID`. |
| **`ActionType.RUN_CLI_COMMAND`** | Section 9.1, 10 (4D) | **MISSING** | Add enum value to `parasite_ai/mind/memory.py:ActionType`. |
| **`ActionPlan.cli_command`** | Section 9.1, 10 (4D) | **MISSING** | Add `cli_command: Optional[str] = None` to `parasite_ai/mind/memory.py:ActionPlan`. |
| **`PlanStep.tool_route`** | Section 9.1, 10 (4D) | **MISSING** | Add `tool_route: Optional[Literal["GUI", "CLI", "ADVISOR"]] = None` to `parasite_ai/mind/plan.py:PlanStep`. |
| **`serialize_textual_scene_brief`** | Section 7.2, 7.3, 10 (4A) | **MISSING** | Implement in `parasite_ai/vision/grounding.py` or `parasite_ai/mind/plan.py` generating $< 3\text{ KB}$ SOM Markdown table + YAML active window brief. |
| **`GroundedCapabilityContract` & Manifest** | Section 4.2, 10 (4A) | **MISSING** | Implement `build_grounded_capability_manifest()` in `parasite_ai/mind/plan.py`. |
| **Consultation Prompt Modernization** | Section 4.4, 10 (4A) | **OUTDATED** | Update `GEMINI_CONSULTATION_TEMPLATE` and `format_gemini_consultation_prompt` to accept `List[UIElement]`, `WindowInfo`, and embed capability manifest. |
| **ActionDispatcher CLI Execution** | Section 6.4, 10 (4D) | **MISSING** | Add `ActionType.RUN_CLI_COMMAND` dispatch branch invoking `CLIExecutionSandbox.execute()`. |
| **Action-Aware Strike Evaluation** | Section 3.1, 10 (4B) | **MISSING** | Update `EpisodicMemory.record_step()` to bypass visual diff when `action == RUN_CLI_COMMAND` and evaluate based on `returncode == 0`. |
| **`BrainConfig.mode` Default** | Section 9.1, 11, VERIF-8 | **DEFECT (browser_offload)** | Update `parasite_ai/config.py:178` default from `"browser_offload"` to `"local_llm"`. |
| **`UniversalAppResolver` & Precision Matching** | Section 8.2, 8.3, 10 (4E) | **DEFECT (Collisions, Unreachable T3)** | Replace naive substring match with `PrecisionAppMatcher`; implement `_start_search_attempts` and `_run_dialog_attempts` tracking. |

### Concrete Implementation Steps for Workers:
1. **Module Creation:** Create `parasite_ai/mind/affordance.py` implementing `ActionAffordance`, `AffordanceAssessment`, `AffordanceEvaluator`, `CLIExecutionResult`, and `CLIExecutionSandbox`. Ensure forbidden regexes include `requests` and `Invoke-WebRequest|iwr|Invoke-RestMethod|irm`.
2. **Schema Extensions:**
   - In `parasite_ai/mind/memory.py`: Add `RUN_CLI_COMMAND` to `ActionType`; add `cli_command: Optional[str] = None` to `ActionPlan`; add `CadenceTier` and `EscalationStateMachine`.
   - In `parasite_ai/mind/plan.py`: Add `tool_route: Optional[Literal["GUI", "CLI", "ADVISOR"]] = None` to `PlanStep`; add `escalation_tier` and `tier_strikes` to `LivingPlan`.
3. **Textual Scene Serialization:**
   - In `parasite_ai/vision/grounding.py` or `parasite_ai/mind/plan.py`: Implement `serialize_textual_scene_brief()`.
   - In `parasite_ai/mind/plan.py`: Update `format_gemini_consultation_prompt()` and embed `build_grounded_capability_manifest()`.
4. **Execution & Dispatch Plumbing:**
   - In `parasite_ai/mind/dual_mind.py`: Wire `AffordanceEvaluator` in `DualMindPipeline.step()`; wire `CLIExecutionSandbox.execute()` in `ActionDispatcher.dispatch()`.
   - In `parasite_ai/mind/memory.py`: Add action-aware strike evaluation in `EpisodicMemory.record_step()` for CLI actions.
5. **Invariant Correction:**
   - In `parasite_ai/config.py`: Change `BrainConfig.mode` default to `"local_llm"`.
6. **New Test Suites:**
   - Create `tests/test_tool_aware_reasoning.py` (VERIF-4).
   - Create `tests/test_cli_sandbox.py` (VERIF-10).
   - Create `tests/test_scene_serialization.py` (VERIF-5).

---

## 5. Verification Method

To independently reproduce and verify every finding in this report:

### Step 1: Verify Missing Production Modules and Schemas
Run the following Python one-liner to verify that `affordance.py` and the required schema fields are missing:
```powershell
& "C:\ParasiteAI\.venv\Scripts\python.exe" -c "
try:
    import parasite_ai.mind.affordance as aff
    print('affordance.py exists: YES')
except ImportError as e:
    print('affordance.py exists: NO (', e, ')')

from parasite_ai.mind.memory import ActionType, ActionPlan
print('ActionType.RUN_CLI_COMMAND exists:', hasattr(ActionType, 'RUN_CLI_COMMAND'))
plan = ActionPlan()
print('ActionPlan.cli_command exists:', hasattr(plan, 'cli_command'))

from parasite_ai.mind.plan import PlanStep
step = PlanStep(step_id=1, intent='NAVIGATE', description='test', success_criteria='test')
print('PlanStep.tool_route exists:', hasattr(step, 'tool_route'))

from parasite_ai.config import BrainConfig
bc = BrainConfig()
print('BrainConfig.mode default:', bc.mode, '(MUST be local_llm, currently:', bc.mode, ')')
"
```
**Expected Output on Current Codebase:**
- `affordance.py exists: NO ( No module named 'parasite_ai.mind.affordance' )`
- `ActionType.RUN_CLI_COMMAND exists: False`
- `ActionPlan.cli_command exists: False`
- `PlanStep.tool_route exists: False`
- `BrainConfig.mode default: browser_offload (MUST be local_llm, currently: browser_offload)`

### Step 2: Verify Absence of Textual Scene Serialization
```powershell
& "C:\ParasiteAI\.venv\Scripts\python.exe" -c "
try:
    from parasite_ai.vision.grounding import serialize_textual_scene_brief
    print('serialize_textual_scene_brief in grounding: YES')
except ImportError:
    print('serialize_textual_scene_brief in grounding: NO')

try:
    from parasite_ai.mind.plan import serialize_textual_scene_brief
    print('serialize_textual_scene_brief in plan: YES')
except ImportError:
    print('serialize_textual_scene_brief in plan: NO')
"
```
**Expected Output:** Both report `NO`.

### Step 3: Verify Test Mock vs Production Isolation
Inspect lines 153–220 of `C:\ParasiteAI\tests\test_challenger_p4_iter2_empirical.py` to confirm that `MasterPlanCLIExecutionSandbox` is defined locally inside the test file and not imported from `parasite_ai/mind/affordance`.
Notice line 179: `requests` and `Invoke-WebRequest` are missing from `FORBIDDEN_PATTERNS`.

### Step 4: Post-Implementation Invalidation Condition
This survey report will be invalidated when:
1. `parasite_ai/mind/affordance.py` exists and exports `ActionAffordance`, `AffordanceAssessment`, `AffordanceEvaluator`, `CLIExecutionResult`, and `CLIExecutionSandbox`.
2. `ActionType.RUN_CLI_COMMAND`, `ActionPlan.cli_command`, and `PlanStep.tool_route` exist and serialize cleanly under Pydantic v2.
3. `BrainConfig.mode` defaults to `"local_llm"`.
4. `serialize_textual_scene_brief` produces valid Markdown SOM tables and Active Window Briefs under $< 3\text{ KB}$.
5. `pytest tests/test_tool_aware_reasoning.py tests/test_cli_sandbox.py tests/test_scene_serialization.py` executes 100% green.
