"""
tests/test_launch_grounding_fix.py - Unit tests validating launch grounding, Run dialog redirection,
premature DONE interception, and process attribution fixes.
"""

from unittest.mock import MagicMock
import pytest

from parasite_ai.config import get_default_config
from parasite_ai.hands.keyboard import KeyboardDriver
from parasite_ai.mind.brain_manager import LlamaCppBackend, LocalBrainManager, MockBackend
from parasite_ai.mind.dual_mind import DualMindPipeline, PersonaEngine
from parasite_ai.mind.memory import ActionPlan, ActionType, EpisodicMemory
from parasite_ai.mind.plan import LivingPlan, PlanStep, StepIntent, verify_step_completion
from parasite_ai.safety.window_guard import WindowInfo
from parasite_ai.ui.types import UIElement
from parasite_ai.vision.grounding import ScreenGrounder


def test_uielement_and_som_summary_process_attribution() -> None:
    """Validates that UIElement carries process_name and window_title and formats them in SOM summary."""
    grounder = ScreenGrounder()
    elem1 = UIElement.from_bbox(
        id=1,
        bbox=(26, 26, 993, 519),
        label="Text Area",
        role="Document",
        process_name="WindowsTerminal.exe",
        window_title="Developer PowerShell",
    )
    elem2 = UIElement.from_bbox(
        id=2,
        bbox=(230, 934, 297, 17),
        label="Open:",
        role="Edit",
        process_name="explorer.exe",
        window_title="Run",
    )

    summary = grounder.format_som_summary([elem1, elem2])
    assert 'app: WindowsTerminal.exe' in summary
    assert 'window: "Developer PowerShell"' in summary
    assert 'app: explorer.exe' in summary
    assert 'window: "Run"' in summary


def test_verify_step_completion_rejects_non_matching_active_window() -> None:
    """
    Validates that verify_step_completion for LAUNCH_OR_ACTIVATE rejects visual diff >= 0.02
    when current_window is known and does not match target_app (e.g. Run dialog open instead of Notepad).
    """
    step = PlanStep(
        step_id=1,
        intent=StepIntent.LAUNCH_OR_ACTIVATE,
        description="Launch or focus target application: notepad",
        target_description="notepad",
        success_criteria="Application 'notepad' is visible and active on desktop",
    )
    action = ActionPlan(action=ActionType.HOTKEY, keys=["win", "r"], reasoning="Open Windows Run dialog")
    from parasite_ai.mind.dual_mind import ActionResult
    result = ActionResult(success=True)

    # Active window is the Run dialog (explorer.exe), NOT notepad
    run_dialog_window = WindowInfo(
        hwnd=1234,
        title="Run",
        class_name="#32770",
        process_name="explorer.exe",
        process_path="C:\\Windows\\explorer.exe",
        pid=999,
        rect=(100, 800, 500, 1000),
        is_sensitive=False,
        reason="",
    )

    # Even with high screen diff (e.g. 0.22), it must NOT declare launch complete
    assert verify_step_completion(step, action, result, screen_diff=0.22, current_window=run_dialog_window) is False

    # Once Notepad becomes the active window, it must verify successfully
    notepad_window = WindowInfo(
        hwnd=5678,
        title="Untitled - Notepad",
        class_name="Notepad",
        process_name="notepad.exe",
        process_path="C:\\Windows\\notepad.exe",
        pid=1000,
        rect=(50, 50, 800, 600),
        is_sensitive=False,
        reason="",
    )
    assert verify_step_completion(step, action, result, screen_diff=0.0, current_window=notepad_window) is True


def test_dual_mind_redirects_run_dialog_launch() -> None:
    """
    Validates that when the Run dialog is open and target app is not active,
    misdirected clicks targeting background windows are redirected to type target app into the Run dialog.
    """
    mock_brain = MagicMock()
    mock_brain.generate_thought.return_value = "I see the Run dialog and a text area."
    # Brain attempts to click the background text area (Target 1) instead of the Run edit box (Target 2)
    mock_brain.generate_action.return_value = {
        "action": "CLICK",
        "target_id": 1,
        "reasoning": "Clicking background text area mistakenly",
    }

    elements = [
        UIElement.from_bbox(
            id=1,
            bbox=(26, 26, 993, 519),
            label="Text Area",
            role="Document",
            process_name="WindowsTerminal.exe",
            window_title="Developer PowerShell",
        ),
        UIElement.from_bbox(
            id=2,
            bbox=(230, 934, 297, 17),
            label="Open:",
            role="Edit",
            process_name="explorer.exe",
            window_title="Run",
        ),
    ]

    pipeline = DualMindPipeline(brain_manager=mock_brain)
    mock_guard = MagicMock()
    mock_guard.get_active_window.return_value = WindowInfo(
        hwnd=1234,
        title="Run",
        class_name="#32770",
        process_name="explorer.exe",
        process_path="",
        pid=999,
        rect=(0, 0, 400, 300),
        is_sensitive=False,
        reason="",
    )
    pipeline.window_guard = mock_guard

    rec = pipeline.step(
        user_goal="open notepad and write an introduction",
        grounded_elements=elements,
    )

    # Must be redirected to CLICK_AND_TYPE into Target 2 with "notepad" and submit=True
    assert rec.action.action == ActionType.CLICK_AND_TYPE
    assert rec.action.target_id == 2
    assert "notepad" in (rec.action.text or "").lower()
    assert rec.action.submit is True


