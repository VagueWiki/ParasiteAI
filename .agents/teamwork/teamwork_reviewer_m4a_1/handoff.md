# Milestone 4A Review & Adversarial Challenge Report

**Reviewer:** `teamwork_reviewer_m4a_1` (Roles: reviewer, critic)  
**Milestone:** 4A — Capability Contract & Textual Scene Serialization  
**Timestamp:** 2026-11-01T08:12:30Z  
**Verdict:** **APPROVE**  
**Integrity Audit:** PASS (Zero integrity violations, zero facades, zero hardcoded test bypasses)

---

## 1. Observation

Direct forensic observations from codebase inspection, git diff analysis, and independent test runs:

1. **`BrainConfig.mode` Default Invariant (`parasite_ai/config.py:177-180`):**
   ```python
   mode: Literal["local_llm", "browser_offload", "hybrid", "mock"] = Field(
       default="local_llm",  # Invariant: Zero silent cloud exfiltration
       description="Primary brain execution mode"
   )
   ```
   - Instantiation check:
     - `BrainConfig().mode == "local_llm"`
     - `AppConfig().brain.mode == "local_llm"`
     - `AppConfig().mind.mode == "local_llm"`
   - `tests/test_config.py` lines 33-34, 82, 126, 187 properly updated to assert `"local_llm"`.
   - Verified via `pytest tests/test_config.py`: 11 / 11 tests passed.

2. **`CadenceTier` Enum & StepRecord (`parasite_ai/mind/memory.py:108-115, 188`):**
   ```python
   class CadenceTier(str, Enum):
       """Hierarchical escalation cadence tiers for cognitive execution."""
       TIER_1_LOCAL = "TIER_1_LOCAL"
       TIER_2_CONSULT = "TIER_2_CONSULT"
       TIER_3_GUIDED = "TIER_3_GUIDED"
       TIER_4_CO_PILOT = "TIER_4_CO_PILOT"
       USER_OVERRIDE = "USER_OVERRIDE"
   ```
   - `StepRecord` includes `tier_level: CadenceTier = Field(default=CadenceTier.TIER_1_LOCAL, description="Active escalation tier level")`.
   - `LivingPlan` in `parasite_ai/mind/plan.py:80-83` includes `escalation_tier: CadenceTier = CadenceTier.TIER_1_LOCAL` and `tier_strikes: int = 0`.

3. **Grounded Capability Contract & Manifest (`parasite_ai/mind/plan.py:183-303`):**
   - `GroundedCapabilityContract` defines full Pydantic model with fields matching Master Plan Section 4.2.
   - `build_grounded_capability_manifest()` dynamically queries `get_virtual_screen_bounds()` from `parasite_ai.vision.capture` with fallback `(0, 0, 3840, 1080)`.
   - Generated YAML embeds:
     - Physical mouse limits: cubic Bézier kinematics, 120Hz polling rate, min-jerk velocity, 1px Gaussian jitter.
     - Physical keyboard limits: atomic Ctrl+V (<100ms) with clipboard backup/restore, KEYEVENTF_UNICODE typing with 25-75ms human jitter.
     - Perception constraints: Set-of-Mark tags, 1:1 foveal crop, 64-bit dHash gating, Win32 caret blinking via 64-bit GUITHREADINFO (cbSize=72).
     - Explicit prohibitions (VERIF-2): zero headless browser automation, zero CLI scraping (`curl`, `wget`, `requests`, `playwright`, `puppeteer`, `selenium`, `beautifulsoup`), zero programmatic UIA pattern calls (`ValuePattern.SetValue`, `InvokePattern.Invoke`), zero private OS messages (`WM_SETTEXT`), and zero application lookup tables (`app_map = {}`).
     - Sub-2ms hardware touch preemption and instant hard kill (`Ctrl+Alt+K` / `Ctrl+Alt+Q`).

4. **Textual Scene Serialization (`parasite_ai/mind/plan.py:305-409`):**
   - Implements `serialize_textual_scene_brief()` returning Active Window Brief YAML and Set-of-Mark markdown table.
   - Dynamic table byte budgeting enforces strict payload limit:
     ```python
     max_table_bytes = 2800 - len(brief_header.encode("utf-8"))
     ...
     if current_table_bytes + row_bytes > max_table_bytes - 100:
         break
     ```
   - Standard brief: ~1,500 bytes.
   - Tested under adversarial stress with 100 elements containing emojis, complex Chinese characters, pipes, and newlines: produced exactly 2,701 bytes (< 3072 bytes / 3 KB limit, satisfying VERIF-5).
   - Tested with large element pool (80+ elements): correctly truncated with `[Truncated: ... additional elements omitted to preserve <3KB budget]`.

