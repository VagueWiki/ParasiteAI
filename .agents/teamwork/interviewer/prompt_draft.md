Evaluate the ParasiteAI codebase and milestone implementations (M1–M5), check current system health against real desktop and hardware constraints, and deliver an evaluation report alongside a prioritized execution plan for next steps.

Working directory: g:\__Docs\ParasiteAI
Integrity mode: development

Reference material:
- PROJECT.md
- C:\Users\Suici\.gemini\antigravity\brain\9febbb50-4316-49f8-85fe-f612a778b2d3\implementation_plan.md
- C:\Users\Suici\.gemini\antigravity\brain\9febbb50-4316-49f8-85fe-f612a778b2d3\state_evaluation_plan.md

## Requirements

### R1. State Evaluation & Milestone 5 Gate
Audit the ParasiteAI codebase across all implemented milestones (M1–M5), verifying test suite health (`uv run pytest`), conducting the full Milestone 5 review and audit gate (reviewers, challengers, auditor), and identifying discrepancies between unit/simulated test results and real desktop execution requirements (companion dock, click-through HUD, Bezier glide, physical abort, Chrome/Gemini offload selectors).

### R2. Non-Intrusive Live Verification & Safety Guardrail
Perform safe, non-interactive live desktop verification, including verifying local model availability in `models/` and loading within the 8 GB VRAM budget (RTX 4060), and launching the companion dock in dry-run mode without mouse or keyboard takeover. The team must ask for explicit user consent before initiating any live test that takes over the user's mouse or keyboard.

### R3. Repository Cleanup
Remove leftover temporary files (`test_none.yaml`, `test_none2.yaml`, repository root `__pycache__`) and fix typographical errors in `PROJECT.md` ("BAczier").

### R4. Prioritized Action Plan
Deliver a clear, prioritized execution plan detailing the sequential tasks for remaining work, including live desktop smoke tests, live action verification, offload validation, and follow-up milestones.

## Acceptance Criteria

### Milestone 5 Gate & Audit
- [ ] `uv run pytest` executes with all tests passing.
- [ ] Milestone 5 review, challenger, and auditor swarm completes evaluation and records gate status in `PROJECT.md`.
- [ ] Discrepancy analysis completed identifying gaps between simulated test suites and live desktop hardware/OS behavior.

### Safe Live Verification & Model Inspection
- [ ] Model asset inspection completed confirming whether local model files exist and whether they load within the 8 GB VRAM budget.
- [ ] Companion dock launched and verified in dry-run mode without taking over mouse or keyboard.
- [ ] No live mouse or keyboard takeover executed without prior explicit user consent.

### Cleanup
- [ ] `test_none.yaml` and `test_none2.yaml` removed from the repository.
- [ ] Repository root `__pycache__` directory removed.
- [ ] "BAczier" typo corrected in `PROJECT.md`.

### Prioritized Plan
- [ ] Concrete, prioritized action plan delivered outlining the exact sequence of live verification steps and completion roadmap.
