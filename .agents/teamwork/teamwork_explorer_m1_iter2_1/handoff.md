# Handoff Report — Milestone M1 Iteration 2: Brain Manager Concurrency & State Machine Hardening

## 1. Observation
1. **Test Failures Observed**:
   Executing `uv run pytest tests/test_stress_concurrency.py tests/test_stress_m1.py` revealed four failing tests:
   - `tests/test_stress_concurrency.py::test_cancel_download_from_within_progress_callback`
     Verbatim Error: `RuntimeError: cannot join current thread`
     Traceback origin: `parasite_ai/mind/brain_manager.py:779` in `cancel_download()`:
     ```python
     self._download_thread.join(timeout=2.0)
     ```
   - `tests/test_stress_concurrency.py::test_concurrent_generate_state_race`
     Verbatim Error: `AssertionError: Race condition detected! manager.state was left as BrainState.INFERRING instead of READY_LOCAL after concurrent inference finished.`
     Traceback origin: `parasite_ai/mind/brain_manager.py:861-875` in `generate()`:
     ```python
     prev_state = self.state
     self.state = BrainState.INFERRING
     ...
     finally:
         with self._lock:
             self.state = prev_state
     ```
   - `tests/test_stress_m1.py::TestBrowserOffloadToggleStress::test_state_machine_generate_and_toggle_interleaving`
     Verbatim Error: `AssertionError: State corrupted! Mode is BrainMode.BROWSER_OFFLOAD but state is BrainState.READY_LOCAL`
     Traceback origin: `parasite_ai/mind/brain_manager.py:875` where `self.state = prev_state` unconditionally clobbered `READY_BROWSER_OFFLOAD` set by `toggle_browser_only_mode(True)` during inference.
   - `tests/test_stress_m1.py::TestHostileActionExtraction::test_preamble_with_multiple_braces_and_nested_json`
     Verbatim Error: `AssertionError: Failed to extract valid action JSON from output with preamble braces and nested JSON: None`
     Traceback origin: `parasite_ai/mind/brain_manager.py:973-989` where Pass 3 greedy regex `\{[\s\S]*\}` absorbed preamble text `{state: active}`, and Pass 4 non-greedy regex `\{[\s\S]*?\}` truncated at the first inner closing brace `}`.
   - `tests/test_stress_m1.py::TestVRAMBudgetMockHardware::test_vram_budget_exceeded_by_model_headroom`
     Verbatim Error: `AssertionError: Engine attempted full GPU offload (n_gpu_layers=-1) despite free VRAM (2500MB) being lower than the model requirement (5200MB) and budget (4000MB)`
     Traceback origin: `parasite_ai/mind/brain_manager.py:519-521` in `_instantiate_local_engine()` where only `free_mb < 2000` was checked, allowing `-1` through when `free_mb` was 2500 MB (< 4000 MB budget, < 5200 MB 7B requirement).

2. **Empirical Validation with Patches**:
   When candidate patches addressing these 5 root causes were applied in-memory, `uv run pytest tests/` completed with:
   `============================= 111 passed in 9.60s =============================` (100% pass rate).

---

## 2. Logic Chain
1. **Re-entrant Join Crash**:
   - `progress_callback` is executed on `self._download_thread` inside `_download_worker()` (observation 1).
   - Calling `manager.cancel_download()` from within `progress_callback` causes the executing thread to call `self._download_thread.join(timeout=2.0)`.
   - In Python's `threading` module, calling `join()` on `threading.current_thread()` triggers `RuntimeError: cannot join current thread` to prevent immediate deadlock.
   - Guarding the join with `threading.current_thread() is not self._download_thread` prevents the illegal call, while setting `self._cancel_download_event` signals the worker to break and clean up `temp_path` immediately.

2. **Concurrent `generate()` State Race & Interleaving Clobber**:
   - When Thread A starts `generate()`, it records `prev_state = READY_LOCAL` and sets `self.state = INFERRING`.
   - When Thread B starts `generate()` concurrently while Thread A is running, Thread B observes `self.state == INFERRING` and sets its own `prev_state = INFERRING`.
   - If Thread A finishes before Thread B, Thread A sets `self.state = READY_LOCAL`.
   - When Thread B finishes later, Thread B executes `self.state = prev_state` (`INFERRING`), leaving the manager stuck in `INFERRING` indefinitely despite idle state (observation 1).
   - Similarly, if `toggle_browser_only_mode(True)` is invoked during inference, it sets `self.state = READY_BROWSER_OFFLOAD`. When inference exits, `finally: self.state = prev_state` clobbers this state back to `READY_LOCAL`, violating state-machine invariants (observation 1).
   - Solution: Introduce `self._inferring_count: int` and `self._pre_infer_state: Optional[BrainState]`.
     - Only when `self._inferring_count == 0` does the manager record `_pre_infer_state = self.state`.
     - In `finally:`, decrement `_inferring_count`. Only when `_inferring_count == 0` is state restored.
     - If `self.state` was altered during inference (e.g. `self.state != BrainState.INFERRING` due to `toggle_browser_only_mode`), the clobber is avoided. If `self.state == BrainState.INFERRING`, it restores to `READY_BROWSER_OFFLOAD` (if mode was toggled) or `_pre_infer_state`.
     - State mutating functions (`toggle_browser_only_mode`, `unload_model`, `load_model`) update `_pre_infer_state` in tandem under `self._lock`.

3. **VRAM Headroom Underflow Guard**:
   - `_instantiate_local_engine()` received `gpu_layers = -1` (full GPU offload requested by config).
   - When free VRAM was 2500 MB, `free_mb < 2000` evaluated to False, so `gpu_layers` remained `-1` despite 2500 MB being insufficient for the 7B model (5200 MB required) and below the 4000 MB configured budget.
   - Solution: Compare `free_mb` against both `req_mb` and `model_req_vram` from `CURATED_MODELS`. When `gpu_layers == -1` and `free_mb < min(req_mb, model_req_vram)`, downgrade `gpu_layers` to `recommended_gpu_layers` (e.g. 28) or CPU fallback.

4. **Resilient JSON Parsing for Preamble Braces + Nested Objects**:
   - Regex `\{[\s\S]*\}` is greedy across the entire response and picks up non-JSON preamble `{...}`.
   - Non-greedy `\{[\s\S]*?\}` fails on nested objects because it terminates on the first inner `}`.
   - Solution: Use `json.JSONDecoder().raw_decode` starting at each `{` occurrence. Python's standard library decoder properly parses nested objects, handles escaped characters, and ignores preceding text without catastrophic backtracking.

---

## 3. Caveats
- No source code files were edited during this investigation (strict read-only explorer role).
- All fixes were fully validated in-process using Python monkeypatching to guarantee zero regressions.
- The Worker only needs to apply the exact diffs documented in `plan.md` to `parasite_ai/mind/brain_manager.py`.

---

## 4. Conclusion
All concurrency issues and edge cases in `parasite_ai/mind/brain_manager.py` have been diagnosed, root-caused, and verified with exact drop-in solutions.
Applying the 7 changes detailed in `plan.md` will bring the test suite from 106/111 passing to 111/111 passing (100%).

---

## 5. Verification Method
After the Worker updates `parasite_ai/mind/brain_manager.py`, execute:
```powershell
uv run pytest tests/test_stress_concurrency.py
uv run pytest tests/test_stress_m1.py
uv run pytest
```
Expected output:
```
============================= 111 passed in ~9.6s =============================
```
