# Dispatch for Explorer M3 (2/3)

Working Directory: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m3_2\
Original Request: g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md
Project Spec: g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md
Survey 3 Report: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_survey_3\survey_report.md
Existing Config: g:\__Docs\ParasiteAI\parasite_ai\config.py

Milestone: M3 — Desktop Companion Dock & Ghost-Hand Overlay
Focus: Ghost-Hand Screen Overlay HUD (`parasite_ai/ui/ghost_hud.py`)
Requirements:
1. Fullscreen transparent click-through overlay spanning full virtual desktop (`QGuiApplication.primaryScreen().virtualGeometry()`).
2. Win32 extended window styles applied via `user32.SetWindowLongW` on `self.winId()`:
   - `WS_EX_LAYERED (0x00080000)`
   - `WS_EX_TRANSPARENT (0x00000020)` (clicks pass straight through!)
   - `WS_EX_TOPMOST (0x00000008)`
   - `WS_EX_NOACTIVATE (0x08000000)` (never steals focus)
   - `WS_EX_TOOLWINDOW (0x00000080)`
   - `Qt.WidgetAttribute.WA_TranslucentBackground` & `WA_TransparentForMouseEvents`.
3. Set-of-Mark (SoM) visual rendering with `QPainter`:
   - Numbered bounding boxes `[#1..#N]` over grounded UI elements.
   - Distinct color themes: Cyan for buttons (`#00e5ff`), Magenta for inputs (`#ff007f`), Gold Amber for OCR text (`#f59e0b`), Blue for links (`#3b82f6`).
   - High-contrast rounded pill badges with ID and element label.
4. 300ms Pre-Click Targeting Reticle & Path Preview:
   - Animated glowing crosshair and targeting brackets at `(target_x, target_y)`.
   - Floating banner: `Aiming: [#ID] Click in 300ms`.
   - Dynamic curved Bézier path preview from current cursor to target coordinate.
   - Clean clearing/timeout after click or upon interrupt abort.
5. Headless testability and simulation verification using `pytest-qt`.

Deliverable:
Technical implementation plan in `plan.md` and structured `handoff.md`.

## 2026-10-29T15:47:48Z
You are teamwork_explorer_m3_2, Explorer 2 for Milestone M3: Desktop Companion Dock & Ghost-Hand Overlay.

Your working directory is: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m3_2\

You MUST read:
1. ORIGINAL_REQUEST: g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md
2. Master Project Spec: g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md
3. Your Dispatch: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m3_2\DISPATCH.md
4. Survey 3 Report: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_survey_3\survey_report.md
5. Existing Config in `parasite_ai/config.py` (specifically `GhostHUDConfig`)

Focus:
Ghost-Hand Screen Overlay HUD (`parasite_ai/ui/ghost_hud.py`)

Technical Specifications Needed:
1. Fullscreen transparent click-through overlay spanning full virtual desktop (`QGuiApplication.primaryScreen().virtualGeometry()`).
2. Win32 extended window styles applied via `user32.SetWindowLongW` on `self.winId()`:
   - `WS_EX_LAYERED (0x00080000)`
   - `WS_EX_TRANSPARENT (0x00000020)` (clicks pass straight through to desktop!)
   - `WS_EX_TOPMOST (0x00000008)`
   - `WS_EX_NOACTIVATE (0x08000000)` (never steals focus)
   - `WS_EX_TOOLWINDOW (0x00000080)`
   - `Qt.WidgetAttribute.WA_TranslucentBackground` & `WA_TransparentForMouseEvents`.
3. Set-of-Mark (SoM) visual rendering with `QPainter`:
   - Numbered bounding boxes `[#1..#N]` over grounded UI elements.
   - Distinct color themes: Cyan for buttons (`#00e5ff`), Magenta for inputs (`#ff007f`), Gold Amber for OCR text (`#f59e0b`), Blue for links (`#3b82f6`).
   - High-contrast rounded pill badges with ID and element label.
4. 300ms Pre-Click Targeting Reticle & Path Preview:
   - Animated glowing crosshair and targeting brackets at `(target_x, target_y)`.
   - Floating banner: `Aiming: [#ID] Click in 300ms`.
   - Dynamic curved Bézier path preview from current cursor to target coordinate.
   - Clean clearing/timeout after click or upon interrupt abort.
5. Headless testability and simulation verification using `pytest-qt`.

Deliverable:
Write your complete technical implementation plan in `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m3_2\plan.md` and your final report in `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m3_2\handoff.md`.
When finished, notify the orchestrator via send_message.
