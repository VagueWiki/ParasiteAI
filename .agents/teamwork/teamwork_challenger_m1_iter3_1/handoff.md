# Empirical Challenger Handoff Report — Milestone 1 Iteration 3

**Verdict**: **REQUEST_CHANGES**

## 1. Observation
1. **Target File & Lines**: `parasite_ai/mind/brain_manager.py` lines 776–784:
   ```python
   # Completeness Verification: Detect truncated / premature stream termination
   temp_size = temp_path.stat().st_size if temp_path.exists() else 0
   if (real_total > 0 and bytes_downloaded < real_total) or (real_total > 0 and temp_size < real_total) or temp_size == 0:
       logger.error(
           "Download incomplete for %s: received %d of %d expected bytes (on-disk: %d bytes)",
           filename,
           bytes_downloaded,
           real_total,
           temp_size,
       )
   ```
2. **Re-run of Baseline and Truncation Tests**:
   - `uv run pytest tests/test_challenger_m1_iter2_1.py -k "test_partial_streaming_clean_close_truncation_detection" -v`:
     `1 passed, 26 deselected in 0.62s` (exit code 0).
   - Baseline suite before new test file: `173 passed in 17.70s` (exit code 0).
3. **Empirical Adversarial Variations Suite**:
   Executed `uv run pytest tests/test_challenger_m1_iter3.py -v` across the 5 required variations (content-length: 1,000,000 bytes):
   - `0_bytes`: PASSED (transited to `BrainState.DOWNLOAD_FAILED`, 0 `.tmp` files, 0 `.gguf` files).
   - `1_byte`: PASSED (transited to `BrainState.DOWNLOAD_FAILED`, 0 `.tmp` files, 0 `.gguf` files).
   - `16_bytes_header_only`: PASSED (transited to `BrainState.DOWNLOAD_FAILED`, 0 `.tmp` files, 0 `.gguf` files).
   - `real_total_minus_1`: PASSED (transited to `BrainState.DOWNLOAD_FAILED`, 0 `.tmp` files, 0 `.gguf` files).
   - `real_total_plus_100`: **FAILED** with exit code 1:
     ```
     FAILED tests/test_challenger_m1_iter3.py::test_adversarial_stream_truncation_and_overflow[real_total_plus_100-1000000-1000100] - AssertionError: Vulnerability: Incomplete/mismatched stream (real_total_plus_100: sent 1000100 vs expected 1000000) was promoted to destination model file: [WindowsPath('.../models_real_total_plus_100/qwen2.5-3b-instruct-q4_k_m.gguf')]
     assert 1 == 0
      +  where 1 = len([WindowsPath('.../models_real_total_plus_100/qwen2.5-3b-instruct-q4_k_m.gguf')])
     ```
4. **Full Suite Execution**:
   - `uv run pytest -v`: `1 failed, 177 passed in 16.05s` (exit code 1).

## 2. Logic Chain
1. *Observation 1* shows that the completeness check only evaluates `bytes_downloaded < real_total` and `temp_size < real_total` (strictly less than). It completely omits checking whether `bytes_downloaded > real_total` or `temp_size > real_total`.
2. When an HTTP stream yields `real_total + 100` bytes (e.g. 1,000,100 bytes against a 1,000,000 byte Content-Length):
   - `bytes_downloaded < real_total` evaluates to `False`.
   - `temp_size < real_total` evaluates to `False`.
   - `temp_size == 0` evaluates to `False`.
   Consequently, the failure block (lines 785–797) does NOT execute.
3. Execution then proceeds to line 808: `is_valid = validate_gguf_header(temp_path)`. Because `validate_gguf_header` only checks magic (`b"GGUF"`) and version (`2` or `3`) in the first 8 bytes, an oversized payload starting with a valid header passes validation.
4. Execution then reaches lines 826–840:
   - `temp_path.replace(target_path)` promotes the oversized, corrupted file to destination.
   - `self.state = BrainState.MODEL_READY_ON_DISK` marks the model as ready.
   - `self._current_progress.status = "completed"` and `percentage = 100.0`.
   - The file is NOT cleaned up, and state is NOT `BrainState.DOWNLOAD_FAILED`.
5. *Observation 3* empirically confirms that for `real_total_plus_100`, the target file was created on disk (`targets=1`) and `manager.state` was `BrainState.MODEL_READY_ON_DISK`.

## 3. Caveats
- No caveats. The behavior was reproduced deterministically through automated testing via `pytest`.

## 4. Conclusion
- The fix in `teamwork_worker_m1_iter3` successfully addressed truncation (`< real_total`, 0B, 1B, 16B, `real_total - 1`), but left an asymmetric vulnerability for stream overflow / oversized payloads (`> real_total`, e.g. `real_total + 100`).
- Any size mismatch (`!= real_total`) represents a payload corruption, HTTP stream desynchronization, response splitting, or boundary leak.
- **Actionable Remediation**:
  In `parasite_ai/mind/brain_manager.py:777`, update the condition to enforce strict equality when `real_total > 0`:
  ```python
  if (real_total > 0 and bytes_downloaded != real_total) or (real_total > 0 and temp_size != real_total) or temp_size == 0:
      logger.error(
          "Download size mismatch or incomplete for %s: received %d of %d expected bytes (on-disk: %d bytes)",
          filename,
          bytes_downloaded,
          real_total,
          temp_size,
      )
  ```
  This immediately catches both truncation (`< real_total`) and overflow (`> real_total`), cleans up `temp_path`, sets `BrainState.DOWNLOAD_FAILED`, and marks `status = "failed"`.

## 5. Verification Method
- **Targeted Adversarial Test Suite**:
  ```powershell
  uv run pytest tests/test_challenger_m1_iter3.py -v
  ```
  Expected on fixed code: `5 passed in ~1.0s` (exit code 0).
  Current behavior: `1 failed, 4 passed` (`test_adversarial_stream_truncation_and_overflow[real_total_plus_100-1000000-1000100]` fails).
- **Full Test Suite Execution**:
  ```powershell
  uv run pytest -v
  ```
  Expected on fixed code: `178 passed` (exit code 0).
