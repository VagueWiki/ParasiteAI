## 2026-11-01T13:01:02Z

You are Worker M4E for Phase 4 Milestone 4E (UniversalAppResolver Hardening & Precision Matching) in ParasiteAI.

Working Directory: C:\ParasiteAI\.agents\teamwork\teamwork_worker_m4e\
Original Request: C:\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md
Master Reference Plan: c:\Users\Suici\.gemini\antigravity\brain\464b4ef0-398b-45b1-94dc-857256a38046\phase_4_master_plan.md (§8, §10 Sub-Phase 4E, §12 VERIF-11)
Scope Document: C:\ParasiteAI\.agents\teamwork\orchestrator_4\SCOPE.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

TASK & DELIVERABLES:
1. Implement `PrecisionAppMatcher` in `parasite_ai/mind/resolver.py` per Master Plan §8.3:
   - `NEGATIVE_VERBS = {"exit", "close", "quit", "cancel", "uninstall", "delete", "remove", "kill"}`
   - `PREFERRED_ROLES = {"button", "listitem", "menuitem", "hyperlink", "image", "pane", "icon", "treeitem", "tabitem", "window"}`
   - `score_match(cls, label: str, target: str) -> float`:
     - Level 1: Exact match (`l_norm == t_norm`) -> 1.0.
     - Token boundary check: If any token in `NEGATIVE_VERBS` -> returns 0.0 immediately (disqualifies destructive/exit elements).
     - Level 2: Exact prefix match with token boundary (`target + " "`, `target + " -"`, `target + ":"`) -> 0.95.
     - Level 3: Word boundary regex match (`\b` + re.escape(t_norm) + `\b`) -> `0.80 + (0.10 * pos_ratio)` where `pos_ratio = max(0.0, 1.0 - (idx / max(1, len(l_norm))))`.
     - Rejection: Arbitrary substrings without word boundaries (e.g. 'art' in 'SmartScreen', 'cat' in 'catalog') score 0.0.
   - `find_best_element(cls, target: str, elements: List[UIElement], threshold: float = 0.80) -> Optional[Tuple[UIElement, float]]`.
2. Remediate `UniversalAppResolver` in `parasite_ai/mind/resolver.py` per Master Plan §8.2:
   - State variables:
     - `_target_app: Optional[str] = None`
     - `_start_search_attempts: int = 0`
     - `_search_opened: bool = False`
     - `_run_dialog_attempts: int = 0`
     - `_run_opened: bool = False`
   - Reset state counters when a new `target_app` is targeted.
   - Tier 1: Scans active visible SOM elements with `PrecisionAppMatcher.find_best_element(target_app, elements, threshold=0.80)`. If found, emits `ActionType.CLICK` and resets launcher state.
   - Tier 2 (Windows Start Search Chord):
     - Step A: If `_start_search_attempts == 0` and `not _search_opened`: emits `ActionPlan(action=ActionType.HOTKEY, keys=["win"], wait_ms=250)`, sets `_search_opened = True`.
     - Step B: If `_search_opened`: emits `ActionPlan(action=ActionType.TYPE, text=f"{target_app}\n", submit=True)`, clears `_search_opened = False`, increments `_start_search_attempts = 1`.
   - Tier 3 (Windows Run Dialog Fallback Transition):
     - If Start Search was attempted (`_start_search_attempts >= 1`):
     - Step A: If `_run_dialog_attempts == 0` and `not _run_opened`: emits `ActionPlan(action=ActionType.HOTKEY, keys=["win", "r"], wait_ms=250)`, sets `_run_opened = True`.
     - Step B: If `_run_opened`: emits `ActionPlan(action=ActionType.TYPE, text=f"{target_app}\n", submit=True)`, clears `_run_opened = False`, increments `_run_dialog_attempts = 1`.
   - Exhaustion: If both Tier 2 and Tier 3 have been attempted (`_start_search_attempts >= 1` and `_run_dialog_attempts >= 1`), emits `ActionType.WAIT` with diagnostic reasoning, cleanly escalating to a cognitive replan rather than looping infinitely.
   - Enforce non-blocking millisecond checks against `cancellation_token`.
3. LivingPlan Step Verification across 8 StepIntents in `parasite_ai/mind/plan.py`:
   - Implement `verify_step_completion(step: PlanStep, action: ActionPlan, result: ActionResult, screen_diff: float, current_window: WindowInfo) -> bool` covering all 8 intents (`NAVIGATE`, `INPUT_DATA`, `SELECT_OPTION`, `VERIFY_STATE`, `LAUNCH_OR_ACTIVATE`, `DISMISS_DIALOG`, `CONSULT_ADVISOR`, `CONCLUDE`).
   - Support automated contingency step insertion for missing caret focus, 0% diff stagnation, and modal dialogs.
4. Author Comprehensive Test Suite:
   - `tests/test_resolver_precision.py` (VERIF-11):
     - PrecisionAppMatcher scoring: exact match, destructive verb rejection ("Exit Notepad", "Close Window" for "notepad"), prefix boundary matching, word-boundary regex matching, substring rejection ("art" vs "SmartScreen", "cat" vs "catalog", "edit" vs "credit").
     - UniversalAppResolver 3-tier state machine transitions: Tier 1 match -> Click; Tier 2 Start search (`Win` -> `Type`); Tier 3 Run dialog fallback (`Win+R` -> `Type`); Exhaustion -> `ActionType.WAIT` (no infinite loop).
     - Cancellation token preemption in resolver.
     - `verify_step_completion` across all 8 `StepIntent` types.
5. Run Tests & Full Regression:
   - Run: `.\.venv\Scripts\python.exe -m pytest tests/test_resolver_precision.py -v`
   - Run full regression: `.\.venv\Scripts\python.exe -m pytest tests/ -q`
   - Check anti-hardcoding invariant: `git grep -i "app_map" parasite_ai/` -> 0 occurrences.
6. Write handoff report to `C:\ParasiteAI\.agents\teamwork\teamwork_worker_m4e\handoff.md`.
7. Send message to parent with your verdict and findings.
