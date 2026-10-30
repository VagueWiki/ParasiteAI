# Dispatch for Explorer M2 (2/3)

Working Directory: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m2_2\
Original Request: g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md
Project Spec: g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md
Survey 2 Report: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_survey_2\survey_report.md

Milestone: M2 — Safety & Physical Input Layer
Focus: Kinematic Mouse Trajectory Engine (`parasite_ai/hands/kinematics.py` and `parasite_ai/hands/mouse.py`)
Requirements:
1. Human-like trajectories avoiding straight lines or instant jumps: Cubic Bézier curve, Flash & Hogan Minimum Jerk easing ($\tau(s) = 10s^3 - 15s^4 + 6s^5$), physiologic micro-jitter, and natural overshoot.
2. 120Hz trajectory interpolation with high-resolution Windows timers (`timeBeginPeriod(1)`).
3. Interrupt-aware execution: checks cancellation token before every step to abort in < 2ms.
4. Pre-click reticle signaling hook (300ms preview before physical click).

Deliverable: Concrete implementation plan and test specifications for Worker in `plan.md` and `handoff.md`.


## 2026-10-29T12:40:56Z
You are teamwork_explorer_m2_2, an exploration agent for ParasiteAI Milestone M2: Safety & Physical Input Layer.

Your working directory is: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m2_2\
You MUST read:
1. ORIGINAL_REQUEST: g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md
2. Master Project Spec: g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md
3. Your Dispatch: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m2_2\DISPATCH.md
4. Survey 2 Technical Report: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_survey_2\survey_report.md
5. Existing codebase in g:\__Docs\ParasiteAI\parasite_ai\

Your Focus:
Kinematic Mouse Trajectory Engine: `parasite_ai/hands/kinematics.py` and `parasite_ai/hands/mouse.py`, plus tests `tests/test_kinematics.py` and `tests/test_mouse_driver.py`.

Technical Requirements to analyze & specify:
1. Mathematical modeling of human arm & wrist kinematics:
   - Fitts's Law duration scaling: $T = a + b \log_2(1 + D/W)$ with $a=0.16s, b=0.11s/bit, W=40px$, clamped between $0.18s$ and $0.65s$.
   - Cubic Bézier curve with perpendicular offset arc deviation ($A = D \cdot \text{Uniform}(-0.14, 0.14)$).
   - Flash & Hogan Minimum Jerk trajectory polynomial: $\tau(s) = 10s^3 - 15s^4 + 6s^5$ mapping normalized time to displacement with zero boundary velocities and accelerations.
   - Physiological micro-jitter (8-12Hz) with sine boundary damping $\sin(\pi s)$ ensuring jitter is exactly zero at endpoints ($s=0$ and $s=1$).
   - Target overshoot (2-5px) and rapid corrective micro-hop (40-60ms) for natural human-like targeting.
2. Mouse Driver execution:
   - 120Hz trajectory interpolation using Windows high-resolution scheduler (`timeBeginPeriod(1)`).
   - Interruptible step loop: checks `cancellation_token` or `interrupt_event.wait(timeout=step_interval)` before every step to abort instantly in < 2ms if physical hardware touch occurs.
   - Pre-click reticle callback hook: signals HUD preview (300ms) before clicking or starting movement.
   - Left click, right click, double click, drag-and-drop implementations using Win32 `SendInput` / `mouse_event` with `LLMHF_INJECTED = 1`.
   - Mockable / deterministic simulation mode for headless CI test execution.

Deliverable:
Write your complete technical implementation plan in `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m2_2\plan.md` and your final report in `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m2_2\handoff.md`. Include exact mathematical formulas, class definitions, function signatures, trajectory evaluation loops, and pytest test suite specs.
When finished, notify the orchestrator via send_message.
