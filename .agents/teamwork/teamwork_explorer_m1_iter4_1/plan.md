# Architectural & Remediation Plan: Two-Sided Stream Verification & Early Abort

**Author**: teamwork_explorer_m1_iter4_1  
**Milestone**: M1 Iteration 4  
**Target File**: `parasite_ai/mind/brain_manager.py`  
**Failing Test**: `tests/test_challenger_m1_iter3.py::test_adversarial_stream_truncation_and_overflow[real_total_plus_100-1000000-1000100]`

---

## 1. Problem Statement & Root Cause

### 1.1 Root Cause
In `parasite_ai/mind/brain_manager.py` (lines 776–784), post-download stream validation only tested strictly less than (`< real_total`):
```python
temp_size = temp_path.stat().st_size if temp_path.exists() else 0
if (real_total > 0 and bytes_downloaded < real_total) or (real_total > 0 and temp_size < real_total) or temp_size == 0:
    logger.error(...)
    ...
```
When an HTTP streaming response yielded more bytes than `real_total` (e.g. 1,000,100 bytes against a `Content-Length` of 1,000,000):
1. `bytes_downloaded < real_total` evaluated to `False`.
2. `temp_size < real_total` evaluated to `False`.
3. `temp_size == 0` evaluated to `False`.

Consequently, execution bypassed the failure cleanup block, reached binary GGUF header validation (which passed because the stream began with a valid 16-byte GGUF v3 header), and promoted the corrupted/oversized temporary file to `target_path`. State was marked `BrainState.MODEL_READY_ON_DISK`.

### 1.2 Resource Leak & DoS Risk During Streaming
Additionally, inside the chunk-reading loop (`for chunk in resp.iter_bytes(chunk_size=256 * 1024):`), there was no check on accumulated `bytes_downloaded` exceeding `real_total`. If a malicious or misconfigured server streamed an unbounded payload (e.g. 50 GB for a 1 GB model), the client would continue reading from the network and writing chunks to disk indefinitely until disk space was exhausted.

---

## 2. Design Specification

We design a two-layer defense mechanism:

### Layer 1: Chunk-Loop Early Abort
Inside `for chunk in resp.iter_bytes(chunk_size=256 * 1024):`, immediately after writing the chunk and incrementing `bytes_downloaded`:
- Check if `real_total > 0 and bytes_downloaded > real_total`.
- If true:
  1. Log an error noting stream overflow and early abort.
  2. Execute `break` to immediately exit the chunk loop.
- Exiting the chunk loop automatically:
  - Halts all further network consumption from `resp.iter_bytes()`.
  - Exits the `with open(temp_path, "wb") as f:` block, flushing and closing the file handle (mandatory on Windows before unlinking).
  - Exits the `with httpx.stream(...) as resp:` block, closing the HTTP connection.
  - Drops into Layer 2 (the post-stream verification block).

### Layer 2: Strict Post-Stream Two-Sided Size Verification
At lines 776–797, replace the one-sided `< real_total` check with a strict two-sided equality check:
```python
temp_size = temp_path.stat().st_size if temp_path.exists() else 0
if (
    (real_total > 0 and bytes_downloaded != real_total)
    or (real_total > 0 and temp_size != real_total)
    or temp_size == 0
    or real_total <= 0
):
```
If triggered:
1. Log:
   ```python
   logger.error(
       "Download size mismatch or incomplete for %s: received %d of %d expected bytes (on-disk: %d bytes)",
       filename,
       bytes_downloaded,
       real_total,
       temp_size,
   )
   ```
2. Unlink `temp_path` if it exists.
3. Acquire `self._lock`:
   - Set `self.state = BrainState.DOWNLOAD_FAILED`.
   - Set `self._current_progress.status = "failed"`.
   - Update `self._current_progress.bytes_downloaded = bytes_downloaded`.
4. Fire `progress_callback(prog)`.
5. Return immediately to prevent GGUF header validation and file promotion.

---

## 3. Concrete Code Proposal (For Worker Implementer)

### Chunk-Loop Modification (`parasite_ai/mind/brain_manager.py:728-732`)
```python
<<<<
                                f.write(chunk)
                                bytes_downloaded += len(chunk)
                                now = time.time()
====
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

                                now = time.time()
>>>>
```

### Post-Stream Verification Modification (`parasite_ai/mind/brain_manager.py:776-797`)
```python
<<<<
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
                        if temp_path.exists():
                            try:
                                temp_path.unlink()
                            except Exception:
                                pass
                        with self._lock:
                            self.state = BrainState.DOWNLOAD_FAILED
                            if self._current_progress:
                                self._current_progress.status = "failed"
                            prog = self._current_progress
                        if progress_callback and prog:
                            progress_callback(prog)
                        return
====
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
>>>>
```

---

## 4. Edge Case Matrix & Verification Analysis

| Scenario | Input `real_total` | Received Bytes | Behavior & Guarantees |
|---|---|---|---|
| **Standard Complete Download** | `1,000,000` | `1,000,000` | `bytes_downloaded > real_total` is False; post-check `!=` is False; passes to GGUF header validation and promotion. |
| **Premature Stream Truncation** | `1,000,000` | `999,999` (or `1`, `16`) | Loop finishes on EOF; post-check catches `bytes_downloaded != real_total`; `temp_path` unlinked; `DOWNLOAD_FAILED`. |
| **Clean Close Empty Stream** | `1,000,000` | `0` | Loop does not execute; `temp_size == 0` and `!= real_total` trigger; `DOWNLOAD_FAILED`. |
| **Stream Overflow (+100 B)** | `1,000,000` | `1,000,100` | Chunk pushing over `1,000,000` triggers early abort `break`; post-check catches `!= real_total`; `temp_path` unlinked; `DOWNLOAD_FAILED`. |
| **Massive / Unbounded Stream** | `1,000,000` | 50 GB stream | Loop aborts on first chunk exceeding 1 MB (at ~1.25 MB); connection closed; 0 dangling temp files; no disk exhaustion. |
| **User Cancellation** | Any | Any | Handled at lines 712–726 and 759–773; transitions to `BrainState.NO_MODEL_PRESENT`, status `'cancelled'`. |
| **Zero/Negative Content-Length** | `0` or `-1` | Any | Caught by `real_total <= 0` or `temp_size == 0`; transitions to `BrainState.DOWNLOAD_FAILED`. |

---

## 5. Verification Commands for Worker Implementer

1. **Adversarial Test Suite**:
   ```powershell
   uv run pytest tests/test_challenger_m1_iter3.py -v
   ```
   *Expected*: `5 passed in ~1.0s` (exit code 0).

2. **Full Regression Test Suite**:
   ```powershell
   uv run pytest -v
   ```
   *Expected*: `178 passed in ~17.0s` (exit code 0).
