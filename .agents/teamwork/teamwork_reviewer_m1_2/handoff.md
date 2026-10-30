# Handoff Report — Milestone M1: Foundation & Zero-Config Setup Review

## 1. Observation

### 1.1 Test Suite Execution
- **Command**: `uv run pytest -v`
- **Output**:
  ```
  ============================= test session starts =============================
  platform win32 -- Python 3.12.13, pytest-9.2.0, pluggy-1.7.0 -- G:\__Docs\ParasiteAI\.venv\Scripts\python.exe
  cachedir: .pytest_cache
  PyQt6 6.12.0 -- Qt runtime 6.12.0 -- Qt compiled 6.12.0
  rootdir: G:\__Docs\ParasiteAI
  configfile: pyproject.toml
  testpaths: tests
  plugins: anyio-4.15.1, asyncio-1.4.1, mock-3.17.0, qt-4.5.0
  asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=function, asyncio_default_test_loop_scope=function
  collecting ... collected 28 items

  tests/test_brain_manager.py::test_models_dir_creation PASSED             [  3%]
  tests/test_brain_manager.py::test_scan_models_empty PASSED               [  7%]
  tests/test_brain_manager.py::test_gguf_header_validation PASSED          [ 10%]
  tests/test_brain_manager.py::test_scan_models_populated PASSED           [ 14%]
  tests/test_brain_manager.py::test_browser_only_mode_toggle PASSED        [ 17%]
  tests/test_brain_manager.py::test_download_streaming_and_callbacks PASSED [ 21%]
  tests/test_brain_manager.py::test_download_cancellation PASSED           [ 25%]
  tests/test_brain_manager.py::test_inference_dispatch_mock PASSED         [ 28%]
  tests/test_brain_manager.py::test_action_json_resilience PASSED          [ 32%]
  tests/test_brain_manager.py::test_vram_budget_evaluation PASSED          [ 35%]
  tests/test_brain_manager.py::test_format_bytes PASSED                    [ 39%]
  tests/test_brain_manager.py::test_action_json_resilience_with_braces_in_preamble PASSED [ 42%]
  tests/test_brain_manager.py::test_download_network_failure PASSED        [ 46%]
  tests/test_brain_manager.py::test_download_already_in_progress PASSED    [ 50%]
  tests/test_brain_manager.py::test_load_and_unload_model PASSED           [ 53%]
  tests/test_brain_manager.py::test_browser_offload_backend_delegation PASSED [ 57%]
  tests/test_brain_manager.py::test_openai_endpoint_backend PASSED         [ 60%]
  tests/test_config.py::test_default_config_instantiation PASSED           [ 64%]
  tests/test_config.py::test_yaml_roundtrip PASSED                         [ 67%]
  tests/test_config.py::test_partial_yaml_loading PASSED                   [ 71%]
  tests/test_config.py::test_mind_alias_compatibility PASSED               [ 75%]
  tests/test_config.py::test_environment_variable_overrides PASSED         [ 78%]
  tests/test_config.py::test_missing_config_auto_generates_file PASSED     [ 82%]
  tests/test_config.py::test_validation_bounds PASSED                      [ 85%]
  tests/test_config.py::test_hex_color_validation PASSED                   [ 89%]
  tests/test_config.py::test_corrupt_yaml_file_raises_error PASSED         [ 92%]
  tests/test_config.py::test_load_root_config_yaml PASSED                  [ 96%]
  tests/test_config.py::test_empty_yaml_returns_default_config PASSED      [100%]

  ============================= 28 passed in 2.16s ==============================
  ```
  - **Exit Code**: 0.

### 1.2 Integrity Check
- **Codebase Audited**:
  - `pyproject.toml`
  - `config.yaml`
  - `parasite_ai/config.py`
  - `parasite_ai/mind/brain_manager.py`
  - `tests/test_config.py`
  - `tests/test_brain_manager.py`
- **Result**: No hardcoded test responses embedded in source files. Binary GGUF validation performs genuine header byte unpacking (`struct.unpack("<I", version_bytes)[0]`), model downloader implements real `httpx.stream` chunking and cancellation event polling, Pydantic V2 models validate real constraints, and multi-pass regex/JSON extraction handles realistic noisy LLM outputs.
- **Integrity Tag**: No integrity violations detected.

### 1.3 Adversarial Stress-Testing Observations

#### Observation A: YAML Empty Section with Environment Variable Override
- **Location**: `parasite_ai/config.py:468`
- **Test Command**:
  ```powershell
  python -c "from parasite_ai.config import load_config; from pathlib import Path; p = Path('test_none.yaml'); p.write_text('system:\n', encoding='utf-8'); import os; os.environ['PARASITE_LOG_LEVEL'] = 'DEBUG'; load_config(p); p.unlink()"
  ```
