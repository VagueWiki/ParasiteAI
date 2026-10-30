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
    mock_kbd.type_text.assert_called()


def test_multiline_prompt_shift_enter() -> None:
    clip = MockClipboardBackend()
    win = MockBrowserWindowBackend(existing_hwnd=1111)

    mock_kbd = MagicMock()
    mock_kbd.type_text.return_value = True
    mock_kbd.hotkey.return_value = True

    offloader = BrowserOffloader(
        clipboard_backend=clip,
        window_backend=win,
        keyboard_driver=mock_kbd,
    )
    offloader.verifier.execute_harvest = MagicMock(return_value="Success")

    prompt = "Line 1\nLine 2\nLine 3"
    offloader.query_web_ai(prompt)

    mock_kbd.type_text.assert_any_call(prompt, submit=True, cancellation_token=None)


def test_offloader_cancellation_during_typing() -> None:
    clip = MockClipboardBackend(initial_text="Important clip")
    win = MockBrowserWindowBackend(existing_hwnd=2222)

    mock_kbd = MagicMock()
    # Simulate user touch interrupt during typing
    mock_kbd.type_text.return_value = False

    offloader = BrowserOffloader(
        clipboard_backend=clip,
        window_backend=win,
        keyboard_driver=mock_kbd,
    )

    with pytest.raises(OffloadHarvestError, match="Typing was aborted"):
        offloader.query_web_ai("Hello")

    assert offloader.state == OffloaderState.FAILED


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
    empty_models = tmp_path / "models"
    empty_models.mkdir()

    cfg = AppConfig()
    cfg.system.models_dir = empty_models
    cfg.brain.mode = "local_llm"  # Request local LLM, but no model exists on disk

    brain_manager = LocalBrainManager(config=cfg)

    # Must automatically fallback to zero-VRAM browser offload!
    status = brain_manager.get_status()
    assert brain_manager.mode == BrainMode.BROWSER_OFFLOAD
    assert brain_manager.state == BrainState.READY_BROWSER_OFFLOAD
    assert status.mode == BrainMode.BROWSER_OFFLOAD


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

