# Dispatch for Explorer M1 Iteration 2 (3/3)

## 2026-10-29T11:32:21Z
Working Directory: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m1_iter2_3\
Original Request: g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md
Project Spec: g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md

Failure Context from Reviewers/Challengers:
1. `_instantiate_local_engine` in `parasite_ai/mind/brain_manager.py:270`:
   `req_mb = self.config.brain.local_model.vram_budget_mb` is assigned but never evaluated against available VRAM. If available VRAM is insufficient for model size, full GPU offload (`n_gpu_layers = -1`) is still attempted, risking CUDA OOM crashes.
   Test: `tests/test_stress_m1.py::TestVRAMBudgetMockHardware::test_vram_budget_exceeded_by_model_headroom`.
2. `load_config` in `parasite_ai/config.py`:
   When environment variable overrides are set and a section is instantiated with defaults or empty mapping, a `TypeError` can be raised during dictionary merging.

Mission:
Investigate and design exact fix recommendations for VRAM budgeting in `brain_manager.py` (calculating appropriate `n_gpu_layers` based on available free VRAM and budget) and robust dictionary merging in `config.py`.
Write fix plan for worker to `plan.md` and `handoff.md`, and message parent when complete. Do NOT write source code files.
