# DISPATCH — Challenger 1 (Milestone 4E)

## Mission
Adversarially stress-test `PrecisionAppMatcher` against hundreds of edge cases, substring collision attacks, negative verb traps, noisy OCR/accessibility labels, casing, punctuation, and Unicode variations.

## Key Context & Paths
- Master Plan: `c:\Users\Suici\.gemini\antigravity\brain\464b4ef0-398b-45b1-94dc-857256a38046\phase_4_master_plan.md` (§8, §10 Sub-Phase 4E, §12 VERIF-11)
- Original Request: `C:\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md`
- Scope: `C:\ParasiteAI\.agents\teamwork\orchestrator_4\SCOPE.md`
- Worker Handoff: `C:\ParasiteAI\.agents\teamwork\teamwork_worker_m4e\handoff.md`
- Your Workspace: `C:\ParasiteAI\.agents\teamwork\challenger_m4e_1\`

## Target Adversarial Areas
1. Substring Collision Invariants (0.0 false click score):
   - "art" against "SmartScreen", "catalog", "Restart", "Chart", "Dart", "Bystander"
   - "cat" against "catalog", "scatter", "indicate", "application", "locate"
   - "edit" against "credit", "expedite", "hereditary", "sedition"
   - "notepad" against "Exit Notepad", "Close Notepad", "Uninstall Notepad", "Delete Notepad", "Kill Notepad"
   - "calc" against "Recalculate", "Decalcify", "Exit Calculator"
2. Negative Verb Traps:
   - Ensure ANY negative verb ("exit", "close", "quit", "cancel", "uninstall", "delete", "remove", "kill") zeroes the score (0.0) regardless of whether target is present.
3. Boundary & Exact Matching:
   - Verify word boundaries (`\b`) match cleanly: "Notepad" matches "Open Notepad", "Notepad - Untitled", "Notepad: Text Editor".
   - Verify non-alphanumeric separators: "Visual Studio Code" vs "Code", "Paint.NET" vs "Paint".
   - Verify thresholding: `find_best_element` correctly returns None when all candidates are below threshold.
4. Deliverable:
   - Author empirical stress test suite `tests/test_challenger_m4e_precision.py`.
   - Run tests using `.\.venv\Scripts\python.exe -m pytest tests/test_challenger_m4e_precision.py -v`.
   - Write `handoff.md` in `C:\ParasiteAI\.agents\teamwork\challenger_m4e_1\` with explicit verdict (`APPROVE` or `REQUEST_CHANGES`) and notify orchestrator.


## 2026-11-01T13:22:05Z
From: cd3091f7-f068-4caf-9067-08e977e1378e
Content:
You are Challenger 1 for Milestone 4E (PrecisionAppMatcher Adversarial Stress Testing).
Your working directory is C:\ParasiteAI\.agents\teamwork\challenger_m4e_1\.
Read your instructions in C:\ParasiteAI\.agents\teamwork\challenger_m4e_1\DISPATCH.md.
Also read ORIGINAL_REQUEST.md at C:\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md, SCOPE.md at C:\ParasiteAI\.agents\teamwork\orchestrator_4\SCOPE.md, and the worker handoff at C:\ParasiteAI\.agents\teamwork\teamwork_worker_m4e\handoff.md.
Adversarially stress-test PrecisionAppMatcher against hundreds of substring collision attacks, negative verb traps, noisy labels, casing, and boundary conditions.
Author tests/test_challenger_m4e_precision.py and run via .\.venv\Scripts\python.exe -m pytest tests/test_challenger_m4e_precision.py -v.
Write handoff.md in C:\ParasiteAI\.agents\teamwork\challenger_m4e_1\ with explicit verdict APPROVE or REQUEST_CHANGES and send message back to orchestrator.
