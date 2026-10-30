# Implementation Plan: VRAM Budgeting & Config Merging Fixes

**Target Milestone**: M1 Iteration 2  
**Author**: `teamwork_explorer_m1_iter2_3`  
**Target Files**:
1. `parasite_ai/mind/brain_manager.py` (lines 513–539)
2. `parasite_ai/config.py` (lines 454–479)
3. `tests/test_config.py` (new tests)

---

## 1. Problem 1: VRAM Budgeting & Dynamic Layer Scaling

### Problem Analysis
In `parasite_ai/mind/brain_manager.py:516`:
```python
used_mb, free_mb = check_vram_headroom()
req_mb = self.config.brain.local_model.vram_budget_mb

gpu_layers = self.config.brain.local_model.gpu_layers
if free_mb < 2000:
    # Low VRAM: reduce layers to CPU fallback
    gpu_layers = 0
```
- The variable `req_mb` was initialized from configuration but never used.
- When `free_mb` is above the hard threshold of 2000 MB (e.g. 2500 MB) but the model requires 5200 MB (e.g., Qwen 2.5 7B), or if the configured `vram_budget_mb` is 4000 MB, the system still assigns `gpu_layers = -1` (full GPU offload).
- Full GPU offload when VRAM or budget is insufficient causes CUDA out-of-memory crashes or test failures (`tests/test_stress_m1.py::TestVRAMBudgetMockHardware::test_vram_budget_exceeded_by_model_headroom`).

### Exact Fix Design
In `parasite_ai/mind/brain_manager.py`, replace `_instantiate_local_engine` (lines 513–540):

```python
<<<<
    def _instantiate_local_engine(self, model_path: Union[Path, str]) -> bool:
        """Try instantiating LlamaCppBackend, fallback to mock or endpoint."""
        used_mb, free_mb = check_vram_headroom()
        req_mb = self.config.brain.local_model.vram_budget_mb

        gpu_layers = self.config.brain.local_model.gpu_layers
        if free_mb < 2000:
            # Low VRAM: reduce layers to CPU fallback
            gpu_layers = 0

        try:
            backend = LlamaCppBackend(
                model_path=model_path,
                n_gpu_layers=gpu_layers,
                n_ctx=self.config.brain.local_model.context_size,
            )
            if backend.is_available():
                self.active_backend = backend
                self.state = BrainState.READY_LOCAL
                return True
        except Exception as exc:
            logger.warning("LlamaCpp initialization failed: %s", exc)

        # Fallback to MockBackend for test/dev stability
        self.active_backend = MockBackend()
        self.state = BrainState.READY_LOCAL
        return True
====
    def _instantiate_local_engine(self, model_path: Union[Path, str]) -> bool:
        """Try instantiating LlamaCppBackend, fallback to mock or endpoint."""
        used_mb, free_mb = check_vram_headroom()
        budget_mb = self.config.brain.local_model.vram_budget_mb
        effective_vram_mb = min(free_mb, budget_mb)

        configured_layers = self.config.brain.local_model.gpu_layers

        # Lookup model requirements and layer counts
        model_name = Path(model_path).name
        curated_info = next((m for m in CURATED_MODELS if m["filename"] == model_name), None)
        if curated_info:
            vram_required_mb = curated_info.get("vram_required_mb", 3500)
            rec_layers = curated_info.get("recommended_gpu_layers", -1)
            total_layers = rec_layers if rec_layers > 0 else 32
        else:
            meta = next((m for m in self.available_models if m.filename == model_name), None)
            vram_required_mb = meta.vram_required_mb if meta else 3500
            total_layers = 32

        # Evaluate VRAM budget against requirements
        if effective_vram_mb < 2000:
            # Low VRAM / low budget: force CPU fallback (0 layers) to prevent CUDA OOM
            gpu_layers = 0
        elif effective_vram_mb < vram_required_mb:
            # VRAM budget is exceeded by model requirement:
            # Scale offload layers proportionally to fit within effective VRAM
            layer_ratio = effective_vram_mb / vram_required_mb
            scaled_layers = max(0, int(total_layers * layer_ratio))
            if configured_layers == -1:
                gpu_layers = scaled_layers
            else:
                gpu_layers = min(configured_layers, scaled_layers)
        else:
            # Sufficient VRAM and budget for configured layers
            gpu_layers = configured_layers

        try:
            backend = LlamaCppBackend(
                model_path=model_path,
                n_gpu_layers=gpu_layers,
                n_ctx=self.config.brain.local_model.context_size,
            )
            if backend.is_available():
                self.active_backend = backend
                self.state = BrainState.READY_LOCAL
                return True
        except Exception as exc:
            logger.warning("LlamaCpp initialization failed: %s", exc)

        # Fallback to MockBackend for test/dev stability
        self.active_backend = MockBackend()
        self.state = BrainState.READY_LOCAL
        return True
>>>>
```

### Rationale & Invariant Guarantees
1. **Low VRAM Threshold (< 2000 MB)**: Still enforces `gpu_layers = 0` (preserves `test_low_vram_triggers_gpu_layers_zero`).
2. **Ample VRAM (>= vram_required_mb)**: Preserves `configured_layers` (e.g. `-1` remains `-1`, satisfying `test_ample_vram_preserves_gpu_layers`).
3. **Tight Headroom (2000 <= effective_vram < vram_required_mb)**: Scales layers down proportionally (`int(total_layers * (effective_vram / vram_required))`), guaranteeing `gpu_layers != -1`, resolving `test_vram_budget_exceeded_by_model_headroom`.
4. **Explicit User Limits**: If user configures a positive `gpu_layers`, `min(configured_layers, scaled_layers)` guarantees the engine never exceeds either the user cap or the hardware headroom.

