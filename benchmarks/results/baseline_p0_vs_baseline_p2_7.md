# ParasiteAI Comparative Benchmark Scorecard: baseline_p0 vs baseline_p2_7
**Generated:** 2026-11-11 19:46:24  
**Baseline (`baseline_p0`):** 1 Tasks  
**Candidate (`baseline_p2_7`):** 20 Tasks  

## 1. Executive Summary & Key Metric Deltas
| Metric | Baseline (`baseline_p0`) | Candidate (`baseline_p2_7`) | Empirical Delta | Target Gate |
| :--- | :---: | :---: | :---: | :--- |
| **Overall Pass Rate** | 100.0% (1) | **20.0%** (4) | -80.0% (Regressed) | Lift over P0 |
| **False-`DONE` Rate** | 0.0% (0) | **0.0%** (0) | 0.0% | <= 10.0% |
| **Median Step Latency** | 5.902s | **8.686s** | +2.78s (Regressed) | <= 3.0s |
| **P90 Step Latency** | 5.965s | **9.360s** | +3.39s (Regressed) | <= 6.0s |
| **Mean Duration / Task** | 18.5s | **60.3s** | +41.80s (Regressed) | Lower is better |
| **Hardware Interrupts** | 0 | **0** | 0 | 0 (No self-interruption) |

## 2. Difficulty Level Breakdown
| Level | Baseline Pass Rate | Candidate Pass Rate | Delta | Target |
| :--- | :---: | :---: | :---: | :--- |
| **L1** | 100.0% (1/1) | **30.0%** (3/10) | -70.0% (Regressed) | >= 50% |
| **L2** | 0.0% (0/0) | **0.0%** (0/7) | 0.0% | >= 25% |
| **L3** | 0.0% (0/0) | **33.3%** (1/3) | **+33.3%** (Improved) | Informational |

## 3. Task-by-Task Transition Matrix
| Task ID | Name | Level | Baseline Outcome | Candidate Outcome | Transition Verdict | Duration Delta |
| :--- | :--- | :---: | :--- | :--- | :--- | :--- |
| `L1-06` | Close Pre-Opened Notepad | L1 | ✅ PASS | ✅ PASS | ✅ MAINTAINED PASS | +26.5s |
| `L1-01` | Launch Notepad | L1 | ❌ FAIL | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +45.0s |
| `L1-02` | Launch Calculator | L1 | ❌ FAIL | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +45.0s |
| `L1-03` | Launch Paint | L1 | ❌ FAIL | ✅ PASS | 🟢 **NEW PASS** | +37.1s |
| `L1-04` | Type Exact Token in Notepad | L1 | ❌ FAIL | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +60.0s |
| `L1-05` | Compose Greeting in Notepad (No Goal Echo) | L1 | ❌ FAIL | ✅ PASS | 🟢 **NEW PASS** | +60.1s |
| `L1-07` | Minimize Pre-Opened Notepad | L1 | ❌ FAIL | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +45.0s |
| `L1-08` | Compute Multiplication in Calculator | L1 | ❌ FAIL | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +60.0s |
| `L1-09` | Launch File Explorer | L1 | ❌ FAIL | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +45.0s |
| `L1-10` | Type and Copy Text to Clipboard in Notepad | L1 | ❌ FAIL | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +60.1s |
| `L2-01` | Save Notepad Document to Workspace File | L2 | ❌ FAIL | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +75.0s |
| `L2-02` | Open Seed File and Append Text | L2 | ❌ FAIL | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +75.0s |
| `L2-03` | Cross-App Calculator Result to Notepad | L2 | ❌ FAIL | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +75.0s |
| `L2-04` | Rename File in Workspace | L2 | ❌ FAIL | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +75.3s |
| `L2-05` | Create Directory in Workspace via File Explorer | L2 | ❌ FAIL | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +75.1s |
| `L2-06` | Dismiss Modal Error Dialog and Open Notepad | L2 | ❌ FAIL | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +60.0s |
| `L2-07` | Harvest Token from Open Notepad to Clipboard | L2 | ❌ FAIL | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +60.1s |
| `L3-01` | Close Dirty Notepad and Choose Don't Save | L3 | ❌ FAIL | ✅ PASS | 🟢 **NEW PASS** | +60.1s |
| `L3-02` | Compute in Calculator, Format & Save in Notepad | L3 | ❌ FAIL | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +72.0s |
| `L3-03` | Browser Navigation & Cross-App Note Recording | L3 | ❌ FAIL | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +75.8s |