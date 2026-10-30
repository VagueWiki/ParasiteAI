# Task Assignment: Milestone M5 Explorer 2 (End-to-End Subsystem Wiring & Closed-Loop Integration)

**Recipient**: `teamwork_explorer_m5_2`
**Role**: `teamwork_explorer`
**Working Directory**: `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m5_2\`
**Assigned Milestone**: Milestone M5 — Integration, Entry Points & E2E Acceptance

---

## Focus Area: End-to-End Subsystem Wiring & Closed-Loop Integration
1. **Requirements to Analyze**:
   - `ORIGINAL_REQUEST.md` (Live Desktop Operation and Verification Invariants).
   - `PROJECT.md` Feature 18 & Interface Contracts.
2. **Architecture & Scope**:
   - Full closed-loop data flow:
     1. User types goal in `CompanionDock` Goal input -> emits `goal_submitted` -> enqueued in `UIBridge._goal_queue`.
     2. Cognitive background worker dequeues goal -> sets state `THINKING` via `bridge.notify_state`.
     3. Screen Grounding captures screen & runs UIA/OCR -> sends elements to `GhostHUD` (`bridge.set_hud_targets`) and `CompanionDock` thumbnail (`bridge.notify_perception`).
     4. Pass 1 Persona monologue generated -> streamed to dialogue typewriter and thought stream (`bridge.notify_speech`, `bridge.notify_thought`).
     5. Pass 2 Action generated (`CLICK [#N]`, `TYPE`, etc.) -> sets state `DRIVING`.
     6. Target coordinates resolved -> 300ms pre-click reticle displayed on `GhostHUD` (`bridge.show_reticle`).
     7. Kinematic curved mouse movement executed with sub-2ms hardware interrupt check.
     8. Action settles -> screen diff computed -> recorded in `EpisodicMemory`.
     9. Step telemetry updated on dock progress bar (`bridge.notify_telemetry`).
     10. If 3 strikes occur -> 3-strike loop detector fires emergency PANIC reset.
     11. If physical hardware touch occurs -> `InterruptGuard` trips in <2ms, halts synthetic actions, dock sets `USER_OVERRIDE`.
     12. If sensitive window becomes foreground -> `WindowGuard` halts observation, dock sets `PROTECTED`, vision blacks out.
3. **Investigation Tasks**:
   - Trace all signal connections between `UIBridge`, `CompanionDock`, `GhostHUD`, `DualMindPipeline`, `InterruptGuard`, and `WindowGuard`.
   - Identify any missing signal parameters or threading race conditions.
   - Formulate a cohesive runtime orchestrator class or loop runner (`parasite_ai/runtime.py` or integrated into `main.py`).
4. **Deliverables**:
   - Write comprehensive implementation plan in `plan.md`.
   - Write handoff report in `handoff.md`.
   - Notify orchestrator via `send_message`.


## 2026-10-29T17:30:28Z
You are assigned as Milestone M5 Explorer 2 (`teamwork_explorer_m5_2`).

Working Directory:
`g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m5_2\`

Read your full dispatch instructions:
`g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m5_2\DISPATCH.md`

MANDATORY FIRST ACTIONS:
1. Initialize your `BRIEFING.md` and `progress.md` in your working directory.
2. Read `g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md`.
3. Read `g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md`.

EXPLORER FOCUS:
- End-to-End Subsystem Wiring & Closed-Loop Integration (`parasite_ai/runtime.py` or `main.py`).
- Trace and connect all signals between `UIBridge`, `CompanionDock`, `GhostHUD`, `DualMindPipeline`, `InterruptGuard`, and `WindowGuard`.
- Verify goal submission -> thinking -> perception -> monologue speech -> Set-of-Mark reticle -> kinematic driving -> screen diff -> memory record -> loop reset.
- Author comprehensive `plan.md` and `handoff.md`.
- Notify the orchestrator via `send_message`.
