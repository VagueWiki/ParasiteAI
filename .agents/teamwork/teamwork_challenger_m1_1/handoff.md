# Empirical Challenger Report — Milestone M1: Foundation & Zero-Config Setup

## Verdict: REQUEST_CHANGES

---

## 1. Observation

### Test Execution Overview
Executed the full empirical test suite including newly constructed adversarial harnesses:
```powershell
uv run pytest
```
Output:
```
============================= test session starts =============================
platform win32 -- Python 3.12.13, pytest-9.2.0, pluggy-1.7.0 -- G:\__Docs\ParasiteAI\.venv\Scripts\python.exe
cachedir: .pytest_cache
PyQt6 6.12.0 -- Qt runtime 6.12.0 -- Qt compiled 6.12.0
rootdir: G:\__Docs\ParasiteAI
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.15.1, asyncio-1.4.1, mock-3.17.0, qt-4.5.0
collected 111 items

=========================== short test summary info ===========================
FAILED tests/test_stress_concurrency.py::test_cancel_download_from_within_progress_callback
FAILED tests/test_stress_concurrency.py::test_concurrent_generate_state_race
FAILED tests/test_stress_m1.py::TestHostileActionExtraction::test_preamble_with_multiple_braces_and_nested_json
FAILED tests/test_stress_m1.py::TestVRAMBudgetMockHardware::test_vram_budget_exceeded_by_model_headroom
FAILED tests/test_stress_m1.py::TestBrowserOffloadToggleStress::test_state_machine_generate_and_toggle_interleaving
======================= 5 failed, 106 passed in 11.58s ========================
```

---

### Detailed Defect Observations

#### Observation 1: Re-entrant Thread Self-Join in `cancel_download()`
- **File**: `parasite_ai/mind/brain_manager.py:778`
- **Code**:
  ```python
  def cancel_download(self) -> None:
      """Signals active streaming download to abort and clean up."""
      self._cancel_download_event.set()
      if self._download_thread and self._download_thread.is_alive():
          self._download_thread.join(timeout=2.0)
  ```
- **Verbatim Failure**:
  ```
  FAILED tests/test_stress_concurrency.py::test_cancel_download_from_within_progress_callback
  Failed: cancel_download crashed when called from callback: [RuntimeError('cannot join current thread'), RuntimeError('cannot join current thread')]
  ```
- **Context**: When `progress_callback` is invoked from within `_download_worker()`, any cancellation triggered from that callback executes on the worker thread itself. Calling `self._download_thread.join()` causes Python's `threading.Thread` to detect a thread attempting to join itself and raise `RuntimeError: cannot join current thread`.

#### Observation 2: Permanent `BrainState.INFERRING` State Clobbering in Concurrent `generate()`
- **File**: `parasite_ai/mind/brain_manager.py:861-876`
- **Code**:
  ```python
          prev_state = self.state
          self.state = BrainState.INFERRING

      try:
          return self.active_backend.generate(
              prompt=prompt,
              ...
          )
      finally:
          with self._lock:
              self.state = prev_state
  ```
- **Verbatim Failure**:
  ```
  FAILED tests/test_stress_concurrency.py::test_concurrent_generate_state_race
  AssertionError: Race condition detected! manager.state was left as BrainState.INFERRING instead of READY_LOCAL after concurrent inference finished.
  assert <BrainState.INFERRING: 'INFERRING'> == <BrainState.READY_LOCAL: 'READY_LOCAL'>
    - READY_LOCAL
    + INFERRING
  ```
- **Context**: `prev_state` is captured before inference, but `self._lock` is released while `generate()` runs. When a second thread calls `generate()` while the first is executing, the second thread reads `prev_state = self.state` which is already `INFERRING`. In the second thread's `finally:` block, `self.state = prev_state` assigns `self.state = BrainState.INFERRING`, permanently locking the state machine in `INFERRING` even after all threads complete.

