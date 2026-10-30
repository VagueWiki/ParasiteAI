# Task Assignment: Milestone M3 Challenger 2 (Ghost HUD Geometries, Reticle & Win32 Stress)

**Recipient**: `teamwork_challenger_m3_2`
**Role**: `teamwork_challenger`
**Working Directory**: `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_challenger_m3_2\`
**Assigned Milestone**: Milestone M3 — Desktop Companion Dock & Ghost-Hand Overlay

---

## Mandatory Instructions
1. Read `g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md`.
2. Read `g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md`.
3. Read `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_worker_m3\handoff.md`.
4. Adversarially stress-test `parasite_ai/ui/ghost_hud.py`, `parasite_ai/ui/win32_styles.py`, and `parasite_ai/ui/dpi.py`.
5. Create an adversarial test suite in `tests/test_ghost_hud_adversarial.py` covering:
   - Extreme multi-monitor virtual desktop configurations (e.g. secondary monitor on left with negative `(x, y)` bounds, 3-monitor surround with 7680x1440 span).
   - High-density Set-of-Mark rendering: 200+ elements simultaneously on screen with overlapping bounding boxes, zero-sized bounds, and out-of-screen targets.
   - Reticle preemption and cancellation races: aborting reticle mid-flight, concurrent `show_reticle()` invocations before prior 300ms timer elapses, and zero-duration reticle requests.
   - Bézier curve trajectory preview edge cases: identical start/target points (zero distance), points across monitor boundaries, extreme arc heights, and negative coordinates.
   - Win32 extended style bitmask verification and robustness under simulated invalid window handles and non-Windows OS mocks.
6. Execute your adversarial tests and the full suite:
   - `uv run pytest tests/test_ghost_hud_adversarial.py -v`
   - `uv run pytest -v`
7. Produce `handoff.md` with:
   - Observation, Logic Chain, Caveats, Conclusion, Verification Method.
   - Clear Gate Verdict: **APPROVE** (if robust) or **REQUEST_CHANGES** (if flaws found).
8. Notify the orchestrator via `send_message`.
