# Handoff Report — Milestone M1 Iteration 3 Explorer

**Author**: `teamwork_explorer_m1_iter3_1`  
**Working Directory**: `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m1_iter3_1\`  
**Target Milestone**: M1 Iteration 3  
**Date**: 2026-10-29  

---

## 1. Observation

### Verbatim Test Failure
Running the focused challenger test command:
```powershell
uv run pytest tests/test_challenger_m1_iter2_1.py -k "test_partial_streaming_clean_close_truncation_detection" -v
```
Resulted in deterministic failure:
```
FAILED tests/test_challenger_m1_iter2_1.py::test_partial_streaming_clean_close_truncation_detection - AssertionError: Vulnerability: Truncated 128-byte partial download of 2.3GB model was marked MODEL_READY_ON_DISK! state=BrainState.MODEL_READY_ON_DISK, target_file_size=128
assert <BrainState.MODEL_READY_ON_DISK: 'MODEL_READY_ON_DISK'> != <BrainState.MODEL_READY_ON_DISK: 'MODEL_READY_ON_DISK'>
 +  where <BrainState.MODEL_READY_ON_DISK: 'MODEL_READY_ON_DISK'> = <parasite_ai.mind.brain_manager.LocalBrainManager object at 0x000001F2F3E55070>.state
 +  and   <BrainState.MODEL_READY_ON_DISK: 'MODEL_READY_ON_DISK'> = BrainState.MODEL_READY_ON_DISK
====================== 1 failed, 26 deselected in 0.91s =======================
```

Full suite execution:
```powershell
uv run pytest -v
```
Produced: `1 failed, 172 passed in 15.88s`. Exactly 1 test in the entire test suite fails.

### Direct Codebase Observation
In `parasite_ai/mind/brain_manager.py` (lines 759–800):
```python
                    if self._cancel_download_event.is_set():
                        logger.info("Download cancelled before completion.")
                        if temp_path.exists():
                            try:
                                temp_path.unlink()
                            except Exception:
                                pass
                        with self._lock:
                            self.state = BrainState.NO_MODEL_PRESENT
                            if self._current_progress:
                                self._current_progress.status = "cancelled"
                        return

                    # Download finished - Validate GGUF header
                    with self._lock:
                        if self._current_progress:
                            self._current_progress.status = "verifying"
                        if progress_callback and self._current_progress:
                            progress_callback(self._current_progress)

                    # Atomically rename
                    if temp_path.exists():
                        if target_path.exists():
                            target_path.unlink()
                        temp_path.replace(target_path)

                    is_valid = validate_gguf_header(target_path)
                    with self._lock:
                        if is_valid:
                            self.state = BrainState.MODEL_READY_ON_DISK
                            self.current_model = filename
                            if self._current_progress:
                                self._current_progress.status = "completed"
                                self._current_progress.percentage = 100.0
                        else:
                            self.state = BrainState.DOWNLOAD_FAILED
                            if self._current_progress:
                                self._current_progress.status = "failed"

                        if progress_callback and self._current_progress:
                            progress_callback(self._current_progress)
```

In `tests/test_challenger_m1_iter2_1.py` (lines 513–519):
```python
    # An incomplete/truncated stream where bytes_downloaded < total_bytes
    # MUST NOT be treated as a successfully completed download!
    assert manager.state != BrainState.MODEL_READY_ON_DISK, (
        f"Vulnerability: Truncated 128-byte partial download of 2.3GB model was marked MODEL_READY_ON_DISK! "
        f"state={manager.state}, target_file_size={models_dir.joinpath('qwen2.5-3b-instruct-q4_k_m.gguf').stat().st_size}"
    )
    assert manager.state == BrainState.DOWNLOAD_FAILED
