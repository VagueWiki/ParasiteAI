# Handoff Report — Milestone M1 Iteration 2 Challenger

**Author**: `teamwork_challenger_m1_iter2_1`  
**Working Directory**: `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_challenger_m1_iter2_1\`  
**Date**: 2026-10-29  
**Verdict**: **REQUEST_CHANGES**

---

## 1. Observation

### Test Execution Summary
- **Baseline suite (`uv run pytest -v`)**: Passed 111 of 111 baseline tests.
- **Combined suite with Challenger 2 tests**: Passed 146 of 146 tests (`tests/test_challenger_m1_iter2.py`).
- **Empirical stress suite authored by instance 1 (`tests/test_challenger_m1_iter2_1.py`)**: 27 tests executed:
  - 26 passed.
  - 1 failed deterministically: `tests/test_challenger_m1_iter2_1.py::test_partial_streaming_clean_close_truncation_detection`.

### Verbatim Failure
```
FAILED tests/test_challenger_m1_iter2_1.py::test_partial_streaming_clean_close_truncation_detection - AssertionError: Vulnerability: Truncated 128-byte partial download of 2.3GB model was marked MODEL_READY_ON_DISK! state=BrainState.MODEL_READY_ON_DISK, target_file_size=128
assert <BrainState.MODEL_READY_ON_DISK: 'MODEL_READY_ON_DISK'> != <BrainState.MODEL_READY_ON_DISK: 'MODEL_READY_ON_DISK'>
 +  where <BrainState.MODEL_READY_ON_DISK: 'MODEL_READY_ON_DISK'> = <parasite_ai.mind.brain_manager.LocalBrainManager object at 0x0000019200D93560>.state
 +  and   <BrainState.MODEL_READY_ON_DISK: 'MODEL_READY_ON_DISK'> = BrainState.MODEL_READY_ON_DISK
