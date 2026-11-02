## 2026-10-31T11:39:03Z

You are a Worker agent for ParasiteAI.
Your working directory is: C:\ParasiteAI\.agents\teamwork\teamwork_worker_p3\

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Mandatory inputs to read before starting:
- C:\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md (Authoritative requirements)
- C:\ParasiteAI\.agents\teamwork\orchestrator_1\SCOPE.md (Phase 3 architecture & scope)
- C:\ParasiteAI\HANDOFF.md (System context & invariants)
- C:\ParasiteAI\PROJECT.md
- C:\ParasiteAI\.agents\teamwork\teamwork_explorer_p3_1\handoff.md (Phase 3A ROI diffing exploration blueprint)
- C:\ParasiteAI\.agents\teamwork\teamwork_explorer_p3_2\handoff.md (Phase 3B Win32 Caret Focus exploration blueprint)
- C:\ParasiteAI\.agents\teamwork\teamwork_explorer_p3_3\handoff.md (Phase 3C Start Search Cadence exploration blueprint)

Exclusive Write Ownership:
You own exclusively:
- `parasite_ai/ui/types.py`
- `parasite_ai/mind/dual_mind.py`
- `parasite_ai/mind/resolver.py`
- `tests/test_challenger_m4_2.py`
- `tests/test_phase3_execution_loop.py`

Your mission is to implement Phase 3 (Execution Loop Hardening):

### 1. Phase 3A: Localized ROI Diffing
- In `parasite_ai/ui/types.py`:
  - Define `BoundingBox(BaseModel)` with `x: int, y: int, width: int, height: int`.
  - Implement `pad(self, padding_px: int = 20, bounds: Optional[Tuple[int, int, int, int]] = None) -> BoundingBox` with virtual desktop clamping (using `get_virtual_screen_bounds()` default `3840x1080 @ 100% DPI`).
  - Implement `crop_frame(self, frame: Optional[np.ndarray], bounds: Optional[Tuple[int, int, int, int]] = None) -> Optional[np.ndarray]` and `as_tuple()`.
  - Add `target_bbox` property and `pad(self, padding_px: int = 20, bounds=None) -> BoundingBox` to `UIElement`.
- In `parasite_ai/mind/dual_mind.py`:
  - Implement `extract_action_target_roi(...)` resolving the target bounding box (target_id -> target coordinates -> point (x,y) -> active window -> None for global actions).
  - Update Step 6 in `DualMindPipeline.step()` to perform localized ROI diffing on `target_bbox.pad(20px)` when a target ROI exists, falling back cleanly to full desktop diffing for global actions or ungrounded hotkeys.
- In `tests/test_challenger_m4_2.py`:
  - Update line 712 (`test_noise_frame_diff_causes_strike_while_real_diff_resets`) so `real_change_frame` changes pixels inside `TargetBtn` (e.g. `real_change_frame[50:70, 50:70, :] = 200`), ensuring the test passes under both localized ROI diffing and full desktop diffing.

### 2. Phase 3B: Win32 Caret Focus Verification
- In `parasite_ai/mind/dual_mind.py` (using `ctypes` and `ctypes.wintypes`, zero `pywin32` dependencies):
  - Define `GUITHREADINFO` ctypes structure with `cbSize = sizeof(GUITHREADINFO)` (72 bytes on x64).
  - Implement `verify_caret_focus(...)` or equivalent helper calling `GetGUIThreadInfo(0, byref(info))` checking `(info.flags & 0x00000001) or (info.hwndCaret != 0)`.
  - Integrate this check in `ActionDispatcher.dispatch()` for `ActionType.TYPE` prior to typing (with a short backoff/poll up to 250ms, polling every 25ms and checking cancellation token). If caret focus is not detected after the timeout, return `ActionResult(success=False, error="Caret focus not detected")` (or appropriate error) to trigger an episodic strike rather than dropping blind keystrokes into an unfocused window.

### 3. Phase 3C: Start Search Cadence Buffer
- In `parasite_ai/mind/resolver.py`:
  - In `UniversalAppResolver`, add configurable `cadence_buffer_ms: float = 250.0`.
  - In `resolve_launch_action()`, enforce a 250ms cadence pause (`time.sleep(self.cadence_buffer_s)` or cancellation-aware wait) between the `Win` key chord and typing the target application name when `self._search_opened` is True.

### 4. Phase 3D: Tests & Invariant Verification
- Create `tests/test_phase3_execution_loop.py` containing comprehensive unit tests with mocks for:
  - 3A: Localized ROI diffing (geometry, padding +20px, virtual boundary clamping 3840x1080, multi-monitor seam preservation, noise rejection in peripheral tray vs target change detection).
  - 3B: Win32 Caret Focus verification (blinking caret flag, hwndCaret != 0, unacquired caret with backoff timeout, cancellation token preemption, exception fallback).
  - 3C: Start Search Cadence Buffer (verifying 250ms pause between Win hotkey and application typing with mock time).
- Run the full test suite:
  `Set-Location C:\ParasiteAI; & "C:\ParasiteAI\.venv\Scripts\python.exe" -m pytest`
  Ensure all 797 existing tests + new unit tests pass (100% green).
- Verify all architectural invariants: sub-2ms hardware touch preemption, Ctrl+Alt+K hard kill, brain.mode: "local_llm", strict anti-hardcoding rule (no app-specific branching), and dual-monitor virtual desktop coordinates (3840x1080).

### Output Requirements
- Write your complete handoff report to: `C:\ParasiteAI\.agents\teamwork\teamwork_worker_p3\handoff.md`.
- Include in your report: Observation, Logic Chain, Caveats, Conclusion, Verification Method (exact commands and test outputs).
- Once finished, notify via `send_message`.
