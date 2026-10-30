# Handoff Report — Review & Adversarial Audit: Milestone M1

## Review Summary

**Verdict**: REQUEST_CHANGES  
**Integrity Audit**: PASSED (Zero integrity violations. No dummy facades, no hardcoded cheating, genuine implementation)  
**Overall Risk Assessment**: HIGH (4 test failures in `uv run pytest`, state machine race conditions, recursive thread crash)

---

## 1. Observation

### 1.1 Full Test Suite Execution
- **Command**: `uv run pytest -v`
- **Result**: `107 passed, 4 failed in 13.48s (exit code 1)`
- **Verbatim Failures**:
  1. `tests/test_stress_concurrency.py::test_cancel_download_from_within_progress_callback`
     ```
     RuntimeError: cannot join current thread
     ```
  2. `tests/test_stress_m1.py::TestBrowserOffloadToggleStress::test_state_machine_generate_and_toggle_interleaving`
     ```
     AssertionError: State corrupted! Mode is BrainMode.BROWSER_OFFLOAD but state is BrainState.READY_LOCAL
     assert <BrainState.READY_LOCAL: 'READY_LOCAL'> == <BrainState.READY_BROWSER_OFFLOAD: 'READY_BROWSER_OFFLOAD'>
     ```
  3. `tests/test_stress_m1.py::TestHostileActionExtraction::test_preamble_with_multiple_braces_and_nested_json`
     ```
     AssertionError: Failed to extract valid action JSON from output with preamble braces and nested JSON: None
     assert None is not None
     ```
  4. `tests/test_stress_m1.py::TestVRAMBudgetMockHardware::test_vram_budget_exceeded_by_model_headroom`
     ```
     AssertionError: Engine attempted full GPU offload (n_gpu_layers=-1) despite free VRAM (2500MB) being lower than the model requirement (5200MB) and budget (4000MB)
     assert -1 != -1
     ```

### 1.2 Isolated M1 Unit Tests
- **Command**: `uv run pytest tests/test_config.py tests/test_brain_manager.py -v`
- **Result**: `28 passed in 2.07s (exit code 0)`
- Confirms baseline functionality was implemented, but lacked hardening against concurrency, thread lifecycle, nested JSON, and VRAM boundary conditions.

---

## 2. Logic Chain & Findings

### Finding 1 [Critical / Major] — Recursive Thread Join Crash in `cancel_download`
- **What**: Invoking `cancel_download()` from inside a `progress_callback` causes an unhandled `RuntimeError: cannot join current thread`.
- **Where**: `parasite_ai/mind/brain_manager.py:775-780`
  ```python
  def cancel_download(self) -> None:
      """Signals active streaming download to abort and clean up."""
      self._cancel_download_event.set()
      if self._download_thread and self._download_thread.is_alive():
          self._download_thread.join(timeout=2.0)
  ```
- **Why**: `progress_callback(prog)` is executed directly on `self._download_thread`. If a consumer UI widget or callback initiates cancellation upon reaching a condition, `join()` attempts to wait on the currently running thread, raising `RuntimeError`.
- **Suggestion**:
  ```python
  def cancel_download(self) -> None:
      self._cancel_download_event.set()
      if (
          self._download_thread
          and self._download_thread.is_alive()
          and threading.current_thread() != self._download_thread
      ):
          self._download_thread.join(timeout=2.0)
  ```

---

### Finding 2 [Critical / Major] — State Machine Overwrite and Stuck `INFERRING` in `generate`
- **What**: `LocalBrainManager.generate` blindly resets `self.state = prev_state` in its `finally` block, destroying state changes made during inference (such as mode toggles or model unloading) and permanently locking the state to `INFERRING` under concurrent execution.
- **Where**: `parasite_ai/mind/brain_manager.py:861-876`
  ```python
  prev_state = self.state
  self.state = BrainState.INFERRING
  try:
      return self.active_backend.generate(...)
  finally:
      with self._lock:
          self.state = prev_state
  ```
- **Why**:
  1. **Mode/Unload Clobber**: If `toggle_browser_only_mode(True)` or `unload_model()` is called while a long inference is running, `self.mode` becomes `BROWSER_OFFLOAD` (or model unloaded), but when `generate` finishes, `finally` sets `self.state = prev_state (READY_LOCAL)`.
  2. **Concurrent Lockup**: If Thread A enters `generate()`, setting state to `INFERRING`, and Thread B enters `generate()`, Thread B records `prev_state = INFERRING`. When Thread B finishes last, `self.state` is restored to `INFERRING` forever.
- **Suggestion**:
  Do not unconditionally restore `prev_state`. Verify and reconcile against current mode and active backend availability:
  ```python
  finally:
      with self._lock:
          if self.state == BrainState.INFERRING:
              if self.mode == BrainMode.BROWSER_OFFLOAD:
                  self.state = BrainState.READY_BROWSER_OFFLOAD
              elif self.active_backend and self.active_backend.is_available():
                  self.state = BrainState.READY_LOCAL
              else:
                  self.state = BrainState.MODEL_READY_ON_DISK
  ```

---

