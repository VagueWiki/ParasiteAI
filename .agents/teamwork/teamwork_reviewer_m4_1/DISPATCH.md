# Task Assignment: Milestone M4 Reviewer 1 (Screen Grounding & Perception)

**Recipient**: `teamwork_reviewer_m4_1`
**Role**: `teamwork_reviewer`
**Working Directory**: `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_reviewer_m4_1\`
**Assigned Milestone**: Milestone M4 — Perception, Memory & Browser Brain Offload

---

## Focus Area: Feature 12 — Hybrid Screen Grounding & Perception
1. Inspect implementation files:
   - `parasite_ai/vision/capture.py`
   - `parasite_ai/vision/grounding.py`
   - `parasite_ai/vision/__init__.py`
   - `tests/test_grounding.py`
2. Inspect compatibility with:
   - `parasite_ai/ui/types.py` (`UIElement` contract, Set-of-Mark 1-based indexing, `@computed_field bbox`, `@computed_field center`)
   - `parasite_ai/ui/ghost_hud.py` (`GhostHUD.set_targets`)
   - `parasite_ai/ui/companion_dock.py` (`CompanionDock.update_perception_preview`)
   - `parasite_ai/ui/bridge.py` (`UIBridge.set_hud_targets`, `UIBridge.notify_perception`)
3. Verification Tasks:
   - Run `uv run pytest tests/test_grounding.py -v`
   - Run `uv run pytest` (verify 100% pass across all 475 tests, 0 regressions)
   - Inspect Tier 1 UIA tree walk (depth limit 5, max 120 elements, interactive controls filter)
   - Inspect Tier 2 Scoped RapidOCR fallback (active window crop, coordinates map)
   - Inspect Tier 3 Spatial IoU ($\ge 0.35$) and Containment ($\ge 0.70$) deduplication and label merging
4. Review Verdict:
   - Must conclude with an explicit binary verdict: `APPROVE` or `REQUEST_CHANGES`.
   - Write handoff report in `handoff.md`.
   - Notify orchestrator via `send_message`.


## 2026-10-29T17:17:52Z
[Message] timestamp=2026-10-29T17:17:52Z sender=9a16f679-6db4-4849-ba56-0f4856cbbf9b priority=MESSAGE_PRIORITY_HIGH content=You are assigned as Milestone M4 Reviewer 1 (`teamwork_reviewer_m4_1`).

Working Directory:
`g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_reviewer_m4_1\`

Read your full dispatch instructions:
`g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_reviewer_m4_1\DISPATCH.md`

MANDATORY FIRST ACTIONS:
1. Initialize your `BRIEFING.md` and `progress.md` in your working directory.
2. Read `g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md`.
3. Read `g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md`.

REVIEW FOCUS:
- Feature 12 — Hybrid Screen Grounding (`parasite_ai/vision/capture.py`, `parasite_ai/vision/grounding.py`, `parasite_ai/vision/__init__.py`, `tests/test_grounding.py`).
- Inspect Tier 1 UIA tree walking, Tier 2 Scoped RapidOCR, Tier 3 IoU and containment deduplication, and `UIElement` contracts.
- Run `uv run pytest tests/test_grounding.py -v` and `uv run pytest`.
- Deliver an explicit binary verdict: `APPROVE` or `REQUEST_CHANGES` in `handoff.md`.
- Notify the orchestrator via `send_message`.
