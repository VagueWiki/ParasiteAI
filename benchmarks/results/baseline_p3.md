# ParasiteAI Benchmark Report (baseline_p3)
**Date:** 2026-11-11 23:51:59  
**Host Environment:** Windows 10 / NVIDIA GeForce RTX 4060 (8188 MB VRAM, Driver 610.74)  
**Total Tasks:** 20  
**Ground-Truth Pass Rate:** **35.0%** (7/20)  
**Claimed DONE Rate:** 10.0%  
**False DONE Rate:** 5.0% (1 occurrences)  
**Mean Steps:** 7.0 | **Mean Duration:** 45.65s  
**Median Step Latency:** 6.034s | **P90 Step Latency:** 6.763s  
**Hardware Interrupts:** 0  

## Performance by Difficulty Level
| Level | Passed / Total | Pass Rate | Gate Target |
| :--- | :--- | :--- | :--- |
| **L1** | 5 / 10 | **50.0%** | >= 70% |
| **L2** | 1 / 7 | **14.3%** | >= 40% |
| **L3** | 1 / 3 | **33.3%** | Informational |

## Failure Mode Taxonomy
| Failure Category | Occurrences | Description |
| :--- | :---: | :--- |
| `MAX_STEPS_EXHAUSTED` | 12 | Cognitive step budget exhausted before goal completion. |
| `PASS` | 7 | Task verified successfully by objective OS verifier. |
| `FALSE_DONE` | 1 | Model claimed DONE, but OS ground-truth state failed. |

## Detailed Task Scorecard
| Task ID | Name | Tier | Lvl | Verifier | Agent | Outcome Mode | Steps | Duration | Exit Reason |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `L1-01` | Launch Notepad | Tier_A | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 5 | 37.741s | `MAX_STEPS` |
| `L1-02` | Launch Calculator | Tier_A | L1 | ✅ PASS | DONE | `PASS` | 5 | 29.448s | `DONE` |
| `L1-03` | Launch Paint | Tier_A | L1 | ✅ PASS | FAIL | `PASS` | 5 | 31.473s | `MAX_STEPS` |
| `L1-04` | Type Exact Token in Notepad | Tier_B | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 8 | 58.672s | `MAX_STEPS` |
| `L1-05` | Compose Greeting in Notepad (No Goal Echo) | Tier_B | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 8 | 56.988s | `MAX_STEPS` |
| `L1-06` | Close Pre-Opened Notepad | Tier_B | L1 | ✅ PASS | FAIL | `PASS` | 5 | 32.384s | `MAX_STEPS` |
| `L1-07` | Minimize Pre-Opened Notepad | Tier_B | L1 | ✅ PASS | FAIL | `PASS` | 5 | 34.107s | `MAX_STEPS` |
| `L1-08` | Compute Multiplication in Calculator | Tier_B | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 8 | 51.214s | `MAX_STEPS` |
| `L1-09` | Launch File Explorer | Tier_A | L1 | ✅ PASS | FAIL | `PASS` | 5 | 32.815s | `MAX_STEPS` |
| `L1-10` | Type and Copy Text to Clipboard in Notepad | Tier_B | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 8 | 49.74s | `MAX_STEPS` |
| `L2-01` | Save Notepad Document to Workspace File | Tier_C | L2 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 8 | 50.522s | `MAX_STEPS` |
| `L2-02` | Open Seed File and Append Text | Tier_C | L2 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 8 | 48.504s | `MAX_STEPS` |
| `L2-03` | Cross-App Calculator Result to Notepad | Tier_C | L2 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 8 | 50.173s | `MAX_STEPS` |
| `L2-04` | Rename File in Workspace | Tier_C | L2 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 8 | 50.656s | `MAX_STEPS` |
| `L2-05` | Create Directory in Workspace via File Explorer | Tier_C | L2 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 8 | 51.198s | `MAX_STEPS` |
| `L2-06` | Dismiss Modal Error Dialog and Open Notepad | Tier_D | L2 | ❌ FAIL | DONE | `FALSE_DONE` | 6 | 38.649s | `DONE` |
| `L2-07` | Harvest Token from Open Notepad to Clipboard | Tier_C | L2 | ✅ PASS | FAIL | `PASS` | 8 | 48.234s | `MAX_STEPS` |
| `L3-01` | Close Dirty Notepad and Choose Don't Save | Tier_D | L3 | ✅ PASS | FAIL | `PASS` | 8 | 53.693s | `MAX_STEPS` |
| `L3-02` | Compute in Calculator, Format & Save in Notepad | Tier_D | L3 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 8 | 50.567s | `MAX_STEPS` |
| `L3-03` | Browser Navigation & Cross-App Note Recording | Tier_C | L3 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 8 | 56.293s | `MAX_STEPS` |