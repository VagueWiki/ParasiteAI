# Task Assignment: Milestone M4 Reviewer 2 (Memory, Dual-Mind & Browser Offload)

**Recipient**: `teamwork_reviewer_m4_2`
**Role**: `teamwork_reviewer`
**Working Directory**: `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_reviewer_m4_2\`
**Assigned Milestone**: Milestone M4 — Perception, Memory & Browser Brain Offload

---

## Focus Area: Features 13, 14, 15 — Episodic Memory, Dual-Mind Pipeline & Browser Offloader
1. Inspect implementation files:
   - `parasite_ai/mind/memory.py`
   - `parasite_ai/mind/dual_mind.py`
   - `parasite_ai/mind/offloader.py`
   - `parasite_ai/mind/__init__.py`
   - `tests/test_memory.py`
   - `tests/test_dual_mind.py`
   - `tests/test_browser_offloader.py`
2. Inspect compatibility with:
   - `parasite_ai/safety/interrupt_guard.py` (sub-2ms hardware cancellation token preemption)
   - `parasite_ai/safety/window_guard.py` (sensitive window blocking)
   - `parasite_ai/hands/mouse.py` & `keyboard.py` (physical driver invocation)
   - `parasite_ai/mind/brain_manager.py` (`BrowserOffloadBackend` integration)
3. Verification Tasks:
   - Run `uv run pytest tests/test_memory.py tests/test_dual_mind.py -v`
   - Run `uv run pytest tests/test_browser_offloader.py -v`
   - Run `uv run pytest` (verify 100% pass across all 475 tests, 0 regressions)
   - Verify 3-strike loop detector (trips on 3 strikes, resets on $\text{diff} \ge 0.02$)
   - Verify Sentinel Clipboard Verification (backup -> inject UUID -> poll -> guaranteed restore in `finally:`)
   - Verify Pass 1 `PersonaEngine` monologue & Pass 2 `ActionDispatcher` validation
4. Review Verdict:
   - Must conclude with an explicit binary verdict: `APPROVE` or `REQUEST_CHANGES`.
   - Write handoff report in `handoff.md`.
   - Notify orchestrator via `send_message`.


## 2026-10-29T17:17:59Z
[Message] timestamp=2026-10-29T17:17:59Z sender=9a16f679-6db4-4849-ba56-0f4856cbbf9b priority=MESSAGE_PRIORITY_HIGH content=You are assigned as Milestone M4 Reviewer 2 (`teamwork_reviewer_m4_2`).

Working Directory:
`g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_reviewer_m4_2\`

Read your full dispatch instructions:
`g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_reviewer_m4_2\DISPATCH.md`

MANDATORY FIRST ACTIONS:
1. Initialize your `BRIEFING.md` and `progress.md` in your working directory.
2. Read `g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md`.
3. Read `g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md`.

REVIEW FOCUS:
- Features 13, 14, 15: Episodic Memory, Dual-Mind Pipeline & Visible Browser Offloader (`parasite_ai/mind/memory.py`, `parasite_ai/mind/dual_mind.py`, `parasite_ai/mind/offloader.py`, `parasite_ai/mind/__init__.py`, `tests/test_memory.py`, `tests/test_dual_mind.py`, `tests/test_browser_offloader.py`).
- Inspect 3-strike failure loop detector, Pass 1 `PersonaEngine` monologue & Pass 2 `ActionDispatcher` preemption, Sentinel Clipboard Verification protocol, and `LocalBrainManager.BrowserOffloadBackend` integration.
- Run `uv run pytest tests/test_memory.py tests/test_dual_mind.py -v`, `uv run pytest tests/test_browser_offloader.py -v`, and `uv run pytest`.
- Deliver an explicit binary verdict: `APPROVE` or `REQUEST_CHANGES` in `handoff.md`.
- Notify the orchestrator via `send_message`.
