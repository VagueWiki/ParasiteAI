# Dispatch for Forensic Auditor (Milestone M2 Gate)

Working Directory: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_auditor_m2\
Original Request: g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md
Master Project Spec: g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md
Worker Handoff: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_worker_m2_gen3\handoff.md

Milestone: M2 — Safety & Physical Input Layer
Auditing Mandate:
Perform forensic integrity verification of all M2 code and tests:
1. Genuine implementation verification:
   - Check `parasite_ai/safety/interrupt_guard.py`, `window_guard.py`, `panic.py`, `parasite_ai/hands/kinematics.py`, `mouse.py`, `keyboard.py`.
   - Ensure NO dummy implementations, no facades, no hardcoded return values, and no trivial mock passes.
   - Verify that Win32 ctypes structures match 64-bit ABI (`INPUT` 40 bytes, `MSLLHOOKSTRUCT` 32 bytes, `KBDLLHOOKSTRUCT` 24 bytes).
   - Verify that kinematic trajectory mathematics authentically implement Flash & Hogan Minimum Jerk polynomial $\tau(s) = 10s^3 - 15s^4 + 6s^5$, Cubic Bézier curves, and micro-jitter damping.
   - Verify that `KeyboardDriver` genuinely splits astral plane characters into UTF-16 surrogate pairs and handles `Shift+Enter` for multiline safety.
   - Verify that `WindowGuard` enforces fail-safe defaults for `hwnd == 0` and inaccessible processes.
2. Anti-Cheating & Test Integrity:
   - Inspect all tests under `tests/` for tautological assertions (e.g., `assert True`, `assert 1 == 1`, empty test bodies).
   - Ensure tests genuinely invoke production classes and assert real state transitions.
3. Execution verification:
   - Run `uv run pytest -v` to independently confirm all tests execute and pass genuinely.

Verdict: CLEAN or INTEGRITY VIOLATION.
Write full forensic report to `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_auditor_m2\handoff.md`.

## 2026-10-29T13:11:58Z
You are teamwork_auditor_m2, Forensic Integrity Auditor for Milestone M2 Gate Evaluation.

Your working directory is: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_auditor_m2\

You MUST read:
1. ORIGINAL_REQUEST: g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md
2. Master Project Spec: g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md
3. Your Dispatch: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_auditor_m2\DISPATCH.md
4. Worker Handoff: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_worker_m2_gen3\handoff.md
5. Production source files in `parasite_ai/safety/` and `parasite_ai/hands/`
6. Test suites in `tests/`
