# Implementation Plan & Recommendations for Worker: Download State Machine Recovery & Atomic File Cleanup

**Target File**: `parasite_ai/mind/brain_manager.py`  
**Author**: `teamwork_explorer_m1_iter3_2`  
**Date**: 2026-10-29  
**Status**: Ready for Implementation  

---

## 1. Problem Formulation & Root Cause Analysis

### 1.1 The Breaking Defect
In `tests/test_challenger_m1_iter2_1.py::test_partial_streaming_clean_close_truncation_detection`:
When an HTTP streaming connection cleanly closes after receiving only 128 bytes (with a valid 8-byte GGUF header) out of a 2.3 GB payload:
1. The chunk iteration finishes without raising an HTTP exception.
2. The download worker moves the 128-byte `.tmp` file to `target_path` (`qwen2.5-3b-instruct-q4_k_m.gguf`).
3. `validate_gguf_header(target_path)` checks only `size >= 8`, magic `b"GGUF"`, and version `3`, all of which pass on the 128-byte stub.
4. The manager falsely transitions to `BrainState.MODEL_READY_ON_DISK` with `current_model = filename` and `status = "completed"`.
5. The broken 128-byte stub is left permanently on disk, poisoning subsequent startups and preventing re-downloading.

### 1.2 Root Cause 1: Lack of Size Completeness Verification
`_download_worker` in `parasite_ai/mind/brain_manager.py` tracks `bytes_downloaded` and extracts `real_total` from `resp.headers.get("content-length")` (falling back to curated/default size). However, when the stream loop terminates, it **never compares** `bytes_downloaded` against `real_total`.

### 1.3 Root Cause 2: Inverted Validation and File Move Order
In `parasite_ai/mind/brain_manager.py` lines 780–785:
```python
# CURRENT FLAWED SEQUENCE:
if temp_path.exists():
    if target_path.exists():
        target_path.unlink()
    temp_path.replace(target_path)  # <--- Destroys previous target_path BEFORE validation!

is_valid = validate_gguf_header(target_path) # <--- Validates AFTER overwrite!
```
This is a critical architectural violation:
- If `temp_path` is corrupt or truncated, it **deletes any pre-existing valid model at `target_path`** and replaces it with broken data.
- If `validate_gguf_header` then fails, `target_path` is **never cleaned up**; the corrupt `.gguf` file remains on disk.

### 1.4 Root Cause 3: Ambiguity Around `self.current_model` and Previous Models
- If a user already had Model A loaded or on disk, and attempts to download Model B which fails or truncates:
  - If `self.current_model` is blindly set to `filename` (Model B), the assistant points to a non-existent or failed model.
  - If `self.current_model` is unconditionally cleared to `None`, the assistant loses reference to Model A, which was valid and unharmed on disk!
  - If `self.current_model` is left unverified, dangling pointers can occur.

---

## 2. Architectural Design & Invariants

### Invariant 1: Four-Phase Atomic Download Pipeline
1. **Phase 1: Streaming to Isolated Staging Path**:
   Write all bytes exclusively to `temp_path = self.models_dir / f"{filename}.download.tmp"`. Never touch `target_path` during streaming.
2. **Phase 2: Size Completeness Check**:
   Immediately upon stream loop completion, verify:
   `bytes_downloaded >= real_total` (if `real_total > 0`) and `bytes_downloaded >= 8`.
   If incomplete, immediately unlink `temp_path`, transition to `DOWNLOAD_FAILED`, and exit without touching `target_path`.
3. **Phase 3: In-Situ Header Validation on Staged Temp File**:
   Validate `validate_gguf_header(temp_path)` **before** any rename!
   If header validation fails, immediately unlink `temp_path`, transition to `DOWNLOAD_FAILED`, and exit without touching `target_path`.
4. **Phase 4: Atomic Promotion**:
   Only after Phase 2 AND Phase 3 pass completely:
   Replace `target_path` with `temp_path` using `temp_path.replace(target_path)`.
   Transition to `MODEL_READY_ON_DISK` with `self.current_model = filename` and `status = "completed"`.

