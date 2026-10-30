# Handoff Report: Two-Sided Stream Verification & Early Abort Fix

**Agent**: `teamwork_worker_m1_iter4`  
**Milestone**: M1 Iteration 4  
**Date**: 2026-10-29  
**Recipient**: `orchestrator` (`9a16f679-6db4-4849-ba56-0f4856cbbf9b`)  

---

## 1. Observation

1. **Initial Test Run Failure**:
   Running `uv run pytest tests/test_challenger_m1_iter3.py -v` produced 1 failure and 4 passes:
   ```
   FAILED tests/test_challenger_m1_iter3.py::test_adversarial_stream_truncation_and_overflow[real_total_plus_100-1000000-1000100] - AssertionError: Vulnerability: Incomplete/mismatched stream (real_total_plus_100: sent 1000100 vs expected 1000000) was promoted to destination model file: [WindowsPath('C:/Users/Suici/AppData/Local/Temp/pytest-of-Suici/pytest-106/test_adversarial_stream_trunca4/models_real_total_plus_100/qwen2.5-3b-instruct-q4_k_m.gguf')]
   assert 1 == 0
   ```
2. **Vulnerability Location**:
   In `parasite_ai/mind/brain_manager.py`:
   - At line 728, chunks were written and `bytes_downloaded` accumulated without checking whether `bytes_downloaded > real_total`.
   - At line 777 (prior to edit), post-download verification used one-sided inequality:
     ```python
     temp_size = temp_path.stat().st_size if temp_path.exists() else 0
     if (real_total > 0 and bytes_downloaded < real_total) or (real_total > 0 and temp_size < real_total) or temp_size == 0:
     ```
   Because `1000100 < 1000000` is `False`, the failure block was skipped, and the oversized file was promoted to the destination `.gguf` file.
3. **Applied Code Edits**:
   - Added early chunk-loop abort in `parasite_ai/mind/brain_manager.py` (lines 731–740):
     ```python
     # Early abort if stream exceeds expected content length
     if real_total > 0 and bytes_downloaded > real_total:
         logger.error(
             "Download stream overflow for %s: received %d bytes > %d expected bytes (aborting stream)",
             filename,
             bytes_downloaded,
             real_total,
         )
         break
     ```
   - Updated completeness verification in `parasite_ai/mind/brain_manager.py` (lines 786–815):
     ```python
     # Completeness Verification: Detect truncated stream or oversized overflow
     temp_size = temp_path.stat().st_size if temp_path.exists() else 0
     if (
         (real_total > 0 and bytes_downloaded != real_total)
         or (real_total > 0 and temp_size != real_total)
         or temp_size == 0
         or real_total <= 0
     ):
         logger.error(
             "Download size mismatch or incomplete for %s: received %d of %d expected bytes (on-disk: %d bytes)",
             filename,
             bytes_downloaded,
             real_total,
             temp_size,
         )
         if temp_path.exists():
             try:
                 temp_path.unlink()
             except Exception:
                 pass
         with self._lock:
             self.state = BrainState.DOWNLOAD_FAILED
             if self._current_progress:
                 self._current_progress.status = "failed"
                 self._current_progress.bytes_downloaded = bytes_downloaded
             prog = self._current_progress
         if progress_callback and prog:
             progress_callback(prog)
         return
     ```
4. **Targeted Test Results**:
   Running `uv run pytest tests/test_challenger_m1_iter3.py -v`:
   ```
   ============================== 5 passed in 0.77s ==============================
   ```
5. **Full Test Suite Results**:
   Running `uv run pytest -v`:
   ```
   ============================ 178 passed in 15.97s =============================
   Exit code: 0
   ```

---

## 2. Logic Chain

1. In the adversarial test `real_total_plus_100`, the mock server yields 1,000,100 bytes against a `Content-Length` of 1,000,000.
2. With the early abort condition `if real_total > 0 and bytes_downloaded > real_total: break`, as soon as a chunk causes `bytes_downloaded` to exceed 1,000,000, the chunk loop immediately breaks. This prevents unbounded stream consumption and closes file handles and network sockets.
3. Upon exiting the loop, the two-sided equality check evaluates:
   - `real_total > 0 and bytes_downloaded != real_total`: evaluates to `True` (e.g. 1,000,100 != 1,000,000 or truncated byte count).
   - `real_total > 0 and temp_size != real_total`: evaluates to `True`.
4. Entering the mismatch branch executes `temp_path.unlink()`, preventing any file accumulation or dangling `.tmp` files.
5. `self.state = BrainState.DOWNLOAD_FAILED` and `self._current_progress.status = "failed"` are set under `self._lock`, and `progress_callback` is notified.
6. The function returns before reaching GGUF header validation or atomic file promotion (`temp_path.replace(target_path)`).
7. For valid downloads (such as `test_download_streaming_and_callbacks` with 2,056 bytes), `bytes_downloaded == real_total` and `temp_size == real_total`, so the branch is bypassed, header validation succeeds, and the file is properly promoted to `BrainState.MODEL_READY_ON_DISK`.
8. Consequently, 100% of tests (178/178) pass with zero regressions.

---

## 3. Caveats

No caveats. The changes strictly target download stream size validation in `parasite_ai/mind/brain_manager.py` without introducing external dependencies or altering unrelated interfaces.

---

## 4. Conclusion

The adversarial stream overflow vulnerability is completely resolved. Oversized streams abort early during chunk writing and fail completeness validation. Temporary files are unlinked, the state transitions to `BrainState.DOWNLOAD_FAILED`, and the progress status is set to `"failed"`. All 178 tests across the test suite pass with exit code 0.

---

## 5. Verification Method

To independently reproduce and verify this fix:

1. **Run the adversarial stream test suite**:
   ```powershell
   uv run pytest tests/test_challenger_m1_iter3.py -v
   ```
   *Expected result*: All 5 tests pass (`0_bytes`, `1_byte`, `16_bytes_header_only`, `real_total_minus_1`, `real_total_plus_100`).

2. **Run the full test suite**:
   ```powershell
   uv run pytest -v
   ```
   *Expected result*: All 178 tests pass with exit code 0.

3. **Inspect the source changes**:
   Inspect lines 728–740 and 786–815 in `parasite_ai/mind/brain_manager.py`.

Invalidation condition: Any test failure in `pytest` or promotion of oversized/corrupted files to `.gguf` destination.
