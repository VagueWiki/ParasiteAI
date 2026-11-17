# ParasiteAI Comparative Benchmark Scorecard: baseline_p2 vs baseline_p2_5
**Generated:** 2026-11-10 01:31:50  
**Baseline (`baseline_p2`):** 20 Tasks  
**Candidate (`baseline_p2_5`):** 20 Tasks  

## 1. Executive Summary & Key Metric Deltas
| Metric | Baseline (`baseline_p2`) | Candidate (`baseline_p2_5`) | Empirical Delta | Target Gate |
| :--- | :---: | :---: | :---: | :--- |
| **Overall Pass Rate** | 5.0% (1) | **0.0%** (0) | -5.0% (Regressed) | Lift over P0 |
| **False-`DONE` Rate** | 0.0% (0) | **0.0%** (0) | 0.0% | <= 10.0% |
| **Median Step Latency** | 3.881s | **3.592s** | **-0.29s** (Improved) | <= 3.0s |
| **P90 Step Latency** | 5.242s | **4.361s** | **-0.88s** (Improved) | <= 6.0s |
| **Mean Duration / Task** | 32.3s | **29.3s** | **-3.04s** (Improved) | Lower is better |
| **Hardware Interrupts** | 2 | **0** | 0 | 0 (No self-interruption) |

## 2. Difficulty Level Breakdown
| Level | Baseline Pass Rate | Candidate Pass Rate | Delta | Target |
| :--- | :---: | :---: | :---: | :--- |
| **L1** | 10.0% (1/10) | **0.0%** (0/10) | -10.0% (Regressed) | >= 50% |
| **L2** | 0.0% (0/7) | **0.0%** (0/7) | 0.0% | >= 25% |
| **L3** | 0.0% (0/3) | **0.0%** (0/3) | 0.0% | Informational |

## 3. Task-by-Task Transition Matrix
| Task ID | Name | Level | Baseline Outcome | Candidate Outcome | Transition Verdict | Duration Delta |
| :--- | :--- | :---: | :--- | :--- | :--- | :--- |
| `L1-01` | Launch Notepad | L1 | ✅ PASS | ❌ MAX_STEPS_EXHAUSTED | 🔴 **REGRESSION** | +1.8s |
| `L1-02` | Launch Calculator | L1 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | -1.3s |
| `L1-03` | Launch Paint | L1 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | -0.7s |
| `L1-04` | Type Exact Token in Notepad | L1 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +1.6s |
| `L1-05` | Compose Greeting in Notepad (No Goal Echo) | L1 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +0.4s |
| `L1-06` | Close Pre-Opened Notepad | L1 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | -3.4s |
| `L1-07` | Minimize Pre-Opened Notepad | L1 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | -3.1s |
| `L1-08` | Compute Multiplication in Calculator | L1 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | -5.0s |
| `L1-09` | Launch File Explorer | L1 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +2.3s |
| `L1-10` | Type and Copy Text to Clipboard in Notepad | L1 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +1.0s |
| `L2-01` | Save Notepad Document to Workspace File | L2 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | -3.8s |
| `L2-02` | Open Seed File and Append Text | L2 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | -3.3s |
| `L2-03` | Cross-App Calculator Result to Notepad | L2 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | -7.3s |
| `L2-04` | Rename File in Workspace | L2 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +3.8s |
| `L2-05` | Create Directory in Workspace via File Explorer | L2 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +0.5s |
| `L2-06` | Dismiss Modal Error Dialog and Open Notepad | L2 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | -18.2s |
| `L2-07` | Harvest Token from Open Notepad to Clipboard | L2 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | -3.8s |
| `L3-01` | Close Dirty Notepad and Choose Don't Save | L3 | ❌ HARDWARE_PREEMPTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | -5.1s |
| `L3-02` | Compute in Calculator, Format & Save in Notepad | L3 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | -15.2s |
| `L3-03` | Browser Navigation & Cross-App Note Recording | L3 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | -1.8s |