### Invariant 2: State Transitions on Failure / Truncation
- On **stream truncation** (`bytes_downloaded < real_total`), **corrupted header**, or **network/OS exception**:
  - `self.state = BrainState.DOWNLOAD_FAILED`
  - `self._current_progress.status = "failed"`
  - Call progress callback (if provided).
  - `target_path` is untouched.
- On **user cancellation** (`cancel_download()`):
  - `self.state = BrainState.NO_MODEL_PRESENT`
  - `self._current_progress.status = "cancelled"`
  - Call progress callback (if provided).
  - `temp_path` is unlinked; `target_path` is untouched.

### Invariant 3: `self.current_model` Retention & Sanitization
On download failure, truncation, or cancellation:
- **Never** set `self.current_model` to the failed download's target filename.
- Check the validity of the previous model:
  ```python
  if self.current_model:
      prev_file = self.models_dir / self.current_model
      if not (prev_file.is_file() and validate_gguf_header(prev_file)):
          self.current_model = None
  ```
- **Rule Summary**:
  - If a valid model was already on disk and unharmed, `self.current_model` is **KEPT** intact so the system can reload it or continue running inference.
  - If no model was previously on disk (or the previous file was missing/corrupt), `self.current_model` is set to `None`.

### Invariant 4: Zero Dangling Stubs Guarantee
- If a download fails or is cancelled at any stage:
  - `temp_path.unlink()` is guaranteed to execute (wrapped in `try ... except Exception: pass` after closing file handles).
  - Since `temp_path` was never renamed to `target_path`, `target_path` never receives broken files.
  - No `.download.tmp` files or truncated `.gguf` stubs are left to block subsequent `start_download()` calls.

---

## 3. Concrete Code Modifications for Worker

### Target File: `parasite_ai/mind/brain_manager.py`

#### Edit: Replace lines 759–814 in `LocalBrainManager._download_worker()`

**Existing Flawed Code** (Lines 759–814):
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

                except Exception as exc:
                    logger.error("Download failed: %s", exc)
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
```

**Proposed Replacement Code**:
```python
                    # Helper for safe cleanup of temp file
                    def _cleanup_temp() -> None:
                        if temp_path.exists():
                            try:
                                temp_path.unlink()
                            except Exception:
                                pass

                    # Helper to sanitize current_model on failure
                    def _sanitize_current_model() -> None:
                        if self.current_model:
                            prev_path = self.models_dir / self.current_model
                            if not (prev_path.is_file() and validate_gguf_header(prev_path)):
                                self.current_model = None

                    # 1. Check if user cancelled
                    if self._cancel_download_event.is_set():
                        logger.info("Download cancelled before completion.")
                        _cleanup_temp()
                        with self._lock:
                            self.state = BrainState.NO_MODEL_PRESENT
                            if self._current_progress:
                                self._current_progress.status = "cancelled"
                            _sanitize_current_model()
                        if progress_callback and self._current_progress:
                            progress_callback(self._current_progress)
                        return

                    # 2. Check stream completeness (detect premature socket close / truncated download)
                    if (real_total > 0 and bytes_downloaded < real_total) or bytes_downloaded < 8:
                        logger.error(
                            "Download incomplete: received %d of %d expected bytes for %s",
                            bytes_downloaded,
                            real_total,
                            filename,
                        )
                        _cleanup_temp()
                        with self._lock:
                            self.state = BrainState.DOWNLOAD_FAILED
                            if self._current_progress:
                                self._current_progress.status = "failed"
                            _sanitize_current_model()
                        if progress_callback and self._current_progress:
                            progress_callback(self._current_progress)
                        return

                    # 3. Transition to verifying and validate GGUF header on temp_path BEFORE touching target_path
                    with self._lock:
                        if self._current_progress:
                            self._current_progress.status = "verifying"
                        if progress_callback and self._current_progress:
                            progress_callback(self._current_progress)

                    is_valid = validate_gguf_header(temp_path)
                    if not is_valid:
                        logger.error("Download failed GGUF header validation for %s", filename)
                        _cleanup_temp()
                        with self._lock:
                            self.state = BrainState.DOWNLOAD_FAILED
                            if self._current_progress:
                                self._current_progress.status = "failed"
                            _sanitize_current_model()
                        if progress_callback and self._current_progress:
                            progress_callback(self._current_progress)
                        return

                    # 4. Atomically promote validated temp_path to target_path
                    try:
                        if target_path.exists():
                            try:
                                target_path.unlink()
                            except Exception:
                                pass
                        temp_path.replace(target_path)
                    except Exception as exc:
                        logger.error("Failed to promote %s to %s: %s", temp_path, target_path, exc)
                        _cleanup_temp()
                        with self._lock:
                            self.state = BrainState.DOWNLOAD_FAILED
                            if self._current_progress:
                                self._current_progress.status = "failed"
                            _sanitize_current_model()
                        if progress_callback and self._current_progress:
                            progress_callback(self._current_progress)
                        return

                    # 5. Success: Mark model ready on disk
                    with self._lock:
                        self.state = BrainState.MODEL_READY_ON_DISK
                        self.current_model = filename
                        if self._current_progress:
                            self._current_progress.status = "completed"
                            self._current_progress.percentage = 100.0

                        if progress_callback and self._current_progress:
                            progress_callback(self._current_progress)

                except Exception as exc:
                    logger.error("Download failed: %s", exc)
                    if temp_path.exists():
                        try:
                            temp_path.unlink()
                        except Exception:
                            pass
                    with self._lock:
                        self.state = BrainState.DOWNLOAD_FAILED
                        if self._current_progress:
                            self._current_progress.status = "failed"
                        if self.current_model:
                            prev_path = self.models_dir / self.current_model
                            if not (prev_path.is_file() and validate_gguf_header(prev_path)):
                                self.current_model = None
                        if progress_callback and self._current_progress:
                            progress_callback(self._current_progress)
