# Handoff Report — Milestone M1 Iteration 2 Challenger

**Author**: `teamwork_challenger_m1_iter2_2`  
**Working Directory**: `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_challenger_m1_iter2_2`  
**Date**: 2026-10-29  
**Empirical Verdict**: **REQUEST_CHANGES**

---

## 1. Observation

### Targeted Adversarial Stress Harness (`tests/test_challenger_m1_iter2.py`)
Executed dedicated 35-test stress suite via `uv run pytest tests/test_challenger_m1_iter2.py -v`:
- `tests/test_challenger_m1_iter2.py::TestActionParserAdversarialInputs`: 25 passed in 1.8s
- `tests/test_challenger_m1_iter2.py::TestVRAMScalingBoundaryValues`: 10 passed in 1.0s
Result: `35 passed in 2.81s`, exit code 0.

#### Detailed Scope Stress Observations:
1. **Hostile Action Parser Inputs**:
   - **Markdown code blocks with 4+ backticks**: Successfully parsed across 4, 5, 6, 8, and 12 backticks (`ticks = '`' * backtick_count`), mismatched opening/closing fences (e.g. 5 opening / 3 closing, 3 opening / 5 closing), and nested fences (outer 5 backticks markdown enclosing inner 3 backticks json).
   - **Deep nesting**: Successfully parsed actions containing deeply nested parameters/metadata up to 100 levels (`level_0` ... `level_99` wrapping `{"final_val": 42}`), as well as multiple nested non-action telemetry preamble blocks appearing prior to the action object.
   - **Unescaped quotes inside strings**: Output `{"action": "CLICK_AND_TYPE", "text": "He said "hello" to me", "reasoning": "test"}` does not crash or raise uncaught `JSONDecodeError`; `generate_action` safely falls back to `{"action": "WAIT", "wait_ms": 1000, "reasoning": "Re-evaluating target..."}` within 2ms. Escaped quotes (`\"`) and escaped backslashes before quotes (`\\\\\"`) are correctly extracted with string contents intact.
   - **Trailing junk**: Output followed by unclosed braces (`{ unclosed_object: { another_unclosed: "broken`), unclosed quotes (`"dangling string...`), random brackets/commas (`,,, ]]] }}} ;;; >>> ???`), and mixed prefix/suffix junk extracts the valid action cleanly.
   - **Flood/DOS resilience**: 500 unclosed braces processed in <5ms without `RecursionError`; 500 unclosed backticks processed in <20ms without catastrophic backtracking; 5,000 escaped backslashes processed in <5ms; full unicode/emojis (`🔍`, `🚀`, `🦀`, `测试`, `💖`) preserved.

2. **VRAM Scaling Boundary Conditions (`_instantiate_local_engine`)**:
   - `0 MB` free VRAM: `effective_vram_mb = 0 < 2000` -> enforces `n_gpu_layers = 0` (CPU fallback).
   - `1999 MB` free VRAM: `effective_vram_mb = 1999 < 2000` -> enforces `n_gpu_layers = 0` (CPU fallback).
   - `2000 MB` free VRAM: `effective_vram_mb = 2000 >= 2000` -> calculates `layer_ratio = 2000 / 5200 = 0.3846`, assigns `scaled_layers = int(28 * 0.3846) = 10` layers.
   - `Exact match` (5200 MB free == 5200 MB required): `effective_vram_mb < vram_required_mb` is False -> preserves configured layers `n_gpu_layers = -1` (full GPU offload).
   - `Overflow` (128,000 MB free): Safe integer calculation without overflow -> preserves configured layers `n_gpu_layers = -1`.
   - `Negative VRAM` (-100 MB from driver glitch): `min(-100, budget) = -100 < 2000` -> enforces `n_gpu_layers = 0`.
   - `Budget capping`: Free VRAM is 16,000 MB but user set `vram_budget_mb = 1800` -> `min(16000, 1800) = 1800 < 2000` -> enforces `n_gpu_layers = 0`.
   - `Configured layers capping`: Configured 25 layers with 2000 MB available (fits 10) -> assigns `min(25, 10) = 10`. Configured 6 layers with 2000 MB available (fits 10) -> preserves `min(6, 10) = 6`.
   - `Unknown models`: Custom GGUF model not in catalog defaults cleanly to 3500 MB requirement and 32 total layers, scaling to 22 layers with 2500 MB free.

### Full Test Suite Execution (`uv run pytest -v`)
Execution of the full test suite (`uv run pytest -v`) executed 173 items:
`1 failed, 172 passed in 17.68s` (exit code 1).

**Verbatim failure log**:
```
FAILED tests/test_challenger_m1_iter2_1.py::test_partial_streaming_clean_close_truncation_detection - AssertionError: Vulnerability: Truncated 128-byte partial download of 2.3GB model was marked MODEL_READY_ON_DISK! state=BrainState.MODEL_READY_ON_DISK, target_file_size=128
assert <BrainState.MODEL_READY_ON_DISK: 'MODEL_READY_ON_DISK'> != <BrainState.MODEL_READY_ON_DISK: 'MODEL_READY_ON_DISK'>
 +  where <BrainState.MODEL_READY_ON_DISK: 'MODEL_READY_ON_DISK'> = <parasite_ai.mind.brain_manager.LocalBrainManager object at 0x0000027A9F1FE2A0>.state
 +  and   <BrainState.MODEL_READY_ON_DISK: 'MODEL_READY_ON_DISK'> = BrainState.MODEL_READY_ON_DISK
```

### Codebase Inspection of Vulnerability
In `parasite_ai/mind/brain_manager.py`:
```python
707:                     with httpx.stream("GET", download_url, follow_redirects=True, timeout=30.0) as resp:
708:                         resp.raise_for_status()
709:                         real_total = int(resp.headers.get("content-length", total_bytes))
710:                         with open(temp_path, "wb") as f:
711:                             for chunk in resp.iter_bytes(chunk_size=256 * 1024):
...
729:                                 bytes_downloaded += len(chunk)
...
780:                     if temp_path.exists():
781:                         if target_path.exists():
782:                             target_path.unlink()
783:                         temp_path.replace(target_path)
784: 
785:                     is_valid = validate_gguf_header(target_path)
786:                     with self._lock:
787:                         if is_valid:
788:                             self.state = BrainState.MODEL_READY_ON_DISK
789:                             self.current_model = filename
```
Observation: When an HTTP stream terminates prematurely without raising an exception (clean close after receiving only partial chunks), `bytes_downloaded < real_total`. However, line 785 only verifies `is_valid = validate_gguf_header(target_path)`. Since the first 16 bytes contain valid GGUF magic and version, `validate_gguf_header` returns `True`. The truncated file (e.g. 128 bytes) is renamed to the target filename and promoted to `BrainState.MODEL_READY_ON_DISK`.

---

## 2. Logic Chain

1. **Iteration 2 Action Parser Fix Assessment**:
   - Inspection of `parasite_ai/mind/brain_manager.py` lines 1021–1121 confirms the 4-pass extraction architecture: direct JSON parse -> fence regex matching with balanced-brace scanning -> full-text balanced-brace scanning -> raw_decode scan from every `{`.
   - Adversarial stress tests empirically proved this design correctly isolates valid action dictionaries amidst hostile preamble braces, 4+ backtick fences up to 12 backticks, mismatched fences, up to 100 levels of nested structures, and trailing junk.
   - Hostile syntax errors (e.g. unescaped quotes inside string values) fail RFC 8259 decoding safely without unhandled exceptions and trigger the deterministic safe fallback `{"action": "WAIT", ...}`.
   - Conclusion: Action parser fixes are **sound and robust**.

2. **Iteration 2 VRAM Scaling Logic Fix Assessment**:
   - Inspection of `parasite_ai/mind/brain_manager.py` lines 515–551 shows proper evaluation of `effective_vram_mb = min(free_mb, budget_mb)`.
   - At boundary values `< 2000 MB` (including 0 MB, -100 MB, and 1999 MB), it strictly forces `gpu_layers = 0` (CPU fallback).
   - At `2000 MB`, proportional scaling kicks in (`effective_vram_mb / vram_required_mb`), scaling layers to fit without CUDA OOM.
   - At exact match (5200 MB == 5200 MB) and overflow (128,000 MB), configured layer parameters are preserved without division-by-zero or numerical errors.
   - User budget capping and custom layer caps are strictly obeyed.
   - Conclusion: VRAM scaling logic fixes are **sound and verified**.

3. **Full Suite Test Failure**:
   - The test suite execution is an explicit acceptance criterion: `Execute test suite (uv run pytest -v)`.
   - `uv run pytest -v` failed with exit code 1 due to `test_partial_streaming_clean_close_truncation_detection`.
   - The root cause is that `brain_manager.py` does not check whether `bytes_downloaded >= real_total` (or `target_path.stat().st_size >= real_total`) prior to promoting the file to `MODEL_READY_ON_DISK`. If a connection drops cleanly midway through a multi-gigabyte download, the corrupt stub is accepted as valid.
   - Because the test suite has 1 failing test, milestone completion criteria are not met.

---

## 3. Caveats

- Per reviewer instructions ("Review-only — do NOT modify implementation code"), the truncation detection defect has been reported as a finding and was NOT modified by this agent.
- All 35 tests in `tests/test_challenger_m1_iter2.py` pass cleanly and remain in the workspace as permanent regression coverage for adversarial inputs and boundary values.

---

## 4. Conclusion

**Verdict**: **REQUEST_CHANGES**

- **Passed components**:
  - Action parser on hostile adversarial inputs: **APPROVED**
  - VRAM scaling logic across all boundary conditions: **APPROVED**
- **Blocking defect**:
  - Test suite failure: `tests/test_challenger_m1_iter2_1.py::test_partial_streaming_clean_close_truncation_detection` fails.
  - Required fix: In `parasite_ai/mind/brain_manager.py` inside `_download_worker()`, check that `bytes_downloaded >= real_total` before promoting state to `BrainState.MODEL_READY_ON_DISK`. If `bytes_downloaded < real_total`, clean up the file and transition to `BrainState.DOWNLOAD_FAILED`.

---

## 5. Verification Method

To independently verify all observations and test results:

1. **Verify Action Parser and VRAM Scaling Stress Suite**:
   ```powershell
   uv run pytest tests/test_challenger_m1_iter2.py -v
   ```
   *Expected*: `35 passed in ~2.8s`, exit code 0.

2. **Verify Full Test Suite and Reproduce the Truncation Failure**:
   ```powershell
   uv run pytest -v
   ```
   *Expected*: `1 failed, 172 passed in ~17.7s`, exit code 1 (`test_partial_streaming_clean_close_truncation_detection` fails).
