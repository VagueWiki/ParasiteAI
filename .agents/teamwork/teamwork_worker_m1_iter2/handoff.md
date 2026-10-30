# Handoff Report — Milestone M1 Iteration 2

**Author**: `teamwork_worker_m1_iter2`  
**Working Directory**: `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_worker_m1_iter2`  
**Date**: 2026-10-29  

---

## 1. Observation

### Initial Test Run
Execution of `uv run pytest -v` on baseline codebase failed 5 out of 111 tests (`5 failed, 106 passed in 10.27s`):
1. `tests/test_stress_concurrency.py::test_cancel_download_from_within_progress_callback`:
   ```
   FAILED tests/test_stress_concurrency.py::test_cancel_download_from_within_progress_callback - Failed: cancel_download crashed when called from callback: [RuntimeError('cannot join current thread'), RuntimeError('cannot join current thread')]
   ```
2. `tests/test_stress_concurrency.py::test_concurrent_generate_state_race`:
   ```
   FAILED tests/test_stress_concurrency.py::test_concurrent_generate_state_race - AssertionError: Race condition detected! manager.state was left as BrainState.INFERRING instead of READY_LOCAL after concurrent inference finished.
   assert <BrainState.INFERRING: 'INFERRING'> == <BrainState.READY_LOCAL: 'READY_LOCAL'>
   ```
3. `tests/test_stress_m1.py::TestHostileActionExtraction::test_preamble_with_multiple_braces_and_nested_json`:
   ```
   FAILED tests/test_stress_m1.py::TestHostileActionExtraction::test_preamble_with_multiple_braces_and_nested_json - AssertionError: Failed to extract valid action JSON from output with preamble braces and nested JSON: None
   assert None is not None
   ```
4. `tests/test_stress_m1.py::TestVRAMBudgetMockHardware::test_vram_budget_exceeded_by_model_headroom`:
   ```
   FAILED tests/test_stress_m1.py::TestVRAMBudgetMockHardware::test_vram_budget_exceeded_by_model_headroom - AssertionError: Engine attempted full GPU offload (n_gpu_layers=-1) despite free VRAM (2500MB) being lower than the model requirement (5200MB) and budget (4000MB)
   assert -1 != -1
   ```
5. `tests/test_stress_m1.py::TestBrowserOffloadToggleStress::test_state_machine_generate_and_toggle_interleaving`:
   ```
   FAILED tests/test_stress_m1.py::TestBrowserOffloadToggleStress::test_state_machine_generate_and_toggle_interleaving - AssertionError: State corrupted! Mode is BrainMode.BROWSER_OFFLOAD but state is BrainState.READY_LOCAL
   assert <BrainState.READY_LOCAL: 'READY_LOCAL'> == <BrainState.READY_BROWSER_OFFLOAD: 'READY_BROWSER_OFFLOAD'>
   ```

### Codebase Inspection
- `parasite_ai/mind/brain_manager.py`:
  - `cancel_download()` unconditionally called `self._download_thread.join(timeout=2.0)`. When called inside `progress_callback`, the executing thread is `self._download_thread`, causing Python to raise `RuntimeError: cannot join current thread`.
  - `generate()` saved `prev_state = self.state` before setting `self.state = BrainState.INFERRING` without counting concurrent inferences. When multiple threads called `generate()` concurrently, subsequent threads captured `prev_state = INFERRING`, restoring the state to `INFERRING` upon exit. Additionally, calls to `toggle_browser_only_mode()` during inference were overwritten by `finally: self.state = prev_state`.
  - `_instantiate_local_engine()` defined `req_mb = self.config.brain.local_model.vram_budget_mb` but never evaluated it against `free_mb` or model requirements. If `free_mb >= 2000`, `gpu_layers` remained `-1`, triggering attempts to fully offload large models even when free VRAM was far lower than the model requirement.
  - `_extract_action_json()` relied on regular expressions (`\{[\s\S]*\}` and `\{[\s\S]*?\}`) which cannot handle nested objects or preambles with `{}`.
- `parasite_ai/config.py`:
  - `handle_aliases_and_env()` used `data.setdefault("system", {})["log_level"] = ...` which fails if `"system"` or `"brain"` is explicitly `None` or an instantiated `BaseModel`.

