# Handoff Report — Explorer M1 Iteration 3 (Instance 2)

**Author**: `teamwork_explorer_m1_iter3_2`  
**Working Directory**: `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m1_iter3_2\`  
**Date**: 2026-10-29  
**Focus**: State Machine Recovery & Atomic File Cleanup upon download failure/truncation.  

---

## 1. Observation

### 1.1 Empirical Failure Reproduction
Executing the targeted challenger stress test:
```powershell
uv run pytest -v tests/test_challenger_m1_iter2_1.py -k "test_partial_streaming_clean_close_truncation_detection"
```
Produced verbatim output:
```
FAILED tests/test_challenger_m1_iter2_1.py::test_partial_streaming_clean_close_truncation_detection - AssertionError: Vulnerability: Truncated 128-byte partial download of 2.3GB model was marked MODEL_READY_ON_DISK! state=BrainState.MODEL_READY_ON_DISK, target_file_size=128
assert <BrainState.MODEL_READY_ON_DISK: 'MODEL_READY_ON_DISK'> != <BrainState.MODEL_READY_ON_DISK: 'MODEL_READY_ON_DISK'>
 +  where <BrainState.MODEL_READY_ON_DISK: 'MODEL_READY_ON_DISK'> = <parasite_ai.mind.brain_manager.LocalBrainManager object at 0x000001E6BEC74D40>.state
 +  and   <BrainState.MODEL_READY_ON_DISK: 'MODEL_READY_ON_DISK'> = BrainState.MODEL_READY_ON_DISK
