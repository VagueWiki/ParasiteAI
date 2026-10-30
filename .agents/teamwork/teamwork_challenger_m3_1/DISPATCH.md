# Task Assignment: Milestone M3 Challenger 1 (Companion Dock Concurrency & Telemetry Stress)

**Recipient**: `teamwork_challenger_m3_1`
**Role**: `teamwork_challenger`
**Working Directory**: `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_challenger_m3_1\`
**Assigned Milestone**: Milestone M3 — Desktop Companion Dock & Ghost-Hand Overlay

---

## Mandatory Instructions
1. Read `g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md`.
2. Read `g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md`.
3. Read `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_worker_m3\handoff.md`.
4. Adversarially stress-test `parasite_ai/ui/companion_dock.py`, `parasite_ai/ui/bridge.py`, and `parasite_ai/ui/types.py`.
5. Create an adversarial test suite in `tests/test_companion_dock_adversarial.py` covering:
   - High-throughput cross-thread signal emission from multiple threads concurrently (flooding status changes, speech tokens, and thought lines).
   - Rapid state cycling across all 6 states (`WATCHING` -> `THINKING` -> `DRIVING` -> `USER_OVERRIDE` -> `OFFLOADING` -> `PROTECTED` and back).
   - Telemetry queue bursts and rapid progress bar updates (0 to 100%).
   - Perception privacy masking transitions under rapid toggling: ensure sensitive frames are completely blacked out with zero pixel leakage of prior thumbnails.
   - Goal submission queue under thread competition: rapid simultaneous goal submissions, empty strings, multi-kilobyte prompt payloads.
   - Dock dragging edge cases: clamp tests with negative coordinates, multi-screen offscreen drag attempts, and non-interactive child widget pass-through.
6. Execute your adversarial tests and the full suite:
   - `uv run pytest tests/test_companion_dock_adversarial.py -v`
   - `uv run pytest -v`
7. Produce `handoff.md` with:
   - Observation, Logic Chain, Caveats, Conclusion, Verification Method.
   - Clear Gate Verdict: **APPROVE** (if robust) or **REQUEST_CHANGES** (if flaws found).
8. Notify the orchestrator via `send_message`.
