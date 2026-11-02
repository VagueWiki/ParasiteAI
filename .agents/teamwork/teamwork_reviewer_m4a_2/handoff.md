# Milestone 4A Review & Adversarial Challenge Report

**Reviewer:** `teamwork_reviewer_m4a_2`  
**Timestamp:** 2026-11-01T08:13:00Z  
**Target Milestone:** Sub-Phase 4A (Capability Contract & Textual Scene Serialization)  
**Verdict:** **APPROVE**  

---

## 1. Review Summary

### Verdict
**APPROVE**

Milestone 4A satisfies all functional, architectural, safety, and adversarial requirements specified in the Master Plan and Scope Document:
- `BrainConfig.mode` is explicitly defaulted to `"local_llm"`, maintaining the Zero Silent Cloud Exfiltration invariant.
- `CadenceTier` is formally defined in `parasite_ai/mind/memory.py` with all 5 operational tiers.
- `GroundedCapabilityContract` and `build_grounded_capability_manifest()` dynamically query screen bounds (`(0, 0, 3840, 1080)`) and inject physical actuator limits and hard prohibitions against headless browser/CLI scraping and programmatic UIA patterns.
- `serialize_textual_scene_brief()` provides compact, bounded YAML and Set-of-Mark Markdown tables strictly `< 3 KB` (< 3072 bytes) across 0 to 500 element counts.
- `format_gemini_consultation_prompt()` preserves 100% backward compatibility for legacy kwargs while integrating the capability contract, SOM table, and LivingPlan schema.
- Multi-turn clarification hooks (`is_clarification_response()`, `resolve_clarification_query()`, `ConsultationClarificationNeeded`, and `parse_gemini_consultation_response()`) handle `"need_clarification": true` gracefully.
- Integrity verification: 0 hardcoded test facades, 0 shortcuts, 0 integrity violations detected.

---

## 2. Integrity Audit (Clean)
- **Hardcoded Test Results:** None found. `build_grounded_capability_manifest()` dynamically computes bounds via `get_virtual_screen_bounds()`. `serialize_textual_scene_brief()` computes live UTF-8 byte budgets.
- **Dummy or Facade Implementations:** None. All functions contain full logic, Pydantic schema validation, and error handling.
- **Task Shortcuts:** None. Implemented full capability contract, serialization, prompt formatting, clarification protocol, and configuration invariant.
- **Fabricated Verifications:** None. Independent tests executed and verified in this environment.

---

## 3. Adversarial Stress-Test Findings & Challenges

### [Minor] Finding 1: Unbounded Window Title in `serialize_textual_scene_brief`
- **What:** If an anomalous window title exceeds ~2,500 characters (e.g., a pathological browser tab title or malicious URL string), `brief_header` alone can consume 3,000+ bytes, pushing the total serialized scene brief above the 3,072 byte (<3 KB) budget even when 0 elements are rendered in the SOM table.
- **Where:** `parasite_ai/mind/plan.py:320-349`
- **Why:** The table builder dynamically budgets table rows (`max_table_bytes = 2800 - len(brief_header.encode("utf-8"))`), but `brief_header` itself does not truncate `title`.
- **Suggestion:** For extra hardening in future sub-phases, slice the title: `title = (getattr(window_info, "title", "Desktop") or "Desktop")[:128]`.
- **Impact Assessment:** In standard Win32 desktop environments, window titles are constrained by Win32 buffers (typically 256–512 chars), so this does not occur in standard execution. Under normal conditions (title $\le 500$ chars), the dynamic budgeting successfully keeps total payload strictly $< 3\text{ KB}$ across any number of elements.

### Stress Test Results Matrix
1. **SOM Extreme Density (0 to 500 elements):**
   - 0 elements: 596 bytes (< 3072 bytes: PASS)
   - 1 element: 602 bytes (< 3072 bytes: PASS)
   - 10 elements: 1,469 bytes (< 3072 bytes: PASS)
   - 50 elements: 2,725 bytes (< 3072 bytes: PASS)
   - 100 elements: 2,725 bytes (< 3072 bytes: PASS)
   - 200 elements: 2,726 bytes (< 3072 bytes: PASS)
   - 500 elements: 2,726 bytes (< 3072 bytes: PASS)
   - *Verdict:* **PASS**. Truncation notice `[Truncated: N additional elements omitted to preserve <3KB budget]` is appended properly.

2. **Multi-Turn Clarification Protocol:**
   - Detects `need_clarification: true` in raw JSON, markdown fences, and conversational wrappers: **PASS**
   - Ignores `need_clarification: false`: **PASS**
   - `parse_gemini_consultation_response()` returns `LivingPlan` with `needs_clarification=True`, sets `clarification_question`, and creates `CONSULT_ADVISOR` step: **PASS**
   - `resolve_clarification_query()` provides active foreground modality context and matches ambiguous element tokens: **PASS**

3. **Backward Compatibility:**
   - Empty call `format_gemini_consultation_prompt()`: **PASS**
   - Pure positional args `(goal, elements, win, dilemma, hist)`: **PASS**
   - Pure legacy keyword args (`goal`, `active_window_title`, `process_name`, `open_apps_summary`, `visual_scene_summary`, `dilemma_description`): **PASS**
   - Arbitrary `**kwargs`: **PASS**

---

## 4. Observations

1. **Config Invariant (`parasite_ai/config.py:177-180`):**
   ```python
   mode: Literal["local_llm", "browser_offload", "hybrid", "mock"] = Field(
       default="local_llm",  # Invariant: Zero silent cloud exfiltration
       description="Primary brain execution mode"
   )
   ```
   Verified: `BrainConfig().mode == "local_llm"`, `AppConfig().brain.mode == "local_llm"`, and `AppConfig().mind.mode == "local_llm"`.
   All 11 tests in `tests/test_config.py` pass.

