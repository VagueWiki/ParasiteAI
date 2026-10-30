# Task Assignment: Milestone M4 Explorer 2 (Episodic Memory & Dual-Mind Pipeline)

**Recipient**: `teamwork_explorer_m4_2`
**Role**: `teamwork_explorer`
**Working Directory**: `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m4_2\`
**Assigned Milestone**: Milestone M4 — Perception, Memory & Browser Brain Offload

---

## Focus Area: Features 13 & 14 — Episodic Working Memory & Dual-Mind Pipeline
1. **Requirements to Analyze**:
   - `ORIGINAL_REQUEST.md` (Requirement R4 & Dual-Mind Pipeline: Pass 1 Monologue vs Pass 2 Action).
   - `PROJECT.md` Features 13 & 14 & survey reports.
2. **Architecture & Scope**:
   - `parasite_ai/mind/memory.py`:
     - Episodic memory ring-buffer: tracking the last N actions, targets, screenshots (or perceptual hashes), and perceived results.
     - Screen diff verification: computing visual state change before/after action execution (pixel diff threshold or structural similarity hash) to confirm action impact.
     - 3-strike failure loop detection: identifying repeated identical actions without meaningful screen changes; triggering cognitive panic/strategy switch/user escalation if 3 consecutive strikes occur.
   - `parasite_ai/mind/dual_mind.py`:
     - Pass 1: Persona monologue generation — synthesizes user goal, screen state, and episodic memory into character reasoning, speech bubble message, and mood derivation (`WATCHING`, `THINKING`, `DRIVING`, etc.).
     - Pass 2: Deterministic Action Dispatcher — parses/enforces structured JSON schema (`CLICK`, `TYPE`, `SCROLL`, `WAIT`, `HOTKEY`, `PANIC`), resolves target coordinates via `ScreenGrounder` or explicit `(x, y)`, validates screen boundaries, and calls physical hands (`MouseDriver`, `KeyboardDriver`).
3. **Investigation Tasks**:
   - Inspect existing `ActionParser` in `parasite_ai/mind/brain_manager.py`, `MouseDriver`, `KeyboardDriver`, `InterruptGuard`, and `UIBridge`.
   - Design class contracts: `EpisodicMemory`, `DualMindPipeline`, `ActionDispatcher`.
   - Specify automated test strategy in `tests/test_memory.py` and `tests/test_dual_mind.py`.
4. **Deliverables**:
   - Write comprehensive implementation plan in `plan.md`.
   - Write handoff report in `handoff.md`.
   - Notify orchestrator via `send_message`.


## 2026-10-29T16:54:21Z
**Context**: Milestone M4 (Perception, Memory & Dual-Mind Pipeline).
**Content**: Explorer 1 (`teamwork_explorer_m4_1`) and Explorer 3 (`teamwork_explorer_m4_3`) have both completed their plans and handoffs. Checking in on your progress regarding Features 13 & 14 (Episodic Memory & Dual-Mind Cognitive Pipeline).
**Action**: Please provide an update on your progress or deliver your `plan.md` and `handoff.md` once complete.
