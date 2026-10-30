# BRIEFING — 2026-10-29T15:54:30Z

## Mission
Investigate and design technical specifications and implementation plan for the Ghost-Hand Screen Overlay HUD (`parasite_ai/ui/ghost_hud.py`) in Milestone M3. [COMPLETED]

## 🔒 My Identity
- Archetype: explorer
- Roles: investigator, architect, plan-generator
- Working directory: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m3_2
- Original parent: 9a16f679-6db4-4849-ba56-0f4856cbbf9b
- Milestone: M3 (Desktop Companion Dock & Ghost-Hand Overlay)

## 🔒 Key Constraints
- Read-only investigation — do NOT implement production code
- Win32 extended window styles applied via `user32.SetWindowLongW` on `self.winId()`
- Full virtual desktop coverage (`QGuiApplication.primaryScreen().virtualGeometry()`)
- Click-through transparent overlay (`WS_EX_LAYERED`, `WS_EX_TRANSPARENT`, `WS_EX_TOPMOST`, `WS_EX_NOACTIVATE`, `WS_EX_TOOLWINDOW`)
- High-contrast Set-of-Mark (SoM) bounding boxes & pill badges with category colors
- 300ms pre-click targeting reticle, aiming banner, and Bézier path preview
- Headless testability and simulation verification using `pytest-qt`

## Current Parent
- Conversation ID: 9a16f679-6db4-4849-ba56-0f4856cbbf9b
- Updated: 2026-10-29T15:54:30Z

## Investigation State
- **Explored paths**:
  - `parasite_ai/config.py` (GhostHUDConfig, UIConfig, MouseConfig)
  - `parasite_ai/hands/kinematics.py` (Cubic Bézier control points formula)
  - `parasite_ai/hands/mouse.py` (reticle_callback hook, cancellation token handling)
  - `pyproject.toml` (PyQt6 6.12.0 and pytest-qt 4.5.0 pinned)
  - Win32 API (`user32.SetWindowLongW`, `GWL_EXSTYLE`, extended window styles)
  - Multi-monitor virtual geometry and coordinate offsetting
- **Key findings**:
  - Win32 extended window styles (`WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW`) verified on PyQt6 QWidget.
  - Full virtual desktop geometry verified (`(0, 0, 3840, 1080)` on test machine).
  - Pre-click reticle countdown (300ms) aligns with `MouseDriver.reticle_callback`.
  - Headless test execution verified via `widget.render(pixmap)` and `qtbot.waitSignal`.
- **Unexplored areas**: None for GhostHUD overlay; dock and integration handled by peer explorers.

## Key Decisions Made
- Architecture specified in `plan.md` with full code implementation sketch.
- 5-Component handoff report generated in `handoff.md`.
- Normalized `HUDTarget` data class handles dicts, Pydantic `UIElement`, and duck-typed objects.
- Role-based color palette mapped: Cyan (Buttons), Magenta (Edits), Amber (OCR), Blue (Links).
- Dynamic contracting reticle (32px to 16px radius) with floating banner and Bézier trajectory preview.

## Artifact Index
- `DISPATCH.md` — Task assignment and requirements
- `plan.md` — Comprehensive technical implementation plan
- `handoff.md` — 5-Component hard handoff report
- `progress.md` — Liveness and status heartbeat