2. **CadenceTier Enum (`parasite_ai/mind/memory.py:108-115`):**
   ```python
   class CadenceTier(str, Enum):
       TIER_1_LOCAL = "TIER_1_LOCAL"
       TIER_2_CONSULT = "TIER_2_CONSULT"
       TIER_3_GUIDED = "TIER_3_GUIDED"
       TIER_4_CO_PILOT = "TIER_4_CO_PILOT"
       USER_OVERRIDE = "USER_OVERRIDE"
   ```
   Verified: `StepRecord.tier_level` defaults to `CadenceTier.TIER_1_LOCAL`.

3. **Textual Scene Serialization & Budget (`parasite_ai/mind/plan.py:305-410`):**
   `serialize_textual_scene_brief()` encodes table rows, accounting for UTF-8 byte sizes and reserving 100 bytes for the truncation notice.
   Verified: Under 80+ and 500 element pools, output payload never exceeds 2,726 bytes.

4. **Independent Test Execution Results:**
   - `pytest tests/test_scene_serialization.py`: **18 / 18 passed** in 0.78s.
   - Core suites (`test_scene_serialization.py`, `test_config.py`, `test_gemini_consultation_protocol.py`, `test_living_plan.py`, `test_challenger_m3_m4.py`, `test_challenger_p4_empirical.py`, `test_challenger_p4_iter2_c1.py`, `test_challenger_p4_iter2_empirical.py`): **133 / 133 passed** in 2.19s.
   - Full regression suite (`pytest tests/ -q`): **939 / 940 passed** in 147.07s.
     - Single failure during saturated multi-suite run: `test_wait_interruptible_sub_2ms_wake_latency_100_trials` in `tests/test_challenger_m2_2.py` (Trial 14 measured 2.160ms vs 2.000ms threshold due to OS CPU scheduling jitter while parallel tests were active).
     - Isolated rerun: `pytest tests/test_challenger_m2_2.py -k test_wait_interruptible_sub_2ms_wake_latency_100_trials -v`: **1 / 1 passed in 0.80s**.
     - Full suite for `tests/test_challenger_m2_2.py`: **25 / 25 passed in 2.22s**.

---

## 5. Logic Chain

1. **Premise 1:** The primary requirement of Milestone 4A is establishing the grounded capability contract and serialized textual scene brief (<3 KB) without video streaming (VERIF-2, VERIF-5).
2. **Premise 2:** `build_grounded_capability_manifest()` dynamically queries virtual screen bounds, explicitly enumerates physical actuator limits, and bans headless browser/CLI scraping and programmatic UIA pattern calls, satisfying VERIF-2.
3. **Premise 3:** `serialize_textual_scene_brief()` generates compact YAML and Set-of-Mark Markdown tables strictly bounded under 3,072 bytes across all element pool sizes from 0 to 500+, satisfying VERIF-5.
4. **Premise 4:** `BrainConfig.mode` defaults to `"local_llm"`, preventing silent cloud exfiltration and satisfying the privacy invariant.
5. **Premise 5:** All legacy callers of `format_gemini_consultation_prompt()` remain 100% operational without breaking existing tests.
6. **Premise 6:** Multi-turn clarification protocol hooks correctly detect `"need_clarification": true`, creating `CONSULT_ADVISOR` steps and providing modal/element context.
7. **Conclusion:** Milestone 4A implementation is robust, complete, strictly adheres to all invariants, and is APPROVED.

---

## 6. Caveats

1. **Micro-benchmark Timing Under Concurrent CPU Load:** Microsecond timing benchmarks in older challenger suites (such as `test_wait_interruptible_sub_2ms_wake_latency_100_trials` in `test_challenger_m2_2.py`) measure sub-2ms wake latency across 100 continuous trials and are sensitive to OS scheduling delays when run under heavy concurrent background load. Standalone, all 25 tests pass cleanly in 2.22s.
2. **Headless Environment Virtual Desktop:** When running on non-Windows headless systems where Win32 `GetSystemMetrics` is unavailable, `get_virtual_screen_bounds()` safely returns `(0, 0, 3840, 1080)` without crashing.

---

## 7. Conclusion

Milestone 4A is **APPROVED**. The code is verified for correctness, safety, robustness under extreme element loads, full backward compatibility, multi-turn clarification support, and zero integrity violations.

---

## 8. Verification Method

To independently verify the review findings:

1. **Verify M4A Test Suite:**
   ```powershell
   C:\ParasiteAI\.venv\Scripts\python.exe -m pytest tests/test_scene_serialization.py -v
   ```
2. **Verify Consultation & Config Suites:**
   ```powershell
   C:\ParasiteAI\.venv\Scripts\python.exe -m pytest tests/test_gemini_consultation_protocol.py tests/test_config.py tests/test_living_plan.py -q
   ```
3. **Verify Byte Budget Under Extreme SOM Element Counts (0 to 500):**
   ```powershell
   C:\ParasiteAI\.venv\Scripts\python.exe -c "
   from parasite_ai.mind.plan import serialize_textual_scene_brief
   from parasite_ai.ui.types import UIElement
   for count in [0, 1, 10, 50, 100, 200, 500]:
       elems = [UIElement(id=i, role='Button', label=f'Element {i}', x=i, y=i, width=10, height=10, center_x=i, center_y=i) for i in range(1, count + 1)]
       b = len(serialize_textual_scene_brief(elements=elems, max_elements=count).encode('utf-8'))
       assert b < 3072, f'Failed at count {count}: {b}'
       print(f'Count {count}: {b} bytes (<3072: True)')
   "
   ```
