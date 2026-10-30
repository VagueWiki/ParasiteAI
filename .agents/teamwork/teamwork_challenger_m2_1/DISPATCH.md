# Dispatch for Challenger 1 (Milestone M2 Gate)

Working Directory: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_challenger_m2_1\
Original Request: g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md
Master Project Spec: g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md
Worker Handoff: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_worker_m2_gen3\handoff.md

Milestone: M2 — Safety & Physical Input Layer
Adversarial Focus:
1. Safety Subsystem Stress Testing:
   - Rapid alternating injected vs physical input events to test for race conditions or state desync.
   - High-frequency simulation of physical touches during active trajectory sleep.
   - Multi-monitor corner slam at virtual desktop boundaries (`SM_XVIRTUALSCREEN`, `SM_CXVIRTUALSCREEN`).
   - Window Guard with edge-case titles, empty strings, null handles, dead PIDs, and permission denied exceptions.
2. Kinematic & Mouse Stress Testing:
   - Zero-distance hops ($D=0$), negative coordinates, diagonal screen sweeps, and extreme distances.
   - Trajectory verification: assert no single-step jump exceeds maximum threshold, verify monotonic progress, ensure endpoint $P_3$ is reached with 0 pixel error.
   - Verify all held buttons are released when cancelled mid-drag.
3. Write adversarial tests in `tests/test_challenger_m2_1.py` and run `uv run pytest tests/test_challenger_m2_1.py -v`.

Verdict: APPROVE or REQUEST_CHANGES.
Write report to `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_challenger_m2_1\handoff.md`.
## 2026-10-29T13:11:42Z
You are teamwork_challenger_m2_1, Challenger 1 for Milestone M2 Gate Evaluation.

Your working directory is: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_challenger_m2_1\

You MUST read:
1. ORIGINAL_REQUEST: g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md
2. Master Project Spec: g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md
3. Your Dispatch: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_challenger_m2_1\DISPATCH.md
4. Worker Handoff: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_worker_m2_gen3\handoff.md
5. Existing codebase in `parasite_ai/` and `tests/`

Your Mandate:
Adversarially challenge and stress-test the Safety and Kinematics subsystems:
1. Write adversarial tests in `tests/test_challenger_m2_1.py`:
   - Stress test alternating physical vs synthetic event bursts on `InterruptGuard`.
   - Rapid preemption of `MouseDriver` during active movement and verify that all held buttons are unconditionally released.
   - Screen corner slam stress testing on primary and virtual desktop coordinates.
   - Extreme coordinates for `KinematicsEngine`: zero distance hops, diagonal screen sweeps, verifying monotonic progress, maximum step displacement bounds, and 0-pixel landing error.
   - WindowGuard edge cases: empty strings, whitespace-only titles, dead PIDs, and permission-denied cases.
2. Execute your adversarial test suite and the full project test suite:
   `uv run pytest tests/test_challenger_m2_1.py -v`
   `uv run pytest -v`
3. Issue a verdict: APPROVE or REQUEST_CHANGES.
4. Write your full report in `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_challenger_m2_1\handoff.md` and notify orchestrator via send_message.
