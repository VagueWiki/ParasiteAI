# Task Assignment: Milestone M4 Implementation Worker

**Recipient**: `teamwork_worker_m4`
**Role**: `teamwork_worker`
**Working Directory**: `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_worker_m4\`
**Assigned Milestone**: Milestone M4 — Perception, Memory & Browser Brain Offload

---

## ⚠️ MANDATORY INTEGRITY WARNING (ZERO TOLERANCE)
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

---

## Required Reference Documents (READ BEFORE CODING)
1. `g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md` (Authoritative User Request)
2. `g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md` (System Architecture & Contracts)
3. Explorer Plans:
   - Feature 12 (Grounding): `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m4_1\plan.md`
   - Features 13 & 14 (Memory & Dual-Mind): `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m4_2\plan.md`
   - Feature 15 (Browser Offload): `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m4_3\plan.md`

---

## Scope & File Ownership
You have EXCLUSIVE write ownership of the following files:
1. `parasite_ai/vision/__init__.py`
2. `parasite_ai/vision/capture.py`
3. `parasite_ai/vision/grounding.py`
4. `parasite_ai/mind/memory.py`
5. `parasite_ai/mind/dual_mind.py`
6. `parasite_ai/mind/offloader.py`
7. `parasite_ai/mind/__init__.py`
8. `tests/test_grounding.py`
9. `tests/test_memory.py`
10. `tests/test_dual_mind.py`
11. `tests/test_browser_offloader.py`

---

## Detailed Implementation Requirements

### 1. Vision & Screen Grounding (`parasite_ai/vision/`):
- `capture.py`: `ScreenCapture` class with `mss` and PIL fallbacks. Handles headless CI environments gracefully (catching `ScreenShotError` or `OSError` without crashing).
- `grounding.py`: `ScreenGrounder` implementing:
  - Tier 1: Win32 UI Automation tree walking via `uiautomation` (depth limit 5, max 120 elements, interactive controls: Button, Edit, Hyperlink, ComboBox, TabItem, CheckBox, RadioButton, MenuItem, ListItem, Document).
  - Tier 2: Scoped RapidOCR fallback via `rapidocr_onnxruntime` when UIA yields sparse elements (< 6 controls, e.g. web canvas/game toolkits) or when explicitly configured. Scoped to foreground window rectangle.
  - Tier 3: Spatial IoU ($\ge 0.35$) and Containment ratio ($\ge 0.70$) deduplication and label merging.
  - Returns compact, 1-based indexed `list[UIElement]` compatible with `parasite_ai/ui/types.py` (`id`, `bbox`, `center`, `role`, `label`).
  - Seamlessly pushes targets to `GhostHUD` (`UIBridge.set_hud_targets`) and `CompanionDock` (`UIBridge.notify_perception`).

### 2. Episodic Working Memory (`parasite_ai/mind/memory.py`):
- Vectorized NumPy screen diff computation ($\Delta > 15$, threshold 0.02) + 64-bit perceptual `dHash` (16 bytes per snapshot) with Hamming distance.
- `EpisodicMemory` FIFO ring-buffer (capacity 20, thread-safe `RLock`) storing `StepRecord` (`ActionPlan`, `success`, `diff_ratio`, `timestamp`, `error`).
- 3-Strike Failure Loop Detector: tracks consecutive interactive failures (`CLICK`, `TYPE`, `HOTKEY`, `SCROLL` with diff < 0.02 or exceptions). Sets `is_in_loop() == True` on 3 strikes; resets on success ($\text{diff} \ge 0.02$).
- LLM prompt history formatting (`format_for_prompt()`).

### 3. Dual-Mind Cognitive Pipeline (`parasite_ai/mind/dual_mind.py`):
- Pass 1: `PersonaEngine` generating character monologue, thought stream (`UIBridge.notify_thought`), speech bubble (`UIBridge.notify_speech`), and derived companion moods (`Curious`, `Focused`, `Cautious`, `Panic-Averted`).
- Pass 2: `ActionDispatcher` enforcing Pydantic `ActionPlan` (`CLICK`, `TYPE`, `SCROLL`, `WAIT`, `HOTKEY`, `PANIC`), resolving Set-of-Mark `target_id` to `(center_x, center_y)`, validating screen boundaries, and calling physical hands (`MouseDriver`, `KeyboardDriver`) passing sub-2ms hardware `cancellation_token`.
- `DualMindPipeline`: orchestrating closed-loop perception, safety checks (`WindowGuard`), Pass 1, Pass 2, settling, diff calculation, memory recording, and UI updates.

### 4. Visible Browser Brain Offloader (`parasite_ai/mind/offloader.py`):
- 100% visible physical Chrome automation: strictly ZERO headless browsers, ZERO invisible scrapers, ZERO hidden CDP sockets.
- Focuses or launches user's visible Chrome window (`ShowWindow`, `SetForegroundWindow`, `AttachThreadInput`).
- Navigates via physical keystrokes (`Ctrl+L` -> URL -> `Enter`), types prompt via `KeyboardDriver` with human cadence jitter and multiline `Shift+Enter` safety.
- Sentinel Clipboard Verification protocol:
  1. Backs up user's existing clipboard text safely.
  2. Injects unique 128-bit UUID sentinel token (`__PARASITE_SENTINEL_{uuid}__`).
  3. Triggers response copy.
  4. Polls clipboard: accepts harvested text ONLY when different from sentinel token and non-empty.
  5. Guaranteed restoration of original user clipboard in `finally:`.
- Decoupled backends: `IClipboardBackend` (`Win32ClipboardBackend` / `MockClipboardBackend`) and `IBrowserWindowBackend` (`Win32BrowserWindowBackend` / `MockBrowserWindowBackend`).
- Integrated into `LocalBrainManager.BrowserOffloadBackend` and zero-VRAM startup fallback.

### 5. Automated Test Suites:
- `tests/test_grounding.py`: UIA mock tree walking, RapidOCR fallback, spatial IoU/containment deduplication, degenerate box filtering, headless resilience.
- `tests/test_memory.py`: Pixel diff calculation, dHash computation, ring buffer eviction, 3-strike loop detector trips and resets, thread-safety.
- `tests/test_dual_mind.py`: Action validation, target resolution, out-of-bounds rejection, cancellation token preemption, mood transitions, end-to-end pipeline.
- `tests/test_browser_offloader.py`: Window focus/launch state machine, sentinel clipboard backup/verify/restore, multiline typing safety, cancellation interrupt aborts, BrainManager fallback.

---

## Verification Requirements
You must run the tests yourself and document results in your handoff report:
1. `uv run pytest tests/test_grounding.py -v`
2. `uv run pytest tests/test_memory.py tests/test_dual_mind.py -v`
3. `uv run pytest tests/test_browser_offloader.py -v`
4. `uv run pytest` -> Ensure 100% of all 424 existing tests pass with 0 regressions, plus all new M4 tests pass.

Author `handoff.md` with: Observation, Logic Chain, Caveats, Conclusion, and Verification Method.
Notify orchestrator via `send_message` when done.