5. **Strategic Consultation Prompt (`parasite_ai/mind/plan.py:412-526`):**
   - `format_gemini_consultation_prompt()` embeds capability manifest, active desktop state, SOM inventory, dilemma, and instructions with LivingPlan schema.
   - Tested dual parameter support: handles both new positional signature `(user_goal, elements, window_info, dilemma, recent_history)` and legacy keyword arguments `(goal, active_window_title, process_name, open_apps_summary, visual_scene_summary, dilemma_description)`.
   - Backward compatibility alias `GEMINI_CONSULTATION_TEMPLATE` preserved.

6. **Multi-Turn Clarification Protocol (`parasite_ai/mind/plan.py:652-740`):**
   - `is_clarification_response()` correctly identifies `"need_clarification": true`.
   - `resolve_clarification_query()` inspects foreground window sensitivity and matches SOM controls.
   - `parse_gemini_consultation_response()` wraps clarification responses into a `LivingPlan` with `needs_clarification=True` and a `StepIntent.CONSULT_ADVISOR` step.

7. **Strict Anti-Hardcoding Invariant (VERIF-6):**
   - `git grep -i "app_map" parasite_ai/` returned exit code 1 with 0 matches.

8. **Test Execution & Regression Gate:**
   - Milestone 4A suite: `pytest tests/test_scene_serialization.py -v` → **18 / 18 passed** in 0.79s.
   - Core M4A test group: `pytest tests/test_scene_serialization.py tests/test_config.py tests/test_living_plan.py tests/test_gemini_consultation_protocol.py -v` → **60 / 60 passed** in 1.25s.
   - Challenger test group: `pytest tests/test_challenger_m3_m4.py tests/test_challenger_p4_empirical.py tests/test_challenger_p4_iter2_c1.py tests/test_challenger_p4_iter2_empirical.py -v` → **73 / 73 passed** in 2.09s.
   - Full regression suite: `pytest tests/ -q` → **940 / 940 passed** in 148.55s with 0 failures and 0 regressions.

---

## 2. Logic Chain

1. **Premise 1 (Zero Silent Exfiltration):** In Phase 4, desktop automation runs with an offline local model by default. `BrainConfig.mode` defaulted previously to `"browser_offload"`. The update in `parasite_ai/config.py` explicitly locks `mode` default to `"local_llm"` and aligns `AppConfig.brain.mode` and `AppConfig.mind.mode`. This fulfills R2 and VERIF-5 invariant constraints.
2. **Premise 2 (Escalation Foundation):** Sub-Phase 4B requires `CadenceTier` to govern the 4-tier escalation state machine. Introducing `CadenceTier` in `parasite_ai/mind/memory.py` and referencing it in `StepRecord` and `LivingPlan` establishes the canonical type contract without circular dependencies.
3. **Premise 3 (Grounded Capability Contract):** Cloud advisors hallucinate DOM access, headless web scrapers, and programmatic accessibility pattern calls if unconstrained. Ingesting `build_grounded_capability_manifest()` directly into `format_gemini_consultation_prompt()` explicitly enforces physical kinematics and read-only UI Automation bounds, satisfying VERIF-2.
4. **Premise 4 (Textual Scene Serialization & Privacy):** Bandwidth-heavy video streaming compromises privacy, adds latency, and steals VRAM. `serialize_textual_scene_brief()` converts Set-of-Mark tags and window telemetry into pure text budgeted strictly under 3 KB (< 3072 bytes), satisfying VERIF-5.
5. **Premise 5 (Multi-Turn Clarification):** Real-world consultations occasionally encounter ambiguous controls. Implementing clarification detection and resolution functions enables interactive two-way refinement before plan execution.
6. **Premise 6 (Zero Regressions):** Full regression test run demonstrates 100% test pass rate (940/940), verifying that no existing functionality from Milestones 1–5 or Phases 1–3 was degraded.

---

## 3. Caveats