#### Observation 3: State-to-Mode Desynchronization on Concurrent Browser Offload Toggle
- **File**: `parasite_ai/mind/brain_manager.py:875`
- **Verbatim Failure**:
  ```
  FAILED tests/test_stress_m1.py::TestBrowserOffloadToggleStress::test_state_machine_generate_and_toggle_interleaving
  AssertionError: State corrupted! Mode is BrainMode.BROWSER_OFFLOAD but state is BrainState.READY_LOCAL
  assert <BrainState.READY_LOCAL: 'READY_LOCAL'> == <BrainState.READY_BROWSER_OFFLOAD: 'READY_BROWSER_OFFLOAD'>
    - READY_BROWSER_OFFLOAD
    + READY_LOCAL
  ```
- **Context**: When a user or controller calls `manager.toggle_browser_only_mode(True)` while a background inference is concluding, `toggle_browser_only_mode` sets `self.mode = BrainMode.BROWSER_OFFLOAD` and `self.state = BrainState.READY_BROWSER_OFFLOAD`. Concurrently, `generate()` finishes and its `finally:` block overwrites `self.state` with its stale `prev_state` (`READY_LOCAL`), producing an inconsistent hybrid state (`mode == BROWSER_OFFLOAD`, `state == READY_LOCAL`).

#### Observation 4: Unenforced VRAM Budget & Unconditional `-1` GPU Layer Offload
- **File**: `parasite_ai/mind/brain_manager.py:516, 519-521`
- **Code**:
  ```python
      used_mb, free_mb = check_vram_headroom()
      req_mb = self.config.brain.local_model.vram_budget_mb

      gpu_layers = self.config.brain.local_model.gpu_layers
      if free_mb < 2000:
          # Low VRAM: reduce layers to CPU fallback
          gpu_layers = 0
  ```
- **Verbatim Failure**:
  ```
  FAILED tests/test_stress_m1.py::TestVRAMBudgetMockHardware::test_vram_budget_exceeded_by_model_headroom
  AssertionError: Engine attempted full GPU offload (n_gpu_layers=-1) despite free VRAM (2500MB) being lower than the model requirement (5200MB) and budget (4000MB)
  assert -1 != -1
  ```
- **Context**: Variable `req_mb = self.config.brain.local_model.vram_budget_mb` on line 516 is assigned but never referenced anywhere. The check only tests `if free_mb < 2000:`. If free VRAM is 2500 MB (which is > 2000 MB) but the model requires 5200 MB and the budget is 4000 MB, `gpu_layers` is passed as `-1` to `llama_cpp`, causing CUDA OOM on host GPU (RTX 4060).

#### Observation 5: Regex Action Extraction Failure on Nested JSON Objects with Preamble Braces
- **File**: `parasite_ai/mind/brain_manager.py:973-989`
- **Code**:
  ```python
  # Pass 3: Greedy match for single JSON object
  match = re.search(r"\{[\s\S]*\}", raw_response)
  ...
  # Pass 4: Find all potential JSON objects
  for candidate in re.findall(r"\{[\s\S]*?\}", raw_response):
  ```
- **Verbatim Failure**:
  ```
  FAILED tests/test_stress_m1.py::TestHostileActionExtraction::test_preamble_with_multiple_braces_and_nested_json
  AssertionError: Failed to extract valid action JSON from output with preamble braces and nested JSON: None
  assert None is not None
  ```
- **Context**: When conversational thoughts contain curly braces (e.g. `{state: active}`) and the action JSON contains nested objects (e.g. `{"action": "CLICK", "metadata": {"key": "val"}}`), Pass 3 greedy regex spans from `{state` to the end (failing `json.loads`), while Pass 4 non-greedy regex `r"\{[\s\S]*?\}"` matches up to the first inner closing brace `{"key": "val"}` (yielding invalid truncated JSON).

---

## 2. Logic Chain

