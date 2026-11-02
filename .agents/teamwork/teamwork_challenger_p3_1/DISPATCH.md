## 2026-10-31T11:53:25Z
You are a Challenger agent for ParasiteAI.
Your working directory is: C:\ParasiteAI\.agents\teamwork\teamwork_challenger_p3_1\

Mandatory inputs to read before starting:
- C:\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md (Authoritative requirements)
- C:\ParasiteAI\.agents\teamwork\orchestrator_1\SCOPE.md (Phase 3 architecture & scope)
- C:\ParasiteAI\HANDOFF.md (System context & invariants)
- C:\ParasiteAI\PROJECT.md
- C:\ParasiteAI\.agents\teamwork\teamwork_worker_p3\handoff.md (Worker implementation handoff)

Your mission:
Empirically stress-test Requirement R1 (Phase 3A: Localized ROI Diffing):
1. Test extreme boundary conditions for `BoundingBox.pad(20px)`:
   - Elements partially off-screen (e.g. x=-10, y=0, width=50, height=50).
   - Elements on the boundary of Monitor 1 and Monitor 2 (x=1910, crossing 1920 seam).
   - Elements at the extreme bottom-right of the virtual desktop (x=3830, y=1070).
   - Zero-width or zero-height elements.
2. Test peripheral noise rejection:
   - Emulate changes in system tray (x=3800, y=1050) while clicking a target element on Monitor 1 (x=200, y=200); verify that localized ROI diffing yields 0.0 diff and records a strike.
   - Emulate changes strictly inside target ROI; verify diff exceeds threshold and resets strikes to 0.
3. Test fallback behavior:
   - Verify ungrounded point clicks create a 40x40 padded ROI centered on coordinates.
   - Verify global actions (`HOTKEY`, etc.) cleanly fall back to full desktop diffing without raising errors.
4. Execute tests via: `Set-Location C:\ParasiteAI; & "C:\ParasiteAI\.venv\Scripts\python.exe" -m pytest tests/test_phase3_execution_loop.py -v`.

Output Requirements:
- Write your empirical stress test report to: `C:\ParasiteAI\.agents\teamwork\teamwork_challenger_p3_1\handoff.md`.
- Declare your empirical verdict: **APPROVE** or **REJECT** with evidence.
- Notify the orchestrator via `send_message`.
