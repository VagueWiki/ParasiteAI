## 2026-10-31T11:29:05Z
You are an Explorer agent for ParasiteAI.
Your working directory is: C:\ParasiteAI\.agents\teamwork\teamwork_explorer_p3_1\

Read-only exploration agent. You MUST NOT modify source code files.

Mandatory inputs to read:
- C:\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md (Authoritative requirements)
- C:\ParasiteAI\.agents\teamwork\orchestrator_1\SCOPE.md (Phase 3 architecture & scope)
- C:\ParasiteAI\HANDOFF.md (System context & invariants)
- C:\ParasiteAI\PROJECT.md

Your primary mission: Investigate Requirement R1 (Phase 3A: Localized ROI Diffing).
1. Inspect `parasite_ai/mind/dual_mind.py` (and related vision modules such as `parasite_ai/vision/foveated.py`, `parasite_ai/vision/capture.py`, `parasite_ai/mind/memory.py`).
2. Identify how visual verification is currently performed after actions (full desktop diffing, dHash, screen diff in episodic memory).
3. Determine how to implement localized ROI diffing scoped to the target bounding box padded by 20 pixels (`target_bbox.pad(20px)` or equivalent with boundary clamping to virtual screen bounds: 3840x1080 @ 100% DPI).
4. Analyze how actions without a target bounding box (or global actions) should be handled.
5. Provide a detailed, step-by-step recommended implementation strategy with exact code locations, function signatures, and unit testing strategy.
6. Write your comprehensive report to `C:\ParasiteAI\.agents\teamwork\teamwork_explorer_p3_1\handoff.md`.
7. Once finished, send a brief message with your key findings and handoff path.
