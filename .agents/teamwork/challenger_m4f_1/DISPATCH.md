# DISPATCH — Challenger 1 (Milestone 4F: Ctypes ABI Adversarial Verification)

## Mission
Adversarially challenge and stress-test the Win32 ctypes struct implementations on 64-bit ABI (VERIF-9).

## Key Context & Paths
- Master Plan: `c:\Users\Suici\.gemini\antigravity\brain\464b4ef0-398b-45b1-94dc-857256a38046\phase_4_master_plan.md` (§9.2, §12 VERIF-9)
- Original Request: `C:\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md`
- Scope: `C:\ParasiteAI\.agents\teamwork\orchestrator_4\SCOPE.md`
- Worker Handoff: `C:\ParasiteAI\.agents\teamwork\teamwork_worker_m4f\handoff.md`
- Your Workspace: `C:\ParasiteAI\.agents\teamwork\challenger_m4f_1\`

## Target Adversarial Areas
1. Structure packing and alignment in 64-bit Windows ABI:
   - Verify compiler padding bytes in `MSLLHOOKSTRUCT`, `MOUSEINPUT`, `INPUT`.
   - Verify alignment of `INPUT_UNION` and field overlaps between `mi`, `ki`, `hi`.
   - Verify 64-bit pointer sizes (`HWND`, `c_size_t`, `ULONG_PTR`).
2. Extreme values and byte-level serialization:
   - Inject bitmasks (`LLMHF_INJECTED = 0x01`, `LLKHF_INJECTED = 0x10`) into `flags` fields.
   - Verify ctypes memory casting and buffer compatibility (`ctypes.memmove`, `ctypes.string_at`).
3. Author empirical test suite `tests/test_challenger_m4f_ctypes.py`.
4. Run via `.\.venv\Scripts\python.exe -m pytest tests/test_challenger_m4f_ctypes.py -v`.
5. Write `handoff.md` in `C:\ParasiteAI\.agents\teamwork\challenger_m4f_1\` with explicit verdict `APPROVE` or `REQUEST_CHANGES` and notify orchestrator.

## 2026-11-01T13:43:38Z
You are Challenger 1 for Milestone 4F (Ctypes ABI Adversarial Verification).
Your working directory is C:\ParasiteAI\.agents\teamwork\challenger_m4f_1\.
Read your instructions in C:\ParasiteAI\.agents\teamwork\challenger_m4f_1\DISPATCH.md.
Also read ORIGINAL_REQUEST.md at C:\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md, SCOPE.md at C:\ParasiteAI\.agents\teamwork\orchestrator_4\SCOPE.md, and the worker handoff at C:\ParasiteAI\.agents\teamwork\teamwork_worker_m4f\handoff.md.
Adversarially challenge and stress-test the Win32 ctypes struct implementations on 64-bit ABI (VERIF-9). Verify structure packing, compiler padding, field offsets, union overlaps, and bitmask injection (LLMHF_INJECTED, LLKHF_INJECTED).
Author tests/test_challenger_m4f_ctypes.py and run via .\.venv\Scripts\python.exe -m pytest tests/test_challenger_m4f_ctypes.py -v.
Write handoff.md in C:\ParasiteAI\.agents\teamwork\challenger_m4f_1\ with explicit verdict APPROVE or REQUEST_CHANGES and send message back to orchestrator.

## 2026-11-01T13:51:33Z
**Context**: Milestone 4F Ctypes Verification
**Content**: Note that the package name in this repo is `parasite_ai` (not `src/parasite`). All 10 structs are exported in `parasite_ai.input.types`. See `tests/test_schema_mapping.py` for reference implementations. Author your adversarial tests in `tests/test_challenger_m4f_ctypes.py` and run via `.\.venv\Scripts\python.exe -m pytest tests/test_challenger_m4f_ctypes.py -v`.
**Action**: Implement `tests/test_challenger_m4f_ctypes.py`, run pytest, and submit `handoff.md`.