def test_dual_mind_intercepts_premature_done() -> None:
    """
    Validates that if the brain emits DONE before the target application is active,
    DualMind intercepts premature DONE and resolves application launch.
    """
    mock_brain = MagicMock()
    mock_brain.generate_thought.return_value = "I think the goal is finished."
    mock_brain.generate_action.return_value = {
        "action": "DONE",
        "reasoning": "Task completed prematurely",
    }

    elements = [
        UIElement.from_bbox(
            id=1,
            bbox=(26, 26, 993, 519),
            label="Text Area",
            role="Document",
            process_name="WindowsTerminal.exe",
            window_title="Developer PowerShell",
        ),
    ]

    pipeline = DualMindPipeline(brain_manager=mock_brain)
    mock_guard = MagicMock()
    mock_guard.get_active_window.return_value = WindowInfo(
        hwnd=1234,
        title="Developer PowerShell",
        class_name="ConsoleWindowClass",
        process_name="WindowsTerminal.exe",
        process_path="",
        pid=999,
        rect=(0, 0, 400, 300),
        is_sensitive=False,
        reason="",
    )
    pipeline.window_guard = mock_guard

    rec = pipeline.step(
        user_goal="open notepad and write an introduction",
        grounded_elements=elements,
    )

    # Must NOT execute DONE; must initiate launch (e.g. Win key or Win+R hotkey)
    assert rec.action.action != ActionType.DONE
    assert rec.action.action in (ActionType.HOTKEY, ActionType.CLICK, ActionType.CLICK_AND_TYPE)


def test_format_concise_scene_summary() -> None:
    """Verifies that format_concise_scene_summary generates a high-level summary without coordinate clutter."""
    grounder = ScreenGrounder()
    elements = [
        UIElement.from_bbox(
            id=1,
            bbox=(10, 10, 200, 50),
            label="File",
            role="MenuItem",
            process_name="notepad.exe",
            window_title="Untitled - Notepad",
            is_active_window=True,
        ),
        UIElement.from_bbox(
            id=2,
            bbox=(10, 60, 500, 400),
            label="Text Editor",
            role="Edit",
            process_name="notepad.exe",
            window_title="Untitled - Notepad",
            is_active_window=True,
        ),
        UIElement.from_bbox(
            id=3,
            bbox=(0, 0, 50, 50),
            label="Recycle Bin",
            role="ListItem",
            process_name="explorer.exe",
            window_title="Program Manager",
            is_active_window=False,
        ),
    ]

    summary = grounder.format_concise_scene_summary(elements)
    assert 'Active Window: "Untitled - Notepad" (app: notepad.exe)' in summary
    assert "notepad.exe" in summary
    assert "Key Controls:" in summary
    assert '[#1] MenuItem "File"' in summary
    assert "Background/Desktop Targets: 1 other items" in summary
    # Must NOT contain raw coordinates
    assert " at (" not in summary


def test_persona_engine_sanitizes_echoed_som_table() -> None:
    """Verifies PersonaEngine._sanitize_monologue_text strips out echoed SOM headers and coordinate lists."""
    hallucinated_text = (
        "I need to open notepad.\n\n"
        "### Grounded Screen Targets [Set-of-Mark]:\n"
        "- [#1] Document \"Text Area\" at (2625, 454) [993x519] [app: conhost.exe]\n"
        "- [#2] Button \"Minimize\" at (2998, 211) [47x30] [app: conhost.exe]\n"
    )
    cleaned = PersonaEngine._sanitize_monologue_text(hallucinated_text)
    assert cleaned == "I need to open notepad."
    assert "### Grounded Screen Targets" not in cleaned
    assert "2625, 454" not in cleaned


