# Dispatch Messages

## 2026-10-29T10:55:53Z

Build ParasiteAI, a 100% visible, desktop-native local AI assistant operating on the user's physical desktop with zero headless browsers, zero invisible scrapers, and zero CLI-only interfaces, starting as a functional desktop prototype engineered with a clean path to production.

Working directory: g:\__Docs\ParasiteAI
Integrity mode: development

Reference material: C:\Users\Suici\.gemini\antigravity\brain\9febbb50-4316-49f8-85fe-f612a778b2d3\implementation_plan.md

## Requirements

### R1. Foundation & Zero-Config Local Brain Setup
Set up the Python 3.12 project environment using uv with pyproject.toml, configuration in config.yaml, and a local brain manager supporting local model management and browser-offload coordination.

### R2. Visible Desktop Companion GUI & Ghost-Hand Overlay
Provide an always-on-top desktop companion dock displaying live character speech and thoughts, state and mood indicators (WATCHING, THINKING, DRIVING, OFFLOADING, USER OVERRIDE), live perception feed, goal input, and pause/panic controls, alongside a click-through transparent Win32 screen overlay (Ghost-Hand HUD) that renders numbered Set-of-Mark targeting boxes and a 300ms pre-click reticle over real desktop controls.

### R3. Safety & Physical Input Layer
Implement physical mouse and keyboard control with human-looking mouse movements (utilizing human-like kinematic curves, realistic acceleration/deceleration, micro-jitter, and slight overshoot rather than mechanical or straight-line jumps) and Unicode typing, backed by Win32 low-level hardware hooks filtering synthetic vs physical input to instantly abort actions in <2ms on physical hardware touch, a global panic abort mechanism, and a window guard pausing actions when sensitive windows are active.

### R4. Perception, Cognition & Visible Browser Brain Offload
Implement hybrid screen grounding combining Win32 UI Automation and OCR, episodic working memory tracking action history and screen diff verification, a dual-mind cognitive pipeline (Persona voice pass + Action Dispatcher pass), and a visible browser offload state machine configured for Google Chrome to physically interact with web AI and harvest responses via sentinel clipboard verification without corrupting user clipboard contents.

### R5. Entry Points & Verification Test Suite
Provide execution entry points (main.py and launch_parasite.bat) and an automated test suite under tests/ covering interrupt guard, grounding, memory, and offloader logic executed via uv run pytest.

## Acceptance Criteria

### Automated Verification
- [ ] `uv run pytest` executes with all tests passing.
- [ ] Test verifies synthetic input events (`LLMHF_INJECTED = 1`) do not trigger an interrupt, while physical hardware input (`LLMHF_INJECTED = 0`) aborts mouse movement in < 2ms.
- [ ] Test verifies hybrid screen grounding locates desktop UI elements with coordinates.
- [ ] Test verifies episodic working memory detects consecutive action failure loops.
- [ ] Test verifies sentinel clipboard verification saves, validates response text, and restores original clipboard contents.

### Live Desktop Operation
- [ ] Launching via `uv run python main.py` or `launch_parasite.bat` starts the companion dock and transparent Ghost-Hand HUD overlay.
- [ ] Companion dock displays live state indicators, character speech area, and interactive controls (pause/resume, goal input).
- [ ] Ghost-Hand HUD overlay renders transparently over the desktop without intercepting user clicks when idle, displaying numbered Set-of-Mark boxes over interactive elements.
- [ ] Mouse driving executes human-looking curved trajectories with natural acceleration/deceleration, overshoot, and micro-jitter preceded by a 300ms targeting preview reticle, avoiding instant teleportation and mechanical straight-line jumps.
- [ ] Physical touch of the mouse or keyboard hardware during synthetic movement instantly halts execution (<2ms).
- [ ] Window guard detects active sensitive/protected windows and pauses assistant observation and physical actions.
- [ ] Browser brain offloading visibly focuses Google Chrome, enters prompts, and extracts responses via verified clipboard interaction.

---
Execution Instructions for Project Orchestrator:
- Working Directory: g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\
- Workspace Directory: g:\__Docs\ParasiteAI
- Original Request: g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md
- Maintain your BRIEFING.md and progress.md in your working directory.
- Dispatch specialists (explorers, workers, reviewers) to execute each milestone.
- Report completion when all requirements and acceptance criteria are satisfied.

## 2026-10-29T13:22:38Z
Heartbeat check: Please update your progress.md with current status of Milestone M2 Gate evaluation.

## 2026-10-29T15:46:00Z
Milestone M2 is confirmed complete. Please proceed immediately with Milestone M3: Desktop Companion Dock & Ghost-Hand Overlay. Dispatch the M3 exploratory swarm or implementation team.


## 2026-10-29T20:54:28Z

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
