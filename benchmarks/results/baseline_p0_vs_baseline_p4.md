# ParasiteAI Comparative Benchmark Scorecard: baseline_p0 vs baseline_p4
**Generated:** 2026-11-16 21:14:25  
**Baseline (`baseline_p0`):** 1 Tasks  
**Candidate (`baseline_p4`):** 20 Tasks  

## 1. Executive Summary & Key Metric Deltas
| Metric | Baseline (`baseline_p0`) | Candidate (`baseline_p4`) | Empirical Delta | Target Gate |
| :--- | :---: | :---: | :---: | :--- |
| **Overall Pass Rate** | 0.0% (0) | **90.0%** (18) | **+90.0%** (Improved) | Lift over P0 |
| **False-`DONE` Rate** | 0.0% (0) | **0.0%** (0) | 0.0% | <= 10.0% |
| **Median Step Latency** | 5.976s | **4.819s** | **-1.16s** (Improved) | <= 3.0s |
| **P90 Step Latency** | 6.596s | **8.584s** | +1.99s (Regressed) | <= 6.0s |
| **Mean Duration / Task** | 52.7s | **45.4s** | **-7.29s** (Improved) | Lower is better |
| **Hardware Interrupts** | 0 | **0** | 0 | 0 (No self-interruption) |

## 2. Difficulty Level Breakdown
| Level | Baseline Pass Rate | Candidate Pass Rate | Delta | Target |
| :--- | :---: | :---: | :---: | :--- |
| **L1** | 0.0% (0/1) | **100.0%** (10/10) | **+100.0%** (Improved) | >= 50% |
| **L2** | 0.0% (0/0) | **85.7%** (6/7) | **+85.7%** (Improved) | >= 25% |
| **L3** | 0.0% (0/0) | **66.7%** (2/3) | **+66.7%** (Improved) | Informational |

## 3. Task-by-Task Transition Matrix
| Task ID | Name | Level | Baseline Outcome | Candidate Outcome | Transition Verdict | Duration Delta |
| :--- | :--- | :---: | :--- | :--- | :--- | :--- |
| `L1-08` | Compute Multiplication in Calculator | L1 | ❌ MAX_STEPS_EXHAUSTED | ✅ PASS | 🟢 **NEW PASS** | -39.0s |
| `L1-01` | Launch Notepad | L1 | ❌ FAIL | ✅ PASS | 🟢 **NEW PASS** | +10.4s |
| `L1-02` | Launch Calculator | L1 | ❌ FAIL | ✅ PASS | 🟢 **NEW PASS** | +10.2s |
| `L1-03` | Launch Paint | L1 | ❌ FAIL | ✅ PASS | 🟢 **NEW PASS** | +10.0s |
| `L1-04` | Type Exact Token in Notepad | L1 | ❌ FAIL | ✅ PASS | 🟢 **NEW PASS** | +12.6s |
| `L1-05` | Compose Greeting in Notepad (No Goal Echo) | L1 | ❌ FAIL | ✅ PASS | 🟢 **NEW PASS** | +47.5s |
| `L1-06` | Close Pre-Opened Notepad | L1 | ❌ FAIL | ✅ PASS | 🟢 **NEW PASS** | +16.1s |
| `L1-07` | Minimize Pre-Opened Notepad | L1 | ❌ FAIL | ✅ PASS | 🟢 **NEW PASS** | +4.0s |
| `L1-09` | Launch File Explorer | L1 | ❌ FAIL | ✅ PASS | 🟢 **NEW PASS** | +12.1s |
| `L1-10` | Type and Copy Text to Clipboard in Notepad | L1 | ❌ FAIL | ✅ PASS | 🟢 **NEW PASS** | +9.5s |
| `L2-01` | Save Notepad Document to Workspace File | L2 | ❌ FAIL | ✅ PASS | 🟢 **NEW PASS** | +12.2s |
| `L2-02` | Open Seed File and Append Text | L2 | ❌ FAIL | ✅ PASS | 🟢 **NEW PASS** | +17.4s |
| `L2-03` | Cross-App Calculator Result to Notepad | L2 | ❌ FAIL | ✅ PASS | 🟢 **NEW PASS** | +26.7s |
| `L2-04` | Rename File in Workspace | L2 | ❌ FAIL | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +240.2s |
| `L2-05` | Create Directory in Workspace via File Explorer | L2 | ❌ FAIL | ✅ PASS | 🟢 **NEW PASS** | +19.9s |
| `L2-06` | Dismiss Modal Error Dialog and Open Notepad | L2 | ❌ FAIL | ✅ PASS | 🟢 **NEW PASS** | +25.1s |
| `L2-07` | Harvest Token from Open Notepad to Clipboard | L2 | ❌ FAIL | ✅ PASS | 🟢 **NEW PASS** | +28.3s |
| `L3-01` | Close Dirty Notepad and Choose Don't Save | L3 | ❌ FAIL | ✅ PASS | 🟢 **NEW PASS** | +30.1s |
| `L3-02` | Compute in Calculator, Format & Save in Notepad | L3 | ❌ FAIL | ✅ PASS | 🟢 **NEW PASS** | +101.1s |
| `L3-03` | Browser Navigation & Cross-App Note Recording | L3 | ❌ FAIL | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +260.1s |