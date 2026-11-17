# ParasiteAI Comparative Benchmark Scorecard: baseline_p0 vs baseline_p3
**Generated:** 2026-11-11 23:52:00  
**Baseline (`baseline_p0`):** 1 Tasks  
**Candidate (`baseline_p3`):** 20 Tasks  

## 1. Executive Summary & Key Metric Deltas
| Metric | Baseline (`baseline_p0`) | Candidate (`baseline_p3`) | Empirical Delta | Target Gate |
| :--- | :---: | :---: | :---: | :--- |
| **Overall Pass Rate** | 100.0% (1) | **35.0%** (7) | -65.0% (Regressed) | Lift over P0 |
| **False-`DONE` Rate** | 0.0% (0) | **5.0%** (1) | +5.0% (Regressed) | <= 10.0% |
| **Median Step Latency** | 5.902s | **6.034s** | +0.13s (Regressed) | <= 3.0s |
| **P90 Step Latency** | 5.965s | **6.763s** | +0.80s (Regressed) | <= 6.0s |
| **Mean Duration / Task** | 18.5s | **45.6s** | +27.16s (Regressed) | Lower is better |
| **Hardware Interrupts** | 0 | **0** | 0 | 0 (No self-interruption) |

## 2. Difficulty Level Breakdown
| Level | Baseline Pass Rate | Candidate Pass Rate | Delta | Target |
| :--- | :---: | :---: | :---: | :--- |
| **L1** | 100.0% (1/1) | **50.0%** (5/10) | -50.0% (Regressed) | >= 50% |
| **L2** | 0.0% (0/0) | **14.3%** (1/7) | **+14.3%** (Improved) | >= 25% |
| **L3** | 0.0% (0/0) | **33.3%** (1/3) | **+33.3%** (Improved) | Informational |

## 3. Task-by-Task Transition Matrix
| Task ID | Name | Level | Baseline Outcome | Candidate Outcome | Transition Verdict | Duration Delta |
| :--- | :--- | :---: | :--- | :--- | :--- | :--- |
| `L1-06` | Close Pre-Opened Notepad | L1 | ✅ PASS | ✅ PASS | ✅ MAINTAINED PASS | +13.9s |
| `L1-01` | Launch Notepad | L1 | ❌ FAIL | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +37.7s |
| `L1-02` | Launch Calculator | L1 | ❌ FAIL | ✅ PASS | 🟢 **NEW PASS** | +29.4s |
| `L1-03` | Launch Paint | L1 | ❌ FAIL | ✅ PASS | 🟢 **NEW PASS** | +31.5s |
| `L1-04` | Type Exact Token in Notepad | L1 | ❌ FAIL | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +58.7s |
| `L1-05` | Compose Greeting in Notepad (No Goal Echo) | L1 | ❌ FAIL | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +57.0s |
| `L1-07` | Minimize Pre-Opened Notepad | L1 | ❌ FAIL | ✅ PASS | 🟢 **NEW PASS** | +34.1s |
| `L1-08` | Compute Multiplication in Calculator | L1 | ❌ FAIL | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +51.2s |
| `L1-09` | Launch File Explorer | L1 | ❌ FAIL | ✅ PASS | 🟢 **NEW PASS** | +32.8s |
| `L1-10` | Type and Copy Text to Clipboard in Notepad | L1 | ❌ FAIL | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +49.7s |
| `L2-01` | Save Notepad Document to Workspace File | L2 | ❌ FAIL | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +50.5s |
| `L2-02` | Open Seed File and Append Text | L2 | ❌ FAIL | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +48.5s |
| `L2-03` | Cross-App Calculator Result to Notepad | L2 | ❌ FAIL | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +50.2s |
| `L2-04` | Rename File in Workspace | L2 | ❌ FAIL | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +50.7s |
| `L2-05` | Create Directory in Workspace via File Explorer | L2 | ❌ FAIL | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +51.2s |
| `L2-06` | Dismiss Modal Error Dialog and Open Notepad | L2 | ❌ FAIL | ❌ FALSE_DONE | ⚪ UNRESOLVED | +38.6s |
| `L2-07` | Harvest Token from Open Notepad to Clipboard | L2 | ❌ FAIL | ✅ PASS | 🟢 **NEW PASS** | +48.2s |
| `L3-01` | Close Dirty Notepad and Choose Don't Save | L3 | ❌ FAIL | ✅ PASS | 🟢 **NEW PASS** | +53.7s |
| `L3-02` | Compute in Calculator, Format & Save in Notepad | L3 | ❌ FAIL | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +50.6s |
| `L3-03` | Browser Navigation & Cross-App Note Recording | L3 | ❌ FAIL | ❌ MAX_STEPS_EXHAUSTED | ⚪ UNRESOLVED | +56.3s |