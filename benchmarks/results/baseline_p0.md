# ParasiteAI Benchmark Report (baseline_p0)
**Date:** 2026-11-07 03:07:01  
**Host Environment:** Windows 10 / NVIDIA GeForce RTX 4060 (8188 MB VRAM, Driver 610.74)  
**Total Tasks:** 20  
**Ground-Truth Pass Rate:** **5.0%** (1/20)  
**Claimed DONE Rate:** 25.0%  
**False DONE Rate:** 20.0% (4 occurrences)  
**Mean Steps:** 3.15 | **Mean Duration:** 39.27s  
**Median Step Latency:** 5.986s | **P90 Step Latency:** 9.798s  
**Hardware Interrupts:** 0  

## Performance by Difficulty Level
| Level | Passed / Total | Pass Rate | Gate Target |
| :--- | :--- | :--- | :--- |
| **L1** | 1 / 10 | **10.0%** | >= 70% |
| **L2** | 0 / 7 | **0.0%** | >= 40% |
| **L3** | 0 / 3 | **0.0%** | Informational |

## Failure Mode Taxonomy
| Failure Category | Occurrences | Description |
| :--- | :---: | :--- |
| `MAX_STEPS_EXHAUSTED` | 13 | Cognitive step budget exhausted before goal completion. |
| `FALSE_DONE` | 4 | Model claimed DONE, but OS ground-truth state failed. |
| `UNKNOWN_FAILURE` | 2 | Unhandled exception or unmapped failure. |
| `PASS` | 1 | Task verified successfully by objective OS verifier. |

## Detailed Task Scorecard
| Task ID | Name | Tier | Lvl | Verifier | Agent | Outcome Mode | Steps | Duration | Exit Reason |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `L1-01` | Launch Notepad | Tier_A | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 0 | 45.274s | `TIMEOUT` |
| `L1-02` | Launch Calculator | Tier_A | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 0 | 45.209s | `TIMEOUT` |
| `L1-03` | Launch Paint | Tier_A | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 5 | 38.781s | `MAX_STEPS` |
| `L1-04` | Type Exact Token in Notepad | Tier_B | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 5 | 31.807s | `MAX_STEPS` |
| `L1-05` | Compose Greeting in Notepad (No Goal Echo) | Tier_B | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 0 | 60.218s | `TIMEOUT` |
| `L1-06` | Close Pre-Opened Notepad | Tier_B | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 0 | 45.219s | `TIMEOUT` |
| `L1-07` | Minimize Pre-Opened Notepad | Tier_B | L1 | ✅ PASS | DONE | `PASS` | 2 | 15.917s | `DONE` |
| `L1-08` | Compute Multiplication in Calculator | Tier_B | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 5 | 36.926s | `MAX_STEPS` |
| `L1-09` | Launch File Explorer | Tier_A | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 5 | 37.032s | `MAX_STEPS` |
| `L1-10` | Type and Copy Text to Clipboard in Notepad | Tier_B | L1 | ❌ FAIL | FAIL | `UNKNOWN_FAILURE` | 2 | 19.091s | `ERROR` |
| `L2-01` | Save Notepad Document to Workspace File | Tier_C | L2 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 5 | 30.108s | `MAX_STEPS` |
| `L2-02` | Open Seed File and Append Text | Tier_C | L2 | ❌ FAIL | DONE | `FALSE_DONE` | 4 | 25.198s | `DONE` |
| `L2-03` | Cross-App Calculator Result to Notepad | Tier_C | L2 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 5 | 27.047s | `MAX_STEPS` |
| `L2-04` | Rename File in Workspace | Tier_C | L2 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 5 | 42.114s | `MAX_STEPS` |
| `L2-05` | Create Directory in Workspace via File Explorer | Tier_C | L2 | ❌ FAIL | DONE | `FALSE_DONE` | 5 | 42.122s | `DONE` |
| `L2-06` | Dismiss Modal Error Dialog and Open Notepad | Tier_D | L2 | ❌ FAIL | DONE | `FALSE_DONE` | 5 | 46.244s | `DONE` |
| `L2-07` | Harvest Token from Open Notepad to Clipboard | Tier_C | L2 | ❌ FAIL | DONE | `FALSE_DONE` | 4 | 36.887s | `DONE` |
| `L3-01` | Close Dirty Notepad and Choose Don't Save | Tier_D | L3 | ❌ FAIL | FAIL | `UNKNOWN_FAILURE` | 1 | 20.691s | `ERROR` |
| `L3-02` | Compute in Calculator, Format & Save in Notepad | Tier_D | L3 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 5 | 49.256s | `MAX_STEPS` |
| `L3-03` | Browser Navigation & Cross-App Note Recording | Tier_C | L3 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 0 | 90.208s | `TIMEOUT` |