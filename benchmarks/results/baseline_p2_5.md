# ParasiteAI Benchmark Report (baseline_p2_5)
**Date:** 2026-11-10 01:31:50  
**Host Environment:** Windows 10 / NVIDIA GeForce RTX 4060 (8188 MB VRAM, Driver 610.74)  
**Total Tasks:** 20  
**Ground-Truth Pass Rate:** **0.0%** (0/20)  
**Claimed DONE Rate:** 0.0%  
**False DONE Rate:** 0.0% (0 occurrences)  
**Mean Steps:** 7.1 | **Mean Duration:** 29.3s  
**Median Step Latency:** 3.592s | **P90 Step Latency:** 4.361s  
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
| `MAX_STEPS_EXHAUSTED` | 20 | Cognitive step budget exhausted before goal completion. |

## Detailed Task Scorecard
| Task ID | Name | Tier | Lvl | Verifier | Agent | Outcome Mode | Steps | Duration | Exit Reason |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `L1-01` | Launch Notepad | Tier_A | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 5 | 20.732s | `MAX_STEPS` |
| `L1-02` | Launch Calculator | Tier_A | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 5 | 20.075s | `MAX_STEPS` |
| `L1-03` | Launch Paint | Tier_A | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 5 | 22.537s | `MAX_STEPS` |
| `L1-04` | Type Exact Token in Notepad | Tier_B | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 8 | 34.544s | `MAX_STEPS` |
| `L1-05` | Compose Greeting in Notepad (No Goal Echo) | Tier_B | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 8 | 32.223s | `MAX_STEPS` |
| `L1-06` | Close Pre-Opened Notepad | Tier_B | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 5 | 21.096s | `MAX_STEPS` |
| `L1-07` | Minimize Pre-Opened Notepad | Tier_B | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 5 | 20.877s | `MAX_STEPS` |
| `L1-08` | Compute Multiplication in Calculator | Tier_B | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 8 | 33.274s | `MAX_STEPS` |
| `L1-09` | Launch File Explorer | Tier_A | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 5 | 22.982s | `MAX_STEPS` |
| `L1-10` | Type and Copy Text to Clipboard in Notepad | Tier_B | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 8 | 31.704s | `MAX_STEPS` |
| `L2-01` | Save Notepad Document to Workspace File | Tier_C | L2 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 8 | 34.078s | `MAX_STEPS` |
| `L2-02` | Open Seed File and Append Text | Tier_C | L2 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 8 | 34.525s | `MAX_STEPS` |
| `L2-03` | Cross-App Calculator Result to Notepad | Tier_C | L2 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 8 | 32.211s | `MAX_STEPS` |
| `L2-04` | Rename File in Workspace | Tier_C | L2 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 8 | 37.99s | `MAX_STEPS` |
| `L2-05` | Create Directory in Workspace via File Explorer | Tier_C | L2 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 8 | 33.851s | `MAX_STEPS` |
| `L2-06` | Dismiss Modal Error Dialog and Open Notepad | Tier_D | L2 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 8 | 26.158s | `MAX_STEPS` |
| `L2-07` | Harvest Token from Open Notepad to Clipboard | Tier_C | L2 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 8 | 30.434s | `MAX_STEPS` |
| `L3-01` | Close Dirty Notepad and Choose Don't Save | Tier_D | L3 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 8 | 30.145s | `MAX_STEPS` |
| `L3-02` | Compute in Calculator, Format & Save in Notepad | Tier_D | L3 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 8 | 33.874s | `MAX_STEPS` |
| `L3-03` | Browser Navigation & Cross-App Note Recording | Tier_C | L3 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 8 | 32.721s | `MAX_STEPS` |