======================= 1 failed, 172 passed in 16.56s ========================
```

### Verified Target Defect in Codebase
In `parasite_ai/mind/brain_manager.py` (lines 707–795):
```python
707: with httpx.stream("GET", download_url, follow_redirects=True, timeout=30.0) as resp:
708:     resp.raise_for_status()
709:     real_total = int(resp.headers.get("content-length", total_bytes))
710:     with open(temp_path, "wb") as f:
711:         for chunk in resp.iter_bytes(chunk_size=256 * 1024):
...
729:             bytes_downloaded += len(chunk)
...
779: # Atomically rename
780: if temp_path.exists():
781:     if target_path.exists():
782:         target_path.unlink()
783:     temp_path.replace(target_path)
784: 
785: is_valid = validate_gguf_header(target_path)
786: with self._lock:
787:     if is_valid:
788:         self.state = BrainState.MODEL_READY_ON_DISK
789:         self.current_model = filename
790:         if self._current_progress:
791:             self._current_progress.status = "completed"
792:             self._current_progress.percentage = 100.0
```

---

## 2. Logic Chain

1. **Re-entrant `cancel_download` & Worker Abort Evaluation**:
   - `test_reentrant_cancel_with_simultaneous_caller_threads`: 10 external threads calling `cancel_download()` while the worker thread callback concurrently invokes `cancel_download()`. Passed cleanly with zero deadlocks or `RuntimeError: cannot join current thread`.
   - `test_reentrant_cancel_recursive_and_nested_in_callback`: 3 nested recursive calls to `cancel_download()` from within `on_progress` callback on the worker thread. Passed cleanly due to RLock recursion safety.
   - `test_simultaneous_worker_abort_and_multiple_cancels`: Mid-stream network abort with 12 external cancellation threads. Passed cleanly, all `.tmp` files unlinked.
   - `test_start_cancel_hammer_flood`: 30 rapid start/cancel cycles across threads. Passed cleanly.
   - **Assessment**: The worker's fix for re-entrant `cancel_download()` is empirically robust and passes adversarial stress testing.

2. **Concurrency Under High Thread Count (15 Threads) Calling `generate()` While Mode Toggles**:
   - `test_high_concurrency_generate_15_threads_with_continuous_mode_toggling`: 15 worker threads concurrently calling `generate()` while 3 controller threads continuously hammer `toggle_browser_only_mode(True/False)` for 1.5 seconds.
   - Handled >100 interleaved generation calls without exceptions.
   - Upon termination and joining all threads, `_inferring_count` reached 0 and `manager.state` properly restored to match `manager.mode` (e.g. `READY_BROWSER_OFFLOAD` when offload enabled, `READY_LOCAL` when local).
   - `manager.state` was never left stuck in `INFERRING`.
   - `test_concurrent_generate_with_rapid_model_load_unload`: 12 inference threads operating while models are unloaded and loaded in memory. Passed without `NoneType` or concurrency crashes.
   - **Assessment**: The worker's fix for concurrent `generate()` state management is empirically robust and passes adversarial stress testing.

3. **Corrupted GGUF Header Validation**:
   - Evaluated 19 distinct corrupted, malformed, truncated, and unsupported GGUF header variations in `test_adversarial_gguf_header_matrix` (empty file, truncated 1–7 byte files, mutated magic, unsupported versions 0, 1, 4, 255, 65535, max uint32, big-endian byte order).
   - All 19 variants were deterministically rejected by `validate_gguf_header`.
   - **Assessment**: Header format validation is sound.

4. **Partial Streaming Download Truncation Vulnerability (The Breaking Flaw)**:
   - When a streaming download starts, `real_total` is established from `content-length` (e.g. 2,328,221,696 bytes for Qwen 2.5-3B).
   - If the HTTP stream closes prematurely after transferring only a partial payload (e.g., 128 bytes containing `b"GGUF\x03\x00\x00\x00"`) without raising an exception (e.g. clean socket close, proxy cut, or truncated stream):
     - `_download_worker` iterates over the stream, writes 128 bytes, and exits the loop.
     - `_cancel_download_event.is_set()` is `False` (user did not cancel).
     - `_download_worker` does NOT verify `bytes_downloaded >= real_total` or check `target_path.stat().st_size >= real_total`.
     - `temp_path` is atomically renamed to `target_path` (`qwen2.5-3b-instruct-q4_k_m.gguf`).
     - `validate_gguf_header(target_path)` checks `st_size >= 8`, `magic == b"GGUF"`, and `version in (2, 3)`. All evaluate to `True` for the 128-byte truncated stub!
     - `_download_worker` sets `self.state = BrainState.MODEL_READY_ON_DISK` and `self._current_progress.status = "completed"` with `percentage = 100.0`.
   - **Blast Radius**:
     - The assistant believes a full model exists on disk.
     - Subsequent calls to `manager.start_download()` hit lines 686–691: `if target_path.exists() and validate_gguf_header(target_path): return False`. Re-downloading is permanently locked out.
     - Subsequent calls to `manager.load_model()` pass the 128-byte stub to `llama_cpp`, causing runtime failure.
     - In `_init_backend()`, the assistant selects this broken stub and fails rather than safely falling back to Zero-VRAM Browser Offload mode.

---

## 3. Caveats

- Real hardware GPU inference with physical GGUF weights was mocked; real llama-cpp bindings rely on upstream C++ libraries which would segfault or raise C++ runtime exceptions on truncated weights.
- The failure only occurs when a server or middlebox prematurely terminates the stream cleanly without throwing an `httpx` socket error. If a socket error is raised, lines 801–814 handle it as `DOWNLOAD_FAILED`. However, clean truncations (common with flaky HTTP proxies, CDN cutoffs, or chunked transfer drops) bypass this completely.

---

## 4. Conclusion

**Verdict: REQUEST_CHANGES**

The worker must implement size completeness verification in `_download_worker()`:
1. In `parasite_ai/mind/brain_manager.py`, before renaming `temp_path` to `target_path` (or during verification), verify:
   ```python
   if real_total > 0 and bytes_downloaded < real_total:
       logger.error("Download incomplete: received %d of %d bytes", bytes_downloaded, real_total)
       if temp_path.exists():
           try:
               temp_path.unlink()
           except Exception:
               pass
       with self._lock:
           self.state = BrainState.DOWNLOAD_FAILED
           if self._current_progress:
               self._current_progress.status = "failed"
       if progress_callback and self._current_progress:
           progress_callback(self._current_progress)
       return
   ```
2. Ensure that partial files are unlinked and never renamed to `target_path`.

---

## 5. Verification Method

To independently reproduce the vulnerability and verify the fix:

1. **Execute Challenger Stress Test**:
   ```powershell
   uv run pytest tests/test_challenger_m1_iter2_1.py -k "test_partial_streaming_clean_close_truncation_detection" -v
   ```
   - *Current Result*: Fails with `AssertionError: Vulnerability: Truncated 128-byte partial download of 2.3GB model was marked MODEL_READY_ON_DISK!`.
   - *Expected Post-Fix Result*: Passes (manager transitions to `DOWNLOAD_FAILED`, target file is not created/renamed, progress status is `failed`).

2. **Execute Full Suite**:
   ```powershell
   uv run pytest -v
   ```
   - *Current Result*: 1 failed, 172 passed.
   - *Expected Post-Fix Result*: 173 passed.

### Files to Inspect
- `tests/test_challenger_m1_iter2_1.py` (lines 485–520)
- `parasite_ai/mind/brain_manager.py` (lines 770–800)
