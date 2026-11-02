# Worker Dispatch: Milestone 4A (Capability Contract & Textual Scene Serialization)

## Role
teamwork_worker

## Working Directory
C:\ParasiteAI\.agents\teamwork\teamwork_worker_m4a\

## Authoritative Reference Paths
- Original Request: C:\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md
- Scope Document: C:\ParasiteAI\.agents\teamwork\orchestrator_4\SCOPE.md
- Master Plan: c:\Users\Suici\.gemini\antigravity\brain\464b4ef0-398b-45b1-94dc-857256a38046\phase_4_master_plan.md (Sections 4, 7, 9, 10 Sub-Phase 4A, Section 12 VERIF-2, VERIF-5)
- Survey Reports:
  - C:\ParasiteAI\.agents\teamwork\teamwork_explorer_p4_survey_1\handoff.md
  - C:\ParasiteAI\.agents\teamwork\teamwork_explorer_p4_survey_2\handoff.md

## Exclusive File Ownership
- `parasite_ai/config.py`
- `parasite_ai/mind/plan.py`
- `parasite_ai/mind/memory.py` (for `CadenceTier` definition)
- `tests/test_scene_serialization.py`

## Instructions & Requirements
Implement Sub-Phase 4A in full according to the Master Plan:

1. **Config Invariant Fix (`parasite_ai/config.py`)**:
   - In `BrainConfig`, change `mode` field default to `"local_llm"`:
     ```python
     mode: Literal["local_llm", "browser_offload", "hybrid", "mock"] = Field(
         default="local_llm",
         description="Primary brain execution mode"
     )
     ```
   - Verify that default instantiation `BrainConfig().mode == "local_llm"`.

2. **`CadenceTier` in `parasite_ai/mind/memory.py`**:
   - Define `CadenceTier(str, Enum)` with values:
     `TIER_1_LOCAL = "TIER_1_LOCAL"`, `TIER_2_CONSULT = "TIER_2_CONSULT"`, `TIER_3_GUIDED = "TIER_3_GUIDED"`, `TIER_4_CO_PILOT = "TIER_4_CO_PILOT"`, `USER_OVERRIDE = "USER_OVERRIDE"`.

3. **Grounded Capability Contract & Textual Scene Serialization in `parasite_ai/mind/plan.py`**:
   - Add `GroundedCapabilityContract` Pydantic model with fields per Master Plan Section 4.2.
   - Implement `build_grounded_capability_manifest() -> str` dynamically querying `get_virtual_screen_bounds()` from `parasite_ai.safety.window_guard` (or fallback `[0, 0, 3840, 1080]`), specifying actuator limits (Bézier mouse, atomic Ctrl+V paste, cadence typing, supported chords), perception limits (SOM tags [#1..#N], 1:1 foveal crop, ROI diffing, 64-bit dHash, caret focus via GUITHREADINFO cbSize=72), and hard safety constraints (zero headless scraping/curl/playwright/requests/Invoke-WebRequest, zero programmatic UIA pattern calls, sub-2ms preemption, Ctrl+Alt+K, zero app_map).
   - Implement `serialize_textual_scene_brief(elements: List[UIElement], window_info: WindowInfo, recent_diff: float, caret_active: bool) -> str` formatting:
     - Active Window Brief YAML (<1 KB)
     - Textual Set-of-Mark (SOM) markdown table (<2 KB) with columns: `| ID | Control Type | Label / Accessible Name | Bounding Box [x, y, w, h] | Center (x, y) | Source | Flags |`
     - Guarantee total serialized payload is `< 3 KB` of text without raw image/video dependencies.
   - Update `format_gemini_consultation_prompt(user_goal: str, elements: List[UIElement], window_info: WindowInfo, dilemma: str, recent_history: str) -> str` matching `GEMINI_CONSULTATION_TEMPLATE` from Section 4.4, strictly embedding the capability manifest and textual scene brief.
   - Implement multi-turn clarification hooks in `parse_gemini_consultation_response()` (handling `"need_clarification": true`).
   - Extend `PlanStep` with `tool_route: Optional[Literal["GUI", "CLI", "ADVISOR"]] = None`.
   - Extend `LivingPlan` with `escalation_tier: CadenceTier = CadenceTier.TIER_1_LOCAL` and `tier_strikes: int = 0`.

4. **Test Suite `tests/test_scene_serialization.py`**:
   - Test `build_grounded_capability_manifest()`: verify dynamic virtual bounds, actuator limits, and explicit scraping/UIA pattern prohibitions.
   - Test `serialize_textual_scene_brief()`: verify payload size `< 3 KB`, correct markdown table layout, caret status, window info formatting.
   - Test `format_gemini_consultation_prompt()`: verify embedded manifest, SOM tags, LivingPlan JSON schema.
   - Test `BrainConfig().mode == "local_llm"`.
   - Test multi-turn clarification parsing.

5. **Verification**:
   - Run `pytest tests/test_scene_serialization.py` and ensure 100% pass.
   - Run full regression test suite `pytest tests/` and verify zero regressions.
   - Document commands and results in `handoff.md`.

## Mandatory Integrity Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.
