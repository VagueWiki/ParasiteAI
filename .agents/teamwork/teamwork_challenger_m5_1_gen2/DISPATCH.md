# Dispatch for teamwork_challenger_m5_1_gen2

## Task
Adversarially challenge and stress-test Milestone M5 Entry Points and Lifecycle:
- Inspect `main.py`, `parasite_ai/main.py`, `launch_parasite.bat`, and `tests/test_entrypoints.py`.
- Formulate adversarial edge cases:
  - CLI argument injection / invalid values / conflicting flags (e.g. invalid `--brain-mode`, conflicting `--dry-run` with missing config).
  - High-DPI scaling boundary conditions and Windows environment variable handling.
  - Subprocess invocation of `launch_parasite.bat` and python main with unusual working directories or missing environment variables.
  - Signal handling (SIGINT/SIGTERM heartbeat timer during active initialization or teardown).
- Write adversarial stress tests in `tests/test_challenger_m5_1.py`.
- Run tests: `uv run pytest tests/test_challenger_m5_1.py -v`.
- Ensure zero regressions in existing tests.
- Deliver `handoff.md` with:
  - Attack hypotheses tested
  - Test code and execution outputs
  - Edge cases discovered
  - Clear verdict: APPROVE or REQUEST_CHANGES

## 2026-10-29T20:58:02Z
You are teamwork_challenger_m5_1_gen2.
Working directory: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_challenger_m5_1_gen2
Task assignment: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_challenger_m5_1_gen2\DISPATCH.md
Original request path: g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md
Master project plan: g:\__Docs\ParasiteAI\PROJECT.md

Your Tasks:
1. Read g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md and DISPATCH.md.
2. Adversarially challenge Milestone M5 Entry Points and Lifecycle:
   - Inspect `main.py`, `parasite_ai/main.py`, `launch_parasite.bat`, and `tests/test_entrypoints.py`.
   - Target attack surfaces:
     - Invalid/conflicting CLI arguments (e.g. malformed config paths, conflicting brain modes, negative timeouts).
     - DPI awareness initialization edge cases.
     - Environment variable overrides and batch script execution failure modes.
     - SIGINT / SIGTERM / heartbeat timer behavior during startup and shutdown.
3. Author adversarial stress tests in `tests/test_challenger_m5_1.py` (you exclusively own this file).
4. Run your tests with `uv run pytest tests/test_challenger_m5_1.py -v`.
5. Ensure zero regressions across existing tests.
6. Deliver `handoff.md` with:
   - Adversarial hypotheses and test results
   - Edge cases exposed
   - Clear verdict: APPROVE or REQUEST_CHANGES
7. Notify the orchestrator with send_message when complete.