```

Also, in line 714 (early cancellation check inside the chunk loop):
```python
                                if self._cancel_download_event.is_set():
                                    logger.info("Download cancelled by user.")
                                    f.close()
                                    if temp_path.exists():
                                        try:
                                            temp_path.unlink()
                                        except Exception:
                                            pass
                                    with self._lock:
                                        self.state = BrainState.NO_MODEL_PRESENT
                                        if self._current_progress:
                                            self._current_progress.status = "cancelled"
                                        if self.current_model:
                                            prev_path = self.models_dir / self.current_model
                                            if not (prev_path.is_file() and validate_gguf_header(prev_path)):
                                                self.current_model = None
                                        if progress_callback and self._current_progress:
                                            progress_callback(self._current_progress)
                                    return
```
And in `cancel_download()` (lines 834–837):
```python
                self.state = BrainState.NO_MODEL_PRESENT
                if self._current_progress:
                    self._current_progress.status = "cancelled"
                if self.current_model:
                    prev_path = self.models_dir / self.current_model
                    if not (prev_path.is_file() and validate_gguf_header(prev_path)):
                        self.current_model = None
```

---

## 4. Verification Method for Worker & Reviewers

### Step 1: Run the Targeted Failure Test
```powershell
uv run pytest tests/test_challenger_m1_iter2_1.py -k "test_partial_streaming_clean_close_truncation_detection" -v
```
- **Before fix**: Fails with `AssertionError: Vulnerability: Truncated 128-byte partial download of 2.3GB model was marked MODEL_READY_ON_DISK!`.
- **After fix**: Passes cleanly.

### Step 2: Run Full Suite (All 173 Tests)
```powershell
uv run pytest -v
```
- **Expected result**: 173 passed in ~16s.

### Step 3: Verify Edge Case Scenarios
1. **Network Drop**: `test_partial_streaming_download_socket_drop` passes, temp file unlinked.
2. **Cancellation**: `test_download_cancellation` and re-entrant cancel tests pass.
3. **Corrupt GGUF Header**: `test_download_corrupted_stream_validation_failure` passes, target file not created.
4. **Valid Model Preservation**: If `test_model.gguf` already exists on disk and a download for another model fails, `test_model.gguf` remains intact and `manager.current_model == "test_model.gguf"`.
