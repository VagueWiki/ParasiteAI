# BRIEFING — 2026-10-29T11:05:00Z

## Mission
Survey, analyze, and detail technical requirements, specifications, interfaces, and constraints for R2 (Companion GUI & Ghost-Hand HUD), R4 (Perception, Cognition, Browser Offload), and R5 (Entry Points & Test Suite).

## 🔒 My Identity
- Archetype: explorer
- Roles: investigator, synthesis
- Working directory: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_survey_3
- Original parent: 9a16f679-6db4-4849-ba56-0f4856cbbf9b
- Milestone: Survey R2, R4, R5

## 🔒 Key Constraints
- Read-only investigation — do NOT implement source code
- Focus strictly on R2, R4, and R5 requirements, interfaces, data formats, and constraints
- Output comprehensive survey report to `survey_report.md` and standard 5-component report to `handoff.md`

## Current Parent
- Conversation ID: 9a16f679-6db4-4849-ba56-0f4856cbbf9b
- Updated: 2026-10-29T10:57:29Z

## Investigation State
- **Explored paths**: 
  - `g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md`
  - `C:\Users\Suici\.gemini\antigravity\brain\9febbb50-4316-49f8-85fe-f612a778b2d3\implementation_plan.md`
  - Host environment verification via `uv` (Windows 11, uv 0.11.7, package dependency resolution dry-run).
- **Key findings**:
  - Validated clean dependency resolution for PyQt6, mss, rapidocr-onnxruntime, uiautomation, pyperclip, pynput, pydantic, pyyaml, pytest.
  - Specified PyQt6 Companion Dock architecture (states, moods, speech/thought streams, telemetry, controls, DPI awareness).
  - Specified Win32 transparent click-through Ghost-Hand HUD (`WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE | WS_EX_TOPMOST`), Set-of-Mark numbered tags, and 300ms pre-click reticle.
  - Formulated 3-tier Zero-VRAM perception (UIA tree walk + scoped RapidOCR fallback + spatial deduplication).
  - Designed Dual-Mind cognitive pipeline (Pass 1 Persona unconstrained voice + Pass 2 Action Dispatcher strict JSON schema) and Episodic Working Memory with loop detection.
  - Established Visible Browser Brain Offload state machine for Chrome/Opera with Sentinel Clipboard verification protocol (guaranteeing zero clipboard corruption and zero data leakage).
  - Outlined entry points (`main.py`, `launch_parasite.bat`) and comprehensive automated test suite under `tests/`.
- **Unexplored areas**: None within the scope of R2, R4, R5 survey. All technical requirements, interfaces, and constraints are enumerated in `survey_report.md`.

## Key Decisions Made
- Fully documented all data models (`UIElement`, `ActionPlan`, `StepRecord`) in `survey_report.md`.
- Recommended Per-Monitor DPI awareness (`SetProcessDpiAwareness(2)`) to eliminate coordinate scaling bugs.
- Decoupled PyQt6 main UI thread from background engine loop via `pyqtSignal`.

## Artifact Index
- `DISPATCH.md` — incoming dispatch instructions with UTC timestamps
- `BRIEFING.md` — persistent working memory
- `progress.md` — liveness heartbeat
- `survey_report.md` — complete technical survey findings for R2, R4, R5
- `handoff.md` — standard 5-component handoff report
