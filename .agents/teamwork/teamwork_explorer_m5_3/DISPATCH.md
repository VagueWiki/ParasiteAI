# Task Assignment: Milestone M5 Explorer 3 (E2E Test Architecture & Acceptance Verification)

**Recipient**: `teamwork_explorer_m5_3`
**Role**: `teamwork_explorer`
**Working Directory**: `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m5_3\`
**Assigned Milestone**: Milestone M5 — Integration, Entry Points & E2E Acceptance

---

## Focus Area: Feature 18 — E2E Test Suite & Acceptance Verification (`tests/test_e2e_integration.py`)
1. **Requirements to Analyze**:
   - `ORIGINAL_REQUEST.md` (Acceptance Criteria: Automated Verification & Live Desktop Operation).
   - `PROJECT.md` Feature 18 (E2E Acceptance & Tier 5 Adversarial Coverage Hardening).
2. **Architecture & Scope**:
   - Derive comprehensive opaque-box and closed-loop integration test scenarios:
     - Scenario 1: Clean Startup & Zero-Config Default Boot (verifying `main.py --dry-run` or headless startup without crashing).
     - Scenario 2: End-to-End Goal Execution Cycle (Goal input -> Grounding Set-of-Mark -> Persona Speech -> Reticle Display -> Curved Mouse Move -> Action Dispatch -> Diff Calculation -> Step Telemetry Update).
     - Scenario 3: Physical Hardware Touch Interruption (<2ms abort, atomic token set, synthetic actions aborted, dock transitions to `USER_OVERRIDE`).
     - Scenario 4: Sensitive Window Detection & Privacy Blackout (`WindowGuard` detect password manager -> perception feed blacked out -> dock transitions to `PROTECTED` -> actions blocked).
     - Scenario 5: 3-Strike Failure Loop Emergency Reset (3 repeated no-diff actions -> loop detector fires `is_in_loop()` -> emergency PANIC recovery triggered).
     - Scenario 6: Zero-VRAM Visible Browser Brain Offload (fallback to `BrowserOffloadBackend` -> visible Chrome automation -> Sentinel Clipboard Verification with guaranteed restore).
3. **Investigation Tasks**:
   - Design test harness and mockable backends for running all 6 scenarios deterministically under `uv run pytest` in headless CI without requiring physical displays or human hands.
   - Formulate exact test assertions, fixture setups, and timing guarantees.
4. **Deliverables**:
   - Write comprehensive implementation plan in `plan.md`.
   - Write handoff report in `handoff.md`.
   - Notify orchestrator via `send_message`.


## 2026-10-29T17:30:38Z
You are assigned as Milestone M5 Explorer 3 (`teamwork_explorer_m5_3`).

Working Directory:
`g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m5_3\`

Read your full dispatch instructions:
`g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m5_3\DISPATCH.md`

MANDATORY FIRST ACTIONS:
1. Initialize your `BRIEFING.md` and `progress.md` in your working directory.
2. Read `g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md`.
3. Read `g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md`.

EXPLORER FOCUS:
- Feature 18: E2E Test Suite & Acceptance Verification (`tests/test_e2e_integration.py`).
- Design 6 comprehensive end-to-end integration scenarios (Startup, Closed-Loop Goal Execution, Hardware Touch Interruption in <2ms, Sensitive Window Blackout, 3-Strike Loop PANIC Recovery, Zero-VRAM Browser Offload).
- Author comprehensive `plan.md` and `handoff.md`.
- Notify the orchestrator via `send_message`.