====================== 1 failed, 26 deselected in 0.87s =======================
```
Full suite status (`uv run pytest --tb=short`): **1 failed, 172 passed**.

### 1.2 Inspection of `parasite_ai/mind/brain_manager.py`
In `parasite_ai/mind/brain_manager.py`:
1. **Lines 707–737**:
   `resp.headers.get("content-length", total_bytes)` parses `real_total`. The chunk loop increments `bytes_downloaded += len(chunk)`.
2. **Lines 759–770**:
   Cancellation check is present, but upon exiting the chunk iteration, there is **zero check** that `bytes_downloaded >= real_total`.
3. **Lines 780–783**:
   ```python
   # Atomically rename
   if temp_path.exists():
       if target_path.exists():
           target_path.unlink()
       temp_path.replace(target_path)
   ```
   `temp_path` is renamed to `target_path` **before** binary validation occurs.
4. **Lines 785–797**:
   ```python
   is_valid = validate_gguf_header(target_path)
   with self._lock:
       if is_valid:
           self.state = BrainState.MODEL_READY_ON_DISK
           self.current_model = filename
   ```
   `validate_gguf_header` inspects only the first 8 bytes (magic `b"GGUF"` and uint32 version `in (2, 3)`). It returns `True` for any 128-byte payload containing those initial 8 bytes, causing the manager to declare `BrainState.MODEL_READY_ON_DISK`.
5. **Line 794**:
   If `validate_gguf_header(target_path)` evaluates to `False`, `self.state = BrainState.DOWNLOAD_FAILED`, but `target_path` is **never unlinked**. The corrupt file remains permanently at `target_path`.
6. **`self.current_model` behavior across lines 459, 502, 789, 872, 882**:
   `self.current_model` is only assigned when a model is verified on disk or loaded. However, on download failure or truncation, no explicit invariant checks whether a previous valid model remains on disk versus clearing `current_model`.

---

## 2. Logic Chain

1. **Vulnerability Mechanics**:
   - A truncated download with clean TCP termination (e.g., CDN timeout, proxy drop, socket cut without exception) writes partial data to `temp_path`.
   - Because `_download_worker` lacks a size completeness guard (`bytes_downloaded < real_total`), it proceeds to file promotion.
   - `temp_path` is renamed to `target_path`, obliterating any prior file at `target_path`.
   - `validate_gguf_header(target_path)` passes because the initial 128 bytes contain the GGUF magic header.
   - The system sets `self.state = BrainState.MODEL_READY_ON_DISK` and `self.current_model = filename`.
   - A broken 128-byte stub is left on disk. Any subsequent load of this model crashes or segfaults upstream llama.cpp bindings, and re-downloading is obstructed.

2. **File Staging and Validation Inversion**:
   - In any robust atomic file transfer pattern, validation must occur **in-situ on the staging path (`temp_path`)** prior to altering or overwriting `target_path`.
   - Validating after renaming to `target_path` guarantees that whenever validation fails, `target_path` has already been corrupted.
   - Validating `temp_path` first guarantees that `target_path` is untouched in all error conditions (socket drop, truncation, bad header, user cancellation).

3. **State Machine Recovery & `self.current_model` Invariant**:
   - What happens when a download fails or truncates?
     - `self.state` MUST transition to `BrainState.DOWNLOAD_FAILED`.
     - `self._current_progress.status = "failed"`.
   - Does `self.current_model` get cleared or kept?
     - `self.current_model` MUST NEVER be set to the failed target model filename.
     - If `self.current_model` was already referencing a valid model prior to the download (e.g. Model A was loaded or on disk, and Model B was being downloaded):
       - If `self.models_dir / self.current_model` exists and is valid GGUF (`validate_gguf_header`), `self.current_model` is **KEPT**. This allows the user to resume using their existing model, preserves loaded backend state, and prevents silent state loss.
       - If `self.current_model` points to a missing or invalid file (or was `None`), `self.current_model` is set to `None`.
   - What if a previous valid model was on disk?
     - Because `target_path` is never modified until `temp_path` is 100% verified, the previous model file on disk is completely unharmed. If the download was a re-download of the same model, the existing file remains intact; if it was a second model, the first model remains intact.

4. **Atomic File Cleanup**:
   - In all non-successful outcomes (cancellation, truncation, invalid header, exception):
     - `temp_path.unlink()` is invoked in a guarded `try ... except Exception: pass` block after closing handles.
     - `target_path` is never created or overwritten.
     - Result: Zero dangling `.tmp` files and zero corrupted `.gguf` stubs.

---

## 3. Caveats

- In headless mock testing environments, GGUF files are synthetic (8–136 bytes). `validate_gguf_header` cannot enforce a multi-gigabyte minimum file size globally, because unit tests rely on small mock files. Completeness verification must therefore rely on `real_total` (extracted from HTTP `content-length` or curated catalog size) during the download stream.
- On Windows systems, active file locks held by other processes or unclosed Python file objects will cause `PermissionError: [WinError 32]` if `unlink()` or `replace()` is called before closing file handles. Staging file closures must strictly precede `unlink()`.

---

## 4. Conclusion

The fix requires a surgical update to `LocalBrainManager._download_worker()` in `parasite_ai/mind/brain_manager.py` (lines 759–814) implementing:
1. **Size Completeness Guard**: Check `(real_total > 0 and bytes_downloaded < real_total) or bytes_downloaded < 8`. If triggered, unlink `temp_path`, transition to `DOWNLOAD_FAILED`, and exit.
2. **In-Situ Header Validation**: Call `validate_gguf_header(temp_path)` before `target_path` is touched. If invalid, unlink `temp_path`, transition to `DOWNLOAD_FAILED`, and exit.
3. **Atomic Promotion**: Only if both size check and header check pass, call `temp_path.replace(target_path)`.
4. **`self.current_model` Disk Integrity Guard**: Keep `self.current_model` if its file is valid on disk; otherwise clear to `None`. Never assign the failed target filename to `self.current_model`.

The complete, ready-to-apply code plan and exact replacement block have been authored in:
`g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m1_iter3_2\plan.md`.

---

## 5. Verification Method

1. **Verify Truncation Detection**:
   ```powershell
   uv run pytest tests/test_challenger_m1_iter2_1.py -k "test_partial_streaming_clean_close_truncation_detection" -v
   ```
   - Current state: Fails (`AssertionError: Vulnerability: Truncated 128-byte partial download...`).
   - Expected post-implementation state: Passes (transitions to `DOWNLOAD_FAILED`, `temp_path` unlinked, target file not created).

2. **Verify Full Test Suite**:
   ```powershell
   uv run pytest -v
   ```
   - Current state: 1 failed, 172 passed.
   - Expected post-implementation state: 173 passed.

3. **Files to Inspect**:
   - Plan & Recommendations: `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m1_iter3_2\plan.md`
   - Target Implementation File: `parasite_ai/mind/brain_manager.py` (lines 759–814)
   - Failing Test File: `tests/test_challenger_m1_iter2_1.py` (lines 482–520)
