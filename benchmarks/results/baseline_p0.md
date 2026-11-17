# ParasiteAI Benchmark Report (baseline_p0)
**Date:** 2026-11-12 12:33:18  
**Host Environment:** Windows 10 / NVIDIA GeForce RTX 4060 (8188 MB VRAM, Driver 610.74)  
**Total Tasks:** 1  
**Ground-Truth Pass Rate:** **0.0%** (0/1)  
**Claimed DONE Rate:** 0.0%  
**False DONE Rate:** 0.0% (0 occurrences)  
**Mean Steps:** 8.0 | **Mean Duration:** 52.66s  
**Median Step Latency:** 5.976s | **P90 Step Latency:** 6.596s  
**Hardware Interrupts:** 0  

## Performance by Difficulty Level
| Level | Passed / Total | Pass Rate | Gate Target |
| :--- | :--- | :--- | :--- |
| **L1** | 0 / 1 | **0.0%** | >= 70% |

## Failure Mode Taxonomy
| Failure Category | Occurrences | Description |
| :--- | :---: | :--- |
| `MAX_STEPS_EXHAUSTED` | 1 | Cognitive step budget exhausted before goal completion. |

## Detailed Task Scorecard
| Task ID | Name | Tier | Lvl | Verifier | Agent | Outcome Mode | Steps | Duration | Exit Reason |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `L1-08` | Compute Multiplication in Calculator | Tier_B | L1 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | 8 | 52.663s | `MAX_STEPS` |