# Stage P2.5 Post-Mortem & Intermediary Benchmark Certification (baseline_p2_5)

**Date:** 2026-11-10  
**Certifying Run:** `baseline_p2_5.json` (20 tasks: `L1-01` through `L3-03`)  
**Hardware Profile:** Windows 10 x64 | NVIDIA GeForce RTX 4060 (8GB VRAM, Driver 610.74)  
**Model Configuration:** `UI-TARS-1.5-7B.IQ4_XS.gguf` + `mmproj-Q8_0.gguf` on persistent `llama-server.exe` (port 8080)  

---

## 1. Executive Summary & Scorecard

Stage P2.5 introduced foundational CUA visual stability, window focus activation, and modal/stray menu recovery to ParasiteAI. This post-mortem evaluates the complete 20-task benchmark run `baseline_p2_5`.

| Key Metric | P0 Baseline | P2 Baseline | P2.5 Certified (`baseline_p2_5`) | Target Gate | Status |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Pass Rate** | 5.0% (1/20) | 5.0% (1/20) | **0.0% (0/20)** | Lift over P0 | ⚠️ Below Target |
| **False-`DONE` Rate** | 20.0% (4/20) | 0.0% (0/20) | **0.0% (0/20)** | <= 10.0% | 🟢 **PASS (0 Occurrences)** |
| **Median Step Latency** | 5.986s | 3.881s | **3.592s** | <= 5.0s | 🟢 **PASS (-2.39s vs P0)** |
| **P90 Step Latency** | 9.798s | 5.242s | **4.361s** | <= 6.0s | 🟢 **PASS (-5.44s vs P0)** |
| **Mean Task Duration** | 39.3s | 32.3s | **29.3s** | Lower is better | 🟢 **PASS (-10.0s vs P0)** |
| **Hardware Interrupts**| 0 | 2 | **0** | 0 | 🟢 **PASS (Zero Preemptions)** |
| **Cold Start Latency** | 32.0s | 0ms | **0ms** | <= 1.0s | 🟢 **PASS (Persistent Daemon)** |

---

## 2. Architectural Validations in Stage P2.5

### A. Stray Menu & Modal Recovery (Stint P2.5.3)
- **Live Empirical Verification:** In task `L2-01` and `L2-02`, when blocked by stray desktop context menus, UI-TARS proactively issued `Action: HOTKEY(keys=['esc'])` on Step 1:
  > *"I see that the context menu is blocking the workspace, so I need to close it first. I'll press the Esc key to dismiss the menu..."*
- **Screen Verification:** Measured screen diff `0.1084` immediately cleared the menu, preventing menu traps that previously caused hard failures.
- **Oscillation Protection:** In task `L2-06`, consecutive `HOTKEY('esc')` repeats triggered the anti-oscillation heuristic (`[OSCILLATION LOOP DETECTED]`), recording failure strikes and breaking repetition loops.

### B. Window Focus Activation (Stint P2.5.2)
- Target-based window foregrounding fired reliably across background windows (`tauri window`, Notepad, File Explorer):
  > `[WINDOW FOCUS ACTIVATION] Target at (1246, 347) belongs to background window HWND 854066 ('tauri window'). Bringing to foreground.`
- Restored unminimized windows via `SW_RESTORE` and `SetForegroundWindow` without stealing focus from transient modal popups (`#32770`).

### C. Foveated Composite Decommissioning (Stint P2.5.1)
- Eliminating the synthetic Set-of-Marks (SoM) bounding box rendering loops yielded steady, clean 1080p full-screen inputs directly into UI-TARS vision.
- Resulted in pure visual grounding with 0 canned coordinates (Invariant D4).

---

## 3. Root Cause Analysis: `MAX_STEPS_EXHAUSTED` (0/20 Pass Rate)

Across all 20 benchmark tasks, the agent experienced **zero crashes**, **zero hardware interrupts**, and **zero false-DONE claims**. Every task terminated due to `MAX_STEPS_EXHAUSTED` (5 steps for Tier A/B, 8 steps for Tier C/D).

Key behavioral factors identified from `parasite_debug.log`:
1. **Search & Launch Latency Overhead:** When opening applications (Notepad, Calculator, File Explorer), UI-TARS consistently opens Start, clicks the search bar, types the app name, but often clicks the search result or taskbar multiple times instead of pressing `Enter` or double-clicking. By the time the target application appears and renders, 3 to 4 steps of the 5-step budget are already consumed.
2. **Step Budget Constraints in Benchmarks:**
   - 5 steps for Level 1 tasks (launch + initial action) is extremely tight for full visual CUA navigation when opening via Start/Search.
   - For multi-step tasks (e.g. `L1-04` Type Exact Token, `L1-08` Compute Multiplication), the agent reaches the app window but exhausts step 8 before verifying ground truth.
3. **Verifier Strictness & Absence of False Claims:**
   - The agent refused to hallucinate completion; whenever it did not reach definitive state, it did not claim `DONE`.
   - In P0, 4 tasks were falsely marked done by hallucinated text heuristics; with pure UI-TARS grounding, False-`DONE` is strictly **0.0%**.

---

## 4. Recommendations for Subsequent Stints / Stages

1. **Direct Launch Acceleration (`hotkey('win')` + `type(name)` + `hotkey('return')`):**
   - Teach UI-TARS / prompt parser or short-cut execution to press `Enter` immediately after typing application names into the Windows Start/Search bar, reducing app launch from 4 steps to 2 steps.
2. **Contextual Action Chaining:**
   - Allow compound CUA actions where appropriate (e.g., click search + type string in one atomic intent), preserving step budget for the core task objective.
3. **Dynamic Step Budget Scaling:**
   - Scale episode step budget according to task tier (e.g., Tier A/B from 5 -> 8 steps, Tier C/D from 8 -> 12 steps) to allow multi-window workflows to complete fully.
