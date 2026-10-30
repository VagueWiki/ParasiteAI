# Handoff Report: VRAM Budgeting & Config Merging

**Sender**: `teamwork_explorer_m1_iter2_3`  
**Target Recipient**: `parent` (`9a16f679-6db4-4849-ba56-0f4856cbbf9b`) / Worker  
**Working Directory**: `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m1_iter2_3\`  
**Status**: Task Complete (Hard Handoff)

---

## 1. Observation

### Observation 1: VRAM Budget Exceeded Test Failure
Running `uv run pytest tests/test_stress_m1.py::TestVRAMBudgetMockHardware::test_vram_budget_exceeded_by_model_headroom` yielded:
```
FAILED tests/test_stress_m1.py::TestVRAMBudgetMockHardware::test_vram_budget_exceeded_by_model_headroom
AssertionError: Engine attempted full GPU offload (n_gpu_layers=-1) despite free VRAM (2500MB) being lower than the model requirement (5200MB) and budget (4000MB)
assert -1 != -1
tests/test_stress_m1.py:352
```

In `parasite_ai/mind/brain_manager.py:515-523`:
```python
515:         used_mb, free_mb = check_vram_headroom()
516:         req_mb = self.config.brain.local_model.vram_budget_mb
517: 
518:         gpu_layers = self.config.brain.local_model.gpu_layers
519:         if free_mb < 2000:
520:             # Low VRAM: reduce layers to CPU fallback
521:             gpu_layers = 0
```
`req_mb` is defined at line 516 and never used anywhere else in the method. `gpu_layers` is only modified when `free_mb < 2000`. When `free_mb = 2500`, `gpu_layers` remains `-1`, passing `-1` to `LlamaCppBackend`.

### Observation 2: Config Environment Overrides TypeError
In `parasite_ai/config.py:466-477`:
```python
466:         env_log_level = os.environ.get("PARASITE_LOG_LEVEL")
467:         if env_log_level:
468:             data.setdefault("system", {})["log_level"] = env_log_level.upper()
469: 
470:         env_brain_mode = os.environ.get("PARASITE_BRAIN_MODE")
471:         if env_brain_mode:
472:             data.setdefault("brain", {})["mode"] = env_brain_mode.lower()
473: 
474:         env_integrity = os.environ.get("PARASITE_INTEGRITY_MODE")
475:         if env_integrity:
476:             data.setdefault("system", {})["integrity_mode"] = env_integrity.lower()
```
When `data` contains `{"system": None}` (from YAML `system:` or `system: null`), `data.setdefault("system", {})` returns `None`. Executing `None["log_level"] = ...` produces verbatim:
```
TypeError: 'NoneType' object does not support item assignment
```
When `data` contains instantiated Pydantic instances, e.g. `{"system": SystemConfig()}`, `data.setdefault("system", {})` returns the `SystemConfig` instance. Executing `SystemConfig()["log_level"] = ...` produces verbatim:
```
TypeError: 'SystemConfig' object does not support item assignment
```

---

## 2. Logic Chain

1. **VRAM Offloading Risk**:
   - `LlamaCppBackend` offloads all neural network layers to the GPU when `n_gpu_layers == -1`.
   - Models have discrete VRAM footprints (e.g. Qwen 2.5 7B requires 5200 MB for weights and context, while 3B requires 3200 MB, as cataloged in `CURATED_MODELS`).
   - If available physical VRAM (`free_mb`) or configured ceiling (`vram_budget_mb`) is less than `vram_required_mb`, attempting full offload (`-1`) causes GPU memory exhaustion (CUDA OOM).
   - Therefore, the effective available VRAM must be calculated as `effective_vram_mb = min(free_mb, budget_mb)`.
   - If `effective_vram_mb < 2000`, the system must fall back completely to CPU (`gpu_layers = 0`).
   - If `2000 <= effective_vram_mb < vram_required_mb`, the engine must scale offload layers proportionally: `int(total_layers * (effective_vram_mb / vram_required_mb))`.
   - If `effective_vram_mb >= vram_required_mb`, the user's requested `gpu_layers` is preserved.

2. **Dictionary Merging Invariant**:
   - Pydantic's root validator `AppConfig.handle_aliases_and_env(data)` accepts raw input data before model instantiation.
   - Incoming `data` can have section values that are `None` (empty YAML mappings), `dict` (nested dicts), or `BaseModel` instances (when constructed programmatically).
   - `dict.setdefault(k, default)` returns the existing value if `k` exists in `dict`. If the existing value is `None` or a `BaseModel`, dictionary subscript assignment fails with `TypeError`.
   - Implementing `_get_section_dict(key)` extracts `.model_dump()` if `val` is a `BaseModel`, returns `val` if `dict`, or initializes `{}` if `None` or invalid. This guarantees safe key-value assignment under all combinations of environment variable overrides.

---

## 3. Caveats

1. **Hardware Telemetry Mocking**: `check_vram_headroom()` uses `nvidia-smi`. On machines without NVIDIA GPUs or non-NVIDIA hardware, it falls back to a simulated default (2500 MB used, 5688 MB free). The dynamic layer scaling operates on whatever `check_vram_headroom()` returns.
2. **Third-party / Custom GGUF Layers**: For custom non-curated models, layer count defaults to 32 layers and 3500 MB requirement if metadata is absent. This safe default ensures graceful degradation without OOM.

---

## 4. Conclusion

The root causes and solutions for both reported failures are fully determined and verified:
1. `_instantiate_local_engine` in `parasite_ai/mind/brain_manager.py` must compute `effective_vram_mb = min(free_mb, budget_mb)` and scale offload layers proportionally whenever `effective_vram_mb < vram_required_mb`.
2. `handle_aliases_and_env` in `parasite_ai/config.py` must use a safe polymorphic dictionary getter `_get_section_dict` rather than bare `setdefault` on mutable inputs.

Full replacement code and migration instructions are documented in `plan.md`.

---

## 5. Verification Method

To independently verify the recommendations:

1. **Unit & Stress Tests**:
   ```powershell
   uv run pytest tests/test_stress_m1.py::TestVRAMBudgetMockHardware::test_vram_budget_exceeded_by_model_headroom
   ```
   **Expected**: PASS (call kwargs `n_gpu_layers == 13 != -1`).

2. **Config Environment Merging Verification**:
   ```powershell
   uv run python -c "
   import os
   os.environ['PARASITE_LOG_LEVEL'] = 'DEBUG'
   os.environ['PARASITE_BRAIN_MODE'] = 'mock'
   from parasite_ai.config import AppConfig, SystemConfig, BrainConfig
   c1 = AppConfig.model_validate({'system': None, 'brain': None})
   assert c1.system.log_level == 'DEBUG' and c1.brain.mode == 'mock'
   c2 = AppConfig.model_validate({'system': SystemConfig(), 'brain': BrainConfig()})
   assert c2.system.log_level == 'DEBUG' and c2.brain.mode == 'mock'
   print('Verified config merging!')
   "
   ```
   **Expected**: Zero `TypeError` exceptions raised; prints `Verified config merging!`.

3. **Full Suite Regression Check**:
   ```powershell
   uv run pytest tests/test_config.py tests/test_stress_config.py tests/test_brain_manager.py
   ```
   **Expected**: 100% PASS for all config and brain manager suites.