1. **Virtual Screen Metrics on Non-Windows / Headless Environments:** When executing outside a live Windows desktop environment where `GetSystemMetrics` cannot query display geometry, `get_virtual_screen_bounds()` catches exceptions and defaults to `(0, 0, 3840, 1080)`. This fallback is clean and prevents test crashes.
2. **Long Window Titles:** If a third-party application presents an extraordinarily long title (>2,000 characters), the brief header consumes more byte budget, which causes `serialize_textual_scene_brief()` to truncate the Set-of-Mark table earlier. Under native Windows, `WindowGuard` caps window titles at 512 characters via `ctypes.create_unicode_buffer(512)`, safely operating well below any truncation threshold.

---

## 4. Conclusion

Milestone 4A is **fully implemented, certified, and compliant with all Phase 4 specifications**:
- `BrainConfig.mode` defaults to `"local_llm"` (zero silent exfiltration).
- `CadenceTier` enum and schema integration completed.
- `GroundedCapabilityContract`, `build_grounded_capability_manifest()`, `serialize_textual_scene_brief()`, and `format_gemini_consultation_prompt()` implemented and verified.
- Textual scene brief payload strictly guaranteed `< 3 KB` (< 3072 bytes).
- Anti-hardcoding invariant verified (0 `app_map` references).
- 100% test pass rate across 940 tests (0 regressions).
- Final Verdict: **APPROVE**.

---

## 5. Verification Method

To independently reproduce and verify this review:

1. **Verify Default BrainConfig Mode:**
   ```powershell
   C:\ParasiteAI\.venv\Scripts\python.exe -c "from parasite_ai.config import BrainConfig, AppConfig; assert BrainConfig().mode == 'local_llm'; assert AppConfig().brain.mode == 'local_llm'; print('BrainConfig invariant verified: local_llm')"
   ```

2. **Verify Anti-Hardcoding Invariant:**
   ```powershell
   git grep -i "app_map" parasite_ai/
   # Expected exit code: 1 (zero matches)
   ```

3. **Verify Milestone 4A Test Suite:**
   ```powershell
   C:\ParasiteAI\.venv\Scripts\python.exe -m pytest tests/test_scene_serialization.py -v
   # Expected: 18 passed in < 1.0s
   ```

4. **Verify Milestone 4A Core Test Group:**
   ```powershell
   C:\ParasiteAI\.venv\Scripts\python.exe -m pytest tests/test_scene_serialization.py tests/test_config.py tests/test_living_plan.py tests/test_gemini_consultation_protocol.py -v
   # Expected: 60 passed in ~1.3s
   ```

5. **Verify Full Regression Gate:**
   ```powershell
   C:\ParasiteAI\.venv\Scripts\python.exe -m pytest tests/ -q
   # Expected: 940 passed in ~148s
   ```

---

## 6. Adversarial Stress Test Results Matrix

| Stress Test Scenario | Test Input / Vector | Expected Behavior | Actual Behavior | Result |
| :--- | :--- | :--- | :--- | :--- |
| **Unicode & Special Character Flood** | 100 elements with emojis, Chinese glyphs, pipes `\|`, newlines `\n` | Table escapes pipes, replaces newlines, stays `< 3 KB` | Payload size = 2,701 bytes, strictly `< 3072` bytes | **PASS** |
| **Negative Virtual Desktop Coordinates** | `vbounds=(-1920, 0, 3840, 1080)` | Coordinate validation properly formats `[-1920, 1920) x [0, 1080)` | Correct bounds rendered in contract YAML | **PASS** |
| **Large Element Pool Truncation** | 80+ button elements in SOM list | Gracefully truncates and appends budget notice | Truncated to 25 items, payload `< 3072` bytes | **PASS** |
| **Legacy Parameter Compatibility** | Old kwargs (`goal`, `active_window_title`, etc.) | Formats prompt without deprecation crash | Full prompt rendered with valid schema | **PASS** |
| **Multi-Turn Clarification Detection** | JSON containing `"need_clarification": true` | Returns `LivingPlan` with `CONSULT_ADVISOR` step | Valid `LivingPlan` hydrated with clarification fields | **PASS** |
| **Full Regression Suite Gate** | All 940 unit, challenger, and integration tests | 100% green execution with zero regressions | 940 / 940 passed in 148.55s | **PASS** |
