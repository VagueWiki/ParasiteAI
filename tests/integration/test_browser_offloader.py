"""
tests/test_browser_offloader.py - Automated Unit & Integration Tests for Visible Browser Offloader.

Tests Sentinel Clipboard Verification protocol, window focus/launch state machine,
multiline typing safety, hardware cancellation token preemption, and LocalBrainManager delegation.
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock
import pytest

from parasite_ai.config import AppConfig, BrowserOffloadConfig
from parasite_ai.mind.brain_manager import BrainMode, BrainState, LocalBrainManager
from parasite_ai.mind.offloader import (
    BrowserNotFoundError,
    BrowserOffloader,
    MockBrowserWindowBackend,
    MockClipboardBackend,
    OffloadHarvestError,
    OffloaderState,
    SentinelClipboardVerifier,
)
from parasite_ai.ui.types import UIElement


def test_sentinel_token_uniqueness() -> None:
    clip = MockClipboardBackend()
    verifier = SentinelClipboardVerifier(clipboard=clip, token_prefix="__TEST_SENTINEL__")

    tokens = [verifier.generate_sentinel() for _ in range(500)]
    assert len(set(tokens)) == 500
    for tok in tokens:
        assert tok.startswith("__TEST_SENTINEL__")


def test_sentinel_harvest_success() -> None:
    original_text = "Important User Notes on Clipboard"
    clip = MockClipboardBackend(initial_text=original_text)
    verifier = SentinelClipboardVerifier(clipboard=clip, poll_interval_s=0.01, default_timeout_s=1.0)

    ai_model_response = "Here is the step-by-step reasoning from web AI."

    def simulate_successful_copy() -> bool:
        # Check that sentinel is currently in the clipboard
        assert clip.get_text().startswith("__PARASITE_SENTINEL__")
        # Overwrite with AI response (simulating Ctrl+C from web UI)
        clip.set_text(ai_model_response)
        return True

    harvested = verifier.execute_harvest(trigger_copy_action=simulate_successful_copy)

    assert harvested == ai_model_response
    # Guaranteed restoration: original user clipboard must be restored!
    assert clip.get_text() == original_text


def test_sentinel_harvest_miss_or_no_change() -> None:
    original_text = "Secret User Password"
    clip = MockClipboardBackend(initial_text=original_text)
    verifier = SentinelClipboardVerifier(clipboard=clip, poll_interval_s=0.01, default_timeout_s=0.1)

    def simulate_missed_copy() -> bool:
        # Clicked whitespace; clipboard does not change from sentinel
        return True

    harvested = verifier.execute_harvest(trigger_copy_action=simulate_missed_copy)

    assert harvested is None
    # User clipboard restored without leaking original data
    assert clip.get_text() == original_text


def test_sentinel_harvest_empty_original_clip() -> None:
    clip = MockClipboardBackend(initial_text="")
    verifier = SentinelClipboardVerifier(clipboard=clip, poll_interval_s=0.01, default_timeout_s=0.5)

    def simulate_copy() -> bool:
        clip.set_text("Grounded result")
        return True

    harvested = verifier.execute_harvest(trigger_copy_action=simulate_copy)
    assert harvested == "Grounded result"
    assert clip.get_text() == ""


def test_sentinel_harvest_cancellation_token() -> None:
    original_text = "User Data"
    clip = MockClipboardBackend(initial_text=original_text)
    verifier = SentinelClipboardVerifier(clipboard=clip, poll_interval_s=0.01, default_timeout_s=2.0)

    token = threading.Event()

    def simulate_slow_copy() -> bool:
        # Trigger abort right after copy action
        token.set()
        return True

    harvested = verifier.execute_harvest(
        trigger_copy_action=simulate_slow_copy,
        cancellation_token=token,
    )

    assert harvested is None
    assert clip.get_text() == original_text


def test_locate_existing_browser_window() -> None:
    clip = MockClipboardBackend()
    win = MockBrowserWindowBackend(existing_hwnd=12345)
    offloader = BrowserOffloader(clipboard_backend=clip, window_backend=win)

    # When browser window exists (HWND 12345)
    def copy_action() -> bool:
        clip.set_text("Response text")
        return True

    # Mock verifier to harvest immediately
    offloader.verifier.execute_harvest = MagicMock(return_value="Answer from existing Chrome")

    resp = offloader.query_web_ai("Test question")
    assert resp == "Answer from existing Chrome"
    assert 12345 in win.focused_hwnds
    assert len(win.launched_calls) == 0


def test_launch_browser_when_missing(tmp_path: Any) -> None:
    clip = MockClipboardBackend()
    win = MockBrowserWindowBackend(existing_hwnd=None)  # Not open

    fake_chrome = tmp_path / "chrome.exe"
    fake_chrome.write_text("binary")

    cfg = BrowserOffloadConfig(
        browser_paths={"chrome": fake_chrome},
        stream_stability_ms=500,
    )
    offloader = BrowserOffloader(config=cfg, clipboard_backend=clip, window_backend=win)
    offloader.verifier.execute_harvest = MagicMock(return_value="Answer from launched Chrome")

    resp = offloader.query_web_ai("Test prompt")
    assert resp == "Answer from launched Chrome"
    assert len(win.launched_calls) == 1
    assert str(fake_chrome) in win.launched_calls[0][0]


def test_browser_offloader_full_flow() -> None:
    clip = MockClipboardBackend(initial_text="Pre-existing note")
    win = MockBrowserWindowBackend(existing_hwnd=5555)

    mock_kbd = MagicMock()
    mock_kbd.type_text.return_value = True
    mock_kbd.hotkey.return_value = True

    mock_mouse = MagicMock()
    mock_mouse.click.return_value = True

    bridge = MagicMock()

    cfg = BrowserOffloadConfig(stream_timeout_sec=10, stream_stability_ms=500)
    offloader = BrowserOffloader(
        config=cfg,
        clipboard_backend=clip,
        window_backend=win,
        keyboard_driver=mock_kbd,
        mouse_driver=mock_mouse,
        bridge=bridge,
    )

    expected_ai_output = "Task successfully completed by web AI."

    # Intercept copy trigger during verifier harvest
    orig_execute = offloader.verifier.execute_harvest

    def execute_with_simulated_paste(*args: Any, **kwargs: Any) -> str:
        clip.set_text(expected_ai_output)
        return expected_ai_output

    offloader.verifier.execute_harvest = execute_with_simulated_paste

    result = offloader.query_web_ai("Search for weather in Tokyo")

    assert result == expected_ai_output
    assert offloader.state == OffloaderState.COMPLETED
    mock_mouse.click.assert_called()
    mock_kbd.hotkey.assert_any_call("ctrl", "v", cancellation_token=None)
    mock_kbd.hotkey.assert_any_call("enter", cancellation_token=None)


def test_multiline_prompt_shift_enter() -> None:
    clip = MockClipboardBackend(initial_text="User Clip Backup")
    win = MockBrowserWindowBackend(existing_hwnd=1111)

    mock_kbd = MagicMock()
    mock_kbd.hotkey.return_value = True

    offloader = BrowserOffloader(
        clipboard_backend=clip,
        window_backend=win,
        keyboard_driver=mock_kbd,
    )
    offloader.verifier.execute_harvest = MagicMock(return_value="Success")

    prompt = "Line 1\nLine 2\nLine 3"
    offloader.query_web_ai(prompt)

    mock_kbd.hotkey.assert_any_call("ctrl", "v", cancellation_token=None)
    mock_kbd.hotkey.assert_any_call("enter", cancellation_token=None)
    assert clip.get_text() == "User Clip Backup"


def test_offloader_cancellation_during_typing() -> None:
    clip = MockClipboardBackend(initial_text="Important clip")
    win = MockBrowserWindowBackend(existing_hwnd=2222)

    mock_kbd = MagicMock()
    # Simulate user touch interrupt during paste hotkey
    mock_kbd.hotkey.return_value = False

    offloader = BrowserOffloader(
        clipboard_backend=clip,
        window_backend=win,
        keyboard_driver=mock_kbd,
    )

    with pytest.raises(OffloadHarvestError, match="aborted or interrupted"):
        offloader.query_web_ai("Hello")

    assert offloader.state == OffloaderState.FAILED
    assert clip.get_text() == "Important clip"


def test_brain_manager_fallback_delegation() -> None:
    cfg = AppConfig()
    cfg.brain.mode = "browser_offload"

    mock_offloader = MagicMock()
    mock_offloader.query_web_ai.return_value = "Offloaded response from Chrome"

    brain_manager = LocalBrainManager(config=cfg, offloader=mock_offloader)
    assert brain_manager.mode == BrainMode.BROWSER_OFFLOAD

    res = brain_manager.generate(prompt="What is the capital of France?")
    assert res == "Offloaded response from Chrome"
    mock_offloader.query_web_ai.assert_called_once()


def test_zero_vram_startup_mode(tmp_path: Any) -> None:
    """Verify local LLM mode without model on disk decouples without silent web offload mutation."""
    empty_models = tmp_path / "models"
    empty_models.mkdir()

    cfg = AppConfig()
    cfg.system.models_dir = empty_models
    cfg.brain.mode = "local_llm"  # Request local LLM, but no model exists on disk

    brain_manager = LocalBrainManager(config=cfg)

    # In decoupled mode: must NOT automatically mutate mode to browser_offload!
    status = brain_manager.get_status()
    assert brain_manager.mode == BrainMode.LOCAL_LLM
    assert brain_manager.state == BrainState.NO_MODEL_PRESENT
    assert status.mode == BrainMode.LOCAL_LLM
    assert status.state == BrainState.NO_MODEL_PRESENT
    assert brain_manager.active_backend is None


def test_sentinel_harvest_periodic_retrigger() -> None:
    """Verify SentinelClipboardVerifier periodically retriggers copy action while polling."""
    clip = MockClipboardBackend(initial_text="User Clip")
    verifier = SentinelClipboardVerifier(clipboard=clip, poll_interval_s=0.01, default_timeout_s=1.0)

    call_count = 0

    def delayed_copy() -> bool:
        nonlocal call_count
        call_count += 1
        if call_count >= 3:
            clip.set_text("Answer after 3 triggers")
        return True

    harvested = verifier.execute_harvest(trigger_copy_action=delayed_copy, retrigger_interval_s=0.03)
    assert harvested == "Answer after 3 triggers"
    assert call_count >= 3
    assert clip.get_text() == "User Clip"


def test_prompt_clipboard_injection_restores_user_clipboard() -> None:
    """Verify high-speed paste restores user clipboard safely."""
    clip = MockClipboardBackend(initial_text="KeepThisSecret")
    win = MockBrowserWindowBackend(existing_hwnd=9999)
    mock_kbd = MagicMock()
    mock_kbd.hotkey.return_value = True

    offloader = BrowserOffloader(
        clipboard_backend=clip,
        window_backend=win,
        keyboard_driver=mock_kbd,
    )
    offloader.verifier.execute_harvest = MagicMock(return_value="Output")

    resp = offloader.query_web_ai("Prompt with high speed paste")
    assert resp == "Output"
    mock_kbd.hotkey.assert_any_call("ctrl", "v", cancellation_token=None)
    mock_kbd.hotkey.assert_any_call("enter", cancellation_token=None)
    assert clip.get_text() == "KeepThisSecret"


def test_browser_offloader_grounded_selectors() -> None:
    clip = MockClipboardBackend()
    win = MockBrowserWindowBackend(existing_hwnd=12345)
    mock_mouse = MagicMock()
    mock_kbd = MagicMock()

    mock_grounder = MagicMock()
    mock_grounder.ground.return_value = [
        UIElement.from_bbox(id=1, bbox=(200, 700, 400, 60), label="Ask Gemini", role="Edit"),
        UIElement.from_bbox(id=2, bbox=(500, 500, 50, 30), label="Copy response", role="Button"),
    ]

    offloader = BrowserOffloader(
        clipboard_backend=clip,
        window_backend=win,
        mouse_driver=mock_mouse,
        keyboard_driver=mock_kbd,
        grounder=mock_grounder,
    )
    offloader.verifier.execute_harvest = MagicMock(return_value="Answer from grounded offload")

    resp = offloader.query_web_ai("Summarize this document")
    assert resp == "Answer from grounded offload"

    # Verify mouse clicked the grounded prompt box center (400, 730) instead of blind center-bottom
    clicked_coords = [(call.args[0], call.args[1]) for call in mock_mouse.click.call_args_list]
    assert (400, 730) in clicked_coords


def test_browser_offloader_rejects_gemini_demo_question_buttons() -> None:
    """Verify _find_prompt_target never clicks Gemini demo question buttons or starter chips."""
    clip = MockClipboardBackend()
    win = MockBrowserWindowBackend(existing_hwnd=12345)
    win.rect = (0, 0, 1920, 1080)

    mock_grounder = MagicMock()
    mock_grounder.ground.return_value = [
        # Gemini demo question button containing 'ask' and 'prompt' keywords in lower half of window
        UIElement.from_bbox(
            id=1,
            bbox=(600, 620, 260, 80),
            label="Ask Gemini to write a prompt for a sci-fi story",
            role="Button",
        ),
        # Another starter suggestion chip exposed as ListItem
        UIElement.from_bbox(
            id=2,
            bbox=(900, 620, 260, 80),
            label="Help me plan a trip",
            role="ListItem",
        ),
        # Actual bottom chat input box
        UIElement.from_bbox(
            id=3,
            bbox=(460, 960, 1000, 56),
            label="Enter a prompt here",
            role="Edit",
        ),
    ]

    offloader = BrowserOffloader(
        clipboard_backend=clip,
        window_backend=win,
        grounder=mock_grounder,
    )

    px, py = offloader._find_prompt_target(12345)
    # Must select the real Edit control (#3 at center 960, 988), NOT the demo Button (#1)
    assert (px, py) == (960, 988)


def test_browser_offloader_no_blind_center_screen_clicking_loop() -> None:
    """Verify trigger_copy does NOT blindly click the center of the screen when no Copy button is grounded."""
    clip = MockClipboardBackend(initial_text="Original")
    win = MockBrowserWindowBackend(existing_hwnd=12345)
    win.rect = (0, 0, 1920, 1080)

    mock_mouse = MagicMock()
    mock_mouse.click.return_value = True
    mock_kbd = MagicMock()
    mock_kbd.hotkey.return_value = True
    mock_kbd.type_text.return_value = True

    # Grounder finds the prompt box, but no Copy button yet on the first 2 polls, then finds Copy on poll 3
    poll_idx = 0

    def ground_side_effect(*args: Any, **kwargs: Any) -> list[UIElement]:
        nonlocal poll_idx
        poll_idx += 1
        elems = [
            UIElement.from_bbox(id=1, bbox=(460, 960, 1000, 56), label="Enter a prompt here", role="Edit"),
        ]
        if poll_idx >= 4:
            elems.append(
                UIElement.from_bbox(id=2, bbox=(520, 720, 40, 32), label="Copy response", role="Button")
            )
            clip.set_text("Harvested Gemini Blueprint")
        return elems

    mock_grounder = MagicMock()
    mock_grounder.ground.side_effect = ground_side_effect

    cfg = BrowserOffloadConfig(stream_timeout_sec=10, stream_stability_ms=500)
    offloader = BrowserOffloader(
        config=cfg,
        clipboard_backend=clip,
        window_backend=win,
        mouse_driver=mock_mouse,
        keyboard_driver=mock_kbd,
        grounder=mock_grounder,
    )
    offloader.verifier.poll_interval_s = 0.01

    res = offloader.query_web_ai("Provide strategy")
    assert res == "Harvested Gemini Blueprint"

    # Check all mouse click coordinates: must NEVER click (960, 788) (prompt_y - 200 center-screen fallback)
    clicked_coords = [(c.args[0], c.args[1]) for c in mock_mouse.click.call_args_list]
    assert (960, 788) not in clicked_coords
    assert (960, 748) not in clicked_coords
    # Only the prompt box (960, 988) and the grounded Copy button (540, 736) should be clicked
    assert (960, 988) in clicked_coords


def test_browser_offloader_relocates_monitor_2_window_to_monitor_1() -> None:
    """Verifies that an offloaded browser window located on Monitor 2 is snapped onto Monitor 1."""
    clip = MockClipboardBackend()
    win = MockBrowserWindowBackend(existing_hwnd=12345)
    # Window centered on Monitor 2 (x=2020..3420 -> cx=2720)
    win.rect = (2020, 100, 3420, 950)

    mock_mouse = MagicMock()
    mock_mouse.click.return_value = True
    mock_kbd = MagicMock()
    mock_kbd.hotkey.return_value = True

    offloader = BrowserOffloader(
        clipboard_backend=clip,
        window_backend=win,
        mouse_driver=mock_mouse,
        keyboard_driver=mock_kbd,
    )
    offloader.verifier.execute_harvest = MagicMock(return_value="Answer from relocated window")

    resp = offloader.query_web_ai("Provide strategy")
    assert resp == "Answer from relocated window"
    assert win.relocated is True
    # Window should now be on Monitor 1
    assert win.rect[0] >= 0 and win.rect[2] <= 1920
    # Coordinates of mouse click should fall on Monitor 1
    click_x, click_y = mock_mouse.click.call_args_list[0].args[:2]
    assert 0 <= click_x < 1920
    assert 0 <= click_y < 1080


def test_sanitize_consultation_prompt_redacts_secrets_and_api_keys() -> None:
    """Verifies that sensitive tokens, keys, and credentials are scrubbed before browser transmission."""
    from parasite_ai.mind.offloader import sanitize_consultation_prompt

    raw_prompt = (
        "Active Window: Chrome\n"
        "Config token: sk-proj-1234567890abcdefghij1234567890\n"
        "Google API key: AIzaSyD-1234567890abcdefghijklmnopqrstuvw\n"
        "GitHub token: ghp_1234567890abcdefghijklmnopqrstuvwx\n"
        "Auth header: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.t-ID\n"
        "Database: password = my_super_secret_db_pass; user = admin;\n"
        "User Goal: Fix connection error"
    )

    clean = sanitize_consultation_prompt(raw_prompt)

    assert "sk-proj-1234567890abcdefghij1234567890" not in clean
    assert "AIzaSyD-1234567890abcdefghijklmnopqrstuvw" not in clean
    assert "ghp_1234567890abcdefghijklmnopqrstuvwx" not in clean
    assert "my_super_secret_db_pass" not in clean
    assert "[REDACTED_API_KEY]" in clean
    assert "password=[REDACTED_SECRET]" in clean
    assert "User Goal: Fix connection error" in clean


def test_cua_single_pass_injects_advisor_blueprint_into_working_memory() -> None:
    """Verifies that an active strategic advisor plan is surfaced to UI-TARS via working_memory_context."""
    from parasite_ai.mind.dual_mind import DualMindPipeline
    from parasite_ai.mind.memory import ActionPlan, ActionType, EpisodicMemory
    from parasite_ai.mind.plan import LivingPlan, PlanStep, StepIntent

    mock_brain = MagicMock()
    mock_brain.supports_vision.return_value = True
    mock_brain.generate_cua_step.return_value = (
        "Executing advised step",
        ActionPlan(action=ActionType.CLICK, coordinates=(500, 500), reasoning="Click target"),
    )

    mem = EpisodicMemory()
    pipeline = DualMindPipeline(
        brain_manager=mock_brain,
        memory=mem,
        config=None,
    )

    # Inject an advisor-formulated plan
    advisor_plan = LivingPlan(
        user_goal="Dismiss modal error dialog",
        overall_strategy="Strategic Advisor: Click Close on blocking system error dialog",
        steps=[
            PlanStep(
                step_id=1,
                intent=StepIntent.DISMISS_DIALOG,
                description="Click Close button on modal error dialog",
                target_description="Close button",
                success_criteria="Dialog closes",
            ),
        ],
        current_step_id=1,
    )
    pipeline.active_plan = advisor_plan

    pipeline.step(user_goal="Dismiss modal error dialog")

    mock_brain.generate_cua_step.assert_called_once()
    kwargs = mock_brain.generate_cua_step.call_args.kwargs
    wm_ctx = kwargs.get("working_memory_context", "")

    assert "- Strategic Advisor Guidance: Step 1 (DISMISS_DIALOG) — Click Close button on modal error dialog (Target: Close button)" in wm_ctx



