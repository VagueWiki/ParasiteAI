# ParasiteAI Comparative Benchmark Scorecard: baseline_p3 vs baseline_p4
**Generated:** 2026-11-16 21:14:24  
**Baseline (`baseline_p3`):** 20 Tasks  
**Candidate (`baseline_p4`):** 20 Tasks  

## 1. Executive Summary & Key Metric Deltas
| Metric | Baseline (`baseline_p3`) | Candidate (`baseline_p4`) | Empirical Delta | Target Gate |
| :--- | :---: | :---: | :---: | :--- |
| **Overall Pass Rate** | 35.0% (7) | **90.0%** (18) | **+55.0%** (Improved) | Lift over P0 |
| **False-`DONE` Rate** | 5.0% (1) | **0.0%** (0) | **-5.0%** (Improved) | <= 10.0% |
| **Median Step Latency** | 6.034s | **4.819s** | **-1.21s** (Improved) | <= 3.0s |
| **P90 Step Latency** | 6.763s | **8.584s** | +1.82s (Regressed) | <= 6.0s |
| **Mean Duration / Task** | 45.6s | **45.4s** | **-0.28s** (Improved) | Lower is better |
| **Hardware Interrupts** | 0 | **0** | 0 | 0 (No self-interruption) |

## 2. Difficulty Level Breakdown
| Level | Baseline Pass Rate | Candidate Pass Rate | Delta | Target |
| :--- | :---: | :---: | :---: | :--- |
| **L1** | 50.0% (5/10) | **100.0%** (10/10) | **+50.0%** (Improved) | >= 50% |
| **L2** | 14.3% (1/7) | **85.7%** (6/7) | **+71.4%** (Improved) | >= 25% |
| **L3** | 33.3% (1/3) | **66.7%** (2/3) | **+33.4%** (Improved) | Informational |

## 3. Task-by-Task Transition Matrix
| Task ID | Name | Level | Baseline Outcome | Candidate Outcome | Transition Verdict | Duration Delta |
| :--- | :--- | :---: | :--- | :--- | :--- | :--- |
| `L1-01` | Launch Notepad | L1 | ❌ MAX_STEPS_EXHAUSTED | ✅ PASS | 🟢 **NEW PASS** | -27.3s |
| `L1-02` | Launch Calculator | L1 | ✅ PASS | ✅ PASS | ✅ MAINTAINED PASS | -19.2s |
| `L1-03` | Launch Paint | L1 | ✅ PASS | ✅ PASS | ✅ MAINTAINED PASS | -21.4s |
| `L1-04` | Type Exact Token in Notepad | L1 | ❌ MAX_STEPS_EXHAUSTED | ✅ PASS | 🟢 **NEW PASS** | -46.0s |
| `L1-05` | Compose Greeting in Notepad (No Goal Echo) | L1 | ❌ MAX_STEPS_EXHAUSTED | ✅ PASS | 🟢 **NEW PASS** | -9.4s |
| `L1-06` | Close Pre-Opened Notepad | L1 | ✅ PASS | ✅ PASS | ✅ MAINTAINED PASS | -16.3s |
| `L1-07` | Minimize Pre-Opened Notepad | L1 | ✅ PASS | ✅ PASS | ✅ MAINTAINED PASS | -30.1s |
| `L1-08` | Compute Multiplication in Calculator | L1 | ❌ MAX_STEPS_EXHAUSTED | ✅ PASS | 🟢 **NEW PASS** | -37.6s |
| `L1-09` | Launch File Explorer | L1 | ✅ PASS | ✅ PASS | ✅ MAINTAINED PASS | -20.8s |
| `L1-10` | Type and Copy Text to Clipboard in Notepad | L1 | ❌ MAX_STEPS_EXHAUSTED | ✅ PASS | 🟢 **NEW PASS** | -40.2s |
| `L2-01` | Save Notepad Document to Workspace File | L2 | ❌ MAX_STEPS_EXHAUSTED | ✅ PASS | 🟢 **NEW PASS** | -38.3s |
| `L2-02` | Open Seed File and Append Text | L2 | ❌ MAX_STEPS_EXHAUSTED | ✅ PASS | 🟢 **NEW PASS** | -31.1s |
| `L2-03` | Cross-App Calculator Result to Notepad | L2 | ❌ MAX_STEPS_EXHAUSTED | ✅ PASS | 🟢 **NEW PASS** | -23.5s |
| `L2-04` | Rename File in Workspace | L2 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +189.5s |
| `L2-05` | Create Directory in Workspace via File Explorer | L2 | ❌ MAX_STEPS_EXHAUSTED | ✅ PASS | 🟢 **NEW PASS** | -31.3s |
| `L2-06` | Dismiss Modal Error Dialog and Open Notepad | L2 | ❌ FALSE_DONE | ✅ PASS | 🟢 **NEW PASS** | -13.6s |
| `L2-07` | Harvest Token from Open Notepad to Clipboard | L2 | ✅ PASS | ✅ PASS | ✅ MAINTAINED PASS | -19.9s |
| `L3-01` | Close Dirty Notepad and Choose Don't Save | L3 | ✅ PASS | ✅ PASS | ✅ MAINTAINED PASS | -23.6s |
| `L3-02` | Compute in Calculator, Format & Save in Notepad | L3 | ❌ MAX_STEPS_EXHAUSTED | ✅ PASS | 🟢 **NEW PASS** | +50.6s |
| `L3-03` | Browser Navigation & Cross-App Note Recording | L3 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +203.8s |