def test_generate_action_dynamic_token_budget_truncation() -> None:
    """Verifies generate_action adaptively compacts elements and fits within token budgets."""
    cfg = get_default_config()
    cfg.brain.mode = "mock"
    manager = LocalBrainManager(cfg)

    # Generate 80 large elements
    large_elements = [
        {
            "id": i,
            "role": "Button",
            "label": f"Very Long Descriptive Button Label Name Number {i} That Consumes Significant Characters",
            "x": i * 10,
            "y": i * 10,
            "width": 100,
            "height": 30,
            "app": "very_long_process_name_for_testing.exe",
            "window": "Very Long Window Title For Testing Application Context Window",
        }
        for i in range(1, 81)
    ]

    action = manager.generate_action(
        persona_intent="Click the target button to start",
        som_elements=large_elements,
        memory_context="Step 1 completed successfully with visual change 0.05",
    )
    assert isinstance(action, dict)
    assert "action" in action

    # Verify MockBackend call history received prompt with compact elements
    mock_backend: MockBackend = manager.active_backend  # type: ignore
    assert len(mock_backend._call_history) > 0
    last_call = mock_backend._call_history[-1]
    prompt_used = last_call["prompt"]
    # Check that it did NOT dump 80 elements into the prompt
    assert prompt_used.count('"id":') <= 45
    assert prompt_used.count('"id":') < 80
    # Check that redundant keys like 'width' and 'height' were not serialized
    assert '"width":' not in prompt_used


def test_llamacpp_backend_resilient_context_window_recovery() -> None:
    """Verifies that LlamaCppBackend recovers gracefully if llama_cpp raises context overflow ValueError."""
    backend = LlamaCppBackend(model_path="synthetic_stub.gguf", n_ctx=4096)
    mock_llm = MagicMock()

    # First call raises context window overflow, second call succeeds
    mock_llm.tokenize.side_effect = Exception("bypass pre-check")
    mock_llm.create_chat_completion.side_effect = [
        ValueError("Requested tokens (4751) exceed context window of 4096"),
        {"choices": [{"message": {"content": '{"action": "CLICK", "target_id": 1}'}}]},
    ]
    backend._llm = mock_llm

    res = backend.generate(prompt="Long test prompt", system_prompt="System instructions")
    assert '{"action": "CLICK", "target_id": 1}' in res
    assert mock_llm.create_chat_completion.call_count == 2


def test_click_and_type_clears_first() -> None:
    """Verifies that click_and_type with clear_first=True sends Ctrl+A and Backspace."""
    mock_backend = MagicMock()
    mock_backend.sleep_interruptible.return_value = False
    driver = KeyboardDriver(backend=mock_backend)
    driver.hotkey = MagicMock(return_value=True)  # type: ignore
    driver.type_text = MagicMock(return_value=True)  # type: ignore
    driver._raw_mouse_click = MagicMock(return_value=True)  # type: ignore

    ok = driver.click_and_type(x=100, y=100, text="notepad", submit=True, clear_first=True)
    assert ok is True
    # Verify Ctrl+A and Backspace hotkeys were invoked
    calls = [call[0] for call in driver.hotkey.call_args_list]
    assert ("ctrl", "a") in calls
    assert ("backspace",) in calls
    driver.type_text.assert_called_once_with("notepad", submit=True, cancellation_token=None)


def test_verify_step_completion_rejects_error_dialog_and_non_word_boundary() -> None:
    """Verifies verify_step_completion rejects 'cmdnotepad' error dialog from explorer."""
    step = PlanStep(
        step_id=1,
        intent=StepIntent.LAUNCH_OR_ACTIVATE,
        description="Launch or focus target application: notepad",
        target_description="notepad",
        success_criteria="Application 'notepad' is visible and active on desktop",
    )
    action = ActionPlan(action=ActionType.CLICK_AND_TYPE, target_id=1, text="notepad")
    mock_res = MagicMock()
    mock_res.success = True
    mock_res.interrupted = False

    # Case 1: Windows error message box from explorer.exe titled 'cmdnotepad'
    err_win = WindowInfo(
        hwnd=9999,
        title="cmdnotepad",
        class_name="#32770",
        process_name="explorer.exe",
        process_path="",
        pid=100,
        rect=(0, 0, 300, 200),
        is_sensitive=False,
        reason="",
    )
    assert verify_step_completion(step, action, mock_res, 0.5, err_win) is False

    # Case 2: Legitimate Notepad++ or Notepad window
    npp_win = WindowInfo(
        hwnd=8888,
        title="*new 1 - Notepad++",
        class_name="Notepad++",
        process_name="notepad++.exe",
        process_path="",
        pid=200,
        rect=(0, 0, 800, 600),
        is_sensitive=False,
        reason="",
    )
    assert verify_step_completion(step, action, mock_res, 0.5, npp_win) is True


