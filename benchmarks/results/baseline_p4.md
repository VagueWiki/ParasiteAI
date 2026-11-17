# ParasiteAI Benchmark Report (baseline_p4)
**Date:** 2026-11-16 21:14:19  
**Host Environment:** Windows 10 / NVIDIA GeForce RTX 4060 (8188 MB VRAM, Driver 610.74)  
**Total Tasks:** 20  
**Ground-Truth Pass Rate:** **90.0%** (18/20)  
**Claimed DONE Rate:** 90.0%  
**False DONE Rate:** 0.0% (0 occurrences)  
**Mean Steps:** 6.4 | **Step Efficiency (vs Ideal Skill Min):** 1.45x | **Mean Duration:** 45.37s  
**Median Step Latency:** 4.819s | **P90 Step Latency:** 8.584s  
**Hardware Interrupts:** 0  

## Performance by Difficulty Level
| Level | Passed / Total | Pass Rate | Gate Target |
| :--- | :--- | :--- | :--- |
| **L1** | 10 / 10 | **100.0%** | >= 70% |
| **L2** | 6 / 7 | **85.7%** | >= 40% |
| **L3** | 2 / 3 | **66.7%** | Informational |

## Failure Mode Taxonomy
| Failure Category | Occurrences | Description |
| :--- | :---: | :--- |
| `PASS` | 18 | Task verified successfully by objective OS verifier. |
| `MAX_STEPS_EXHAUSTED` | 2 | Cognitive step budget exhausted before goal completion. |

## Detailed Task Scorecard
| Task ID | Name | Tier | Lvl | Verifier | Agent | Outcome Mode | Plan Source | Steps (Act/MinS/MinL/Max) | Duration | Exit Reason |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :--- | :---: | :---: | :--- |
| `L1-01` | Launch Notepad | Tier_A | L1 | ✅ PASS | DONE | `PASS` | `local` | 3 / 2 / 4 / 12 | 10.437s | `DONE` |
| `L1-02` | Launch Calculator | Tier_A | L1 | ✅ PASS | DONE | `PASS` | `local` | 3 / 2 / 4 / 12 | 10.238s | `DONE` |
| `L1-03` | Launch Paint | Tier_A | L1 | ✅ PASS | DONE | `PASS` | `local` | 3 / 2 / 4 / 12 | 10.047s | `DONE` |
| `L1-04` | Type Exact Token in Notepad | Tier_B | L1 | ✅ PASS | DONE | `PASS` | `skill` (notepad-write-text) | 4 / 3 / 5 / 16 | 12.643s | `DONE` |
| `L1-05` | Compose Greeting in Notepad (No Goal Echo) | Tier_B | L1 | ✅ PASS | DONE | `PASS` | `local` | 7 / 3 / 5 / 16 | 47.545s | `DONE` |
| `L1-06` | Close Pre-Opened Notepad | Tier_B | L1 | ✅ PASS | DONE | `PASS` | `local` | 2 / 2 / 2 / 10 | 16.051s | `DONE` |
| `L1-07` | Minimize Pre-Opened Notepad | Tier_B | L1 | ✅ PASS | DONE | `PASS` | `skill` (minimize-notepad) | 2 / 2 / 2 / 10 | 4.045s | `DONE` |
| `L1-08` | Compute Multiplication in Calculator | Tier_B | L1 | ✅ PASS | DONE | `PASS` | `skill` (calculator-evaluate) | 6 / 3 / 6 / 16 | 13.646s | `DONE` |
| `L1-09` | Launch File Explorer | Tier_A | L1 | ✅ PASS | DONE | `PASS` | `local` | 3 / 2 / 2 / 12 | 12.05s | `DONE` |
| `L1-10` | Type and Copy Text to Clipboard in Notepad | Tier_B | L1 | ✅ PASS | DONE | `PASS` | `skill` (open-notepad-type-draft-select-all-text-and-copy) | 7 / 4 / 7 / 16 | 9.502s | `DONE` |
| `L2-01` | Save Notepad Document to Workspace File | Tier_C | L2 | ✅ PASS | DONE | `PASS` | `skill` (open-notepad-type-saved-note-101-and-save-it-as) | 6 / 5 / 9 / 22 | 12.248s | `DONE` |
| `L2-02` | Open Seed File and Append Text | Tier_C | L2 | ✅ PASS | DONE | `PASS` | `skill` (open-c-parasiteai-benchmarks-workspace-seed-txt) | 6 / 5 / 9 / 22 | 17.448s | `DONE` |
| `L2-03` | Cross-App Calculator Result to Notepad | Tier_C | L2 | ✅ PASS | DONE | `PASS` | `skill` (open-calculator-compute-144-12-and-type-the-resu) | 7 / 5 / 9 / 22 | 26.687s | `DONE` |
| `L2-04` | Rename File in Workspace | Tier_C | L2 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | `local` | 16 / 5 / 9 / 22 | 240.186s | `TIMEOUT` |
| `L2-05` | Create Directory in Workspace via File Explorer | Tier_C | L2 | ✅ PASS | DONE | `PASS` | `skill` (create-a-new-folder-named-reports-inside-c-paras) | 6 / 4 / 7 / 22 | 19.911s | `DONE` |
| `L2-06` | Dismiss Modal Error Dialog and Open Notepad | Tier_D | L2 | ✅ PASS | DONE | `PASS` | `farmed` (#15) | 5 / 3 / 5 / 18 | 25.072s | `DONE` |
| `L2-07` | Harvest Token from Open Notepad to Clipboard | Tier_C | L2 | ✅ PASS | DONE | `PASS` | `local` | 4 / 3 / 4 / 16 | 28.293s | `DONE` |
| `L3-01` | Close Dirty Notepad and Choose Don't Save | Tier_D | L3 | ✅ PASS | DONE | `PASS` | `local` | 3 / 3 / 4 / 18 | 30.093s | `DONE` |
| `L3-02` | Compute in Calculator, Format & Save in Notepad | Tier_D | L3 | ✅ PASS | DONE | `PASS` | `proactive_gemini` (#30) | 10 / 7 / 12 / 26 | 101.131s | `DONE` |
| `L3-03` | Browser Navigation & Cross-App Note Recording | Tier_C | L3 | ❌ FAIL | FAIL | `MAX_STEPS_EXHAUSTED` | `farmed` (#17) | 25 / 6 / 10 / 26 | 260.141s | `TIMEOUT` |