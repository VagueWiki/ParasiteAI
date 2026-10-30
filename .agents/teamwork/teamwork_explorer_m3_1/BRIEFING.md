# BRIEFING — 2026-10-29T15:52:00Z

## Mission
Analyze requirements and produce complete technical implementation plan and specifications for the Companion Dock GUI (`parasite_ai/ui/companion_dock.py`) in Milestone M3.

## 🔒 My Identity
- Archetype: explorer
- Roles: investigation, synthesis
- Working directory: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m3_1\
- Original parent: 9a16f679-6db4-4849-ba56-0f4856cbbf9b
- Milestone: M3 — Desktop Companion Dock & Ghost-Hand Overlay

## 🔒 Key Constraints
- Read-only investigation — do NOT implement
- Deliverables: plan.md, handoff.md, progress.md
- PyQt6 architecture with headless testability via pytest-qt (qtbot)

## Current Parent
- Conversation ID: 9a16f679-6db4-4849-ba56-0f4856cbbf9b
- Updated: 2026-10-29T15:47:40Z

## Investigation State
- **Explored paths**:
  - `ORIGINAL_REQUEST.md`, `PROJECT.md`, `survey_report.md`
  - `parasite_ai/config.py` (`UIConfig`, `CompanionDockConfig`)
  - `pyproject.toml`, test suite (321/321 passing)
  - Peer explorer dispatches (`m3_2`, `m3_3`)
- **Key findings**:
  - Frameless always-on-top window requires `WindowStaysOnTopHint | FramelessWindowHint | Tool` + `WA_TranslucentBackground`.
  - Screen anchoring uses `availableGeometry()` to account for taskbar height.
  - 6-state visual palette defined (`WATCHING`, `THINKING`, `DRIVING`, `USER_OVERRIDE`, `OFFLOADING`, `PROTECTED`).
  - Dual-mind presentation decouples high-contrast dialogue bubble from muted italic internal thoughts.
  - Live perception preview integrates sensitive window privacy masking (`PROTECTED` state blacks out thumbnail).
  - Complete `CompanionSignals` Qt architecture with queued connections provides thread-safe GUI updates.
  - Test matrix for `pytest-qt` (`qtbot`) covers all interactive controls and signal emissions.
- **Unexplored areas**: None within Explorer 1 scope.

## Key Decisions Made
- Anchoring algorithm derived strictly against `availableGeometry()` with 24px margins.
- Drag-and-drop boundary clamping ensures header grip cannot be moved completely offscreen.
- State transitions dynamically update border glow and pill badge styling.
- Privacy mask automatically overrides perception thumbnail on `PROTECTED` state.
- All controls wired to standard Qt signals with slot bridges for thread safety.

## Artifact Index
- DISPATCH.md — Task assignment and instructions
- BRIEFING.md — Persistent situational awareness
- progress.md — Liveness heartbeat and progress log
- plan.md — Detailed technical implementation plan for `parasite_ai/ui/companion_dock.py`
- handoff.md — 5-component handoff report
