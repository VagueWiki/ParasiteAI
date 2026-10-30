# BRIEFING — 2026-10-29T16:54:00Z

## Mission
Investigate and design Feature 12 (Hybrid Screen Grounding in `parasite_ai/vision/grounding.py`), detailing Win32 UI Automation tree walking, scoped RapidOCR fallback, spatial IoU deduplication, bounding box normalization to `list[UIElement]`, HUD/Dock integration, and automated headless test strategy.

## 🔒 My Identity
- Archetype: explorer
- Roles: explorer
- Working directory: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m4_1\
- Original parent: 9a16f679-6db4-4849-ba56-0f4856cbbf9b
- Milestone: Milestone M4 — Perception, Memory & Browser Brain Offload

## 🔒 Key Constraints
- Read-only investigation — do NOT implement
- Feature 12: Hybrid Screen Grounding (`parasite_ai/vision/grounding.py`)
- Win32 UI Automation tree walking + scoped RapidOCR fallback
- Spatial IoU deduplication, bounding box normalization to `list[UIElement]`
- Integration with GhostHUD Set-of-Mark and CompanionDock
- Performance budget: full grounding scan in < 500ms
- Formulate complete implementation plan and headless test strategy
- Produce plan.md and handoff.md; notify orchestrator via send_message

## Current Parent
- Conversation ID: 9a16f679-6db4-4849-ba56-0f4856cbbf9b
- Updated: 2026-10-29T16:47:11Z

## Investigation State
- **Explored paths**:
  - `ORIGINAL_REQUEST.md`, `PROJECT.md`, `pyproject.toml`, `config.yaml`
  - `parasite_ai/ui/types.py`, `parasite_ai/ui/ghost_hud.py`, `parasite_ai/ui/companion_dock.py`, `parasite_ai/ui/bridge.py`
  - `parasite_ai/config.py` (`VisionConfig`, `GhostHUDConfig`, `CompanionDockConfig`)
  - Runtime libraries: `uiautomation`, `rapidocr_onnxruntime`, `mss`, `PIL`, `numpy`
- **Key findings**:
  - Full test suite baseline: 424 passed in 30.24s.
  - `uiautomation` and `rapidocr_onnxruntime` verified operational on Python 3.12.
  - `GetForegroundControl()` returns `None` in background/headless context; fallback to `GetRootControl()` or explicit `window_filter: int` HWND is required.
  - RapidOCR warm latency is ~100-500ms on CPU; scoping OCR strictly to the active window rectangle keeps inference within the latency budget.
  - Screen grab (`mss` and `PIL.ImageGrab`) raises `BitBlt` or `OSError` in headless/locked desktop sessions; `ScreenCapture` must handle these gracefully with synthetic fallbacks.
  - Spatial deduplication requires both IoU ($\ge 0.35$) and containment ratio ($\ge 0.70$) to catch internal text labels inside buttons and merge them into UIA labels.
  - `GhostHUD.set_targets()` and `CompanionDock.update_perception_preview()` already interoperate with `UIElement`.
- **Unexplored areas**: None. Complete investigation achieved.

## Key Decisions Made
- Use three-tier hierarchy: Tier 1 (Win32 UIA tree walk with depth limit 5 and max 120 nodes), Tier 2 (Scoped RapidOCR on active window bounds triggered when UIA yields < 6 controls), Tier 3 (Spatial IoU $\ge 0.35$ and containment $\ge 0.70$ deduplication).
- Sequential 1-based Set-of-Mark numbering [#1..#N] capped by `VisionConfig.max_som_elements` (default 60).
- Headless test strategy mocking UIA trees and RapidOCR engine to guarantee 100% CI pass rate.

## Artifact Index
- `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m4_1\DISPATCH.md` — Initial assignment
- `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m4_1\BRIEFING.md` — Persistent situational memory
- `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m4_1\progress.md` — Liveness heartbeat (COMPLETED)
- `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m4_1\plan.md` — Complete implementation plan
- `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m4_1\handoff.md` — Complete 5-component handoff report
