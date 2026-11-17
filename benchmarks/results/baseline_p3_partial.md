# ParasiteAI Benchmark Report (baseline_p3)
**Date:** 2026-11-11 22:15:04  
**Host Environment:** Windows 10 / NVIDIA GeForce RTX 4060 (8188 MB VRAM, Driver 610.74)  
**Total Tasks:** 17  
**Ground-Truth Pass Rate:** **23.5%** (4/17)  
**Claimed DONE Rate:** 11.8%  
**False DONE Rate:** 0.0% (0 occurrences)  
**Mean Steps:** 4.47 | **Mean Duration:** 50.75s  
**Median Step Latency:** 7.476s | **P90 Step Latency:** 8.162s  
**Hardware Interrupts:** 0  

## Performance by Difficulty Level
| Level | Passed / Total | Pass Rate | Gate Target |
| :--- | :--- | :--- | :--- |
| **L1** | 3 / 10 | **30.0%** | >= 70% |
| **L2** | 1 / 7 | **14.3%** | >= 40% |

## Failure Mode Taxonomy
| Failure Category | Occurrences | Description |
| :--- | :---: | :--- |
| `MAX_STEPS_EXHAUSTED` | 11 | Cognitive step budget exhausted before goal completion. |
| `PASS` | 4 | Task verified successfully by objective OS verifier. |
| `UNKNOWN_FAILURE` | 2 | Unhandled exception or unmapped failure. |

## Detailed Task Scorecard
| Task ID | Name | Tier | Lvl | Verifier | Agent | Outcome Mode | Steps | Duration | Exit Reason |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `L1-01` | Launch Notepad | Tier_A | L1 | ❌ FAIL | FAIL | `UNKNOWN_FAILURE` | 2 | 26.496s | `ERROR` |
| `L1-02` | Launch Calculator | Tier_A | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 5 | 36.414s | `MAX_STEPS` |
| `L1-03` | Launch Paint | Tier_A | L1 | ❌ FAIL | FAIL | `UNKNOWN_FAILURE` | 2 | 25.983s | `ERROR` |
| `L1-04` | Type Exact Token in Notepad | Tier_B | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 0 | 60.025s | `TIMEOUT` |
| `L1-05` | Compose Greeting in Notepad (No Goal Echo) | Tier_B | L1 | ✅ PASS | FAIL | `PASS` | 0 | 60.026s | `TIMEOUT` |
| `L1-06` | Close Pre-Opened Notepad | Tier_B | L1 | ✅ PASS | DONE | `PASS` | 4 | 31.418s | `DONE` |
| `L1-07` | Minimize Pre-Opened Notepad | Tier_B | L1 | ✅ PASS | FAIL | `PASS` | 5 | 40.079s | `MAX_STEPS` |
| `L1-08` | Compute Multiplication in Calculator | Tier_B | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 0 | 60.027s | `TIMEOUT` |
| `L1-09` | Launch File Explorer | Tier_A | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 5 | 39.307s | `MAX_STEPS` |
| `L1-10` | Type and Copy Text to Clipboard in Notepad | Tier_B | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 8 | 58.198s | `MAX_STEPS` |
| `L2-01` | Save Notepad Document to Workspace File | Tier_C | L2 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 8 | 63.104s | `MAX_STEPS` |
| `L2-02` | Open Seed File and Append Text | Tier_C | L2 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 8 | 66.186s | `MAX_STEPS` |
| `L2-03` | Cross-App Calculator Result to Notepad | Tier_C | L2 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 8 | 62.855s | `MAX_STEPS` |
| `L2-04` | Rename File in Workspace | Tier_C | L2 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 8 | 61.781s | `MAX_STEPS` |
| `L2-05` | Create Directory in Workspace via File Explorer | Tier_C | L2 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 8 | 69.456s | `MAX_STEPS` |
| `L2-06` | Dismiss Modal Error Dialog and Open Notepad | Tier_D | L2 | ✅ PASS | DONE | `PASS` | 5 | 40.986s | `DONE` |
| `L2-07` | Harvest Token from Open Notepad to Clipboard | Tier_C | L2 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 0 | 60.442s | `TIMEOUT` |