# ParasiteAI Benchmark Report (baseline_p2_7)
**Date:** 2026-11-11 19:46:21  
**Host Environment:** Windows 10 / NVIDIA GeForce RTX 4060 (8188 MB VRAM, Driver 610.74)  
**Total Tasks:** 20  
**Ground-Truth Pass Rate:** **20.0%** (4/20)  
**Claimed DONE Rate:** 5.0%  
**False DONE Rate:** 0.0% (0 occurrences)  
**Mean Steps:** 1.0 | **Mean Duration:** 60.29s  
**Median Step Latency:** 8.686s | **P90 Step Latency:** 9.36s  
**Hardware Interrupts:** 0  

## Performance by Difficulty Level
| Level | Passed / Total | Pass Rate | Gate Target |
| :--- | :--- | :--- | :--- |
| **L1** | 3 / 10 | **30.0%** | >= 70% |
| **L2** | 0 / 7 | **0.0%** | >= 40% |
| **L3** | 1 / 3 | **33.3%** | Informational |

## Failure Mode Taxonomy
| Failure Category | Occurrences | Description |
| :--- | :---: | :--- |
| `MAX_STEPS_EXHAUSTED` | 16 | Cognitive step budget exhausted before goal completion. |
| `PASS` | 4 | Task verified successfully by objective OS verifier. |

## Detailed Task Scorecard
| Task ID | Name | Tier | Lvl | Verifier | Agent | Outcome Mode | Steps | Duration | Exit Reason |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `L1-01` | Launch Notepad | Tier_A | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 0 | 45.026s | `TIMEOUT` |
| `L1-02` | Launch Calculator | Tier_A | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 0 | 45.025s | `TIMEOUT` |
| `L1-03` | Launch Paint | Tier_A | L1 | ✅ PASS | DONE | `PASS` | 4 | 37.091s | `DONE` |
| `L1-04` | Type Exact Token in Notepad | Tier_B | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 0 | 60.024s | `TIMEOUT` |
| `L1-05` | Compose Greeting in Notepad (No Goal Echo) | Tier_B | L1 | ✅ PASS | FAIL | `PASS` | 0 | 60.056s | `TIMEOUT` |
| `L1-06` | Close Pre-Opened Notepad | Tier_B | L1 | ✅ PASS | FAIL | `PASS` | 0 | 45.022s | `TIMEOUT` |
| `L1-07` | Minimize Pre-Opened Notepad | Tier_B | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 0 | 45.022s | `TIMEOUT` |
| `L1-08` | Compute Multiplication in Calculator | Tier_B | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 0 | 60.027s | `TIMEOUT` |
| `L1-09` | Launch File Explorer | Tier_A | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 0 | 45.037s | `TIMEOUT` |
| `L1-10` | Type and Copy Text to Clipboard in Notepad | Tier_B | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 0 | 60.064s | `TIMEOUT` |
| `L2-01` | Save Notepad Document to Workspace File | Tier_C | L2 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 0 | 75.026s | `TIMEOUT` |
| `L2-02` | Open Seed File and Append Text | Tier_C | L2 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 0 | 75.015s | `TIMEOUT` |
| `L2-03` | Cross-App Calculator Result to Notepad | Tier_C | L2 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 0 | 75.03s | `TIMEOUT` |
| `L2-04` | Rename File in Workspace | Tier_C | L2 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 0 | 75.26s | `TIMEOUT` |
| `L2-05` | Create Directory in Workspace via File Explorer | Tier_C | L2 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 0 | 75.12s | `TIMEOUT` |
| `L2-06` | Dismiss Modal Error Dialog and Open Notepad | Tier_D | L2 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 0 | 60.046s | `TIMEOUT` |
| `L2-07` | Harvest Token from Open Notepad to Clipboard | Tier_C | L2 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 0 | 60.062s | `TIMEOUT` |
| `L3-01` | Close Dirty Notepad and Choose Don't Save | Tier_D | L3 | ✅ PASS | FAIL | `PASS` | 0 | 60.097s | `TIMEOUT` |
| `L3-02` | Compute in Calculator, Format & Save in Notepad | Tier_D | L3 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 8 | 72.024s | `MAX_STEPS` |
| `L3-03` | Browser Navigation & Cross-App Note Recording | Tier_C | L3 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 8 | 75.76s | `MAX_STEPS` |