1. *Observation 1* confirms that calling `cancel_download()` from any progress callback or synchronous handler running on the worker thread crashes with `RuntimeError('cannot join current thread')`. This occurs because `cancel_download()` calls `self._download_thread.join()` unconditionally without verifying `self._download_thread != threading.current_thread()`.
2. *Observation 2* demonstrates that when multiple threads enter `generate()` concurrently (such as the dual-mind pipeline running Pass 1 monologue and Pass 2 action dispatcher in parallel, or dock polling thoughts), the transient assignment of `self.state = BrainState.INFERRING` is captured as `prev_state` by subsequent callers. The last finishing thread restores `self.state = BrainState.INFERRING`, permanently corrupting the state machine.
3. *Observation 3* demonstrates that `generate()`'s `finally:` block assumes the brain mode and target state did not change while inference was underway. Toggling browser offload mode mid-inference results in an illegal split state where `mode == BROWSER_OFFLOAD` but `state == READY_LOCAL`.
4. *Observation 4* shows that `req_mb` is completely unused. When free VRAM is 2500 MB on an 8 GB RTX 4060 GPU and a 7B model requiring 5200 MB is loaded, the manager sets `n_gpu_layers = -1`, which directly violates the VRAM budget headroom requirement and causes CUDA OOM crashes.
5. *Observation 5* demonstrates that regular expressions cannot parse nested structures. When the LLM outputs conversational braces followed by a JSON action containing child dictionaries, `_extract_action_json` returns `None`, falling back to `WAIT` and dropping valid actions.
6. Across the remaining 106 tests, GGUF binary header validation (38 tests in `tests/test_stress_gguf.py`) and extreme configuration parsing (14 tests in `tests/test_stress_config.py`) proved highly robust, handling truncated headers, corrupt magic, null bytes, unicode, 100k-character strings, and type confusion without crashes.
7. However, because the 5 identified defects directly affect runtime stability, VRAM safety on the RTX 4060, and dual-mind action execution, Milestone M1 cannot be approved in its current state.

---

## 3. Caveats
- Host environment possesses an NVIDIA RTX 4060 Laptop GPU (8GB VRAM); tests were executed against both real hardware parameters and mocked low-headroom environments.
- Static YAML/JSON schema validation and binary GGUF header validation are rock solid (100% pass across 52 edge cases).
- The identified defects are all contained within `parasite_ai/mind/brain_manager.py` and require targeted logic adjustments rather than architectural rework.

---

## 4. Conclusion
Milestone M1 has high foundational quality in its config schemas and binary GGUF parsing, but exhibits 5 critical runtime defects under concurrency, VRAM budget stress, and nested JSON action parsing.
Final empirical verdict: **REQUEST_CHANGES**.

### Required Action Items for Worker:
1. In `LocalBrainManager.cancel_download()`: Avoid thread self-join by checking `if self._download_thread and self._download_thread.is_alive() and self._download_thread != threading.current_thread():`.
2. In `LocalBrainManager.generate()`: Replace naive `prev_state` restoration with an active inference counter (`self._active_inferences`) and restore to the mode-appropriate idle state (`READY_LOCAL` or `READY_BROWSER_OFFLOAD`) respecting `self.mode`.
3. In `LocalBrainManager._instantiate_local_engine()`: Actually evaluate `free_mb` against `self.config.brain.local_model.vram_budget_mb` and model required VRAM before assigning `gpu_layers = -1`.
4. In `LocalBrainManager._extract_action_json()`: Replace or augment regex extraction with a bracket-depth balancing parser (`depth += 1 / depth -= 1`) to accurately isolate nested JSON objects in the presence of preamble braces.

---

## 5. Verification Method
To independently reproduce and verify all findings:

1. **Verify concurrency & cancellation defects**:
   ```powershell
   uv run pytest tests/test_stress_concurrency.py -v
   ```
   *Expected outcome*: 2 failed (`test_cancel_download_from_within_progress_callback` and `test_concurrent_generate_state_race`), 4 passed.

2. **Verify nested action extraction, VRAM budget, and mode toggle interleaving**:
   ```powershell
   uv run pytest tests/test_stress_m1.py -v
   ```
   *Expected outcome*: 3 failed (`test_preamble_with_multiple_braces_and_nested_json`, `test_vram_budget_exceeded_by_model_headroom`, `test_state_machine_generate_and_toggle_interleaving`).

3. **Verify robust GGUF and config validation**:
   ```powershell
   uv run pytest tests/test_stress_gguf.py tests/test_stress_config.py -v
   ```
   *Expected outcome*: 52 passed in ~3s.

4. **Invalidation condition for verdict**:
   All 111 tests in `uv run pytest` pass cleanly with exit code 0.
