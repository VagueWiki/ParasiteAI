# ParasiteAI Benchmark Report (baseline_p1)
**Date:** 2026-11-08 14:16:50  
**Host Environment:** Windows 10 / NVIDIA GeForce RTX 4060 (8188 MB VRAM, Driver 610.74)  
**Total Tasks:** 20  
**Ground-Truth Pass Rate:** **0.0%** (0/20)  
**Claimed DONE Rate:** 5.0%  
**False DONE Rate:** 5.0% (1 occurrences)  
**Mean Steps:** 2.0 | **Mean Duration:** 46.16s  
**Median Step Latency:** 4.741s | **P90 Step Latency:** 5.635s  
**Hardware Interrupts:** 0  

## Performance by Difficulty Level
| Level | Passed / Total | Pass Rate | Gate Target |
| :--- | :--- | :--- | :--- |
| **L1** | 0 / 10 | **0.0%** | >= 70% |
| **L2** | 0 / 7 | **0.0%** | >= 40% |
| **L3** | 0 / 3 | **0.0%** | Informational |

## Failure Mode Taxonomy
| Failure Category | Occurrences | Description |
| :--- | :---: | :--- |
| `MAX_STEPS_EXHAUSTED` | 19 | Cognitive step budget exhausted before goal completion. |
| `FALSE_DONE` | 1 | Model claimed DONE, but OS ground-truth state failed. |

## Detailed Task Scorecard
| Task ID | Name | Tier | Lvl | Verifier | Agent | Outcome Mode | Steps | Duration | Exit Reason |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `L1-01` | Launch Notepad | Tier_A | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 0 | 45.015s | `TIMEOUT` |
| `L1-02` | Launch Calculator | Tier_A | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 0 | 45.004s | `TIMEOUT` |
| `L1-03` | Launch Paint | Tier_A | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 0 | 45.019s | `TIMEOUT` |
| `L1-04` | Type Exact Token in Notepad | Tier_B | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 0 | 60.018s | `TIMEOUT` |
| `L1-05` | Compose Greeting in Notepad (No Goal Echo) | Tier_B | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 5 | 26.419s | `MAX_STEPS` |
| `L1-06` | Close Pre-Opened Notepad | Tier_B | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 0 | 45.017s | `TIMEOUT` |
| `L1-07` | Minimize Pre-Opened Notepad | Tier_B | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 0 | 45.017s | `TIMEOUT` |
| `L1-08` | Compute Multiplication in Calculator | Tier_B | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 0 | 60.017s | `TIMEOUT` |
| `L1-09` | Launch File Explorer | Tier_A | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 0 | 45.018s | `TIMEOUT` |
| `L1-10` | Type and Copy Text to Clipboard in Notepad | Tier_B | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 0 | 60.018s | `TIMEOUT` |
| `L2-01` | Save Notepad Document to Workspace File | Tier_C | L2 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 5 | 69.362s | `MAX_STEPS` |
| `L2-02` | Open Seed File and Append Text | Tier_C | L2 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 5 | 25.42s | `MAX_STEPS` |
| `L2-03` | Cross-App Calculator Result to Notepad | Tier_C | L2 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 5 | 27.346s | `MAX_STEPS` |
| `L2-04` | Rename File in Workspace | Tier_C | L2 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 5 | 27.845s | `MAX_STEPS` |
| `L2-05` | Create Directory in Workspace via File Explorer | Tier_C | L2 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 5 | 65.746s | `MAX_STEPS` |
| `L2-06` | Dismiss Modal Error Dialog and Open Notepad | Tier_D | L2 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 0 | 60.018s | `TIMEOUT` |
| `L2-07` | Harvest Token from Open Notepad to Clipboard | Tier_C | L2 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 0 | 60.018s | `TIMEOUT` |
| `L3-01` | Close Dirty Notepad and Choose Don't Save | Tier_D | L3 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 0 | 60.019s | `TIMEOUT` |
| `L3-02` | Compute in Calculator, Format & Save in Notepad | Tier_D | L3 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 5 | 24.585s | `MAX_STEPS` |
| `L3-03` | Browser Navigation & Cross-App Note Recording | Tier_C | L3 | ❌ FAIL | DONE | `FALSE_DONE` | 5 | 26.321s | `DONE` |