# ParasiteAI Benchmark Report (baseline_p2_6)
**Date:** 2026-11-10 12:20:35  
**Host Environment:** Windows 10 / NVIDIA GeForce RTX 4060 (8188 MB VRAM, Driver 610.74)  
**Total Tasks:** 20  
**Ground-Truth Pass Rate:** **5.0%** (1/20)  
**Claimed DONE Rate:** 0.0%  
**False DONE Rate:** 0.0% (0 occurrences)  
**Mean Steps:** 7.1 | **Mean Duration:** 29.72s  
**Median Step Latency:** 3.545s | **P90 Step Latency:** 4.221s  
**Hardware Interrupts:** 4  

## Performance by Difficulty Level
| Level | Passed / Total | Pass Rate | Gate Target |
| :--- | :--- | :--- | :--- |
| **L1** | 1 / 10 | **10.0%** | >= 70% |
| **L2** | 0 / 7 | **0.0%** | >= 40% |
| **L3** | 0 / 3 | **0.0%** | Informational |

## Failure Mode Taxonomy
| Failure Category | Occurrences | Description |
| :--- | :---: | :--- |
| `MAX_STEPS_EXHAUSTED` | 18 | Cognitive step budget exhausted before goal completion. |
| `HARDWARE_PREEMPTED` | 1 | Operator physical mouse/keyboard touch paused or preempted episode. |
| `PASS` | 1 | Task verified successfully by objective OS verifier. |

## Detailed Task Scorecard
| Task ID | Name | Tier | Lvl | Verifier | Agent | Outcome Mode | Steps | Duration | Exit Reason |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `L1-01` | Launch Notepad | Tier_A | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 5 | 23.02s | `MAX_STEPS` |
| `L1-02` | Launch Calculator | Tier_A | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 5 | 20.914s | `MAX_STEPS` |
| `L1-03` | Launch Paint | Tier_A | L1 | ❌ FAIL | FAIL | `HARDWARE_PREEMPTED` | 5 | 21.178s | `MAX_STEPS` |
| `L1-04` | Type Exact Token in Notepad | Tier_B | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 8 | 29.42s | `MAX_STEPS` |
| `L1-05` | Compose Greeting in Notepad (No Goal Echo) | Tier_B | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 8 | 30.147s | `MAX_STEPS` |
| `L1-06` | Close Pre-Opened Notepad | Tier_B | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 5 | 19.921s | `MAX_STEPS` |
| `L1-07` | Minimize Pre-Opened Notepad | Tier_B | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 5 | 19.697s | `MAX_STEPS` |
| `L1-08` | Compute Multiplication in Calculator | Tier_B | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 8 | 30.074s | `MAX_STEPS` |
| `L1-09` | Launch File Explorer | Tier_A | L1 | ✅ PASS | FAIL | `PASS` | 5 | 20.709s | `MAX_STEPS` |
| `L1-10` | Type and Copy Text to Clipboard in Notepad | Tier_B | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 8 | 31.204s | `MAX_STEPS` |
| `L2-01` | Save Notepad Document to Workspace File | Tier_C | L2 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 8 | 34.812s | `MAX_STEPS` |
| `L2-02` | Open Seed File and Append Text | Tier_C | L2 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 8 | 29.948s | `MAX_STEPS` |
| `L2-03` | Cross-App Calculator Result to Notepad | Tier_C | L2 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 8 | 32.589s | `MAX_STEPS` |
| `L2-04` | Rename File in Workspace | Tier_C | L2 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 8 | 33.441s | `MAX_STEPS` |
| `L2-05` | Create Directory in Workspace via File Explorer | Tier_C | L2 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 8 | 33.144s | `MAX_STEPS` |
| `L2-06` | Dismiss Modal Error Dialog and Open Notepad | Tier_D | L2 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 8 | 36.137s | `MAX_STEPS` |
| `L2-07` | Harvest Token from Open Notepad to Clipboard | Tier_C | L2 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 8 | 39.021s | `MAX_STEPS` |
| `L3-01` | Close Dirty Notepad and Choose Don't Save | Tier_D | L3 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 8 | 36.072s | `MAX_STEPS` |
| `L3-02` | Compute in Calculator, Format & Save in Notepad | Tier_D | L3 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 8 | 33.58s | `MAX_STEPS` |
| `L3-03` | Browser Navigation & Cross-App Note Recording | Tier_C | L3 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 8 | 39.274s | `MAX_STEPS` |