- **Verbatim Error Output**:
  ```
  Traceback (most recent call last):
    File "G:\__Docs\ParasiteAI\parasite_ai\config.py", line 526, in load_config
      return AppConfig.model_validate(raw_data)
    File "G:\__Docs\ParasiteAI\parasite_ai\config.py", line 468, in handle_aliases_and_env
      data.setdefault("system", {})["log_level"] = env_log_level.upper()
      ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^
  TypeError: 'NoneType' object does not support item assignment
  ```
- **Explanation**: In YAML, an empty section like `system:\n` parses into `{"system": None}`. Because `"system"` is already present in `data`, `data.setdefault("system", {})` returns the existing `None` value instead of `{}`. Indexing into `None["log_level"]` raises an unhandled `TypeError`.

#### Observation B: HuggingFace Catalog 404 for Curated 7B Model
- **Location**: `parasite_ai/mind/brain_manager.py:160-168` and `653-655`
- **Catalog Entry**:
  ```python
  {
      "model_id": "Qwen/Qwen2.5-7B-Instruct-GGUF",
      "filename": "qwen2.5-7b-instruct-q4_k_m.gguf",
      ...
  }
  ```
- **Live HTTP Check**:
  ```powershell
  uv run python -c "import httpx; r7 = httpx.head('https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF/resolve/main/qwen2.5-7b-instruct-q4_k_m.gguf', follow_redirects=True); print('7B status:', r7.status_code)"
  ```
  Output: `7B status: 404`
- **Explanation**: The upstream repository `Qwen/Qwen2.5-7B-Instruct-GGUF` stores the Q4_K_M quant in sharded form (`qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf` and `qwen2.5-7b-instruct-q4_k_m-00002-of-00002.gguf`). There is no single file named `qwen2.5-7b-instruct-q4_k_m.gguf`. Calling `start_download("Qwen/Qwen2.5-7B-Instruct-GGUF")` results in an immediate 404 error and transitions the state to `DOWNLOAD_FAILED`. (The 3B model `Qwen/Qwen2.5-3B-Instruct-GGUF` and 1.5B model return 200 OK).

#### Observation C: Imprecise State Transition upon Download Cancellation
- **Location**: `parasite_ai/mind/brain_manager.py:692`
- **Code**:
  ```python
  if self._cancel_download_event.is_set():
      ...
      with self._lock:
          self.state = BrainState.NO_MODEL_PRESENT
  ```
- **Test Scenario**: A user already has a valid model loaded (`BrainState.READY_LOCAL`). They initiate a download for a second model and subsequently cancel it.
- **Observed Behavior**: `self.state` transitions to `BrainState.NO_MODEL_PRESENT`, discarding awareness of the currently loaded active model.

#### Observation D: Invalid GGUF Download Retained on Disk
- **Location**: `parasite_ai/mind/brain_manager.py:739-753`
- **Code**:
  ```python
  temp_path.replace(target_path)
  is_valid = validate_gguf_header(target_path)
  with self._lock:
      if is_valid:
          ...
      else:
          self.state = BrainState.DOWNLOAD_FAILED
  ```
- **Observed Behavior**: `temp_path` is renamed to `target_path` before validation. When validation fails, `target_path` is left on disk. Subsequent `scan_models()` calls flag this file as `is_downloaded=True, is_valid_gguf=False`.

#### Observation E: State Transition Clashing Between Concurrent `generate()` and `unload_model()`
- **Location**: `parasite_ai/mind/brain_manager.py:828-835, 861-876`
- **Code**:
  ```python
  # in generate():
  prev_state = self.state
  self.state = BrainState.INFERRING
  ...
  finally:
      with self._lock:
          self.state = prev_state
  ```
- **Observed Behavior**: If `unload_model()` is executed concurrently while `generate()` is running, `unload_model()` checks `if self.state == BrainState.READY_LOCAL` (which is `False` due to `INFERRING`). When `generate()` finishes, its `finally` block unconditionally restores `self.state = prev_state` (`READY_LOCAL`), leaving the state as `READY_LOCAL` even though the backend was unloaded.

---

## 2. Logic Chain

1. **Baseline M1 Requirements Satisfied**:
   - `pyproject.toml` pins Python `>=3.12,<3.13`, Hatchling build backend, and required dependencies (`pyqt6`, `uiautomation`, `rapidocr-onnxruntime`, `pynput`, `pyautogui`, `pydantic`, `pyyaml`, `pytest`, `mss`).
   - `config.yaml` and `parasite_ai/config.py` provide full Pydantic V2 models, default self-healing generation on missing file, environment variable overrides, and backward compatibility alias for `mind` -> `brain`.
   - `parasite_ai/mind/brain_manager.py` implements binary GGUF header verification, multi-pass resilient JSON extraction for actions, zero-VRAM browser offload toggle, streaming download tracking, and dual-mind dispatch.
   - All 28 automated unit tests pass in 2.16 seconds without error.

2. **Integrity Chain**:
   - No mock facades or hardcoded answer shortcuts exist in production code.
   - Downloader, GGUF binary inspection, and config parser are genuine implementations.

