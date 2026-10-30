# BRIEFING — 2026-10-29T12:05:30Z

## Mission
Investigate state machine recovery and atomic file cleanup on download failure/truncation, producing concrete recommendations for Worker.

## 🔒 My Identity
- Archetype: explorer
- Roles: investigation, synthesis
- Working directory: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m1_iter3_2\
- Original parent: 9a16f679-6db4-4849-ba56-0f4856cbbf9b
- Milestone: m1_iter3

## 🔒 Key Constraints
- Read-only investigation — do NOT implement
- Do NOT write source code
- Write only to working directory g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m1_iter3_2\
- Write exact recommendations for Worker in plan.md and handoff.md
- Message parent when done

## Current Parent
- Conversation ID: 9a16f679-6db4-4849-ba56-0f4856cbbf9b
- Updated: 2026-10-29T12:05:30Z

## Investigation State
- **Explored paths**:
  - `parasite_ai/mind/brain_manager.py` (lines 100–140, 450–570, 660–840, 870–950)
  - `tests/test_challenger_m1_iter2_1.py` (failure site lines 482–520, and all stress tests)
  - `tests/test_brain_manager.py` (download, cancellation, error recovery, load/unload tests)
  - `tests/test_stress_gguf.py`, `tests/test_stress_concurrency.py`
- **Key findings**:
  1. Root cause of truncation vulnerability: `_download_worker` only looped over chunks; if remote stream ended prematurely without exception, no `bytes_downloaded >= real_total` check existed.
  2. Critical architectural bug in file promotion order: `temp_path.replace(target_path)` was called *before* `validate_gguf_header(target_path)`. Corrupted or truncated downloads actively destroyed prior valid models on disk and left invalid stubs at `target_path`.
  3. `self.current_model` lifecycle invariant: On failure/truncation/cancellation, `self.current_model` must never be assigned the failed target filename. If a prior valid model was on disk, `self.current_model` must be kept intact so local execution can resume or reload. If no valid model is on disk or previous file is missing/invalid, `self.current_model` must be `None`.
  4. State transition requirement: Download failure/truncation must set `self.state = BrainState.DOWNLOAD_FAILED` and `self._current_progress.status = "failed"` to satisfy UI signaling and test suite contracts.
  5. File cleanup atomicity: Validate `temp_path` *in situ* (size completeness + `validate_gguf_header(temp_path)`). Clean up `temp_path` immediately on any error/cancellation/truncation. Never touch `target_path` until all validations succeed.
- **Unexplored areas**: None for M1 download state recovery.

## Key Decisions Made
- Formulated the 4-phase atomic download pipeline: Stream to temp -> Size completeness check -> Header validation on temp -> Atomic replace to target.
- Formulated the exact disk-backed integrity check for `self.current_model` retention vs clearing.

## Artifact Index
- DISPATCH.md — incoming dispatch instructions
- BRIEFING.md — persistent situational awareness
- progress.md — liveness heartbeat
- plan.md — implementation plan and recommendations for Worker
- handoff.md — 5-component handoff report for parent orchestrator
