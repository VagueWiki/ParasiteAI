# Worker (Iter 3) Dispatch: Surgical Text Cleanup & Final Certification

Working directory: C:\ParasiteAI\.agents\teamwork\teamwork_worker_p4_iter3
Target file to update: c:\Users\Suici\.gemini\antigravity\brain\464b4ef0-398b-45b1-94dc-857256a38046\phase_4_master_plan.md
Challenger 1 report: C:\ParasiteAI\.agents\teamwork\teamwork_challenger_p4_iter2_1\handoff.md
Test file to pass: C:\ParasiteAI\tests\test_challenger_p4_iter2_c1.py

Instructions:
Apply the 3 surgical text cleanups specified in Section 5 of Challenger 1's report:
1. Clean Section 5.2 (lines 578-584):
   Remove the stray duplicate block:
   ```python
   ```json[\s\S]*?```", "", text)
           text = re.sub(r"[{}\[\]\"]", "", text)
           text = re.sub(r"\b\d+x\d+\b", "", text)
           text = re.sub(r"\(\d+,\s*\d+\)", "", text)
           return " ".join(text.split()).strip()
   ```
   So that line 578 (`return " ".join(text.split()).strip()`) is followed immediately by the closing code fence (```).
2. Clean Docstrings Across Master Plan:
   Replace all 12 occurrences of literal escaped `\"\"\"` with unescaped `"""` (specifically at lines 253, 262, 328, 729, 732, 763, 766, 802, 805, 992, 995).
3. Seal CLI Sandbox Web Scraping Loophole (Section 6.4):
   In `CLIExecutionSandbox.FORBIDDEN_PATTERNS`, append:
   ```python
           r"\b(?:Invoke-WebRequest|iwr|Invoke-RestMethod|irm)\b",
           r"\brequests\b",
   ```
4. Run verification tests:
   `& "C:\ParasiteAI\.venv\Scripts\python.exe" -m pytest tests/test_challenger_p4_iter2_c1.py -v` (Must pass 8/8 green).
   `& "C:\ParasiteAI\.venv\Scripts\python.exe" -m pytest tests/test_living_plan.py tests/test_gemini_consultation_protocol.py tests/test_interrupt_guard.py tests/test_dual_mind.py tests/test_challenger_p4_empirical.py` (Must pass 78/78 green).
5. Synchronize mirror file:
   `c:\Users\Suici\.gemini\antigravity\brain\c0750c5c-4354-4aa0-b198-17e98f598cf7\phase_4_master_plan.md`.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Output:
Write completion report to:
C:\ParasiteAI\.agents\teamwork\teamwork_worker_p4_iter3\handoff.md

## 2026-11-01T03:11:38Z
You are Worker (Iter 3: Surgical Text Cleanup & Final Certification).
Your working directory is: C:\ParasiteAI\.agents\teamwork\teamwork_worker_p4_iter3\
Read C:\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md first (mandatory).
Read your dispatch instructions at: C:\ParasiteAI\.agents\teamwork\teamwork_worker_p4_iter3\DISPATCH.md
Read Challenger 1's report: C:\ParasiteAI\.agents\teamwork\teamwork_challenger_p4_iter2_1\handoff.md

Target File to update:
`c:\Users\Suici\.gemini\antigravity\brain\464b4ef0-398b-45b1-94dc-857256a38046\phase_4_master_plan.md`

Your Task:
Apply the 3 surgical text cleanups specified in Section 5 of Challenger 1's report:
1. Clean Section 5.2 (lines 578-584):
   Remove the stray duplicate block:
   ```python
   ```json[\s\S]*?```", "", text)
           text = re.sub(r"[{}\[\]\"]", "", text)
           text = re.sub(r"\b\d+x\d+\b", "", text)
           text = re.sub(r"\(\d+,\s*\d+\)", "", text)
           return " ".join(text.split()).strip()
   ```
   So that line 578 (`return " ".join(text.split()).strip()`) is followed immediately by the closing code fence (```).
2. Clean Docstrings Across Master Plan:
   Replace all 12 occurrences of literal escaped `\"\"\"` with unescaped `"""` (specifically at lines 253, 262, 328, 729, 732, 763, 766, 802, 805, 992, 995).
3. Seal CLI Sandbox Web Scraping Loophole (Section 6.4):
   In `CLIExecutionSandbox.FORBIDDEN_PATTERNS`, append:
   ```python
           r"\b(?:Invoke-WebRequest|iwr|Invoke-RestMethod|irm)\b",
           r"\brequests\b",
   ```
4. Run verification tests:
   `& "C:\ParasiteAI\.venv\Scripts\python.exe" -m pytest tests/test_challenger_p4_iter2_c1.py -v` (Must pass 8/8 green).
   `& "C:\ParasiteAI\.venv\Scripts\python.exe" -m pytest tests/test_living_plan.py tests/test_gemini_consultation_protocol.py tests/test_interrupt_guard.py tests/test_dual_mind.py tests/test_challenger_p4_empirical.py` (Must pass 78/78 green).
5. Synchronize mirror file:
   `c:\Users\Suici\.gemini\antigravity\brain\c0750c5c-4354-4aa0-b198-17e98f598cf7\phase_4_master_plan.md`.

