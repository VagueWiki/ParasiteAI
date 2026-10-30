# ParasiteAI — Milestone Gate & Audit Status

## Executive Summary

All 5 milestones (**M1–M5**) of **ParasiteAI** have passed formal review, adversarial challenger stress testing, and forensic integrity auditing.

| Milestone | Scope | Gate Iteration | Verdict | Test Count |
| --- | --- | --- | --- | --- |
| **M1** | Foundation, Pydantic Config & Local Brain Manager | Iteration 4 | **PASS** (Unanimous) | 178 / 178 |
| **M2** | Win32 Low-Level Hooks (`<2ms` Interrupt), Window Guard & Bézier Kinematics | Iteration 1 | **PASS** (Unanimous) | 321 / 321 |
| **M3** | Desktop Companion Dock & Click-Through Ghost-Hand HUD Overlay | Iteration 2 | **PASS** (Unanimous) | 424 / 424 |
| **M4** | Hybrid Screen Grounding, Episodic Memory, Dual-Mind & Chrome Offloader | Iteration 1 | **PASS** (Unanimous) | 552 / 552 |
| **M5** | Runtime Orchestrator, Entry Points (`main.py`, `launch_parasite.bat`) & E2E Hardening | Iteration 2 | **PASS** (Unanimous) | 660 / 660 |

---

## Milestone 5 Iteration 2 Gate Verification Details

### 1. Remediation of Iteration 1 Challenger Findings (Verified Closed)
1. **Worker Thread Exception Survivability (`parasite_ai/runtime.py`):**
   - Wrapped `_execute_goal_episode` and individual step calls in top-level `try...except Exception:` boundaries that neutralize mouse/keyboard inputs, clear HUD reticles/targets, notify the Companion Dock, and keep the background worker thread alive.
2. **Cognitive 3-Strike Loop Decoupling from Hardware Panic (`parasite_ai/runtime.py`, `parasite_ai/mind/dual_mind.py`):**
   - Cognitive 3-strike failure loops trigger a clean episode strategy reset without latching a permanent hardware panic state, and `reset_panic()` / `reset_loop_detector()` re-arm cleanly between goals.
3. **Goal Queue Flush on Panic (`parasite_ai/ui/bridge.py`, `parasite_ai/runtime.py`):**
   - `UIBridge.clear_goals()` purges all queued goals whenever a hardware or GUI panic is triggered, preventing stale goal replay after an emergency abort.
4. **In-Flight Pause Preemption (`parasite_ai/runtime.py`):**
   - Toggling **Pause Hands** in the Companion Dock immediately sets `InterruptGuard`'s cancellation token, halting in-flight cursor movement in `< 20ms` and releasing held buttons.

### 2. Pre-Live Desktop & GPU Inference Hardening (Verified Closed)
1. **Multi-Monitor Virtual Screen Clamping (`parasite_ai/hands/mouse.py`, `parasite_ai/hands/kinematics.py`):**
   - `MouseDriver.normalize_coordinates` clamps coordinates to `[vx, vx + vcx - 1]` and `[vy, vy + vcy - 1]` prior to `[0, 65535]` Win32 normalization, preventing edge wrap-around.
2. **Grounded Chrome UIA Selectors (`parasite_ai/mind/offloader.py`):**
   - `BrowserOffloader._find_prompt_target` and `_find_copy_button` query `ScreenGrounder` (Win32 UI Automation + scoped OCR) to locate Chrome's prompt input and Copy button before falling back to window-relative geometry.
3. **64-Bit Win32 Layered Window Pointers (`parasite_ai/ui/win32_styles.py`):**
   - Uses 64-bit `GetWindowLongPtrW` / `SetWindowLongPtrW` with `c_ssize_t` (`LONG_PTR`).
4. **CUDA 12 `LlamaCppBackend` & `qwen2.5-3b-instruct-q4_k_m.gguf` Live GPU Inference (`parasite_ai/mind/brain_manager.py`, `pyproject.toml`):**
   - Locked prebuilt CUDA 12 `llama-cpp-python` wheel + `nvidia-cuda-runtime-cu12` / `nvidia-cublas-cu12` in `pyproject.toml`.
   - Automatic Windows CUDA DLL directory registration (`_register_cuda_dll_directories()`) in `LlamaCppBackend`.
   - Empirically verified on the host **NVIDIA GeForce RTX 4060 (8 GB VRAM)**: `qwen2.5-3b-instruct-q4_k_m.gguf` loads with full GPU layer offload (`3,382 MB` used VRAM, `4,576 MB` free VRAM) and executes both Pass 1 (Persona monologue) and Pass 2 (JSON Action Dispatcher).
