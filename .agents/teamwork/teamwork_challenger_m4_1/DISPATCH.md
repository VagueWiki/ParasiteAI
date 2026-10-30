# Task Assignment: Milestone M4 Challenger 1 (Screen Grounding Adversarial Stress)

**Recipient**: `teamwork_challenger_m4_1`
**Role**: `teamwork_challenger`
**Working Directory**: `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_challenger_m4_1\`
**Assigned Milestone**: Milestone M4 — Perception, Memory & Browser Brain Offload

---

## Adversarial Focus: Feature 12 — Hybrid Screen Grounding Edge Cases
1. Target Modules:
   - `parasite_ai/vision/grounding.py`
   - `parasite_ai/vision/capture.py`
   - `tests/test_grounding.py`
2. Challenge Objectives:
   - Write an adversarial stress test suite in `tests/test_challenger_m4_1.py` (or similar).
   - Test extreme spatial IoU scenarios: concentric boxes, zero-area boxes, negative coordinates, overlapping bounding boxes at exact threshold boundary (0.349 vs 0.351), containment at 0.699 vs 0.701.
   - Test UIA tree depth blowout: deep trees > 15 levels, trees with 500+ controls (verify max depth and element count clamping).
   - Test RapidOCR fallback under corrupted or non-standard image arrays (e.g., 1x1 image, pure black, pure white, 16-bit or RGBA/BGRA channel permutations).
   - Test degenerate Set-of-Mark generation: elements with missing labels, empty strings, control types outside `INTERACTIVE_ROLES`.
   - Verify that all existing and new tests pass: `uv run pytest`.
3. Challenge Verdict:
   - Conclude with an explicit binary verdict: `APPROVE` (if code handles all adversarial stresses cleanly) or `REQUEST_CHANGES` (if defects/crashes discovered).
   - Write handoff report in `handoff.md`.
   - Notify orchestrator via `send_message`.


## 2026-10-29T17:18:06Z
You are assigned as Milestone M4 Challenger 1 (`teamwork_challenger_m4_1`).

Working Directory:
`g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_challenger_m4_1\`

Read your full dispatch instructions:
`g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_challenger_m4_1\DISPATCH.md`

MANDATORY FIRST ACTIONS:
1. Initialize your `BRIEFING.md` and `progress.md` in your working directory.
2. Read `g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md`.
3. Read `g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md`.

ADVERSARIAL STRESS CHALLENGE:
- Stress-test Feature 12 (Hybrid Screen Grounding: `parasite_ai/vision/grounding.py`, `parasite_ai/vision/capture.py`, `tests/test_grounding.py`).
- Create an adversarial test suite (e.g. `tests/test_challenger_m4_1.py`) covering:
  - Extreme spatial IoU boundaries (0.349 vs 0.351, concentric, zero-area, negative coords).
  - Deep UIA trees (>15 levels, 500+ elements) verifying depth and count limits.
  - Corrupted/unusual image arrays to RapidOCR (1x1, black, white, 16-bit, RGBA/BGRA).
  - Degenerate Set-of-Mark tags (empty labels, non-standard control types).
- Run `uv run pytest tests/test_challenger_m4_1.py -v` and `uv run pytest`.
- Conclude with an explicit binary verdict: `APPROVE` or `REQUEST_CHANGES` in `handoff.md`.
- Notify the orchestrator via `send_message`.