3. **Risk & Severity Assessment**:
   - The findings identified (Observations A through E) represent edge cases in non-standard configurations (empty YAML keys, downloading the non-default 7B catalog entry, thread race during active generation).
   - The primary zero-config workflow (default 3B model, browser offload mode, standard YAML files, and sequential execution) operates reliably.
   - Therefore, Milestone M1 is architecturally sound and functionally complete, warranting an **APPROVE** verdict with documented action items for Milestone M5 hardening.

---

## 3. Caveats

- `llama-cpp-python` is an optional compiled dependency. When CUDA/C++ compilers are absent on the host, `LocalBrainManager` falls back gracefully to `MockBackend` or `BrowserOffloadBackend` as designed.
- Live physical interaction with Chrome and physical input hooks are interface contracts in M1; full physical automation will be integrated across Milestones M2 through M5.

---

## 4. Conclusion & Quality Review Summary

### Review Summary
- **Verdict**: **APPROVE**
- **Overall Quality**: High. Milestone M1 successfully establishes the foundation, dependency pinning, zero-config configuration engine, and local brain manager.

### Findings

#### [Major] Finding 1: Unhandled `TypeError` in `load_config` when YAML sections are empty (`None`) with environment variable overrides
- **Where**: `parasite_ai/config.py:468, 472, 476`
- **Why**: `data.setdefault("system", {})` returns `None` if `system:` is present with no children, causing raw `TypeError: 'NoneType' object does not support item assignment`.
- **Suggested Fix**:
  ```python
  if data.get("system") is None:
      data["system"] = {}
  if data.get("brain") is None:
      data["brain"] = {}
  ```

#### [Major] Finding 2: Curated 7B model in `CURATED_MODELS` causes HTTP 404
- **Where**: `parasite_ai/mind/brain_manager.py:160-168`
- **Why**: Upstream HuggingFace repository shards Q4_K_M weights into multiple `-00001-of-00002` files; single file `qwen2.5-7b-instruct-q4_k_m.gguf` does not exist.
- **Suggested Fix**: Point catalog to an un-sharded repository (e.g., `bartowski/Qwen2.5-7B-Instruct-GGUF`) or implement multi-shard download assembly.

#### [Minor] Finding 3: Download cancellation sets state to `NO_MODEL_PRESENT` even if a local model exists
- **Where**: `parasite_ai/mind/brain_manager.py:692`
- **Why**: Unconditionally overrides state without checking if valid models exist on disk.
- **Suggested Fix**:
  ```python
  valid_models = [m for m in self.scan_models() if m.is_downloaded and m.is_valid_gguf]
  self.state = BrainState.READY_LOCAL if self.active_backend and self.active_backend.is_available() else (
      BrainState.MODEL_READY_ON_DISK if valid_models else BrainState.NO_MODEL_PRESENT
  )
  ```

#### [Minor] Finding 4: Invalid GGUF files remain on disk after verification failure
- **Where**: `parasite_ai/mind/brain_manager.py:749-753`
- **Why**: `temp_path` is moved to `target_path` before header verification; failed files are not unlinked.
- **Suggested Fix**: Add `target_path.unlink(missing_ok=True)` in the verification failure block.

#### [Minor] Finding 5: Race condition between `generate()` and `unload_model()`
- **Where**: `parasite_ai/mind/brain_manager.py:828-835, 874-876`
- **Why**: `generate()` unconditionally restores `prev_state` in its `finally` block, clobbering states updated by concurrent calls to `unload_model()`.
- **Suggested Fix**: Only restore state in `generate()` if `self.state == BrainState.INFERRING`.

### Verified Claims
- `uv run pytest -v` runs with 28 passing tests in ~2 seconds (PASS).
- `validate_gguf_header` validates binary GGUF v2/v3 magic bytes and rejects bad versions/truncation (PASS).
- Missing `config.yaml` automatically generates valid default file (PASS).
- Multi-pass JSON action parser handles raw JSON, markdown blocks, and preambles with curly braces (PASS).
- Zero-VRAM mode toggle switches between `BROWSER_OFFLOAD` and `LOCAL_LLM` (PASS).

---

## 5. Verification Method

To independently reproduce this assessment:
1. Ensure working directory is `g:\__Docs\ParasiteAI`.
2. Run test suite:
   ```powershell
   uv run pytest -v
   ```
   *Expected*: 28 tests passed with exit code 0.
3. Verify zero-config file loading:
   ```powershell
   uv run python -c "from parasite_ai.config import load_config; cfg = load_config(); print(cfg.persona.name, cfg.brain.mode)"
   ```
   *Expected*: `Parasite browser_offload`.
4. Test GGUF validation:
   ```powershell
   uv run python -c "from parasite_ai.mind.brain_manager import validate_gguf_header; print(validate_gguf_header('non_existent.gguf'))"
   ```
   *Expected*: `False`.