def test_grounding_detects_scintilla_editor_pane_as_document() -> None:
    """Verifies that Scintilla editor pane in Notepad++ is grounded as Document 'Editor Canvas'."""
    from unittest.mock import patch
    from tests.conftest import MockControl

    grounder = ScreenGrounder()

    mock_ctl = MockControl("", "PaneControl", 100, 100, 1000, 600)
    mock_ctl.ClassName = "Scintilla"

    mock_win = MockControl("*new 1 - Notepad++", "WindowControl", 100, 100, 1000, 600)
    mock_win.ClassName = "Notepad++"

    mock_auto = MagicMock()
    mock_auto.GetForegroundControl.return_value = mock_win
    mock_auto.GetRootControl.return_value = MagicMock(GetChildren=lambda: [mock_win])
    mock_auto.WalkControl.return_value = [(mock_ctl, 1)]

    with patch.dict("sys.modules", {"uiautomation": mock_auto}):
        grounder._is_hwnd_visible_and_uncloaked = lambda h: True  # type: ignore
        grounder._resolve_process_name = lambda hwnd=0, pid=0: "notepad++.exe"  # type: ignore
        elements = grounder.ground()

    assert len(elements) >= 1
    doc_elem = next((e for e in elements if e.role == "Document"), None)
    assert doc_elem is not None
    assert doc_elem.label == "Editor Canvas"
    assert doc_elem.process_name == "notepad++.exe"


def test_dual_mind_intercepts_app_name_typing_in_document() -> None:
    """Verifies that typing 'notepad' into active Notepad++ is redirected to introduction content."""
    mock_brain = MagicMock()
    mock_brain.generate_thought.return_value = "Notepad is open. Now I will write the introduction."
    # Model mistakenly emits CLICK_AND_TYPE target 5 with text='notepad'
    mock_brain.generate_action.return_value = {
        "action": "CLICK_AND_TYPE",
        "target_id": 5,
        "text": "notepad",
        "submit": True,
        "reasoning": "Open Notepad and start typing",
    }

    elements = [
        UIElement.from_bbox(1, (10, 10, 100, 30), label="Minimize", role="Button", process_name="notepad++.exe", is_active_window=True),
        UIElement.from_bbox(2, (10, 60, 1000, 600), label="Editor Canvas", role="Document", process_name="notepad++.exe", is_active_window=True),
        UIElement.from_bbox(5, (10, 30, 40, 20), label="File", role="MenuItem", process_name="notepad++.exe", is_active_window=True),
    ]

    pipeline = DualMindPipeline(brain_manager=mock_brain)
    mock_guard = MagicMock()
    mock_guard.get_active_window.return_value = WindowInfo(
        hwnd=7777,
        title="*new 1 - Notepad++",
        class_name="Notepad++",
        process_name="notepad++.exe",
        process_path="",
        pid=300,
        rect=(0, 0, 1200, 800),
        is_sensitive=False,
        reason="",
    )
    pipeline.window_guard = mock_guard

    rec = pipeline.step(
        user_goal="open notepad and write yourself an introduction",
        grounded_elements=elements,
    )

    # Must target the Document (Target 2), NOT MenuItem File (Target 5)
    assert rec.action.target_id == 2
    # Must NOT submit with Enter in document
    assert rec.action.submit is False


def test_dual_mind_intercepts_literal_prompt_instruction_typing() -> None:
    """Verifies that typing in document canvas enforces submit=False without submitting newline."""
    mock_brain = MagicMock()
    mock_brain.generate_thought.return_value = "Writing self-introduction into the document canvas."
    mock_brain.generate_action.return_value = {
        "action": "CLICK_AND_TYPE",
        "target_id": 2,
        "text": "write yourself an introduction",
        "submit": True,
        "reasoning": "Executing user goal step",
    }

    elements = [
        UIElement.from_bbox(1, (10, 10, 100, 30), label="File", role="MenuItem", process_name="notepad.exe", is_active_window=True),
        UIElement.from_bbox(2, (10, 60, 1000, 600), label="Text Editor", role="Edit", process_name="notepad.exe", is_active_window=True),
    ]

    pipeline = DualMindPipeline(brain_manager=mock_brain)
    mock_guard = MagicMock()
    mock_guard.get_active_window.return_value = WindowInfo(
        hwnd=8888,
        title="*Untitled - Notepad",
        class_name="Notepad",
        process_name="notepad.exe",
        process_path="",
        pid=400,
        rect=(0, 0, 1200, 800),
        is_sensitive=False,
        reason="",
    )
    pipeline.window_guard = mock_guard

    rec = pipeline.step(
        user_goal="open notepad and write yourself an introduction",
        grounded_elements=elements,
    )

    assert rec.action.target_id == 2
    assert rec.action.submit is False


