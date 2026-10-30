# BRIEFING — 2026-10-29T12:12:00Z

## Mission
Apply download completeness verification and atomic staging validation to `_download_worker` in `parasite_ai/mind/brain_manager.py` and verify all tests pass.

## 🔒 My Identity
- Archetype: worker
- Roles: implementer, qa, specialist
- Working directory: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_worker_m1_iter3\
- Original parent: 9a16f679-6db4-4849-ba56-0f4856cbbf9b
- Milestone: m1_iter3

## 🔒 Key Constraints
- Apply download completeness verification and atomic staging validation to `_download_worker` in `parasite_ai/mind/brain_manager.py` per plans.
- Verify `bytes_downloaded >= real_total` and `temp_path.stat().st_size >= real_total`.
- Validate GGUF header on `temp_path` BEFORE replacing `target_path`.
- If incomplete or invalid, unlink `temp_path`, set `self.state = BrainState.DOWNLOAD_FAILED`, and set `progress.status = "failed"`.
- Only promote `temp_path` to `target_path` when size completeness and header validation both succeed.
- Verify ALL 173 tests pass with exit code 0 (`uv run pytest -v`).
- Minimal change principle: only modify `parasite_ai/mind/brain_manager.py`.
- No cheating, no dummy implementations.

## Current Parent
- Conversation ID: 9a16f679-6db4-4849-ba56-0f4856cbbf9b
- Updated: 2026-10-29T12:06:27Z

## Task Summary
- **What to build**: Download completeness verification and atomic staging validation in `BrainManager._download_worker`.
- **Success criteria**: All 173 tests pass, incomplete downloads and invalid GGUF headers caught before promotion to target_path.
- **Interface contracts**: PROJECT.md
- **Code layout**: parasite_ai/mind/brain_manager.py

## Key Decisions Made
- Added size completeness checks (`bytes_downloaded >= real_total` and `temp_size >= real_total` and `temp_size > 0`) after the chunk loop.
- Pre-validated binary GGUF header directly on `temp_path` before promoting to `target_path`.
- Safely unlinked `temp_path` and transitioned to `BrainState.DOWNLOAD_FAILED` and `status = "failed"` upon completeness or header failure, leaving `target_path` untouched.
- Cleanly promoted `temp_path` to `target_path` only after all validations pass.

## Artifact Index
- DISPATCH.md — Orchestrator dispatch message
- BRIEFING.md — Situational awareness and state
- progress.md — Liveness heartbeat and step tracking
- handoff.md — Final handoff report

## Change Tracker
- **Files modified**: `parasite_ai/mind/brain_manager.py` (download completeness check & staging header validation)
- **Build status**: PASS (`uv run pytest -v` -> 173 passed in 15.47s)
- **Pending issues**: None

## Quality Status
- **Build/test result**: 173/173 tests passed (100%), 0 failures, 0 skipped
- **Lint status**: Clean (py_compile passed)
- **Tests added/modified**: Verified against all existing tests in `tests/`

## Loaded Skills
- None