---

## 2. Logic Chain

1. **Re-entrant self-join resolution**:
   - In `cancel_download()`, checking `threading.current_thread() is not self._download_thread` prior to calling `.join()` prevents attempting to join the running thread itself.
   - In `_download_worker()`, checking `self._cancel_download_event.is_set()` immediately following `progress_callback(prog)` breaks the loop cleanly and triggers immediate temporary file cleanup and cancellation status reporting.
2. **Concurrent inference and state machine synchronization**:
   - In `LocalBrainManager.__init__()`, initialized `self._inferring_count = 0` and `self._pre_infer_state = None`.
   - In `generate()`, incremented `_inferring_count` and only captured `_pre_infer_state` if `_inferring_count == 0`.
   - In `finally:`, decremented `_inferring_count`. Only when `_inferring_count == 0` is the state restored. If `self.mode == BrainMode.BROWSER_OFFLOAD`, state correctly restores to `BrainState.READY_BROWSER_OFFLOAD`.
   - In `toggle_browser_only_mode()`, `load_model()`, and `unload_model()`, updated `self._pre_infer_state` within `self._lock` so transitions during inference persist after inference finishes.
3. **Dynamic VRAM Budgeting & Layer Scaling**:
   - In `_instantiate_local_engine()`, computed `effective_vram_mb = min(free_mb, budget_mb)` and retrieved model VRAM requirement and layer count.
   - If `effective_vram_mb < 2000`: assigned `gpu_layers = 0` (CPU fallback).
   - If `2000 <= effective_vram_mb < vram_required_mb`: calculated `layer_ratio = effective_vram_mb / vram_required_mb` and scaled layers via `max(0, int(total_layers * layer_ratio))`.
   - If `effective_vram_mb >= vram_required_mb`: preserved `configured_layers` (allowing `-1` full GPU offload).
4. **Balanced-brace depth parsing and action extraction**:
   - Implemented `@staticmethod _extract_balanced_json(text: str)` which scans characters tracking `in_string`, escape backslashes `\`, and brace depth (`{` increments, `}` decrements). On depth 0, candidate strings are tested with `json.loads` and verified for `"action"`.
   - Updated `_extract_action_json` with 4 passes: direct JSON parse, regex fence matching (3+ backticks) with balanced-brace extraction within each fence, full text balanced-brace extraction, and fallback to `json.JSONDecoder().raw_decode` from each `{`.
5. **Polymorphic dictionary extraction in config**:
   - In `parasite_ai/config.py`, introduced nested helper `_get_section_dict(key: str)` within `handle_aliases_and_env()`. It extracts existing dictionaries, dumps `BaseModel` instances via `.model_dump()`, and replaces `None` or invalid types with `{}` before applying environment variables.

---

## 3. Caveats

- No caveats. All 111 tests across the entire test suite pass deterministically. No files outside of exclusive ownership (`parasite_ai/mind/brain_manager.py` and `parasite_ai/config.py`) were modified.

---

## 4. Conclusion

All 4 target defects in `parasite_ai/mind/brain_manager.py` and the dictionary extraction defect in `parasite_ai/config.py` have been resolved. The test suite achieves 100% pass rate (`111 passed in 10.24s`, exit code 0). Both files compile cleanly without syntax errors or warnings.

---

## 5. Verification Method

To independently verify the implementation:

1. **Syntax / Compilation Check**:
   ```powershell
   uv run python -m py_compile parasite_ai/config.py parasite_ai/mind/brain_manager.py
   ```
   *Expected*: Exit code 0, no output.

2. **Targeted Subsystem Test Runs**:
   ```powershell
   uv run pytest tests/test_stress_concurrency.py -v
   uv run pytest tests/test_stress_m1.py -v
   uv run pytest tests/test_brain_manager.py -v
   uv run pytest tests/test_config.py -v
   ```
   *Expected*: All tests pass.

3. **Full Suite Execution**:
   ```powershell
   uv run pytest -v
   ```
   *Expected*: `111 passed in ~10s`, exit code 0.

### Files to Inspect
- `parasite_ai/config.py` (lines 454–485)
- `parasite_ai/mind/brain_manager.py` (lines 462–466, 515–548, 750–775, 820–930, 1020–1085)
