# Worker Dispatch: Milestone 4C (Dual-Channel Output Router & Persona Voice)

## Role
teamwork_worker

## Working Directory
C:\ParasiteAI\.agents\teamwork\teamwork_worker_m4c\

## Authoritative Reference Paths
- Original Request: C:\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md
- Scope Document: C:\ParasiteAI\.agents\teamwork\orchestrator_4\SCOPE.md
- Master Plan: c:\Users\Suici\.gemini\antigravity\brain\464b4ef0-398b-45b1-94dc-857256a38046\phase_4_master_plan.md (Section 5, Section 5.2, Section 5.3, Section 10 Sub-Phase 4C, Section 12 VERIF-3)

## Exclusive File Ownership
- `parasite_ai/mind/dual_mind.py`
- `tests/test_dual_channel_output.py`

## Instructions & Requirements
Implement Sub-Phase 4C in full according to the Master Plan:

1. **`DualChannelRouter` in `parasite_ai/mind/dual_mind.py`**:
   - Implement `DualChannelRouter` class:
     ```python
     class DualChannelRouter:
         def __init__(self, bridge: Optional[Any] = None, persona_engine: Optional[Any] = None): ...
         def route_consultation_output(self, raw_advisor_text: str, user_goal: str, active_plan: LivingPlan) -> Tuple[Optional[LivingPlan], str]: ...
         def translate_to_persona_voice(self, raw_rationale: str, updated_plan: Optional[LivingPlan], user_goal: str) -> str: ...
         @staticmethod
         def _sanitize_text(text: str) -> str: ...
     ```
   - Channel A (Machine Plan):
     - Extracts machine blueprint via `extract_strategic_blueprint_json(raw_advisor_text)`.
     - Supports BOTH `"steps"` key AND `"recommended_strategy"` key! (VERIF-3: Blueprint must not be dropped when advisor uses `"recommended_strategy"`).
     - Hydrates `LivingPlan` via `parse_gemini_consultation_response(raw_advisor_text, user_goal)`.
   - Channel B (Persona Dialogue):
     - Translates raw rationale and plan into natural character speech.
     - `_sanitize_text`: Strips all markdown code blocks (` ```[\w]*[\s\S]*?``` `), backticks (` `[^`]*` `), curly braces/brackets/quotes, coordinate tuples `\(\d+,\s*\d+\)`, and dimension pairs `\b\d+x\d+\b`.
     - Filters error tokens: if clean text contains `"error:"`, `"exception"`, `"resource_exhausted"`, returns friendly fallback (e.g. `"I've re-evaluated our plan. Moving to the next step now!"`), never leaking stack traces or raw API error dicts.
     - If `self.bridge and hasattr(self.bridge, "notify_speech")`, emits visible speech strictly through `self.bridge.notify_speech(persona_speech)`.
     - Returns `(updated_plan, persona_speech)`.
   - Pipeline Integration in `DualMindPipeline`:
     - Instantiate `self.dual_channel_router = DualChannelRouter(bridge=self.bridge, persona_engine=self.persona_engine)` in `DualMindPipeline.__init__`.
     - In Tier 2 consultation handling: route raw advisor response through `self.dual_channel_router.route_consultation_output()`.
     - Eradicate legacy leak where raw web advice string (`Web AI advises: ...`) was emitted directly to speech.

2. **Test Suite `tests/test_dual_channel_output.py` (VERIF-3)**:
   - Test Channel A extraction with `"steps"` key: verifies `LivingPlan` hydration.
   - Test Channel A extraction with `"recommended_strategy"` key: verifies `LivingPlan` hydration (VERIF-3 pass criteria).
   - Test Channel B sanitization:
     - Raw JSON leak prevention: assert zero braces `{}`, zero brackets `[]`, zero raw keys in speech.
     - Code block stripping: assert all ` ```python ` and ` ```json ` blocks completely stripped.
     - Backtick stripping: assert all ` `...` ` stripped.
     - Coordinate and dimension stripping: assert `(450, 220)` and `1920x1080` stripped.
     - Error token suppression: assert `RESOURCE_EXHAUSTED`, `code 429`, stack traces produce clean friendly character fallback with zero error tokens.
   - Test `UIBridge.notify_speech()` integration: assert bridge receives strictly sanitized speech.

3. **Verification**:
   - Run `pytest tests/test_dual_channel_output.py tests/test_challenger_p4_empirical.py -v`.
   - Run full regression test suite `pytest tests/` and verify zero regressions.
   - Document results in `handoff.md`.

## Mandatory Integrity Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## 2026-11-01T08:49:48Z
You are Worker for Milestone 4C of ParasiteAI (Dual-Channel Output Router & Persona Voice).
Working directory: C:\ParasiteAI\.agents\teamwork\teamwork_worker_m4c\
Original request path: C:\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md
Scope document path: C:\ParasiteAI\.agents\teamwork\orchestrator_4\SCOPE.md
Master plan path: c:\Users\Suici\.gemini\antigravity\brain\464b4ef0-398b-45b1-94dc-857256a38046\phase_4_master_plan.md
