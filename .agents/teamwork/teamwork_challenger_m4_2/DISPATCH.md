# Task Assignment: Milestone M4 Challenger 2 (Memory, Dual-Mind & Offloader Adversarial Stress)

**Recipient**: `teamwork_challenger_m4_2`
**Role**: `teamwork_challenger`
**Working Directory**: `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_challenger_m4_2\`
**Assigned Milestone**: Milestone M4 — Perception, Memory & Browser Brain Offload

---

## Adversarial Focus: Features 13, 14, 15 — Memory Loop Detector, Preemption & Sentinel Integrity
1. Target Modules:
   - `parasite_ai/mind/memory.py`
   - `parasite_ai/mind/dual_mind.py`
   - `parasite_ai/mind/offloader.py`
2. Challenge Objectives:
   - Write an adversarial stress test suite in `tests/test_challenger_m4_2.py` (or similar).
   - Test 3-strike failure detector edge cases:
     - 2 failures followed by 1 success -> verify strike count resets to 0.
     - Interactive failures vs non-interactive actions (`WAIT`, `DONE`) -> verify non-interactive actions never trigger strikes.
     - Subtle visual noise ($\Delta \le 15$) vs genuine pixel change ($\Delta > 15$).
     - High-concurrency multithreaded recording to `EpisodicMemory` ring-buffer.
   - Test `ActionDispatcher` preemption:
     - Pre-set `cancellation_token` -> verify instant $<2\text{ms}$ abort without calling physical hands.
     - Out-of-bounds target coordinates (negative or beyond virtual desktop) -> verify structured failure without unhandled exceptions.
     - Unresolvable Set-of-Mark `target_id` (e.g. `target_id = 999` when only 5 exist).
   - Test Sentinel Clipboard Verification under error injection:
     - Mock clipboard raising `RuntimeError` during copy -> verify original user clipboard is STILL restored via `finally:`.
     - Clipboard content returns exactly the sentinel token -> verify rejection (must not accept token as AI response).
     - Empty string response -> verify timeout or error.
   - Verify that all existing and new tests pass: `uv run pytest`.
3. Challenge Verdict:
   - Conclude with an explicit binary verdict: `APPROVE` or `REQUEST_CHANGES`.
   - Write handoff report in `handoff.md`.
   - Notify orchestrator via `send_message`.