def test_dual_mind_intercepts_intro_abbreviation_and_redirects_menu_target() -> None:
    """Verifies that typing with menu target redirects to window center and suppresses submit."""
    mock_brain = MagicMock()
    # Persona monologue with thoughts about discord and the screen
    mock_brain.generate_thought.return_value = "Ah, looking at the scene, I see Discord is active, and I have guided you."
    mock_brain.generate_action.return_value = {
        "action": "CLICK_AND_TYPE",
        "target_id": 5,  # Menu item File
        "text": "notepad++",
        "submit": False,
        "reasoning": "Launch Notepad++",
    }

    # Only menu bar elements visible, no Document canvas in elements list
    elements = [
        UIElement.from_bbox(1, (10, 10, 30, 30), label="Minimize", role="Button", process_name="notepad++.exe", is_active_window=True),
        UIElement.from_bbox(5, (10, 40, 50, 20), label="File", role="MenuItem", process_name="notepad++.exe", is_active_window=True),
    ]

    pipeline = DualMindPipeline(brain_manager=mock_brain)
    mock_guard = MagicMock()
    mock_guard.get_active_window.return_value = WindowInfo(
        hwnd=9999,
        title="*new 1 - Notepad++",
        class_name="Notepad++",
        process_name="notepad++.exe",
        process_path="",
        pid=500,
        rect=(100, 100, 1100, 900),  # width=1000, height=800 -> center=(600, 500)
        is_sensitive=False,
        reason="",
    )
    pipeline.window_guard = mock_guard

    rec = pipeline.step(
        user_goal="open notepad++ and write yourself an intro.",
        grounded_elements=elements,
    )

    # Must NOT type into MenuItem File (#5)
    assert rec.action.target_id is None
    # Must click the client center (600, 500)
    assert rec.action.coordinates == (600, 500)
    assert rec.action.submit is False


def test_find_prompt_target_rejects_viewport_document_container() -> None:
    """Verifies BrowserOffloader rejects massive full-viewport document containers."""
    from parasite_ai.mind.offloader import BrowserOffloader

    mock_grounder = MagicMock()
    mock_win_backend = MagicMock()
    mock_win_backend.get_window_rect.return_value = (0, 0, 1920, 1000)

    offloader = BrowserOffloader(grounder=mock_grounder, window_backend=mock_win_backend)

    # Element 1: Giant full-screen document viewport (e.g. view_1034)
    huge_viewport = UIElement.from_bbox(
        1,
        (0, 80, 1920, 920),
        label="view_1034",
        role="Document",
        process_name="chrome.exe",
        is_active_window=True,
    )

    # Element 2: Actual prompt textarea near bottom of viewport
    chat_box = UIElement.from_bbox(
        2,
        (400, 880, 800, 60),
        label="Ask Gemini",
        role="Edit",
        process_name="chrome.exe",
        is_active_window=True,
    )

    # Element 3: Search bar at the top (should be rejected because y < min_input_y)
    top_search = UIElement.from_bbox(
        3,
        (200, 40, 500, 30),
        label="Search or enter URL",
        role="Edit",
        process_name="chrome.exe",
        is_active_window=True,
    )

    mock_grounder.ground.return_value = [huge_viewport, chat_box, top_search]
    target_pos = offloader._find_prompt_target(12345)

    assert target_pos == (chat_box.center_x, chat_box.center_y)


def test_interrupt_guard_cooldown_duration() -> None:
    """Verifies that the mouse/keyboard takeover cooldown was reduced to 2.5s."""
    from parasite_ai.config import SafetyConfig
    from parasite_ai.safety.interrupt_guard import InterruptGuard

    config = SafetyConfig()
    assert config.override_pause_duration_sec == 2.5

    guard = InterruptGuard()
    assert guard._cooldown_seconds == 2.5


def test_format_gemini_consultation_prompt_receives_elements_and_history() -> None:
    """Verifies format_gemini_consultation_prompt populates SOM inventory and history."""
    from parasite_ai.mind.plan import format_gemini_consultation_prompt

    elements = [
        UIElement.from_bbox(1, (10, 10, 80, 30), label="Editor Canvas", role="Document", process_name="notepad.exe", is_active_window=True),
        UIElement.from_bbox(2, (100, 10, 60, 30), label="File", role="MenuItem", process_name="notepad.exe", is_active_window=True),
    ]

    prompt = format_gemini_consultation_prompt(
        user_goal="write yourself an introduction",
        active_window_title="*Untitled - Notepad",
        process_name="notepad.exe",
        visual_scene_summary="2 targets detected",
        elements=elements,
        recent_history="Step 1: LAUNCH_OR_ACTIVATE Notepad -> SUCCESS",
    )

    # Prompt must contain the SOM inventory table with actual elements
    assert "Editor Canvas" in prompt
    assert "File" in prompt
    assert "notepad.exe" in prompt
    assert "Step 1: LAUNCH_OR_ACTIVATE Notepad -> SUCCESS" in prompt
    assert "No interactive controls detected" not in prompt
    assert "No prior actions recorded" not in prompt


