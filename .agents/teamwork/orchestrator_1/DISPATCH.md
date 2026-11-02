# Dispatch Log

## 2026-10-31T11:27:08Z

Implement Phase 3 (Execution Loop Hardening: localized ROI diffing, Win32 caret focus verification, and Start Search cadence buffer) in ParasiteAI, verifying existing test suite status and preserving all safety invariants.

Working directory: C:\ParasiteAI
Integrity mode: development

## Reference Material
- C:\ParasiteAI\HANDOFF.md
- c:\Users\Suici\.gemini\antigravity\brain\4f451e87-09d8-43e7-a3e6-787b1848b093\definitive_master_plan_and_roadmap.md

## Requirements

### R1. Localized ROI Diffing (Phase 3A)
Implement localized ROI diffing in `parasite_ai/mind/dual_mind.py` by scoping post-action visual difference verification to the target bounding box padded by 20 pixels (`target_bbox.pad(20px)`) rather than full desktop diffing, avoiding false positives from desktop background updates or system tray changes.

### R2. Win32 Caret Focus Verification (Phase 3B)
Implement Win32 caret focus verification for text entry using `GetGUIThreadInfo` to verify that `flags & GUI_CARETBLINKING` or `hwndCaret != 0` before emitting `TYPE` actions.

### R3. Start Search Cadence Buffer (Phase 3C)
Implement a 250ms cadence buffer in `parasite_ai/mind/resolver.py` (`UniversalAppResolver`) after the `Win` key chord before typing application names to avoid dropping characters while the Windows Search UI initializes.

### R4. Test Suite and Architectural Invariants
Ensure all existing 797 tests in `tests/` pass (`uv run pytest`) and write new unit tests covering 3A, 3B, and 3C with mocks for Win32 GUI APIs and timing. Maintain all architectural invariants: sub-2ms hardware touch preemption, Ctrl+Alt+K hard kill, `brain.mode: "local_llm"`, strict anti-hardcoding rule (no application-specific branching), and dual-monitor virtual desktop coordinate safety (3840x1080 @ 100% DPI).

## Acceptance Criteria

### Implementation
- [ ] Visual verification in `parasite_ai/mind/dual_mind.py` uses localized ROI diffing scoped to `target_bbox.pad(20px)`.
- [ ] Caret focus verification is called prior to `TYPE` actions via `GetGUIThreadInfo`, checking `GUI_CARETBLINKING` or non-zero `hwndCaret`.
- [ ] A 250ms cadence pause is enforced in `parasite_ai/mind/resolver.py` between the `Win` key trigger and typing the target application name.
- [ ] No application-specific branching or hardcoded lookup tables are added.

### Verification & Testing
- [ ] All 797 existing tests in `tests/` continue to pass without regression.
- [ ] Unit tests for 3A (padded ROI diffing), 3B (Win32 caret focus check with mocked GUI thread info), and 3C (250ms search cadence buffer) are added and passing in `uv run pytest`.
- [ ] Low-level safety hooks (sub-2ms touch preemption and Ctrl+Alt+K hard kill) remain functional.
