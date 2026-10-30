# Milestone M4 Handoff Report: Perception, Memory & Browser Brain Offload

**Author**: `teamwork_worker_m4`  
**Milestone**: Milestone M4 — Perception, Memory & Browser Brain Offload  
**Working Directory**: `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_worker_m4\`  

---

## 1. Observation

Directly observed files, tests, and execution results:

### Scope & Modified Files
- `parasite_ai/vision/__init__.py`: Created exports for `ScreenCapture`, `compute_frame_diff`, `ScreenGrounder`, `RawElement`, `compute_iou`, `compute_containment`, `INTERACTIVE_ROLES`.
- `parasite_ai/vision/capture.py`: Implemented `ScreenCapture` class with `mss.MSS()` and `PIL.ImageGrab` fallbacks, returning synthetic numpy frames in headless CI environments without crashing; implemented `compute_frame_diff` for vectorized downsampled frame comparison.
- `parasite_ai/vision/grounding.py`: Implemented `ScreenGrounder` with:
  - Tier 1: Win32 UI Automation tree walking via `uiautomation.WalkControl` (depth limit 5, max 120 elements, interactive controls filter).
  - Tier 2: Scoped RapidOCR fallback via `rapidocr_onnxruntime` when UIA yields sparse elements (< 6 controls) or when configured, scoped to the active window rectangle.
  - Tier 3: Spatial IoU ($\ge 0.35$) and Containment ratio ($\ge 0.70$) deduplication and label merging.
  - Normalization: 1-based Set-of-Mark sequential IDs `[#1..#N]` returning `list[UIElement]`.
  - Prompt formatter: `format_som_summary` generating markdown table of grounded targets.
- `parasite_ai/mind/memory.py`: Implemented:
  - Vectorized pixel difference calculation `compute_pixel_diff` with channel threshold 15.
  - 64-bit perceptual difference hash `compute_dhash` (16-char hex string) and `hamming_distance`.
  - `ActionPlan`, `ActionType`, `DiffResult`, and `StepRecord` Pydantic models.
  - `EpisodicMemory` FIFO ring-buffer (capacity 20, thread-safe `RLock`) storing `StepRecord`.
  - Deterministic 3-Strike Failure Loop Detector: tracks consecutive interactive failures (`CLICK`, `TYPE`, `HOTKEY`, `SCROLL` with diff < 0.02 or exceptions). Sets `is_in_loop() == True` on 3 strikes; resets on success ($\text{diff} \ge 0.02$).
  - Prompt history formatting: `format_for_prompt()`.
- `parasite_ai/mind/dual_mind.py`: Implemented:
  - Pass 1 `PersonaEngine`: character monologue, internal thought stream, speech bubbles, and derived dynamic companion moods (`Curious`, `Focused`, `Cautious`, `Panic-Averted`, `Idle`).
  - Pass 2 `ActionDispatcher`: deterministic action dispatcher validating Set-of-Mark targets, virtual desktop screen boundaries, and calling physical hands (`MouseDriver`, `KeyboardDriver`) with sub-2ms hardware `cancellation_token` preemption.
  - `DualMindPipeline`: orchestrator coordinating safety guards (`InterruptGuard`, `WindowGuard`), perception (`ScreenGrounder`, `ScreenCapture`), Pass 1 reasoning, Pass 2 execution, post-action settling, screen diff verification, and UI telemetry.
- `parasite_ai/mind/offloader.py`: Implemented:
  - 100% visible desktop browser automation: strictly ZERO headless browsers, ZERO invisible scrapers, ZERO hidden CDP sockets.
  - Sentinel Clipboard Verification protocol (`SentinelClipboardVerifier`): backup original user clipboard -> inject unique 128-bit UUID sentinel token -> trigger copy -> poll for change from sentinel -> guaranteed restoration in `finally:`.
  - Decoupled backends: `IClipboardBackend` (`Win32ClipboardBackend` / `MockClipboardBackend`) and `IBrowserWindowBackend` (`Win32BrowserWindowBackend` / `MockBrowserWindowBackend`).
  - `BrowserOffloader` (alias `ChromeOffloader`) state machine.
- `parasite_ai/mind/__init__.py`: Exported all mind subsystem components.

### Automated Test Execution Results
1. `uv run pytest tests/test_grounding.py -v`:
   - 13 passed in 2.09s (100% pass)
2. `uv run pytest tests/test_memory.py tests/test_dual_mind.py -v`:
   - 26 passed in 0.79s (100% pass)
3. `uv run pytest tests/test_browser_offloader.py -v`:
   - 12 passed in 7.17s (100% pass)
4. `uv run pytest` (Full project suite):
   - 475 passed in 38.46s (100% pass, 0 regressions, all 424 existing tests + 51 new tests passing)

---

## 2. Logic Chain

1. **Vision Grounding (Feature 12)**:
   - Operating directly on the physical desktop requires locating UI elements without heavy GPU models.
   - Tier 1 Win32 UI Automation tree walking queries OS accessibility trees in <15ms with 0 MB VRAM overhead.
   - When canvas or custom game toolkits yield < 6 native controls, Tier 2 Scoped RapidOCR runs CPU ONNX inference scoped to the active window rectangle to keep latency low.
   - Tier 3 IoU ($\ge 0.35$) and Containment ($\ge 0.70$) deduplication suppresses internal text duplicates and enriches unlabeled UIA buttons with recognized OCR text.
   - The resulting elements are formatted into Set-of-Mark targets `[#1..#N]` and published to `GhostHUD` and `CompanionDock` via `UIBridge`.

2. **Episodic Working Memory & Loop Detection (Feature 13)**:
   - Physical execution can miss or fail silently if an unexpected dialog or network lag occurs.
   - By calculating vectorized pre- and post-action pixel differences ($\Delta > 15$, threshold 0.02) and 64-bit dHash perceptual structures, ParasiteAI verifies action impact.
   - The 3-strike failure loop detector counts consecutive interactive failures (screen diff < 0.02 or exceptions) and triggers `is_in_loop() == True` on 3 strikes, enabling the cognitive pipeline to break out of deadlocks.

3. **Dual-Mind Cognitive Pipeline (Feature 14)**:
   - Pass 1 PersonaEngine creates rich character speech and internal thought streams while deriving companion moods based on execution status and failure strikes.
   - Pass 2 ActionDispatcher translates character intent into concrete actions, resolves Set-of-Mark IDs to global coordinates, validates desktop boundaries, and enforces sub-2ms hardware cancellation token checks on every action.
   - DualMindPipeline binds safety guards (`InterruptGuard`, `WindowGuard`), perception, Pass 1, Pass 2, settling, diff calculation, and memory into an atomic step loop.

4. **Visible Browser Brain Offload (Feature 15)**:
   - Zero-VRAM startup requires cognitive reasoning offload without local GPU models.
   - Operating 100% visibly in Chrome satisfies the project core philosophy (no headless browsers, no hidden CDP).
   - The Sentinel Clipboard Verification protocol guarantees user clipboard integrity by backing up user text, testing with a randomized 128-bit UUID, and restoring original user data in a guaranteed `finally:` block.

---

## 3. Caveats

- Win32 UI Automation requires active Windows desktop sessions for live OS accessibility trees; during headless CI or test execution, mock UIA trees and synthetic screen capture frames are utilized.
- Browser offloader focuses Chrome windows and types prompts via physical SendInput; user must ensure Chrome is installed at the configured path for live desktop execution.
- No caveats regarding test suites or specifications.

---

## 4. Conclusion

Milestone M4 (Perception, Memory & Browser Brain Offload) is fully implemented in compliance with `ORIGINAL_REQUEST.md`, `PROJECT.md`, and all three Explorer plans. All 51 new automated tests pass with 100% success and 0 regressions against existing tests.

---

## 5. Verification Method

To independently verify the M4 implementation:

```powershell
# 1. Verify Screen Grounding Perception Suite (13 tests)
uv run pytest tests/test_grounding.py -v

# 2. Verify Episodic Memory & Dual-Mind Suites (26 tests)
uv run pytest tests/test_memory.py tests/test_dual_mind.py -v

# 3. Verify Visible Browser Offloader Suite (12 tests)
uv run pytest tests/test_browser_offloader.py -v

# 4. Verify Full Test Suite Across Entire Project (475 tests total, 0 regressions)
uv run pytest
```
