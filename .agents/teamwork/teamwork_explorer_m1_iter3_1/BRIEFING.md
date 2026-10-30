# BRIEFING — 2026-10-29T12:04:00Z

## Mission
Investigate and design an exact fix in LocalBrainManager._download_worker for partial streaming clean-close truncation detection without modifying source code.

## 🔒 My Identity
- Archetype: explorer
- Roles: Teamwork explorer (read-only investigation, problem analysis, exact fix design)
- Working directory: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m1_iter3_1\
- Original parent: 9a16f679-6db4-4849-ba56-0f4856cbbf9b
- Milestone: M1 Iteration 3

## 🔒 Key Constraints
- Read-only investigation — do NOT implement / modify source code directly
- Must design exact fix in `_download_worker` for partial download detection (`bytes_downloaded < real_total`)
- Provide exact code recommendations for Worker in `plan.md` and `handoff.md`
- Message parent when done

## Current Parent
- Conversation ID: 9a16f679-6db4-4849-ba56-0f4856cbbf9b
- Updated: 2026-10-29T12:04:00Z

## Investigation State
- **Explored paths**:
  - `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_challenger_m1_iter2_1\handoff.md`
  - `g:\__Docs\ParasiteAI\tests\test_challenger_m1_iter2_1.py` (lines 482-520)
  - `g:\__Docs\ParasiteAI\parasite_ai\mind\brain_manager.py` (lines 45-60, 75-86, 470-520, 660-840)
  - `g:\__Docs\ParasiteAI\tests\test_brain_manager.py`
  - `g:\__Docs\ParasiteAI\tests\test_stress_gguf.py`
  - Full test suite via `uv run pytest -v` (172 passed, 1 failed)
- **Key findings**:
  - `test_partial_streaming_clean_close_truncation_detection` fails deterministically because `_download_worker` in `brain_manager.py` (lines 770-795) does not verify whether `bytes_downloaded >= real_total` upon clean generator exit.
  - The 128-byte truncated stub contains `b"GGUF\x03\x00\x00\x00"`, which passes `validate_gguf_header(min_bytes=8)` and is promoted to `BrainState.MODEL_READY_ON_DISK` with `progress.status = 'completed'` and `100.0%`.
  - Enum contract clarification: The actual enum is `BrainState.DOWNLOAD_FAILED` (there is NO `ERROR_DOWNLOAD_FAILED` in `BrainState`; using it would raise `AttributeError`). Progress model is `DownloadProgress(status='failed')`, which is asserted by all test cases (`assert manager.state == BrainState.DOWNLOAD_FAILED` and `assert events[-1].status == "failed"`).
  - Validation order flaw: `temp_path` is currently renamed to `target_path` BEFORE validation, meaning invalid or corrupt files overwrite destination models. Validating `temp_path` before rename prevents disk corruption.
- **Unexplored areas**: None. Defect and fix design fully scoped and verified.

## Key Decisions Made
- Design clean, localized fix in `_download_worker`:
  1. Add stream completeness check: if `(real_total > 0 and bytes_downloaded < real_total) or not temp_path.exists() or temp_path.stat().st_size == 0`, unlink `temp_path`, transition `self.state = BrainState.DOWNLOAD_FAILED`, `progress.status = "failed"`, invoke `progress_callback`, and return.
  2. Perform binary GGUF header validation on `temp_path` BEFORE renaming to `target_path`.
  3. Only replace `target_path` if both completeness check and GGUF header validation succeed.
- Formulate precise diff patch and replacement block in `plan.md` and `handoff.md` for Worker.

## Artifact Index
- `DISPATCH.md` — Inbound instruction log
- `BRIEFING.md` — Situational awareness index
- `progress.md` — Heartbeat / progress log
- `plan.md` — Step-by-step implementation guide for Worker
- `handoff.md` — 5-component handoff report for parent and Worker
