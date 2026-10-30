## 2026-10-29T11:09:45Z
You are teamwork_worker_m1.
Your working directory is: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_worker_m1\
Original Request: g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md
Project Spec: g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md

Explorer Plans to Follow:
- Packaging & Environment: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m1_1\plan.md
- Configuration & Pydantic Models: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m1_2\plan.md
- Local Brain Manager Architecture: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m1_3\plan.md

Your exclusive file ownership:
- pyproject.toml
- config.yaml
- .python-version
- README.md
- parasite_ai/__init__.py
- parasite_ai/config.py
- parasite_ai/mind/__init__.py
- parasite_ai/mind/brain_manager.py
- tests/__init__.py
- tests/test_config.py
- tests/test_brain_manager.py

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Tasks:
1. Implement the Python 3.12 project environment with pyproject.toml using uv and Hatchling per Explorer 1's plan.
2. Implement `config.yaml` and `parasite_ai/config.py` with full Pydantic v2 schemas per Explorer 2's plan.
3. Implement `parasite_ai/mind/brain_manager.py` with pluggable backends (LlamaCppBackend, OpenAIEndpointBackend, BrowserOffloadBackend, MockBackend), binary GGUF header validation (`b"GGUF"`), streaming downloads, zero-VRAM browser offload toggle, and unified inference dispatch per Explorer 3's plan.
4. Implement comprehensive unit tests in `tests/test_config.py` and `tests/test_brain_manager.py`.
5. Run verification commands (`uv sync` and `uv run pytest tests/test_config.py tests/test_brain_manager.py -v`) and verify that 100% of tests pass.
6. Write a detailed handoff report to `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_worker_m1\handoff.md` and message parent when complete.