def test_extract_target_app_play_verb_and_generic_filtering() -> None:
    """Verifies UniversalAppResolver.extract_target_app handles 'play', 'some', and filters generic words."""
    from parasite_ai.mind.resolver import UniversalAppResolver

    assert UniversalAppResolver.extract_target_app("play some rift wizard") == "rift wizard"
    assert UniversalAppResolver.extract_target_app("play rift wizard 2") == "rift wizard 2"
    assert UniversalAppResolver.extract_target_app("play the game rift wizard") == "rift wizard"
    assert UniversalAppResolver.extract_target_app("play some rift wizard please") == "rift wizard"
    assert UniversalAppResolver.extract_target_app("open discord") == "discord"
    assert UniversalAppResolver.extract_target_app("launch visual studio code and write code") == "visual studio code"

    # Generic words must be rejected
    assert UniversalAppResolver.extract_target_app("play some games") is None
    assert UniversalAppResolver.extract_target_app("possibly one that can launch games") is None
    assert UniversalAppResolver.extract_target_app("launch apps") is None


def test_precision_app_matcher_suffix_and_extension_matching() -> None:
    """Verifies PrecisionAppMatcher handles version suffixes, extensions (.url, .lnk), and desktop double click."""
    from parasite_ai.mind.resolver import PrecisionAppMatcher, UniversalAppResolver

    assert PrecisionAppMatcher.score_match("Rift Wizard 2", "rift wizard") >= 0.90
    assert PrecisionAppMatcher.score_match("Rift Wizard 2.url", "rift wizard") >= 0.90
    assert PrecisionAppMatcher.score_match("Rift Wizard", "rift wizard 2") >= 0.90
    assert PrecisionAppMatcher.score_match("Rift Wizard 2 - Shortcut", "rift wizard") >= 0.90

    # Test launching desktop icon emits DOUBLE_CLICK
    resolver = UniversalAppResolver()
    desktop_icon = UIElement.from_bbox(
        id=7,
        bbox=(50, 100, 48, 48),
        label="Rift Wizard 2",
        role="ListItem",
        process_name="explorer.exe",
        window_title="Program Manager",
        is_active_window=False,
    )
    plan = resolver.resolve_launch_action("rift wizard", [desktop_icon])
    assert plan.action == ActionType.DOUBLE_CLICK
    assert plan.target_id == 7
    assert plan.coordinates == (desktop_icon.center_x, desktop_icon.center_y)


