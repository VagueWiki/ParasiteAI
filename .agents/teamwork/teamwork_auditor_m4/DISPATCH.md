# Task Assignment: Milestone M4 Forensic Integrity Auditor

**Recipient**: `teamwork_auditor_m4`
**Role**: `teamwork_auditor`
**Working Directory**: `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_auditor_m4\`
**Assigned Milestone**: Milestone M4 — Perception, Memory & Browser Brain Offload

---

## Forensic Audit Protocol: Zero Tolerance for Integrity Violations
Perform thorough static analysis, runtime verification, and pattern checking across all M4 code and tests:
- `parasite_ai/vision/capture.py`
- `parasite_ai/vision/grounding.py`
- `parasite_ai/vision/__init__.py`
- `parasite_ai/mind/memory.py`
- `parasite_ai/mind/dual_mind.py`
- `parasite_ai/mind/offloader.py`
- `parasite_ai/mind/__init__.py`
- `tests/test_grounding.py`
- `tests/test_memory.py`
- `tests/test_dual_mind.py`
- `tests/test_browser_offloader.py`

### Integrity Checks (Required):
1. **Check 1 — Zero Hardcoded Test Returns**:
   Inspect functions in `parasite_ai/vision/` and `parasite_ai/mind/`. Verify that functions do NOT check `if "test" in str(query)` or return hardcoded expected test values.
2. **Check 2 — Zero Facade / Dummy Implementations**:
   Verify genuine UIA traversal logic, genuine RapidOCR invocation, genuine vectorized NumPy pixel diff calculation, genuine 64-bit dHash computation, genuine ring-buffer FIFO logic, genuine Sentinel token generation (`uuid.uuid4().hex`) and verification, and genuine physical driver dispatch.
3. **Check 3 — Zero Test Circumvention or Mock Leakage**:
   Verify that production code does not rely on test mocks by default. Production backends (`Win32ClipboardBackend`, `Win32BrowserWindowBackend`, `ScreenCapture` with MSS) must be authentic Win32/NumPy implementations.
4. **Check 4 — Verification of Safety & Preemption Invariants**:
   Verify that `ActionDispatcher` genuinely checks `cancellation_token` before and during execution, enabling sub-2ms preemption.
5. **Check 5 — Zero Hidden Browser Sockets**:
   Verify zero usage of Puppeteer, Playwright, Selenium, or hidden Chrome DevTools Protocol (CDP) sockets. Physical Chrome automation must operate via desktop windows and SendInput.
6. **Check 6 — Test Suite Truthfulness**:
   Run `uv run pytest` and verify all 475 tests pass without assertion skips, mocked always-true assertions, or trivial tautologies (`assert True`).

### Audit Verdict:
- Conclude with an explicit binary verdict: `CLEAN` (zero integrity violations) or `INTEGRITY VIOLATION`.
- An `INTEGRITY VIOLATION` verdict is a binary veto that immediately fails the gate.
- Document all evidence in `handoff.md`.
- Notify orchestrator via `send_message`.

## 2026-10-29T17:18:19Z
You are assigned as Milestone M4 Forensic Integrity Auditor (`teamwork_auditor_m4`).

Working Directory:
`g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_auditor_m4\`

Read your full dispatch instructions:
`g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_auditor_m4\DISPATCH.md`

MANDATORY FIRST ACTIONS:
1. Initialize your `BRIEFING.md` and `progress.md` in your working directory.
2. Read `g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md`.
3. Read `g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md`.

AUDIT PROTOCOL (ZERO TOLERANCE):
Execute all 6 forensic integrity checks across all M4 code and tests:
1. Zero Hardcoded Test Returns: No special-casing for test strings or hardcoded mock answers.
2. Zero Facade / Dummy Implementations: Genuine UIA traversal, genuine RapidOCR, genuine vectorized NumPy diff, genuine 64-bit dHash, genuine ring-buffer FIFO, genuine Sentinel token generation (`uuid.uuid4().hex`) and verification, genuine physical driver dispatch.
3. Zero Test Circumvention or Mock Leakage: Production backends must be authentic Win32/NumPy implementations.
4. Preemption Verification: `ActionDispatcher` genuinely checks `cancellation_token` enabling sub-2ms preemption.
5. Zero Hidden Browser Sockets: Strictly zero usage of Puppeteer, Playwright, Selenium, or hidden Chrome DevTools Protocol (CDP) sockets.
6. Test Suite Truthfulness: Run `uv run pytest` and verify all tests pass genuinely without trivial assertions (`assert True`).

Deliver an explicit binary verdict: `CLEAN` or `INTEGRITY VIOLATION` in `handoff.md`.
Notify the orchestrator via `send_message`.