### Finding 3 [Major] — Action JSON Extractor Fails on Preamble Braces + Nested JSON
- **What**: When LLM output contains conversational preamble with curly braces (e.g. `Checking {state: active}...`) AND the action JSON itself has nested dictionaries (e.g. `metadata: {"key": 1}`), without markdown code fences, all 4 parsing passes fail.
- **Where**: `parasite_ai/mind/brain_manager.py:971-989`
- **Why**:
  - Pass 3 (`r"\{[\s\S]*\}"`) is greedy and captures from `{state: active}` to the end, resulting in invalid JSON.
  - Pass 4 (`r"\{[\s\S]*?\}"`) is non-greedy and prematurely terminates at the inner `}` of the nested dictionary, yielding truncated invalid JSON.
- **Suggestion**:
  Implement a brace-counting / depth-tracking scanner for candidate JSON objects:
  ```python
  def _find_balanced_json_objects(text: str) -> List[str]:
      candidates = []
      start = None
      depth = 0
      in_string = False
      escape = False
      for idx, ch in enumerate(text):
          if ch == '"' and not escape:
              in_string = not in_string
          elif not in_string:
              if ch == '{':
                  if depth == 0:
                      start = idx
                  depth += 1
              elif ch == '}':
                  depth -= 1
                  if depth == 0 and start is not None:
                      candidates.append(text[start : idx + 1])
                      start = None
          escape = (ch == '\\' and not escape)
      return candidates
  ```

---

### Finding 4 [Major] — VRAM Headroom Check Ignores `vram_budget_mb` and Required VRAM
- **What**: In `_instantiate_local_engine`, `req_mb = self.config.brain.local_model.vram_budget_mb` is assigned but never evaluated.
- **Where**: `parasite_ai/mind/brain_manager.py:515-522`
  ```python
  used_mb, free_mb = check_vram_headroom()
  req_mb = self.config.brain.local_model.vram_budget_mb

  gpu_layers = self.config.brain.local_model.gpu_layers
  if free_mb < 2000:
      gpu_layers = 0
  ```
- **Why**: The code only checks hardcoded `if free_mb < 2000:`. If free VRAM is 2500MB and budget is 4000MB or model requires 5200MB, it still sets `gpu_layers = -1`, which can crash the GPU or trigger out-of-memory errors on the physical host.
- **Suggestion**:
  ```python
  if free_mb < req_mb or free_mb < 2000:
      gpu_layers = 0
  ```

---

### Finding 5 [Minor] — `TypeError` on `AppConfig` Environment Variable Override
- **What**: When `PARASITE_LOG_LEVEL` or `PARASITE_BRAIN_MODE` is set and `AppConfig(system=SystemConfig())` is invoked programmatically, `data["system"]` is a `SystemConfig` instance, not a dict.
- **Where**: `parasite_ai/config.py:466-477`
- **Why**: `data.setdefault("system", {})["log_level"] = ...` raises `TypeError: 'SystemConfig' object does not support item assignment`.
- **Suggestion**: Check `isinstance(data.get("system"), dict)` or set attribute directly when it is a Pydantic model instance.

---

### Finding 6 [Minor] — Corrupt Download Artifact Not Unlinked on Header Failure
- **What**: If download finishes but header is not valid GGUF, file is left at `target_path`.
- **Where**: `parasite_ai/mind/brain_manager.py:741-753`
- **Suggestion**: Call `target_path.unlink(missing_ok=True)` when `validate_gguf_header(target_path)` is False.

---

### Finding 7 [Minor] — Unsanitized Path Traversal in `load_model`
- **What**: `fpath = self.models_dir / fname` allows relative directory escape if filename contains `..`.
- **Where**: `parasite_ai/mind/brain_manager.py:812-814`
- **Suggestion**: Enforce `fname = Path(fname).name`.

---

## 3. Caveats
- No changes to source code or tests were made by this reviewer, adhering strictly to the review-only role constraint.
- The 28 original unit tests in `tests/test_config.py` and `tests/test_brain_manager.py` pass cleanly; the 4 failures emerged under adversarial stress suites in `tests/test_stress_*.py`.
- Hardware GPU tests for `llama-cpp-python` with compiled CUDA binaries were simulated via mocking, which matches the zero-VRAM and environment design specifications.

---

## 4. Conclusion
Milestone M1 has high structural quality and zero integrity violations, but cannot be approved in its current state because `uv run pytest` fails with 4 failing test cases across thread cancellation, state machine lifecycle, action extraction, and VRAM budgeting.

**Verdict: REQUEST_CHANGES.**  
The worker must address Findings 1 through 4 in `parasite_ai/mind/brain_manager.py` and ensure `uv run pytest` exits 0 across all 111 tests.

---

## 5. Verification Method

To independently verify after fixes are applied:
1. Ensure working directory is repository root: `g:\__Docs\ParasiteAI`.
2. Run the full pytest suite:
   ```powershell
   uv run pytest -v
   ```
   *Expected result*: 111 passed with exit code 0.
3. Specifically test the 4 previously failing cases:
   ```powershell
   uv run pytest tests/test_stress_concurrency.py::test_cancel_download_from_within_progress_callback tests/test_stress_m1.py::TestBrowserOffloadToggleStress::test_state_machine_generate_and_toggle_interleaving tests/test_stress_m1.py::TestHostileActionExtraction::test_preamble_with_multiple_braces_and_nested_json tests/test_stress_m1.py::TestVRAMBudgetMockHardware::test_vram_budget_exceeded_by_model_headroom -v
   ```
   *Expected result*: All 4 tests PASSED with exit code 0.
