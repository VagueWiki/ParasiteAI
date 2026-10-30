# Dispatch for Explorer M3 (1/3)

Working Directory: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m3_1\
Original Request: g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md
Project Spec: g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md
Survey 3 Report: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_survey_3\survey_report.md
Existing Config: g:\__Docs\ParasiteAI\parasite_ai\config.py

Milestone: M3 — Desktop Companion Dock & Ghost-Hand Overlay
Focus: Companion Dock GUI (`parasite_ai/ui/companion_dock.py`)
Requirements:
1. Always-on-top frameless PyQt6 widget (`Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool`).
2. Sizing and anchor: default 340x540px, anchored bottom-right of primary screen with 24px margins, click-and-drag repositioning.
3. Visual states & mood badges:
   - States: `WATCHING` (Green), `THINKING` (Amber), `DRIVING` (Red), `USER_OVERRIDE` (Cyan), `OFFLOADING` (Purple), `PROTECTED` (Grey).
   - Mood indicator: `Curious`, `Focused`, `Cautious`, `Amused`, etc.
4. Internal thought stream widget (muted italic text) + Character speech bubble (high-contrast dialogue card).
5. Action telemetry feed (target ID, action mode, step progress).
6. Live perception thumbnail preview (QPixmap/QImage downscaled).
7. Interactive controls:
   - Goal input (QLineEdit + Send button, Enter key trigger)
   - Pause / Resume toggle button
   - Emergency Panic button (red, instant trigger)
   - Toggle screen tags checkbox
   - Brain mode toggle (Local GGUF vs Browser Offload)
8. PySide6 / PyQt6 Signal architecture: `sig_status_changed`, `sig_thought_updated`, `sig_speech_updated`, `sig_telemetry_updated`, `sig_perception_updated`, `sig_goal_submitted`, `sig_pause_toggled`, `sig_panic_triggered`, `sig_hud_toggled`.
9. Headless testability using `pytest-qt` (`qtbot`).

Deliverable:
Technical implementation plan in `plan.md` and structured `handoff.md`.


## 2026-10-29T15:47:40Z
You are teamwork_explorer_m3_1, Explorer 1 for Milestone M3: Desktop Companion Dock & Ghost-Hand Overlay.

Your working directory is: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m3_1\

You MUST read:
1. ORIGINAL_REQUEST: g:\__Docs\ParasiteAI\.agents\teamwork\ORIGINAL_REQUEST.md
2. Master Project Spec: g:\__Docs\ParasiteAI\.agents\teamwork\orchestrator\PROJECT.md
3. Your Dispatch: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m3_1\DISPATCH.md
4. Survey 3 Report: g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_survey_3\survey_report.md
5. Existing Config in `parasite_ai/config.py` (specifically `UIConfig`, `DockConfig`)

Focus:
Companion Dock GUI (`parasite_ai/ui/companion_dock.py`)

Technical Specifications Needed:
1. PyQt6 frameless always-on-top window (`WindowStaysOnTopHint | FramelessWindowHint | Tool`).
2. Sizing, screen anchoring (bottom-right 24px margin), click-and-drag repositioning.
3. State & mood indicators: `WATCHING` (Green), `THINKING` (Amber), `DRIVING` (Red), `USER_OVERRIDE` (Cyan), `OFFLOADING` (Purple), `PROTECTED` (Grey).
4. Internal thought stream widget (muted italic text) + Character speech bubble (high-contrast dialogue card).
5. Action telemetry feed + Live perception preview thumbnail.
6. Interactive controls: Goal input (QLineEdit + Send, Enter key), Pause/Resume toggle, Emergency Panic button, Toggle HUD tags checkbox, Brain Mode toggle.
7. Complete Qt Signal architecture: `sig_status_changed`, `sig_thought_updated`, `sig_speech_updated`, `sig_telemetry_updated`, `sig_perception_updated`, `sig_goal_submitted`, `sig_pause_toggled`, `sig_panic_triggered`, `sig_hud_toggled`.
8. Test specifications for `pytest-qt` (`qtbot`).

Deliverable:
Write your complete technical implementation plan in `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m3_1\plan.md` and your final report in `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m3_1\handoff.md`.
When finished, notify the orchestrator via send_message.
