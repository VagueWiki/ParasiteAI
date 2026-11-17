# ParasiteAI Comparative Benchmark Scorecard: baseline_p1 vs baseline_p2
**Generated:** 2026-11-08 23:26:32  
**Baseline (`baseline_p1`):** 20 Tasks  
**Candidate (`baseline_p2`):** 20 Tasks  

## 1. Executive Summary & Key Metric Deltas
| Metric | Baseline (`baseline_p1`) | Candidate (`baseline_p2`) | Empirical Delta | Target Gate |
| :--- | :---: | :---: | :---: | :--- |
| **Overall Pass Rate** | 0.0% (0) | **5.0%** (1) | **+5.0%** (Improved) | Lift over P0 |
| **False-`DONE` Rate** | 5.0% (1) | **0.0%** (0) | **-5.0%** (Improved) | <= 10.0% |
| **Median Step Latency** | 4.741s | **3.881s** | **-0.86s** (Improved) | <= 3.0s |
| **P90 Step Latency** | 5.635s | **5.242s** | **-0.39s** (Improved) | <= 6.0s |
| **Mean Duration / Task** | 46.2s | **32.3s** | **-13.82s** (Improved) | Lower is better |
| **Hardware Interrupts** | 0 | **2** | 0 | 0 (No self-interruption) |

## 2. Difficulty Level Breakdown
| Level | Baseline Pass Rate | Candidate Pass Rate | Delta | Target |
| :--- | :---: | :---: | :---: | :--- |
| **L1** | 0.0% (0/10) | **10.0%** (1/10) | **+10.0%** (Improved) | >= 50% |
| **L2** | 0.0% (0/7) | **0.0%** (0/7) | 0.0% | >= 25% |
| **L3** | 0.0% (0/3) | **0.0%** (0/3) | 0.0% | Informational |

## 3. Task-by-Task Transition Matrix
| Task ID | Name | Level | Baseline Outcome | Candidate Outcome | Transition Verdict | Duration Delta |
| :--- | :--- | :---: | :--- | :--- | :--- | :--- |
| `L1-01` | Launch Notepad | L1 | ❌ MAX_STEPS_EXHAUSTED | ✅ PASS | 🟢 **NEW PASS** | -26.1s |
| `L1-02` | Launch Calculator | L1 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | -23.7s |
| `L1-03` | Launch Paint | L1 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | -21.7s |
| `L1-04` | Type Exact Token in Notepad | L1 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | -27.1s |
| `L1-05` | Compose Greeting in Notepad (No Goal Echo) | L1 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +5.4s |
| `L1-06` | Close Pre-Opened Notepad | L1 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | -20.5s |
| `L1-07` | Minimize Pre-Opened Notepad | L1 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | -21.0s |
| `L1-08` | Compute Multiplication in Calculator | L1 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | -21.7s |
| `L1-09` | Launch File Explorer | L1 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | -24.3s |
| `L1-10` | Type and Copy Text to Clipboard in Notepad | L1 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | -29.3s |
| `L2-01` | Save Notepad Document to Workspace File | L2 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | -31.4s |
| `L2-02` | Open Seed File and Append Text | L2 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +12.4s |
| `L2-03` | Cross-App Calculator Result to Notepad | L2 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +12.2s |
| `L2-04` | Rename File in Workspace | L2 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +6.3s |
| `L2-05` | Create Directory in Workspace via File Explorer | L2 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | -32.4s |
| `L2-06` | Dismiss Modal Error Dialog and Open Notepad | L2 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | -15.6s |
| `L2-07` | Harvest Token from Open Notepad to Clipboard | L2 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | -25.8s |
| `L3-01` | Close Dirty Notepad and Choose Don't Save | L3 | ❌ MAX_STEPS_EXHAUSTED | ❌ HARDWARE_PREEMPTED | ⚪ UNRESOLVED | -24.8s |
| `L3-02` | Compute in Calculator, Format & Save in Notepad | L3 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +24.5s |
| `L3-03` | Browser Navigation & Cross-App Note Recording | L3 | ❌ FALSE_DONE | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +8.2s |