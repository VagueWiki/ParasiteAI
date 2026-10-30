# Task Assignment: Milestone M4 Explorer 1 (Hybrid Screen Grounding)

**Recipient**: `teamwork_explorer_m4_1`
**Role**: `teamwork_explorer`
**Working Directory**: `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m4_1\`
**Assigned Milestone**: Milestone M4 — Perception, Memory & Browser Brain Offload

---

## Focus Area: Feature 12 — Hybrid Screen Grounding (`parasite_ai/vision/grounding.py`)
1. **Requirements to Analyze**:
   - `ORIGINAL_REQUEST.md` (Requirement R4: Visual Grounding & Vision Fallback).
   - `PROJECT.md` Feature 12 & survey reports.
2. **Architecture & Scope**:
   - Win32 UI Automation (UIA) tree walking: querying interactive elements (`Button`, `Edit`, `Hyperlink`, `ComboBox`, `ListItem`, etc.) in the active foreground window.
   - Scoped OCR fallback: using RapidOCR or lightweight OCR engine when UIA tree yields sparse controls or for non-standard UI elements (canvas, custom toolkits).
   - Spatial deduplication: IoU (Intersection-over-Union) suppression to prevent overlapping OCR text boxes from duplicating native UIA elements.
   - Bounding box mapping: producing normalized `list[UIElement]` (from `parasite_ai/ui/types.py`) tagged with `[#1..#N]` for direct consumption by `GhostHUD.set_targets()` and `CompanionDock`.
   - Performance budget: full grounding scan in < 500ms.
3. **Investigation Tasks**:
   - Check available libraries in the environment (`pywinauto`, `comtypes`, `rapidocr_onnxruntime`, `opencv-python`, `Pillow`).
   - Define the `ScreenGrounder` class interface, initialization, scan methods, UIA enumeration, OCR invocation, spatial filtering, and error handling.
   - Specify automated test strategy in `tests/test_screen_grounder.py` (mocked UIA trees, synthetic desktop screenshots, IoU deduplication verification).
4. **Deliverables**:
   - Write comprehensive implementation plan in `plan.md`.
   - Write handoff report in `handoff.md`.
   - Notify orchestrator via `send_message`.
