# BRIEFING — 2026-10-29T11:42:00Z

## Mission
Investigate brain_manager.py concurrency and state management bugs, and produce exact code fix recommendations for the Worker.

## 🔒 My Identity
- Archetype: explorer
- Roles: investigation, synthesis
- Working directory: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m1_iter2_1
- Original parent: 9a16f679-6db4-4849-ba56-0f4856cbbf9b
- Milestone: m1_iter2

## 🔒 Key Constraints
- Read-only investigation — do NOT implement
- Do NOT write source code files
- Produce exact code fix recommendations for the Worker
- Write to plan.md and handoff.md, message parent when complete

## Current Parent
- Conversation ID: 9a16f679-6db4-4849-ba56-0f4856cbbf9b
- Updated: 2026-10-29T11:32:08Z

## Investigation State
- **Explored paths**: `parasite_ai/mind/brain_manager.py`, `tests/test_stress_concurrency.py`, `tests/test_stress_m1.py`, full pytest suite (111 tests)
- **Key findings**:
  1. `cancel_download()` crashes with `RuntimeError: cannot join current thread` when invoked from `progress_callback` on worker thread.
  2. `generate()` race condition under concurrent calls: subsequent threads capture `prev_state = INFERRING` and stick manager in `INFERRING`.
  3. `generate()` `finally:` unconditionally restores `prev_state`, clobbering asynchronous state changes like `toggle_browser_only_mode(True)` or `unload_model()`.
  4. `_instantiate_local_engine()` lacks headroom comparison against model required VRAM / budget when `gpu_layers == -1`.
  5. `_extract_action_json()` fails on outputs with conversational braces and nested JSON due to greedy/non-greedy regex mismatch; fixed via `json.JSONDecoder().raw_decode`.
- **Unexplored areas**: None; all 111 tests investigated and verified with 100% pass rate.

## Key Decisions Made
- Confirmed root causes and validated 7 surgical code modifications for `parasite_ai/mind/brain_manager.py`.
- Verified in-process monkeypatched fixes achieving 111/111 passed in 9.60s.
- Authored comprehensive drop-in instructions in `plan.md` and complete handoff in `handoff.md`.

## Artifact Index
- DISPATCH.md — Incoming dispatch message
- BRIEFING.md — Persistent working memory
- progress.md — Heartbeat and activity log
- plan.md — Recommended fix plan with exact code diffs
- handoff.md — 5-component handoff report
