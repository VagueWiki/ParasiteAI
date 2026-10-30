# Remediation Plan: Adversarial Stream Completeness Hardening (Milestone 1 Iteration 4)

## Executive Summary
Investigation into `tests/test_challenger_m1_iter3.py` confirms that replacing the one-sided inequality `< real_total` with strict inequality `!= real_total` in `parasite_ai/mind/brain_manager.py` (line 777) fully resolves the adversarial stream overflow vulnerability (`real_total_plus_100`) while preserving 100% pass rate across the existing 4 truncation tests and all 173 baseline tests (178/178 tests passing, 0 regressions).

---

## 1. Vulnerability Analysis

In `parasite_ai/mind/brain_manager.py:777`:
```python
temp_size = temp_path.stat().st_size if temp_path.exists() else 0
if (real_total > 0 and bytes_downloaded < real_total) or (real_total > 0 and temp_size < real_total) or temp_size == 0:
```

### Flaw Mechanism:
1. **Asymmetric Boundary Check**: The condition strictly guarded against truncation (`bytes_downloaded < real_total` and `temp_size < real_total`), but was blind to stream overflow (`bytes_downloaded > real_total` and `temp_size > real_total`).
2. **False Header Validation Bypass**: An oversized stream starting with valid GGUF magic (`b"GGUF"`) and version (`3`) passed `validate_gguf_header(temp_path)` because the validator only checks magic and version in the first 8-16 bytes.
3. **Improper Promotion**: The corrupted/smuggled file was promoted to `.gguf` destination on disk and the manager entered `BrainState.MODEL_READY_ON_DISK`.

---

## 2. Recommended Code Modification

**Target File**: `parasite_ai/mind/brain_manager.py`  
**Target Lines**: 777–784

### Proposed Replacement:

```python
<<<< BEFORE (Line 777-784)
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
==== AFTER
                    # Completeness Verification: Detect truncated / premature stream termination or stream overflow
                    temp_size = temp_path.stat().st_size if temp_path.exists() else 0
                    if (real_total > 0 and bytes_downloaded != real_total) or (real_total > 0 and temp_size != real_total) or temp_size == 0:
                        logger.error(
                            "Download size mismatch or incomplete for %s: received %d of %d expected bytes (on-disk: %d bytes)",
                            filename,
                            bytes_downloaded,
                            real_total,
                            temp_size,
                        )
>>>>
```

---

## 3. Impact Assessment Across All 5 Adversarial Test Variations

| Variation Name | Sent Bytes | Expected Bytes | Current Check Result (`<`) | Proposed Check Result (`!=`) | Expected State |
|---|---|---|---|---|---|
| `0_bytes` | 0 | 1,000,000 | Caught (`temp_size == 0`) | Caught (`temp_size == 0` & `!=`) | `DOWNLOAD_FAILED` |
| `1_byte` | 1 | 1,000,000 | Caught (`1 < 1000000`) | Caught (`1 != 1000000`) | `DOWNLOAD_FAILED` |
| `16_bytes_header_only` | 16 | 1,000,000 | Caught (`16 < 1000000`) | Caught (`16 != 1000000`) | `DOWNLOAD_FAILED` |
| `real_total_minus_1` | 999,999 | 1,000,000 | Caught (`999999 < 1000000`) | Caught (`999999 != 1000000`) | `DOWNLOAD_FAILED` |
| `real_total_plus_100` | 1,000,100 | 1,000,000 | **VULNERABLE** (Bypassed) | **Caught** (`1000100 != 1000000`) | `DOWNLOAD_FAILED` |

---

## 4. Empirical Verification Evidence

1. **Targeted Adversarial Test Suite Execution (In-Memory Patch)**:
   - Command: `uv run python -c "import pytest, sys, parasite_ai.mind.brain_manager as bm; code = open('parasite_ai/mind/brain_manager.py', encoding='utf-8').read(); new_code = code.replace('(real_total > 0 and bytes_downloaded < real_total) or (real_total > 0 and temp_size < real_total)', '(real_total > 0 and bytes_downloaded != real_total) or (real_total > 0 and temp_size != real_total)'); exec(compile(new_code, bm.__file__, 'exec'), bm.__dict__); sys.exit(pytest.main(['tests/test_challenger_m1_iter3.py', '-v']))"`
   - Result: `5 passed in 0.47s` (exit code 0).
2. **Full Regression Test Suite Execution (In-Memory Patch)**:
   - Command: `uv run python -c "import pytest, sys, parasite_ai.mind.brain_manager as bm; code = open('parasite_ai/mind/brain_manager.py', encoding='utf-8').read(); new_code = code.replace('(real_total > 0 and bytes_downloaded < real_total) or (real_total > 0 and temp_size < real_total)', '(real_total > 0 and bytes_downloaded != real_total) or (real_total > 0 and temp_size != real_total)'); exec(compile(new_code, bm.__file__, 'exec'), bm.__dict__); sys.exit(pytest.main(['tests', '-v']))"`
   - Result: `178 passed in 15.78s` (exit code 0).
   - Zero failures, zero regressions across all 178 tests.

---

## 5. Next Steps for Worker
1. Apply the single-line conditional change in `parasite_ai/mind/brain_manager.py:777` (and update log message in line 779).
2. Run `uv run pytest tests/test_challenger_m1_iter3.py -v`.
3. Run `uv run pytest -v` across the full test suite.
4. Submit handoff to orchestrator/challenger for final acceptance.
