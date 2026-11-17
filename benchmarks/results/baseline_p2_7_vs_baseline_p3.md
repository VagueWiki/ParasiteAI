# ParasiteAI Comparative Benchmark Scorecard: baseline_p2_7 vs baseline_p3
**Generated:** 2026-11-11 23:52:00  
**Baseline (`baseline_p2_7`):** 20 Tasks  
**Candidate (`baseline_p3`):** 20 Tasks  

## 1. Executive Summary & Key Metric Deltas
| Metric | Baseline (`baseline_p2_7`) | Candidate (`baseline_p3`) | Empirical Delta | Target Gate |
| :--- | :---: | :---: | :---: | :--- |
| **Overall Pass Rate** | 20.0% (4) | **35.0%** (7) | **+15.0%** (Improved) | Lift over P0 |
| **False-`DONE` Rate** | 0.0% (0) | **5.0%** (1) | +5.0% (Regressed) | <= 10.0% |
| **Median Step Latency** | 8.686s | **6.034s** | **-2.65s** (Improved) | <= 3.0s |
| **P90 Step Latency** | 9.360s | **6.763s** | **-2.60s** (Improved) | <= 6.0s |
| **Mean Duration / Task** | 60.3s | **45.6s** | **-14.64s** (Improved) | Lower is better |
| **Hardware Interrupts** | 0 | **0** | 0 | 0 (No self-interruption) |

## 2. Difficulty Level Breakdown
| Level | Baseline Pass Rate | Candidate Pass Rate | Delta | Target |
| :--- | :---: | :---: | :---: | :--- |
| **L1** | 30.0% (3/10) | **50.0%** (5/10) | **+20.0%** (Improved) | >= 50% |
| **L2** | 0.0% (0/7) | **14.3%** (1/7) | **+14.3%** (Improved) | >= 25% |
| **L3** | 33.3% (1/3) | **33.3%** (1/3) | 0.0% | Informational |

## 3. Task-by-Task Transition Matrix
| Task ID | Name | Level | Baseline Outcome | Candidate Outcome | Transition Verdict | Duration Delta |
| :--- | :--- | :---: | :--- | :--- | :--- | :--- |
| `L1-01` | Launch Notepad | L1 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | -7.3s |
| `L1-02` | Launch Calculator | L1 | ❌ MAX_STEPS_EXHAUSTED | ✅ PASS | 🟢 **NEW PASS** | -15.6s |
| `L1-03` | Launch Paint | L1 | ✅ PASS | ✅ PASS | ✅ MAINTAINED PASS | -5.6s |
| `L1-04` | Type Exact Token in Notepad | L1 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | -1.4s |
| `L1-05` | Compose Greeting in Notepad (No Goal Echo) | L1 | ✅ PASS | ❌ MAX_STEPS_EXHAUSTED | 🔴 **REGRESSION** | -3.1s |
| `L1-06` | Close Pre-Opened Notepad | L1 | ✅ PASS | ✅ PASS | ✅ MAINTAINED PASS | -12.6s |
| `L1-07` | Minimize Pre-Opened Notepad | L1 | ❌ MAX_STEPS_EXHAUSTED | ✅ PASS | 🟢 **NEW PASS** | -10.9s |
| `L1-08` | Compute Multiplication in Calculator | L1 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | -8.8s |
| `L1-09` | Launch File Explorer | L1 | ❌ MAX_STEPS_EXHAUSTED | ✅ PASS | 🟢 **NEW PASS** | -12.2s |
| `L1-10` | Type and Copy Text to Clipboard in Notepad | L1 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | -10.3s |
| `L2-01` | Save Notepad Document to Workspace File | L2 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | -24.5s |
| `L2-02` | Open Seed File and Append Text | L2 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | -26.5s |
| `L2-03` | Cross-App Calculator Result to Notepad | L2 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | -24.9s |
| `L2-04` | Rename File in Workspace | L2 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | -24.6s |
| `L2-05` | Create Directory in Workspace via File Explorer | L2 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | -23.9s |
| `L2-06` | Dismiss Modal Error Dialog and Open Notepad | L2 | ❌ MAX_STEPS_EXHAUSTED | ❌ FALSE_DONE | ⚪ UNRESOLVED | -21.4s |
| `L2-07` | Harvest Token from Open Notepad to Clipboard | L2 | ❌ MAX_STEPS_EXHAUSTED | ✅ PASS | 🟢 **NEW PASS** | -11.8s |
| `L3-01` | Close Dirty Notepad and Choose Don't Save | L3 | ✅ PASS | ✅ PASS | ✅ MAINTAINED PASS | -6.4s |
| `L3-02` | Compute in Calculator, Format & Save in Notepad | L3 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | -21.5s |
| `L3-03` | Browser Navigation & Cross-App Note Recording | L3 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | -19.5s |