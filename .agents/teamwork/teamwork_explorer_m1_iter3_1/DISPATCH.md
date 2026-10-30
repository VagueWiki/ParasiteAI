## 2026-10-29T11:57:40Z
You are teamwork_explorer_m1_iter3_1.
Working Directory: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m1_iter3_1\
Original Request: g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md
Project Spec: g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md
Challenger Handoff: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_challenger_m1_iter2_1\handoff.md

Failure Context:
Test failure: `tests/test_challenger_m1_iter2_1.py::test_partial_streaming_clean_close_truncation_detection`
Defect: When an HTTP streaming download completes without exception, but `bytes_downloaded < real_total`, `LocalBrainManager._download_worker` in `parasite_ai/mind/brain_manager.py:770-795` renames the truncated `.tmp` file to `.gguf`. If the stub contains valid magic bytes `b"GGUF"` (e.g. 128 bytes), `validate_gguf_header` passes, and the truncated stub is promoted to `BrainState.MODEL_READY_ON_DISK` with `progress.status = 'completed'` and `100.0%`.

Mission:
Investigate and design an exact fix in `_download_worker` verifying:
1. If `real_total > 0` and `bytes_downloaded < real_total`: do NOT promote to `MODEL_READY_ON_DISK`. Delete or clean up the truncated `temp_path`, set `progress.status = 'error'`, and set `self.state = BrainState.ERROR_DOWNLOAD_FAILED` (or prior model state if one existed).
2. Provide exact code recommendations for Worker in `plan.md` and `handoff.md`. Message parent when done. Do NOT write source code.
