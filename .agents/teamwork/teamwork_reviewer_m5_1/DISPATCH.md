# Dispatch: teamwork_reviewer_m5_1
Working Directory: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_reviewer_m5_1\
Role: Entry Points & Lifecycle Reviewer (M5)
Orchestrator Conversation ID: 9a16f679-6db4-4849-ba56-0f4856cbbf9b
Original Request Path: g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md
Project Spec Path: g:\__Docs\ParasiteAI\PROJECT.md
Worker Handoff Path: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_worker_m5\handoff.md

## Assignment
Independently review Milestone M5 entry points, CLI parsing, High-DPI bootstrap, and launcher scripts.
Files to inspect:
- `main.py`
- `parasite_ai/main.py`
- `launch_parasite.bat`
- `parasite_ai/ui/dpi.py`
- `parasite_ai/ui/companion_dock.py`
- `tests/test_entrypoints.py`

Execute verification commands:
- `uv run python main.py --dry-run --headless`
- `uv run pytest tests/test_entrypoints.py -v`

Author your handoff at `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_reviewer_m5_1\handoff.md` with explicit APPROVE or REQUEST_CHANGES verdict.

## 2026-10-29T17:57:22Z
You are teamwork_reviewer_m5_1, Entry Points & Lifecycle Reviewer for Milestone M5.
Your working directory is: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_reviewer_m5_1\
Read g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_reviewer_m5_1\DISPATCH.md, g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md, g:\__Docs\ParasiteAI\PROJECT.md, and g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_worker_m5\handoff.md.

Inspect:
- `main.py`
- `parasite_ai/main.py`
- `launch_parasite.bat`
- `parasite_ai/ui/dpi.py`
- `parasite_ai/ui/companion_dock.py`
- `tests/test_entrypoints.py`

Run verification commands:
- `uv run python main.py --dry-run --headless`
- `uv run pytest tests/test_entrypoints.py -v`

Write your handoff report to `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_reviewer_m5_1\handoff.md` with an explicit verdict: APPROVE or REQUEST_CHANGES.
Send a message to orchestrator `9a16f679-6db4-4849-ba56-0f4856cbbf9b` with your verdict and handoff path when complete.
