# BRIEFING — 2026-10-29T11:08:30Z

## Mission
Investigate and design M1 foundation specifications (pyproject.toml, package metadata, hatchling build, tool.uv, layout, deps) for parasite_ai.

## 🔒 My Identity
- Archetype: explorer
- Roles: investigator, synthesist
- Working directory: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m1_1
- Original parent: 9a16f679-6db4-4849-ba56-0f4856cbbf9b
- Milestone: M1 (Foundation & Zero-Config Setup)

## 🔒 Key Constraints
- Read-only investigation — do NOT implement
- Do NOT write source code files
- Write recommendations to plan.md and handoff report to handoff.md
- Message parent when done

## Current Parent
- Conversation ID: 9a16f679-6db4-4849-ba56-0f4856cbbf9b
- Updated: 2026-10-29T11:08:30Z

## Investigation State
- **Explored paths**:
  - `g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md`
  - `g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md`
  - `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_survey_1\survey_report.md`
  - `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_survey_2\survey_report.md`
  - `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_survey_3\survey_report.md`
  - Host environment verification via `uv --version`, `uv python list`, and `uv pip compile`
- **Key findings**:
  - Python 3.12.13 and Python 3.14.4 both present; explicit `.python-version` (3.12) and `requires-python = ">=3.12,<3.13"` required.
  - 54 candidate packages resolved cleanly in 15s via `uv pip compile --python 3.12` without conflicts.
  - Build backend `hatchling` requires `[tool.hatch.build.targets.wheel] packages = ["parasite_ai"]` to prevent packaging agent metadata.
  - Dev dependencies configured via modern PEP 735 `[dependency-groups] dev` and `[tool.uv] default-groups = ["dev"]`.
- **Unexplored areas**: None within M1 Foundation scope.

## Key Decisions Made
- Pinned Python to `3.12` explicitly via `.python-version` and `pyproject.toml`.
- Relegated `llama-cpp-python` to `[project.optional-dependencies] local-llm` to preserve zero-compile out-of-the-box setup.
- Structured flat-package hierarchy under `parasite_ai/` with `safety`, `hands`, `ui`, `vision`, `mind` subpackages.

## Artifact Index
- `DISPATCH.md` — Incoming task dispatch record
- `progress.md` — Liveness heartbeat & task checklist
- `plan.md` — Complete implementation blueprint and drop-in code specifications for the Worker
- `handoff.md` — 5-component hard handoff report
