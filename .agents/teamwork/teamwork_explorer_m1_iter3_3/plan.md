# Implementation Plan — Download Truncation Fix & Test Suite Verification

**Author**: `teamwork_explorer_m1_iter3_3`  
**Target Assignee**: `teamwork_worker_m1_iter3`  
**Date**: 2026-10-29  
**Focus**: Defect Resolution in `parasite_ai/mind/brain_manager.py` to achieve 100% test suite pass (173/173).

---

## 1. Executive Summary

A comprehensive defect audit of all 9 test files and all 173 collected test cases in `tests/` confirmed:
- **172 tests currently pass cleanly and deterministically.**
- **0 tests are skipped or xfailed.**
- **0 tests exhibit flakiness or concurrency deadlocks.**
- **Exactly 1 test fails**: `tests/test_challenger_m1_iter2_1.py::test_partial_streaming_clean_close_truncation_detection`.

Fixing the download truncation vulnerability in `LocalBrainManager._download_worker()` will directly resolve this failure without introducing side effects or regressions to any of the other 172 tests, achieving a **100% pass rate (173/173 passed)** across the entire test suite.

---

## 2. Test Suite Inventory & Health Audit

| # | Test File | Test Count | Status | Notes |
|---|---|:---:|:---:|---|
| 1 | `tests/__init__.py` | 0 | PASSED | Package marker file. Valid syntax. |
| 2 | `tests/test_brain_manager.py` | 17 | 17/17 PASSED | Validates GGUF headers, model discovery, offload toggle, streaming downloads, mock inference. |
| 3 | `tests/test_challenger_m1_iter2.py` | 35 | 35/35 PASSED | Adversarial action parser stress (25 tests) and VRAM scaling boundary value tests (10 tests). |
| 4 | `tests/test_challenger_m1_iter2_1.py` | 27 | 26/27 PASSED (1 FAILED) | Stress concurrency, 19 GGUF header variations, socket drops, clean close truncation. |
| 5 | `tests/test_config.py` | 11 | 11/11 PASSED | Config loading, serialization, environment overrides, auto-generation, validation bounds. |
| 6 | `tests/test_stress_concurrency.py` | 6 | 6/6 PASSED | Concurrency mutex, re-entrant callback cancellation, rapid start/cancel, state race safety. |
| 7 | `tests/test_stress_config.py` | 14 | 14/14 PASSED | Huge strings, malicious code injection block, type confusion, unicode/null bytes, anchors. |
| 8 | `tests/test_stress_gguf.py` | 38 | 38/38 PASSED | Short files, bad magic, unsupported versions, corrupted stream validation failure. |
| 9 | `tests/test_stress_m1.py` | 25 | 25/25 PASSED | Hostile action extraction (11 tests), mock hardware VRAM budget (8 tests), offload toggle (6 tests). |
| **TOTAL** | **9 files** | **173 items** | **172 PASSED, 1 FAILED** | **0 skipped, 0 flaky** |

---

## 3. Root Cause Analysis of the Single Failure

### Location
File: `parasite_ai/mind/brain_manager.py`, lines 772–786.

### Problem
In `_download_worker()`, after reading bytes from `httpx.stream`, the loop exits when the generator finishes.
If the HTTP stream terminates cleanly (e.g. server closes connection, proxy drops early) after sending only partial data (e.g., 128 bytes of a 2.3 GB model), `bytes_downloaded < real_total`.
However, the worker currently:
1. Ignores `bytes_downloaded < real_total`.
2. Atomically renames `temp_path` (`*.download.tmp`) to `target_path` (`*.gguf`).
3. Calls `validate_gguf_header(target_path)`. Since `validate_gguf_header` only checks the first 8 bytes for `b"GGUF"` magic and version (2 or 3), it evaluates to `True` for any 128-byte stub.
4. Promotes the truncated file to `BrainState.MODEL_READY_ON_DISK` and sets progress to `completed` (100.0%).

### Blast Radius
- The assistant permanently treats a broken 128-byte stub as a valid ready model.
- Subsequent calls to `start_download()` return `False` immediately because lines 686–691 see `target_path.exists() and validate_gguf_header(target_path)`. Re-downloading is locked out.
- Calling `load_model()` attempts to load a 128-byte file, causing runtime crashes or segfaults in `llama-cpp-python`.

---

## 4. Worker Implementation Instructions

### Target File
`parasite_ai/mind/brain_manager.py` (exclusive ownership for Worker)

### Modification Location
Inside `_download_worker()`, immediately after the `if self._cancel_download_event.is_set():` block (line 771) and before `# Download finished - Validate GGUF header` (line 772).

### Exact Code Change

```python
                    # -------------------------------------------------------------
                    # Size Completeness Verification:
                    # Detect premature clean stream closures (truncation).
                    # -------------------------------------------------------------
                    if real_total > 0 and (bytes_downloaded < real_total or (temp_path.exists() and temp_path.stat().st_size < real_total)):
                        logger.error(
                            "Download incomplete for %s: received %d of %d bytes",
                            filename,
                            bytes_downloaded,
                            real_total,
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
                        if progress_callback and self._current_progress:
                            progress_callback(self._current_progress)
                        return
```

### Key Nuances for Worker
1. **Never rename `temp_path` to `target_path` if truncated.**
2. **Safely unlink `temp_path`** so no partial `.download.tmp` files remain on disk.
3. **Acquire `self._lock`** when updating `self.state = BrainState.DOWNLOAD_FAILED` and `self._current_progress.status = "failed"`.
4. **Fire `progress_callback`** with the updated failure progress object before returning.
5. **Return early** from `_download_worker()` to prevent falling through to rename and header validation.

---

## 5. Verification Steps for Worker

1. **Compilation Check**:
   ```powershell
   uv run python -m py_compile parasite_ai/mind/brain_manager.py
   ```
   *Expected*: Exit code 0, no output.

2. **Targeted Failure Verification**:
   ```powershell
   uv run pytest tests/test_challenger_m1_iter2_1.py -k "test_partial_streaming_clean_close_truncation_detection" -v
   ```
   *Expected*: PASSED (exit code 0).

3. **Full Test Suite Execution**:
   ```powershell
   uv run pytest -v
   ```
   *Expected*: Exactly `173 passed in ~16s`, exit code 0.
