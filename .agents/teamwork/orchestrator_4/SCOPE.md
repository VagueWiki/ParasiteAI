# Scope: Phase 4 Implementation — Strategic Gemini Consultation Protocol & Dynamic Contingency Branching

## Architecture
Phase 4 elevates ParasiteAI into a hierarchical, tool-aware cognitive companion:
1. Fast Local Mind (Tier 1 & Tier 3): Local offline model, Set-of-Mark visual grounding, localized ROI diffing.
2. Strategic Advisor (Tier 2 & Tier 4): Structured consultation protocol with Gemini on cognitive deadlock.
3. Tool-Aware Affordance Engine: Heuristic assessment between Physical GUI vs Local Developer Tooling (CLI sandbox) vs External Advisor.
4. Grounded Capability Contract: Immutable physical actuator manifest and perception limits, zero scraping, zero programmatic UIA pattern calls.
5. Dual-Channel Output Separation: Internal machine LivingPlan JSON (Channel A) vs visible character monologue (Channel B).

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Grounded Capability Contract & Manifest | Formal manifest of physical actuators, foveated perception, dynamic screen bounds, and constraints (no scraping/curl/playwright, no programmatic UIA) | M4A | Master Plan §4 |
| 2 | Textual Scene Serialization | Set-of-Mark markdown summary table + active window brief (<3 KB text payload, zero video streaming) | M4A | Master Plan §7 |
| 3 | 4-Tier Escalation State Machine | T1 (0-2 local strikes) -> T2 (Gemini consult) -> T3 (0-2 guided strikes) -> T4 (0-3 co-pilot strikes) -> USER_OVERRIDE | M4B | Master Plan §3 |
| 4 | Action-Aware Strike Evaluation | CLI evaluated by returncode == 0; passive actions (WAIT, DONE) exempt; GUI evaluated by localized ROI diff >= 0.02 | M4B | Master Plan §3.1 |
| 5 | Dual-Channel Output Router | Channel A machine LivingPlan JSON vs Channel B persona speech monologue (zero raw JSON, backticks, or error tokens leaked) | M4C | Master Plan §5 |
| 6 | Tool-Aware Affordance Evaluator | Context-aware heuristic evaluating PHYSICAL_GUI vs LOCAL_DEVELOPER_TOOL vs STRATEGIC_ADVISOR | M4D | Master Plan §6 |
| 7 | CLI Execution Sandbox | Sandboxed subprocess execution with binary whitelist, scraping tool prohibition, 30s timeout, and 10ms cancellation token abort in <20ms | M4D | Master Plan §6.4 |
| 8 | PrecisionAppMatcher | High-precision element matching using word-boundary regex (\b) and destructive verb disqualification | M4E | Master Plan §8.3 |
| 9 | UniversalAppResolver 3-Tier State Machine | Generic launcher with attempt tracking (Tier 1 SOM -> Tier 2 Win chord -> Tier 3 Win+R fallback -> WAIT), eliminating infinite loops | M4E | Master Plan §8.2 |
| 10 | 10 Win32 Ctypes Structs 64-bit ABI | POINT, RECT, MSLLHOOKSTRUCT, KBDLLHOOKSTRUCT, MOUSEINPUT, KEYBDINPUT, HARDWAREINPUT, INPUT_UNION, INPUT, GUITHREADINFO | M4F | Master Plan §9.2 |
| 11 | Victory Verification Matrix (VERIF-1..11) & Regression Gate | 100% green tests across existing baseline + 7 new Phase 4 test suites | M4F | Master Plan §12 |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M4A | Capability Contract & Textual Scene Serialization | Features 1, 2, Config fix (BrainConfig.mode -> "local_llm") | none | DONE |
| M4B | 4-Tier Escalation State Machine in Mind | Features 3, 4 | M4A | DONE |
| M4C | Dual-Channel Output Router & Persona Voice | Feature 5 | M4A, M4B | DONE |
| M4D | Tool-Aware Reasoning & CLI Execution Sandbox | Features 6, 7 | M4A, M4B | DONE |
| M4E | UniversalAppResolver Hardening & Precision Matching | Features 8, 9 | none | DONE |
| M4F | System Integration, Verification Matrix & Full Regression | Features 10, 11 | M4A, M4B, M4C, M4D, M4E | DONE |

## Interface Contracts

### 1. Capability Manifest & Scene Serialization (`parasite_ai/mind/plan.py`)
- `build_grounded_capability_manifest() -> str`: Formats YAML Grounded Capability Contract with dynamic screen bounds and constraints.
- `serialize_textual_scene_brief(elements: List[UIElement], window_info: WindowInfo, recent_diff: float, caret_active: bool) -> str`: Formats Set-of-Mark markdown table + active window brief (<3 KB).
- `format_gemini_consultation_prompt(user_goal: str, elements: List[UIElement], window_info: WindowInfo, dilemma: str, recent_history: str) -> str`: Embeds capability contract, SOM table, window state, and LivingPlan JSON schema.

### 2. Escalation State Machine (`parasite_ai/mind/memory.py`)
- `CadenceTier(str, Enum)`: `TIER_1_LOCAL`, `TIER_2_CONSULT`, `TIER_3_GUIDED`, `TIER_4_CO_PILOT`, `USER_OVERRIDE`.
- `EscalationStateMachine`:
  - `on_action_result(success: bool, screen_diff: float = 0.0, action_type: Optional[ActionType] = None, is_interactive: bool = True, cli_returncode: Optional[int] = None, diff_threshold: float = 0.02) -> CadenceTier`
  - `on_consultation_success() -> None`
  - `on_consultation_failure() -> None`
  - `on_hardware_interrupt() -> None`

### 3. Dual-Channel Output Router (`parasite_ai/mind/dual_mind.py`)
- `DualChannelRouter`:
  - `route_consultation_output(raw_advisor_text: str, user_goal: str, active_plan: LivingPlan) -> Tuple[Optional[LivingPlan], str]`
  - `translate_to_persona_voice(raw_rationale: str, updated_plan: Optional[LivingPlan], user_goal: str) -> str`
  - `_sanitize_text(text: str) -> str`: Strips markdown code blocks, backticks, braces, quotes, coordinate pairs.

### 4. Tool-Aware Affordance & Sandbox (`parasite_ai/mind/affordance.py`)
- `ActionAffordance(str, Enum)`: `PHYSICAL_GUI`, `LOCAL_DEVELOPER_TOOL`, `STRATEGIC_ADVISOR`.
- `AffordanceEvaluator.evaluate(goal: str, active_window_title: str) -> AffordanceAssessment`.
- `CLIExecutionSandbox`:
  - `sanitize_and_tokenize(command_str: str) -> List[str]`
  - `execute(command_str: str, cwd: str = "C:\\ParasiteAI", timeout: float = 30.0, cancellation_token: Optional[threading.Event] = None) -> CLIExecutionResult`

### 5. PrecisionAppMatcher & UniversalAppResolver (`parasite_ai/mind/resolver.py`)
- `PrecisionAppMatcher`:
  - `score_match(label: str, target: str) -> float`
  - `find_best_element(target: str, elements: List[UIElement], threshold: float = 0.80) -> Optional[Tuple[UIElement, float]]`
- `UniversalAppResolver`:
  - `resolve_launch_action(target_app: str, elements: List[UIElement], cancellation_token: Optional[threading.Event] = None) -> ActionPlan`
