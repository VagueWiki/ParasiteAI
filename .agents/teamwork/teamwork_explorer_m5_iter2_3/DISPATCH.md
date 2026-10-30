# Dispatch: Explorer 3 (Milestone 5 Iteration 2 - Local Model Setup & Verification)

## Mission
Investigate and formulate concrete, verified implementation and verification procedures for downloading and loading the local model `qwen2.5-3b-instruct-q4_k_m.gguf` into `models/` within the 8 GB RTX 4060 VRAM budget.

## Context & Inputs
- `g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md`
- `g:\__Docs\ParasiteAI\PROJECT.md`
- `parasite_ai/mind/brain_manager.py`
- `config.yaml`
- `pyproject.toml`
- Target model: `qwen2.5-3b-instruct-q4_k_m.gguf` (approx 2.17 GB)
- Hugging Face repository: e.g., `Qwen/Qwen2.5-3B-Instruct-GGUF`
- GPU: NVIDIA GeForce RTX 4060 (8188 MiB total, ~5.5 GB free headroom)

## Instructions
1. Inspect `parasite_ai/mind/brain_manager.py` and determine:
   - How `BrainManager` resolves model paths, downloads models via Hugging Face Hub / `urllib`, and verifies file size/hash.
   - What backends are supported (`llama-cpp-python`, `llama-server`, or mock).
   - What dependencies or commands are needed to download the file directly using huggingface-hub CLI, curl, or Python script.
2. Verify URL, exact filename, and size for `qwen2.5-3b-instruct-q4_k_m.gguf`.
3. Formulate the verification command for checking model loading and VRAM allocation without crashing or running out of memory.
4. Output your complete report to `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m5_iter2_3\handoff.md`.

## 2026-10-29T21:45:55Z
You are Explorer 3 (teamwork_explorer_m5_iter2_3).
Working directory: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m5_iter2_3\
Original request path: g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md
Project directory: g:\__Docs\ParasiteAI

Role: Read-only exploration agent. You MUST NOT modify or create any implementation or test files. Only write your progress.md and handoff.md in your working directory.

Safety Guardrail:
- Live interactive tests (Notepad task, Gemini offload) are NOT authorized.
- Absolutely NO live mouse or keyboard control. Simulated/dry-run/offscreen modes only.

Mission:
Investigate and formulate concrete, verified implementation and verification procedures for downloading and loading the local model `qwen2.5-3b-instruct-q4_k_m.gguf` into `models/` within the 8 GB RTX 4060 VRAM budget:
1. Inspect parasite_ai/mind/brain_manager.py to see how local models are downloaded, verified, and loaded.
2. Determine exact Hugging Face repository, URL, and download command (e.g. via huggingface_hub / urllib / curl) for `qwen2.5-3b-instruct-q4_k_m.gguf` (~2.17 GB).
3. Investigate how local LLM backends (llama-cpp-python / llama-server / mock) work in BrainManager.
4. Check GPU memory budget: RTX 4060 has 8 GB VRAM. Formulate the verification command to confirm model load and VRAM occupancy.
