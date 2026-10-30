# Empirical Challenge Report — Milestone M1: Foundation & Zero-Config Setup

**Challenger**: `teamwork_challenger_m1_2`  
**Verdict**: **REQUEST_CHANGES**  
**Targets Tested**:
1. Dual-mind action extraction under hostile LLM outputs
2. Memory / VRAM budget calculation under mock hardware environments
3. Zero-VRAM browser offload toggle latency and state machine idempotency

---

## 1. Observation

### Observation 1: Action Extractor Fails on Nested JSON with Preamble Braces
- **File**: `parasite_ai/mind/brain_manager.py:947-990` (`_extract_action_json`)
- **Test File**: `tests/test_stress_m1.py:155-176` (`test_preamble_with_multiple_braces_and_nested_json`)
- **Command**:
  ```powershell
  uv run pytest tests/test_stress_m1.py -k test_preamble_with_multiple_braces_and_nested_json -v
  ```
- **Verbatim Error**:
  ```
  FAILED tests/test_stress_m1.py::TestHostileActionExtraction::test_preamble_with_multiple_braces_and_nested_json - AssertionError: Failed to extract valid action JSON from output with preamble braces and nested JSON: None
  assert None is not None
  ```
- **Code Inspection**:
  In `_extract_action_json`:
  ```python
  # Pass 4: Find all potential JSON objects
  for candidate in re.findall(r"\{[\s\S]*?\}", raw_response):
      try:
          parsed = json.loads(candidate.strip())
          if isinstance(parsed, dict) and "action" in parsed:
              return parsed
      except Exception:
          continue
  ```
  When the raw LLM output contains conversational thoughts with `{...}` (e.g. `I checked {condition}`) and the action object contains any nested dictionary/array (e.g. `"metadata": {"key": "val"}`), Pass 1 fails due to preamble text; Pass 2 fails due to absence of ` ``` ` markdown fence; Pass 3 (`r"\{[\s\S]*\}"`) fails because it greedily spans from the first brace in the preamble to the end of the JSON block; and Pass 4 (`r"\{[\s\S]*?\}"`) non-greedily stops at the *first* closing brace `}` inside the nested structure, producing an unclosed, malformed JSON fragment. `_extract_action_json` returns `None`, forcing `generate_action` to discard the action and fall back to `WAIT`.

---

### Observation 2: Unused VRAM Budget and Unbounded GPU Layer Offload
- **File**: `parasite_ai/mind/brain_manager.py:515-522` (`_instantiate_local_engine`)
- **Test File**: `tests/test_stress_m1.py:327-362` (`test_vram_budget_exceeded_by_model_headroom`)
- **Command**:
  ```powershell
  uv run pytest tests/test_stress_m1.py -k test_vram_budget_exceeded_by_model_headroom -v
  ```
- **Verbatim Error**:
  ```
  FAILED tests/test_stress_m1.py::TestVRAMBudgetMockHardware::test_vram_budget_exceeded_by_model_headroom - AssertionError: Engine attempted full GPU offload (n_gpu_layers=-1) despite free VRAM (2500MB) being lower than the model requirement (5200MB) and budget (4000MB)
  assert -1 != -1
  ```
- **Code Inspection**:
  In `_instantiate_local_engine`:
  ```python
  used_mb, free_mb = check_vram_headroom()
  req_mb = self.config.brain.local_model.vram_budget_mb

  gpu_layers = self.config.brain.local_model.gpu_layers
  if free_mb < 2000:
      # Low VRAM: reduce layers to CPU fallback
      gpu_layers = 0
  ```
  `req_mb` is assigned on line 516 and never referenced again. If free VRAM is 2500 MB (which exceeds the hardcoded `2000` MB check), but a 7B model requires 5200 MB (or the user configured `vram_budget_mb = 4000`), the engine leaves `gpu_layers = -1` (offload all layers to GPU), attempting full offload into insufficient memory and risking CUDA OOM crashes on real hardware.

---

### Observation 3: State Machine Desynchronization on Concurrent Inference & Offload Toggle
- **File**: `parasite_ai/mind/brain_manager.py:861-876` (`generate`) and lines 785-800 (`toggle_browser_only_mode`)
- **Test File**: `tests/test_stress_m1.py:467-500` (`test_state_machine_generate_and_toggle_interleaving`)
- **Command**:
  ```powershell
  uv run pytest tests/test_stress_m1.py -k test_state_machine_generate_and_toggle_interleaving -v
  ```
- **Verbatim Error**:
  ```
  FAILED tests/test_stress_m1.py::TestBrowserOffloadToggleStress::test_state_machine_generate_and_toggle_interleaving - AssertionError: State corrupted! Mode is BrainMode.BROWSER_OFFLOAD but state is BrainState.READY_LOCAL
  assert <BrainState.READY_LOCAL: 'READY_LOCAL'> == <BrainState.READY_BROWSER_OFFLOAD: 'READY_BROWSER_OFFLOAD'>
    
    - READY_BROWSER_OFFLOAD
    + READY_LOCAL
  ```
- **Code Inspection**:
  In `generate`:
  ```python
  with self._lock:
      ...
      prev_state = self.state
      self.state = BrainState.INFERRING

  try:
      return self.active_backend.generate(...)
  finally:
      with self._lock:
          self.state = prev_state
  ```
  `generate` captures `prev_state = self.state` (e.g. `READY_LOCAL`) and releases `self._lock` during inference. If `toggle_browser_only_mode(True)` is called concurrently, it sets `self.mode = BrainMode.BROWSER_OFFLOAD` and `self.state = BrainState.READY_BROWSER_OFFLOAD`. When `generate` completes, its `finally:` block unconditionally restores `self.state = prev_state` (`READY_LOCAL`), desynchronizing the state machine: `mode` is `BROWSER_OFFLOAD` while `state` reports `READY_LOCAL`.

---

### Observation 4: Browser Offload Toggle Latency & Sequential Idempotency
- **Test File**: `tests/test_stress_m1.py:364-386` (`test_rapid_toggle_latency_budget`)
- **Benchmark Result**:
  - In absence of concurrent inference race, 50 rapid sequential toggles averaged **1.84ms** per toggle (peak **8.12ms**), well within the <50ms latency budget.
  - Calling `toggle_browser_only_mode(True)` 5 times consecutively and `toggle_browser_only_mode(False)` 5 times consecutively in single-threaded context is idempotent and stable.

---

## 2. Logic Chain

1. *Step 1 (Observation 1 -> Extractor Fragility)*: Real-world LLMs frequently emit thought monologues containing variables or syntax examples like `{element: active}` alongside JSON actions. Set-of-Mark and planner actions routinely require nested data (e.g., coordinates, bounding boxes, metadata). Because Pass 4 uses regex non-greedy matching `r"\{[\s\S]*?\}"`, it matches from the outer opening brace to the *first* inner closing brace, breaking JSON syntax. Therefore, the extractor fails to parse valid actions under realistic LLM narrative preambles.
2. *Step 2 (Observation 2 -> Budget Enforcement)*: `LocalModelConfig.vram_budget_mb` is defined as a validated Pydantic configuration setting and explicitly listed in `PROJECT.md` Feature 10. In `brain_manager.py:516`, `req_mb = self.config.brain.local_model.vram_budget_mb` is defined but unused. When free VRAM is between 2000 MB and the model requirement (e.g. 2500 MB for a 5200 MB 7B model), full GPU offload (`gpu_layers = -1`) is attempted without scaling or fallback, causing out-of-memory errors on 8GB cards like the RTX 4060.
3. *Step 3 (Observation 3 -> Concurrency State Corruption)*: The Companion Dock UI allows the user to switch to Zero-VRAM offload at any time. When an inference pass is active on the worker thread, `generate` releases the manager lock during the HTTP or model call. The toggle thread transitions the mode and state cleanly. However, `generate`'s `finally:` block unconditionally overwrites `self.state` with `prev_state`, resulting in a corrupt split state (`mode=browser_offload`, `state=READY_LOCAL`).
4. *Step 4 (Synthesis -> Actionable Verdict)*: While baseline single-threaded, happy-path functionality works (22 of 25 stress tests pass), the three stress dimensions expose failure modes in action extraction, VRAM headroom guarding, and concurrency state management. Therefore, changes must be requested before Milestone M1 can be certified.

---

## 3. Caveats

- In pure single-threaded sequential execution, `toggle_browser_only_mode` is fast (< 2ms) and idempotent. The state machine defect only manifests when `toggle_browser_only_mode` or `unload_model` runs concurrently with an active `generate()` call.
- The VRAM budget bug affects configurations where free VRAM is between 2000 MB and `vram_budget_mb` (or the model's required VRAM). Systems with > 6GB free VRAM will not experience CUDA OOM with 3B models, but 7B models will fail on 8GB host GPUs under typical desktop baseline loads (2.5GB DWM usage).

---

## 4. Conclusion

Milestone M1 cannot be approved in its current state. The empirical verdict is **REQUEST_CHANGES**.

The worker must apply the following 3 targeted fixes in `parasite_ai/mind/brain_manager.py`:
1. **Resilient Nested JSON Extraction**:
   In `LocalBrainManager._extract_action_json`, replace the non-greedy `re.findall(r"\{[\s\S]*?\}")` in Pass 4 with a balanced-brace or `json.JSONDecoder().raw_decode` loop scanning from each `{` index.
2. **VRAM Headroom & Budget Enforcement**:
   In `LocalBrainManager._instantiate_local_engine`:
   Check `free_mb` against `self.config.brain.local_model.vram_budget_mb` and model requirements from `CURATED_MODELS`. If `free_mb < min(budget_mb, model_required_mb)`, scale down `gpu_layers` or set `gpu_layers = 0` to safely prevent CUDA OOM.
3. **State Machine Concurrency Protection**:
   In `LocalBrainManager.generate`:
   Inside `finally: with self._lock:`, only restore `self.state = prev_state` if `self.state == BrainState.INFERRING`. If another thread has transitioned `self.state` (e.g. to `READY_BROWSER_OFFLOAD`), do not overwrite it.

---

## 5. Verification Method

To independently reproduce the failures:
1. Ensure working directory is `g:\__Docs\ParasiteAI`.
2. Run the empirical stress test suite:
   ```powershell
   uv run pytest tests/test_stress_m1.py -v
   ```
   *Expected Result*: 22 PASSED, 3 FAILED (demonstrating the 3 bugs documented in Observations 1, 2, and 3).
3. To test each failure individually:
   ```powershell
   # 1. Action extractor nested JSON failure
   uv run pytest tests/test_stress_m1.py -k test_preamble_with_multiple_braces_and_nested_json -v

   # 2. VRAM budget headroom failure
   uv run pytest tests/test_stress_m1.py -k test_vram_budget_exceeded_by_model_headroom -v

   # 3. State machine concurrency race failure
   uv run pytest tests/test_stress_m1.py -k test_state_machine_generate_and_toggle_interleaving -v
   ```
4. Invalidation Condition: Once the worker implements the remediations, running `uv run pytest tests/test_stress_m1.py -v` must result in 25 passed tests with exit code 0.