```

---

## 2. Logic Chain

1. **Premature Clean Stream Termination**:
   - In `_download_worker` (lines 707–758), HTTP chunks are streamed into `temp_path` and `bytes_downloaded` is tracked.
   - When an HTTP server closes the stream prematurely without raising an exception (as mocked by `TruncatedCleanCloseStream`, sending only 128 bytes out of 2,328,221,696 bytes), the `for chunk in resp.iter_bytes(...)` loop terminates naturally.
   - `self._cancel_download_event.is_set()` evaluates to `False` (user did not cancel).
   - No exception was raised, so the `except Exception:` block is bypassed.

2. **Absence of Completeness Verification**:
   - `_download_worker` does NOT compare `bytes_downloaded` or `temp_path.stat().st_size` against `real_total`.
   - The worker immediately proceeds to `temp_path.replace(target_path)`, renaming the truncated 128-byte temporary file to `target_path`.

3. **GGUF Header Validation False Positive**:
   - `validate_gguf_header(target_path)` requires `st_size >= 8`, magic `b"GGUF"`, and version `2` or `3`.
   - Because the 128-byte chunk starts with `b"GGUF\x03\x00\x00\x00"` and has 128 bytes (>= 8), `validate_gguf_header` returns `True`.
   - `_download_worker` sets `self.state = BrainState.MODEL_READY_ON_DISK` and `self._current_progress.status = "completed"`.

4. **Blast Radius**:
   - A corrupt 128-byte stub replaces any existing valid model or masquerades as a fully downloaded 2.3 GB model on disk.
   - Subsequent calls to `load_model()` pass the stub to llama-cpp, failing at runtime.
   - Subsequent calls to `start_download()` are locked out by `target_path.exists() and validate_gguf_header(target_path)`.
   - Zero-VRAM browser offload fallback in `_init_backend()` is bypassed because it detects a seemingly valid local model.

5. **Fix Logic Chain**:
   - Prior to staging validation and rename: check `(real_total > 0 and bytes_downloaded < real_total) or not temp_path.exists() or temp_path.stat().st_size == 0`.
   - If true, log error, unlink `temp_path`, transition `self.state = BrainState.DOWNLOAD_FAILED` and `self._current_progress.status = "failed"`, invoke `progress_callback`, and return.
   - Perform `validate_gguf_header(temp_path)` **before** replacing `target_path`. If header validation fails, unlink `temp_path`, transition to `DOWNLOAD_FAILED`, and abort without corrupting `target_path`.
   - Only call `temp_path.replace(target_path)` if both completeness and header validation succeed.

---

## 3. Caveats

1. **Enum & Status Contract**:
   - The dispatch prompt mentioned: `set progress.status = 'error'` and `set self.state = BrainState.ERROR_DOWNLOAD_FAILED (or prior model state if one existed)`.
   - In `parasite_ai/mind/brain_manager.py`:
     - `BrainState` defines `DOWNLOAD_FAILED`, NOT `ERROR_DOWNLOAD_FAILED`. Accessing `BrainState.ERROR_DOWNLOAD_FAILED` will raise `AttributeError`.
     - `DownloadProgress.status` is typed and documented with allowed statuses: `downloading, verifying, completed, failed, cancelled`.
     - Pytest assertions across the test suite (`test_challenger_m1_iter2_1.py:519`, `test_brain_manager.py:424`, `test_stress_gguf.py:259`) strictly require `assert manager.state == BrainState.DOWNLOAD_FAILED` and `assert events[-1].status == "failed"`.
     - Therefore, the fix must use `BrainState.DOWNLOAD_FAILED` and `status = "failed"`. Reverting to a prior model state or setting `"error"` would fail line 519 of `test_challenger_m1_iter2_1.py`.

2. **Callback Deadlock Prevention**:
   - All `progress_callback` invocations must remain **outside** the `with self._lock:` block to prevent re-entrant deadlocks, which was verified by stress tests in Iteration 2.

3. **No Source Modifications Made**:
   - Consistent with the Explorer read-only persona, no files outside `.agents/teamwork/teamwork_explorer_m1_iter3_1/` have been created or modified.

---

## 4. Conclusion

The exact defect in `parasite_ai/mind/brain_manager.py` is the lack of stream completeness verification prior to promoting temporary download files to destination `.gguf` models.

The Worker must implement the recommended fix in `parasite_ai/mind/brain_manager.py` (lines 771–800) as documented in `plan.md` and `proposed_brain_manager.patch`:
- Add completeness verification: if `(real_total > 0 and bytes_downloaded < real_total) or (real_total > 0 and temp_size < real_total) or temp_size == 0`, unlink `temp_path`, transition to `BrainState.DOWNLOAD_FAILED` with `status = "failed"`, and return.
- Validate `temp_path` before atomically renaming to `target_path`.

---

## 5. Verification Method

To independently verify the fix:

1. **Targeted Challenger Test**:
   ```powershell
   uv run pytest tests/test_challenger_m1_iter2_1.py -k "test_partial_streaming_clean_close_truncation_detection" -v
   ```
   - Current: Fails (`AssertionError: Vulnerability: Truncated 128-byte partial download of 2.3GB model was marked MODEL_READY_ON_DISK!`).
   - Expected post-fix: **1 passed**.

2. **Full Project Test Suite**:
   ```powershell
   uv run pytest -v
   ```
   - Current: `1 failed, 172 passed`.
   - Expected post-fix: **173 passed, 0 failed**.

### Files Created by Explorer
- `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m1_iter3_1\plan.md`
- `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m1_iter3_1\proposed_brain_manager.patch`
- `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m1_iter3_1\handoff.md`
- `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m1_iter3_1\progress.md`
- `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m1_iter3_1\BRIEFING.md`
- `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m1_iter3_1\DISPATCH.md`
