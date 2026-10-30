# Dispatch for teamwork_explorer_discrepancy

## Task
Conduct a comprehensive Discrepancy Analysis between unit/simulated test results and real desktop execution requirements for ParasiteAI across all implemented milestones (M1–M5).

Read:
- `g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md`
- `g:\__Docs\ParasiteAI\PROJECT.md`
- Implementation plan and state evaluation plan:
  - `C:\Users\Suici\.gemini\antigravity\brain\9febbb50-4316-49f8-85fe-f612a778b2d3\implementation_plan.md`
  - `C:\Users\Suici\.gemini\antigravity\brain\9febbb50-4316-49f8-85fe-f612a778b2d3\state_evaluation_plan.md`
- Core codebase files:
  - `parasite_ai/safety/interrupt_guard.py`, `window_guard.py`
  - `parasite_ai/hands/kinematics.py`, `mouse.py`, `keyboard.py`
  - `parasite_ai/ui/companion_dock.py`, `ghost_hud.py`
  - `parasite_ai/vision/capture.py`, `grounding.py`
  - `parasite_ai/mind/memory.py`, `dual_mind.py`, `offloader.py`, `brain_manager.py`
  - `parasite_ai/runtime.py`, `main.py`

Identify and document specific gaps, failure modes, and architectural assumptions between simulated test conditions and live Windows desktop execution:
1. Companion dock: Real DWM window management, always-on-top behavior, DPI scaling, frameless drag.
2. Ghost-Hand HUD: Transparent click-through (`WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE | WS_EX_TOPMOST`), multi-monitor coordinate translation, Windows composition pipeline.
3. Kinematic mouse glide: Bézier curves, Min-Jerk velocity profile, micro-jitter, and overshoot vs real Windows cursor acceleration and physical clipping.
4. Physical touch abort: `WH_MOUSE_LL` and `WH_KEYBOARD_LL` low-level hooks in live interactive sessions vs `simulate_event` in headless tests; sub-2ms preemption in live OS.
5. Chrome/Gemini offloader: Real Chrome UI Automation tree walking, DOM/selector brittleness, dynamic web elements, and Sentinel Clipboard round-trip verification under live clipboard managers / race conditions.
6. Local Brain Manager: 8 GB VRAM budget (RTX 4060) vs model size / GGUF quantization / context window memory footprint.

Deliver `handoff.md` with:
- Observation (verified facts and code references)
- Logic Chain (analysis of each gap)
- Caveats (what cannot be verified without interactive user consent)
- Prioritized Risk Matrix (High/Medium/Low risk discrepancies)
- Remediation recommendations for live testing and follow-up milestones


## 2026-10-29T20:57:51Z
You are teamwork_explorer_discrepancy.
Working directory: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_discrepancy
Task assignment: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_discrepancy\DISPATCH.md
Original request path: g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md
Master project plan: g:\__Docs\ParasiteAI\PROJECT.md
State evaluation plan: C:\Users\Suici\.gemini\antigravity\brain\9febbb50-4316-49f8-85fe-f612a778b2d3\state_evaluation_plan.md
Implementation plan: C:\Users\Suici\.gemini\antigravity\brain\9febbb50-4316-49f8-85fe-f612a778b2d3\implementation_plan.md

Your Tasks:
1. Read g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md and DISPATCH.md.
2. Conduct a deep architectural and implementation discrepancy analysis across M1–M5:
   Compare the unit/simulated test suites (`simulate_event`, offscreen Qt, mock browser windows, etc.) against real physical Windows desktop and hardware execution requirements:
   - Companion dock: Frameless PyQt6 DWM composition, always-on-top, taskbar visibility, multi-DPI scaling.
   - Click-through HUD: `WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE | WS_EX_TOPMOST` click-through guarantees, Set-of-Mark numbered boxes rendering, 300ms pre-click reticle overlay on multi-monitor setups.
   - Bézier glide: Cubic Bézier curves, Flash & Hogan min-jerk velocity profiling, micro-jitter, overshoot vs Windows cursor acceleration curves and physical display clipping.
   - Physical abort: Low-level hardware hooks (`WH_MOUSE_LL`, `WH_KEYBOARD_LL`) filtering synthetic (`LLMHF_INJECTED`) vs physical input in a real interactive Windows session, sub-2ms preemption token.
   - Chrome/Gemini offload selectors: Real Chrome UI Automation tree walking, DOM/selector fragility, dynamic web element positioning, and Sentinel Clipboard round-trip verification under live clipboard managers and race conditions.
   - Brain resource budget: 8 GB VRAM budget on NVIDIA RTX 4060 vs local GGUF models and context limits.
3. Build a structured Risk Matrix (High/Medium/Low) detailing:
   - Feature / Area
   - Simulated test condition
   - Real desktop failure mode / risk
   - Recommended live verification step or hardening action
4. Deliver `handoff.md` in your working directory with comprehensive findings. Notify the orchestrator with send_message when complete.
