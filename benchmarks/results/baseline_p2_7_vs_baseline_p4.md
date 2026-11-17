# ParasiteAI Comparative Benchmark Scorecard: baseline_p2_7 vs baseline_p4
**Generated:** 2026-11-16 21:14:24  
**Baseline (`baseline_p2_7`):** 20 Tasks  
**Candidate (`baseline_p4`):** 20 Tasks  

## 1. Executive Summary & Key Metric Deltas
| Metric | Baseline (`baseline_p2_7`) | Candidate (`baseline_p4`) | Empirical Delta | Target Gate |
| :--- | :---: | :---: | :---: | :--- |
| **Overall Pass Rate** | 20.0% (4) | **90.0%** (18) | **+70.0%** (Improved) | Lift over P0 |
| **False-`DONE` Rate** | 0.0% (0) | **0.0%** (0) | 0.0% | <= 10.0% |
| **Median Step Latency** | 8.686s | **4.819s** | **-3.87s** (Improved) | <= 3.0s |
| **P90 Step Latency** | 9.360s | **8.584s** | **-0.78s** (Improved) | <= 6.0s |
| **Mean Duration / Task** | 60.3s | **45.4s** | **-14.92s** (Improved) | Lower is better |
| **Hardware Interrupts** | 0 | **0** | 0 | 0 (No self-interruption) |

## 2. Difficulty Level Breakdown
| Level | Baseline Pass Rate | Candidate Pass Rate | Delta | Target |
| :--- | :---: | :---: | :---: | :--- |
| **L1** | 30.0% (3/10) | **100.0%** (10/10) | **+70.0%** (Improved) | >= 50% |
| **L2** | 0.0% (0/7) | **85.7%** (6/7) | **+85.7%** (Improved) | >= 25% |
| **L3** | 33.3% (1/3) | **66.7%** (2/3) | **+33.4%** (Improved) | Informational |

## 3. Task-by-Task Transition Matrix
| Task ID | Name | Level | Baseline Outcome | Candidate Outcome | Transition Verdict | Duration Delta |
| :--- | :--- | :---: | :--- | :--- | :--- | :--- |
| `L1-01` | Launch Notepad | L1 | ❌ MAX_STEPS_EXHAUSTED | ✅ PASS | 🟢 **NEW PASS** | -34.6s |
| `L1-02` | Launch Calculator | L1 | ❌ MAX_STEPS_EXHAUSTED | ✅ PASS | 🟢 **NEW PASS** | -34.8s |
| `L1-03` | Launch Paint | L1 | ✅ PASS | ✅ PASS | ✅ MAINTAINED PASS | -27.0s |
| `L1-04` | Type Exact Token in Notepad | L1 | ❌ MAX_STEPS_EXHAUSTED | ✅ PASS | 🟢 **NEW PASS** | -47.4s |
| `L1-05` | Compose Greeting in Notepad (No Goal Echo) | L1 | ✅ PASS | ✅ PASS | ✅ MAINTAINED PASS | -12.5s |
| `L1-06` | Close Pre-Opened Notepad | L1 | ✅ PASS | ✅ PASS | ✅ MAINTAINED PASS | -29.0s |
| `L1-07` | Minimize Pre-Opened Notepad | L1 | ❌ MAX_STEPS_EXHAUSTED | ✅ PASS | 🟢 **NEW PASS** | -41.0s |
| `L1-08` | Compute Multiplication in Calculator | L1 | ❌ MAX_STEPS_EXHAUSTED | ✅ PASS | 🟢 **NEW PASS** | -46.4s |
| `L1-09` | Launch File Explorer | L1 | ❌ MAX_STEPS_EXHAUSTED | ✅ PASS | 🟢 **NEW PASS** | -33.0s |
| `L1-10` | Type and Copy Text to Clipboard in Notepad | L1 | ❌ MAX_STEPS_EXHAUSTED | ✅ PASS | 🟢 **NEW PASS** | -50.6s |
| `L2-01` | Save Notepad Document to Workspace File | L2 | ❌ MAX_STEPS_EXHAUSTED | ✅ PASS | 🟢 **NEW PASS** | -62.8s |
| `L2-02` | Open Seed File and Append Text | L2 | ❌ MAX_STEPS_EXHAUSTED | ✅ PASS | 🟢 **NEW PASS** | -57.6s |
| `L2-03` | Cross-App Calculator Result to Notepad | L2 | ❌ MAX_STEPS_EXHAUSTED | ✅ PASS | 🟢 **NEW PASS** | -48.3s |
| `L2-04` | Rename File in Workspace | L2 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +164.9s |
| `L2-05` | Create Directory in Workspace via File Explorer | L2 | ❌ MAX_STEPS_EXHAUSTED | ✅ PASS | 🟢 **NEW PASS** | -55.2s |
| `L2-06` | Dismiss Modal Error Dialog and Open Notepad | L2 | ❌ MAX_STEPS_EXHAUSTED | ✅ PASS | 🟢 **NEW PASS** | -35.0s |
| `L2-07` | Harvest Token from Open Notepad to Clipboard | L2 | ❌ MAX_STEPS_EXHAUSTED | ✅ PASS | 🟢 **NEW PASS** | -31.8s |
| `L3-01` | Close Dirty Notepad and Choose Don't Save | L3 | ✅ PASS | ✅ PASS | ✅ MAINTAINED PASS | -30.0s |
| `L3-02` | Compute in Calculator, Format & Save in Notepad | L3 | ❌ MAX_STEPS_EXHAUSTED | ✅ PASS | 🟢 **NEW PASS** | +29.1s |
| `L3-03` | Browser Navigation & Cross-App Note Recording | L3 | ❌ MAX_STEPS_EXHAUSTED | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +184.4s |