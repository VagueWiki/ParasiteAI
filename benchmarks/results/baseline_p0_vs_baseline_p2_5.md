# ParasiteAI Comparative Benchmark Scorecard: baseline_p0 vs baseline_p2_5
**Generated:** 2026-11-10 01:31:51  
**Baseline (`baseline_p0`):** 20 Tasks  
**Candidate (`baseline_p2_5`):** 20 Tasks  

## 1. Executive Summary & Key Metric Deltas
| Metric | Baseline (`baseline_p0`) | Candidate (`baseline_p2_5`) | Empirical Delta | Target Gate |
| :--- | :---: | :---: | :---: | :--- |
| **Overall Pass Rate** | 5.0% (1) | **0.0%** (0) | -5.0% (Regressed) | Lift over P0 |
| **False-`DONE` Rate** | 20.0% (4) | **0.0%** (0) | **-20.0%** (Improved) | <= 10.0% |
| **Median Step Latency** | 5.986s | **3.592s** | **-2.39s** (Improved) | <= 3.0s |
| **P90 Step Latency** | 9.798s | **4.361s** | **-5.44s** (Improved) | <= 6.0s |
| **Mean Duration / Task** | 39.3s | **29.3s** | **-9.97s** (Improved) | Lower is better |
| **Hardware Interrupts** | 0 | **0** | 0 | 0 (No self-interruption) |

## 2. Difficulty Level Breakdown
| Level | Baseline Pass Rate | Candidate Pass Rate | Delta | Target |
| :--- | :---: | :---: | :---: | :--- |
| **L1** | 10.0% (1/10) | **0.0%** (0/10) | -10.0% (Regressed) | >= 50% |
| **L2** | 0.0% (0/7) | **0.0%** (0/7) | 0.0% | >= 25% |
| **L3** | 0.0% (0/3) | **0.0%** (0/3) | 0.0% | Informational |

## 3. Task-by-Task Transition Matrix
| Task ID | Name | Level | Baseline Outcome | Candidate Outcome | Transition Verdict | Duration Delta |
| :--- | :--- | :---: | :--- | :--- | :--- | :--- |
| `L1-01` | Launch Notepad | L1 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | -24.5s |
| `L1-02` | Launch Calculator | L1 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | -25.1s |
| `L1-03` | Launch Paint | L1 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | -16.2s |
| `L1-04` | Type Exact Token in Notepad | L1 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +2.7s |
| `L1-05` | Compose Greeting in Notepad (No Goal Echo) | L1 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | -28.0s |
| `L1-06` | Close Pre-Opened Notepad | L1 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | -24.1s |
| `L1-07` | Minimize Pre-Opened Notepad | L1 | ✅ PASS | ❌ MAX_STEPS_EXHAUSTED | 🔴 **REGRESSION** | +5.0s |
| `L1-08` | Compute Multiplication in Calculator | L1 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | -3.7s |
| `L1-09` | Launch File Explorer | L1 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | -14.0s |
| `L1-10` | Type and Copy Text to Clipboard in Notepad | L1 | ❌ UNKNOWN_FAILURE | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +12.6s |
| `L2-01` | Save Notepad Document to Workspace File | L2 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +4.0s |
| `L2-02` | Open Seed File and Append Text | L2 | ❌ FALSE_DONE | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +9.3s |
| `L2-03` | Cross-App Calculator Result to Notepad | L2 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +5.2s |
| `L2-04` | Rename File in Workspace | L2 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | -4.1s |
| `L2-05` | Create Directory in Workspace via File Explorer | L2 | ❌ FALSE_DONE | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | -8.3s |
| `L2-06` | Dismiss Modal Error Dialog and Open Notepad | L2 | ❌ FALSE_DONE | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | -20.1s |
| `L2-07` | Harvest Token from Open Notepad to Clipboard | L2 | ❌ FALSE_DONE | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | -6.5s |
| `L3-01` | Close Dirty Notepad and Choose Don't Save | L3 | ❌ UNKNOWN_FAILURE | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +9.5s |
| `L3-02` | Compute in Calculator, Format & Save in Notepad | L3 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | -15.4s |
| `L3-03` | Browser Navigation & Cross-App Note Recording | L3 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | -57.5s |