def test_crowded_desktop_grounding_preserves_goal_matches() -> None:
    """Verifies that ScreenGrounder visits 150+ desktop items without dropping target past the old 120 cap."""
    grounder = ScreenGrounder()

    mock_auto = MagicMock()
    mock_desktop_win = MagicMock()
    mock_desktop_win.Name = "Program Manager"
    mock_desktop_win.NativeWindowHandle = 1001
    mock_desktop_win.ProcessId = 1234
    mock_bbox = MagicMock()
    mock_bbox.left, mock_bbox.top = 0, 0
    mock_bbox.width.return_value = 1920
    mock_bbox.height.return_value = 1080
    mock_desktop_win.BoundingRectangle = mock_bbox
    mock_auto.ControlFromHandle.return_value = mock_desktop_win
    grounder._resolve_process_name = MagicMock(return_value="explorer.exe")

    # Simulate 150 desktop icons, with Rift Wizard 2 at index 95
    walk_controls = []
    for i in range(150):
        name = "Rift Wizard 2" if i == 95 else f"Desktop App {i}"
        item_ctl = MagicMock()
        item_ctl.Name = name
        item_ctl.ControlTypeName = "ListItemControl"
        item_ctl.ClassName = "SysListView32"
        item_ctl.IsOffscreen = False
        item_ctl.NativeWindowHandle = 0
        c_box = MagicMock()
        c_box.left = (i % 10) * 100
        c_box.top = (i // 10) * 100
        c_box.width.return_value = 64
        c_box.height.return_value = 64
        c_box.xcenter.return_value = c_box.left + 32
        c_box.ycenter.return_value = c_box.top + 32
        item_ctl.BoundingRectangle = c_box
        walk_controls.append((item_ctl, 1))

        # Add child TextControl which should be deduplicated/skipped on desktop
        text_ctl = MagicMock()
        text_ctl.Name = name
        text_ctl.ControlTypeName = "TextControl"
        text_ctl.ClassName = "Static"
        text_ctl.IsOffscreen = False
        text_ctl.NativeWindowHandle = 0
        text_ctl.BoundingRectangle = c_box
        walk_controls.append((text_ctl, 2))

    mock_auto.WalkControl.return_value = walk_controls

    raw_elems, _ = grounder._walk_uia_tree_inner(
        mock_auto,
        window_filter=1001,
        goal_keywords=["rift", "wizard"],
    )

    # Check that deduplication skipped the redundant TextControl children (at most 150 items collected)
    assert len(raw_elems) <= 150
    # Check that Rift Wizard 2 at index 95 was collected
    labels = [e.label for e in raw_elems]
    assert "Rift Wizard 2" in labels

    # Normalize elements and verify Rift Wizard 2 is prioritized to Set-of-Mark #1
    normalized = grounder._normalize_elements(raw_elems, goal_keywords=["rift", "wizard"])
    assert len(normalized) > 0
    assert normalized[0].label == "Rift Wizard 2"
    assert normalized[0].id == 1


def test_dual_mind_play_some_rift_wizard_e2e() -> None:
    """Verifies that 'play some rift wizard' resolves desktop 'Rift Wizard 2' and executes double click."""
    mock_brain = MagicMock()
    # Persona monologue and thought
    mock_brain.generate_monologue.return_value = MagicMock(
        thought="I want to play some rift wizard. Let's launch the game.",
        speech="Starting Rift Wizard for you!",
    )
    # LLM action dispatcher initially suggests waiting or clicking
    mock_brain.generate_action.return_value = {
        "action": "CLICK",
        "target_id": 42,
        "coordinates": [224, 324],
        "reasoning": "Click Rift Wizard 2 to launch",
    }

    desktop_icon = UIElement.from_bbox(
        id=42,
        bbox=(200, 300, 48, 48),
        label="Rift Wizard 2",
        role="ListItem",
        process_name="explorer.exe",
        window_title="Program Manager",
        is_active_window=False,
    )

    pipeline = DualMindPipeline(brain_manager=mock_brain)
    mock_guard = MagicMock()
    mock_guard.get_active_window.return_value = WindowInfo(
        hwnd=1001,
        title="Program Manager",
        class_name="Progman",
        process_name="explorer.exe",
        process_path="",
        pid=1234,
        rect=(0, 0, 1920, 1080),
        is_sensitive=False,
        reason="",
    )
    pipeline.window_guard = mock_guard

    rec = pipeline.step(
        user_goal="play some rift wizard",
        grounded_elements=[desktop_icon],
    )

    # Must resolve to launching Rift Wizard 2 via DOUBLE_CLICK on desktop icon
    assert rec.action.action == ActionType.DOUBLE_CLICK
    assert rec.action.target_id == 42
    assert rec.action.coordinates == (224, 324)
    # Must NOT emit DONE
    assert rec.action.action != ActionType.DONE
    # Plan target must be 'rift wizard'
    assert pipeline.active_plan is not None
    assert "rift wizard" in pipeline.active_plan.steps[0].target_description.lower()


def test_grounding_preserves_occluded_goal_matches() -> None:
    """Verifies that an element matching goal keywords is preserved even if occluded by open windows."""
    grounder = ScreenGrounder()
    mock_auto = MagicMock()

    # Foreground window covering coordinates 100, 100 to 800, 600
    mock_win = MagicMock()
    mock_win.Name = "ParasiteAI Launcher"
    mock_win.ClassName = "ConsoleWindowClass"
    mock_win.NativeWindowHandle = 1001
    mock_win.ProcessId = 1234
    win_box = MagicMock()
    win_box.left, win_box.top, win_box.right, win_box.bottom = 100, 100, 800, 600
    win_box.width.return_value = 700
    win_box.height.return_value = 500
    mock_win.BoundingRectangle = win_box

    # Desktop window behind foreground window
    mock_desktop = MagicMock()
    mock_desktop.Name = "Program Manager"
    mock_desktop.ClassName = "Progman"
    mock_desktop.NativeWindowHandle = 1002
    mock_desktop.ProcessId = 5678
    d_box = MagicMock()
    d_box.left, d_box.top, d_box.right, d_box.bottom = 0, 0, 1920, 1080
    d_box.width.return_value = 1920
    d_box.height.return_value = 1080
    mock_desktop.BoundingRectangle = d_box

    # Desktop icon that is physically located behind the foreground window (pos: 300, 300)
    target_ctl = MagicMock()
    target_ctl.Name = "Rift Wizard 2"
    target_ctl.ControlTypeName = "ListItemControl"
    target_ctl.ClassName = "SysListView32"
    target_ctl.IsOffscreen = False
    target_ctl.NativeWindowHandle = 0
    t_box = MagicMock()
    t_box.left, t_box.top, t_box.right, t_box.bottom = 300, 300, 348, 348
    t_box.width.return_value = 48
    t_box.height.return_value = 48
    t_box.xcenter.return_value = 324
    t_box.ycenter.return_value = 324
    target_ctl.BoundingRectangle = t_box

    # Non-matching desktop icon also behind foreground window (pos: 400, 400)
    other_ctl = MagicMock()
    other_ctl.Name = "Random Other Shortcut"
    other_ctl.ControlTypeName = "ListItemControl"
    other_ctl.ClassName = "SysListView32"
    other_ctl.IsOffscreen = False
    other_ctl.NativeWindowHandle = 0
    o_box = MagicMock()
    o_box.left, o_box.top, o_box.right, o_box.bottom = 400, 400, 448, 448
    o_box.width.return_value = 48
    o_box.height.return_value = 48
    o_box.xcenter.return_value = 424
    o_box.ycenter.return_value = 424
    other_ctl.BoundingRectangle = o_box

    mock_auto.GetForegroundControl.return_value = mock_win
    mock_desktop_root = MagicMock()
    mock_desktop_root.GetChildren.return_value = [mock_win, mock_desktop]
    mock_auto.GetRootControl.return_value = mock_desktop_root

    def walk_side_effect(ctl, includeTop=False, maxDepth=10):
        if ctl == mock_win:
            return []
        if ctl == mock_desktop:
            return [(target_ctl, 1), (other_ctl, 1)]
        return []

    mock_auto.WalkControl.side_effect = walk_side_effect
    grounder._resolve_process_name = MagicMock(side_effect=lambda hwnd, pid: "conhost.exe" if pid == 1234 else "explorer.exe")
    grounder._is_hwnd_visible_and_uncloaked = MagicMock(return_value=True)

    raw_elems, _ = grounder._walk_uia_tree_inner(
        mock_auto,
        goal_keywords=["rift", "wizard"],
    )

    labels = [e.label for e in raw_elems]
    # Target matching goal keywords must be preserved despite occlusion
    assert "Rift Wizard 2" in labels
    # Non-matching occluded element must be dropped
    assert "Random Other Shortcut" not in labels


def test_dual_mind_dismisses_error_dialog() -> None:
    """Verifies that Windows error dialogs like 'Windows cannot find...' are dismissed via Enter."""
    mock_brain = MagicMock()
    mock_brain.generate_action.return_value = {"action": "WAIT"}
    pipeline = DualMindPipeline(brain_manager=mock_brain)
    mock_guard = MagicMock()
    mock_guard.get_active_window.return_value = WindowInfo(
        hwnd=999,
        title="Windows cannot find 'rift wizard'. Make sure you typed the name correctly.",
        class_name="#32770",
        process_name="explorer.exe",
        process_path="",
        pid=1234,
        rect=(200, 200, 400, 200),
        is_sensitive=False,
        reason="",
    )
    pipeline.window_guard = mock_guard

    rec = pipeline.step(user_goal="play some rift wizard", grounded_elements=[])
    assert rec.action.action == ActionType.HOTKEY
    assert rec.action.keys == ["enter"]


def test_dual_mind_prevents_file_explorer_search_box_hijack() -> None:
    """Verifies typing target app into File Explorer folder search box is intercepted."""
    mock_brain = MagicMock()
    mock_brain.generate_action.return_value = {
        "action": "CLICK_AND_TYPE",
        "target_id": 46,
        "text": "rift wizard",
        "reasoning": "Type rift wizard in search box",
    }
    pipeline = DualMindPipeline(brain_manager=mock_brain)
    search_elem = UIElement.from_bbox(
        id=46,
        bbox=(500, 80, 200, 30),
        label="Search Box",
        role="Edit",
        process_name="explorer.exe",
        window_title="ParasiteAI",
        is_active_window=True,
    )
    rec = pipeline.step(
        user_goal="play some rift wizard",
        grounded_elements=[search_elem],
    )
    # Must NOT execute CLICK_AND_TYPE into search box #46; should close unneeded folder window
    assert rec.action.target_id != 46
    assert rec.action.action == ActionType.CLOSE_WINDOW


def test_dual_mind_reveals_desktop_when_shortcut_is_obscured() -> None:
    """Verifies that if active persistent window obscures a desktop icon, it is minimized."""
    mock_brain = MagicMock()
    mock_brain.generate_action.return_value = {
        "action": "CLICK",
        "target_id": 1,
        "reasoning": "Click Rift Wizard 2 shortcut",
    }
    desktop_icon = UIElement.from_bbox(
        id=1,
        bbox=(200, 200, 48, 48),  # center=(224, 224)
        label="Rift Wizard 2",
        role="ListItem",
        process_name="explorer.exe",
        window_title="Program Manager",
        is_active_window=False,
    )
    pipeline = DualMindPipeline(brain_manager=mock_brain)
    mock_guard = MagicMock()
    # Active window covering coordinates (0, 0, 800, 600) including (224, 224)
    mock_guard.get_active_window.return_value = WindowInfo(
        hwnd=555,
        title="ParasiteAI Launcher",
        class_name="ConsoleWindowClass",
        process_name="conhost.exe",
        process_path="",
        pid=123,
        rect=(0, 0, 800, 600),
        is_sensitive=False,
        reason="",
    )
    pipeline.window_guard = mock_guard

    rec = pipeline.step(
        user_goal="play some rift wizard",
        grounded_elements=[desktop_icon],
    )
    # Must emit MINIMIZE_WINDOW to reveal desktop before attempting click
    assert rec.action.action == ActionType.MINIMIZE_WINDOW






