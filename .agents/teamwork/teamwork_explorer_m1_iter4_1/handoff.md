# Explorer Investigation & Design Handoff Report — Milestone 1 Iteration 4

**Agent**: `teamwork_explorer_m1_iter4_1`  
**Working Directory**: `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m1_iter4_1\`  
**Target Module**: `parasite_ai/mind/brain_manager.py`  
**Failing Test**: `tests/test_challenger_m1_iter3.py::test_adversarial_stream_truncation_and_overflow[real_total_plus_100-1000000-1000100]`

---

## 1. Observation

1. **Reproduction Execution & Verbatim Error**:
   Executed `uv run pytest tests/test_challenger_m1_iter3.py -v`:
   ```
   tests/test_challenger_m1_iter3.py::test_adversarial_stream_truncation_and_overflow[0_bytes-1000000-0] PASSED [ 20%]
   tests/test_challenger_m1_iter3.py::test_adversarial_stream_truncation_and_overflow[1_byte-1000000-1] PASSED [ 40%]
   tests/test_challenger_m1_iter3.py::test_adversarial_stream_truncation_and_overflow[16_bytes_header_only-1000000-16] PASSED [ 60%]
   tests/test_challenger_m1_iter3.py::test_adversarial_stream_truncation_and_overflow[real_total_minus_1-1000000-999999] PASSED [ 80%]
   tests/test_challenger_m1_iter3.py::test_adversarial_stream_truncation_and_overflow[real_total_plus_100-1000000-1000100] FAILED [100%]

   FAILED tests/test_challenger_m1_iter3.py::test_adversarial_stream_truncation_and_overflow[real_total_plus_100-1000000-1000100] - AssertionError: Vulnerability: Incomplete/mismatched stream (real_total_plus_100: sent 1000100 vs expected 1000000) was promoted to destination model file: [WindowsPath('.../models_real_total_plus_100/qwen2.5-3b-instruct-q4_k_m.gguf')]
   assert 1 == 0
    +  where 1 = len([WindowsPath('.../models_real_total_plus_100/qwen2.5-3b-instruct-q4_k_m.gguf')])
   ```

2. **Source Inspection — Completeness Verification (`parasite_ai/mind/brain_manager.py:776-784`)**:
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

3. **Source Inspection — Chunk Download Loop (`parasite_ai/mind/brain_manager.py:710-730`)**:
   ```python
   with open(temp_path, "wb") as f:
       for chunk in resp.iter_bytes(chunk_size=256 * 1024):
           if self._cancel_download_event.is_set():
               logger.info("Download cancelled by user.")
               ...
               return

           f.write(chunk)
           bytes_downloaded += len(chunk)
           now = time.time()
   ```
   No check exists inside the loop to verify if `bytes_downloaded` exceeds `real_total`.

4. **Baseline Suite Health**:
   Executed `uv run pytest -k "not test_adversarial_stream_truncation_and_overflow[real_total_plus_100-1000000-1000100]"`:
   `177 passed, 1 deselected in 16.20s` (exit code 0).

---

## 2. Logic Chain

1. From *Observation 2*, the completeness check only triggers when `bytes_downloaded < real_total` or `temp_size < real_total` or `temp_size == 0`.
2. When the server streams `real_total + 100` bytes (1,000,100 bytes against a `Content-Length` of 1,000,000 bytes):
   - `bytes_downloaded < real_total` is `False` (`1000100 < 1000000` is `False`).
   - `temp_size < real_total` is `False` (`1000100 < 1000000` is `False`).
   - `temp_size == 0` is `False`.
   Therefore, the error handling block at lines 785–797 is completely bypassed.
3. Execution proceeds to line 808 (`validate_gguf_header(temp_path)`). Because `validate_gguf_header` validates only the 16-byte GGUF header (`b"GGUF"` magic and version `3`), the oversized payload passes binary header validation.
4. Execution reaches lines 826–840, promoting `temp_path` to `target_path` (`temp_path.replace(target_path)`) and setting `self.state = BrainState.MODEL_READY_ON_DISK`. This directly causes the assertion failure observed in *Observation 1*.
5. From *Observation 3*, inside the streaming loop, the worker continues reading and writing chunks without bound. For large or infinite streams (stream desync, response smuggling, or denial of service), the client will exhaust disk space before reaching any post-download check.
6. Breaking immediately from the chunk loop when `real_total > 0 and bytes_downloaded > real_total`:
   - Halts further network read calls on `resp.iter_bytes()`.
   - Naturally exits `with open(temp_path, "wb") as f:`, closing the file handle (avoiding Windows `PermissionError` during `unlink()`).
   - Naturally exits `with httpx.stream(...) as resp:`, cleanly closing the HTTP connection.
   - Falls directly into the post-download completeness check.
7. Updating the post-download check at line 777 to check `!= real_total` (two-sided equality) ensures that any size mismatch—whether from early abort or end-of-stream discrepancy—is caught, staging `.tmp` files are deleted, state transitions to `BrainState.DOWNLOAD_FAILED`, and the progress status is set to `'failed'`.

---

## 3. Caveats

- **Content-Length Absence**: In standard HTTP downloads from Hugging Face, `Content-Length` is consistently provided. If a non-standard HTTP endpoint does not send `Content-Length`, `resp.headers.get("content-length", total_bytes)` falls back to `total_bytes` (from `CURATED_MODELS` or default `2000000000`). In that case, strict equality requires the downloaded payload to match `total_bytes`. This is the intentional and expected integrity invariant.
- **Scope Restriction**: In accordance with the Explorer archetype and explicit constraints, no source code files were edited during this investigation.

---

## 4. Conclusion

The fix requires two complementary changes in `parasite_ai/mind/brain_manager.py`:

1. **Chunk-Loop Early Abort (`parasite_ai/mind/brain_manager.py:728-732`)**:
   Add an immediate check after accumulating `bytes_downloaded += len(chunk)`:
   ```python
   f.write(chunk)
   bytes_downloaded += len(chunk)

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

2. **Two-Sided Integrity Check (`parasite_ai/mind/brain_manager.py:776-797`)**:
   Replace line 777 with:
   ```python
   # Completeness Verification: Detect truncated, oversized, or corrupted stream termination
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

---

## 5. Verification Method

1. **Targeted Adversarial Test Suite**:
   ```powershell
   uv run pytest tests/test_challenger_m1_iter3.py -v
   ```
   - **Passing Criteria**: All 5 variations (`0_bytes`, `1_byte`, `16_bytes_header_only`, `real_total_minus_1`, `real_total_plus_100`) pass. Exit code 0.
   - **Invalidation Condition**: If `test_adversarial_stream_truncation_and_overflow[real_total_plus_100-1000000-1000100]` fails or creates any `.gguf` or dangling `.tmp` file.

2. **Full Project Test Suite**:
   ```powershell
   uv run pytest -v
   ```
   - **Passing Criteria**: All 178 tests pass. Exit code 0.