---

## 2. Problem 2: Robust Dictionary Merging in Configuration Engine

### Problem Analysis
In `parasite_ai/config.py:466–477`:
```python
# Environment variable overrides
env_log_level = os.environ.get("PARASITE_LOG_LEVEL")
if env_log_level:
    data.setdefault("system", {})["log_level"] = env_log_level.upper()

env_brain_mode = os.environ.get("PARASITE_BRAIN_MODE")
if env_brain_mode:
    data.setdefault("brain", {})["mode"] = env_brain_mode.lower()

env_integrity = os.environ.get("PARASITE_INTEGRITY_MODE")
if env_integrity:
    data.setdefault("system", {})["integrity_mode"] = env_integrity.lower()
```
- If `data` contains `"system": None` (e.g. from YAML `system:` or `system: null`), `data.setdefault("system", {})` returns `None`. `None["log_level"] = ...` triggers:
  `TypeError: 'NoneType' object does not support item assignment`.
- If `data` contains an instantiated Pydantic model (`"system": SystemConfig()`), `setdefault` returns the `SystemConfig` instance, triggering:
  `TypeError: 'SystemConfig' object does not support item assignment`.
- If `"mind": None` is mapped to `"brain"`, `data.setdefault("brain", {})` returns `None` and triggers `TypeError`.

### Exact Fix Design
In `parasite_ai/config.py`, replace `handle_aliases_and_env` (lines 454–479):

```python
<<<<
    @model_validator(mode="before")
    @classmethod
    def handle_aliases_and_env(cls, data: Any) -> Any:
        """Alias 'mind' -> 'brain' and apply environment variable overrides."""
        if not isinstance(data, dict):
            return data

        # Backward compatibility alias: allow 'mind' to populate 'brain'
        if "mind" in data and "brain" not in data:
            data["brain"] = data.pop("mind")

        # Environment variable overrides
        env_log_level = os.environ.get("PARASITE_LOG_LEVEL")
        if env_log_level:
            data.setdefault("system", {})["log_level"] = env_log_level.upper()

        env_brain_mode = os.environ.get("PARASITE_BRAIN_MODE")
        if env_brain_mode:
            data.setdefault("brain", {})["mode"] = env_brain_mode.lower()

        env_integrity = os.environ.get("PARASITE_INTEGRITY_MODE")
        if env_integrity:
            data.setdefault("system", {})["integrity_mode"] = env_integrity.lower()

        return data
====
    @model_validator(mode="before")
    @classmethod
    def handle_aliases_and_env(cls, data: Any) -> Any:
        """Alias 'mind' -> 'brain' and apply environment variable overrides."""
        if not isinstance(data, dict):
            return data

        # Backward compatibility alias: allow 'mind' to populate 'brain'
        if "mind" in data and "brain" not in data:
            data["brain"] = data.pop("mind")

        def _get_section_dict(key: str) -> Dict[str, Any]:
            val = data.get(key)
            if isinstance(val, BaseModel):
                d = val.model_dump()
            elif isinstance(val, dict):
                d = val
            else:
                d = {}
            data[key] = d
            return d

        # Environment variable overrides
        env_log_level = os.environ.get("PARASITE_LOG_LEVEL")
        if env_log_level:
            _get_section_dict("system")["log_level"] = env_log_level.upper()

        env_brain_mode = os.environ.get("PARASITE_BRAIN_MODE")
        if env_brain_mode:
            _get_section_dict("brain")["mode"] = env_brain_mode.lower()

        env_integrity = os.environ.get("PARASITE_INTEGRITY_MODE")
        if env_integrity:
            _get_section_dict("system")["integrity_mode"] = env_integrity.lower()

        return data
>>>>
```

### Unit Tests to Add
Add to `tests/test_config.py`:
```python
def test_env_override_with_null_and_object_sections(monkeypatch):
    """Verify env overrides gracefully merge with null sections and instantiated BaseModels."""
    monkeypatch.setenv("PARASITE_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("PARASITE_BRAIN_MODE", "mock")
    monkeypatch.setenv("PARASITE_INTEGRITY_MODE", "testing")

    # Case 1: Null section in input mapping
    cfg1 = AppConfig.model_validate({"system": None, "brain": None})
    assert cfg1.system.log_level == "DEBUG"
    assert cfg1.brain.mode == "mock"
    assert cfg1.system.integrity_mode == "testing"

    # Case 2: Instantiated BaseModel section in input mapping
    cfg2 = AppConfig.model_validate({"system": SystemConfig(), "brain": BrainConfig()})
    assert cfg2.system.log_level == "DEBUG"
    assert cfg2.brain.mode == "mock"
    assert cfg2.system.integrity_mode == "testing"
```

---

## 3. Worker Execution Checklist
1. Apply the replacement in `parasite_ai/mind/brain_manager.py`.
2. Apply the replacement in `parasite_ai/config.py`.
3. Add the unit test in `tests/test_config.py`.
4. Run verification command:
   ```powershell
   uv run pytest tests/test_config.py tests/test_stress_m1.py -k "test_vram_budget or test_env_override"
   ```
5. Run full test suite:
   ```powershell
   uv run pytest
   ```
