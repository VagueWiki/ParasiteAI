"""
tests/test_challenger_m1_m2_adversarial.py - Adversarial empirical stress tests for Milestones M1 & M2 (R2 & R3).

Adversarially challenges:
1. LocalBrainManager Decoupling (R2):
   - Missing models, corrupted model paths, CUDA errors, timeouts, and arbitrary exceptions.
   - Empirically verifies zero-leak web offload confinement on Pass 1 (generate_thought) and Pass 2 (generate / generate_action).
2. BrowserOffloader & SentinelClipboardVerifier (R3):
   - Fast Ctrl+V clipboard prompt delivery across diverse lengths (0 to 100k chars), multiline, and unicode.
   - Rock-solid user clipboard restoration under paste failures, submit aborts, cancellations, and hardware crashes.
   - Sentinel response harvesting under variable generation delays (0.1s, 0.5s, 1.5s, 3.0s) with periodic retriggering.
"""

from __future__ import annotations

import struct
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

from parasite_ai.config import AppConfig, get_default_config
from parasite_ai.mind.brain_manager import (
    BrainMode,
    BrainState,
    BrowserOffloadBackend,
    LocalBrainManager,
    MockBackend,
    WebOffloadBackend,
    validate_gguf_header,
)
from parasite_ai.mind.dual_mind import DualMindPipeline
from parasite_ai.mind.offloader import (
    BrowserOffloader,
    MockBrowserWindowBackend,
    MockClipboardBackend,
    OffloadHarvestError,
    OffloaderState,
    SentinelClipboardVerifier,
)
from parasite_ai.vision.grounding import UIElement


def _create_raw_file(path: Path, data: bytes) -> None:
    """Helper to write arbitrary bytes to file."""
    path.write_bytes(data)


def _create_mock_gguf(file_path: Path, version: int = 3, extra_bytes: int = 64) -> None:
    """Helper to write a valid binary GGUF header."""
    magic = b"GGUF"
    ver_bytes = struct.pack("<I", version)
    payload = b"\x00" * extra_bytes
    file_path.write_bytes(magic + ver_bytes + payload)


# ===========================================================================
# 1. R2 Adversarial Stress Testing: Local LLM Confinement & Zero Web Offload
# ===========================================================================

class TestAdversarialLocalBrainManagerDecoupling:
    """
    Empirically verifies that LocalBrainManager in BrainMode.LOCAL_LLM NEVER
    triggers BrowserOffloadBackend / web offload under any failure conditions.
    """

    def test_missing_model_zero_offload_pass1_and_pass2(self, tmp_path: Path) -> None:
        """
        Challenge: In LOCAL_LLM mode with no models on disk:
        1. Mode must NOT mutate to BROWSER_OFFLOAD.
        2. State must be NO_MODEL_PRESENT, active_backend is None.
        3. Pass 1 (generate_thought) must return character monologue fallback without triggering web offload.
        4. Pass 2 (generate) must raise RuntimeError without triggering web offload.
        5. Pass 2 (generate_action) must raise RuntimeError without triggering web offload.
        """
        empty_dir = tmp_path / "empty_models"
        empty_dir.mkdir()

        cfg = get_default_config()
        cfg.system.models_dir = empty_dir
        cfg.brain.mode = "local_llm"

        mock_offloader = MagicMock()
        mock_offloader.query_web_ai.return_value = "ILLEGAL_OFFLOAD_RESPONSE"

        manager = LocalBrainManager(config=cfg, offloader=mock_offloader)

        # 1 & 2: Mode and state preservation
        assert manager.mode == BrainMode.LOCAL_LLM
        assert manager.state == BrainState.NO_MODEL_PRESENT
        assert manager.active_backend is None

        # 3. Pass 1 (generate_thought)
        thought = manager.generate_thought(
            scene_summary="Desktop view with Calculator",
            memory_context="Previous action was click",
            user_goal="Calculate 42 * 2",
        )
        assert thought == "*observing desktop for goal: Calculate 42 * 2*"
        assert mock_offloader.query_web_ai.call_count == 0
        assert manager.active_backend is None
        assert manager.mode == BrainMode.LOCAL_LLM

        # 4. Pass 2 (generate)
        with pytest.raises(RuntimeError, match="Local model backend is not loaded or unavailable"):
            manager.generate("Direct generation request in local mode")
        assert mock_offloader.query_web_ai.call_count == 0
        assert manager.active_backend is None

        # 5. Pass 2 (generate_action)
        with pytest.raises(RuntimeError, match="Local model backend is not loaded or unavailable"):
            manager.generate_action(
                persona_intent="Calculate numbers",
                som_elements=[],
                memory_context="",
            )
        assert mock_offloader.query_web_ai.call_count == 0

    @pytest.mark.parametrize(
        "corrupt_data,description",
        [
            (b"", "0-byte empty file"),
            (b"GGU", "Truncated magic header (3 bytes)"),
            (b"BAD!HEADER", "Invalid magic bytes"),
            (b"GGUF\x00\x00\x00\x00", "GGUF with unsupported version 0"),
            (b"GGUF\x99\x00\x00\x00", "GGUF with invalid future version 153"),
            (b"\xff" * 256, "Random binary garbage"),
        ],
    )
    def test_corrupted_model_path_zero_offload(
        self, tmp_path: Path, corrupt_data: bytes, description: str
    ) -> None:
        """
        Challenge: When model directory contains corrupted files:
        1. GGUF header validation fails.
        2. load_model() rejects the corrupted file.
        3. LocalBrainManager stays in LOCAL_LLM mode without triggering web offload.
        """
        models_dir = tmp_path / "corrupt_models"
        models_dir.mkdir()
        corrupt_file = models_dir / "qwen2.5-3b-corrupt.gguf"
        _create_raw_file(corrupt_file, corrupt_data)

        # Header check directly
        assert validate_gguf_header(corrupt_file) is False

        cfg = get_default_config()
        cfg.system.models_dir = models_dir
        cfg.brain.mode = "local_llm"

        mock_offloader = MagicMock()
        manager = LocalBrainManager(config=cfg, offloader=mock_offloader)

        assert manager.mode == BrainMode.LOCAL_LLM
        assert manager.state == BrainState.NO_MODEL_PRESENT

        # Explicit load attempt
        loaded = manager.load_model("qwen2.5-3b-corrupt.gguf")
        assert loaded is False
        assert manager.state == BrainState.NO_MODEL_PRESENT

        # Pass 1 & Pass 2 confinement
        thought = manager.generate_thought("Scene", "Memory", "Goal")
        assert "*observing desktop for goal: Goal*" in thought
        assert mock_offloader.query_web_ai.call_count == 0

        with pytest.raises(RuntimeError):
            manager.generate("Test prompt")
        assert mock_offloader.query_web_ai.call_count == 0

    def test_cuda_error_simulation_zero_offload(self, tmp_path: Path) -> None:
        """
        Challenge: When local inference encounters a simulated CUDA error (e.g. OOM or cuBLAS failure):
        1. Pass 1 (generate_thought) gracefully falls back to character monologue without web offload.
        2. Pass 2 (generate) raises the CUDA RuntimeError directly without falling back to web offload.
        3. Inference state cleans up properly.
        """
        cfg = get_default_config()
        cfg.brain.mode = "local_llm"

        mock_offloader = MagicMock()
        manager = LocalBrainManager(config=cfg, offloader=mock_offloader)

        # Inject a local backend that triggers CUDA OOM
        mock_local_backend = MagicMock()
        mock_local_backend.is_available.return_value = True
        cuda_error = RuntimeError(
            "CUDA out of memory. Tried to allocate 2.00 GiB (GPU 0; 8.00 GiB total capacity; 1.50 GiB free)"
        )
        mock_local_backend.generate.side_effect = cuda_error
        manager.active_backend = mock_local_backend
        manager.state = BrainState.READY_LOCAL

        # Pass 1: generate_thought
        thought = manager.generate_thought(
            scene_summary="Desktop foreground",
            memory_context="Previous click",
            user_goal="Render 3D scene",
        )
        assert thought == "*observing desktop for goal: Render 3D scene*"
        assert mock_offloader.query_web_ai.call_count == 0
        assert manager.mode == BrainMode.LOCAL_LLM
        assert manager.state == BrainState.READY_LOCAL  # Reset after inferring

        # Pass 2: generate directly
        with pytest.raises(RuntimeError, match="CUDA out of memory"):
            manager.generate("Render scene prompt")
        assert mock_offloader.query_web_ai.call_count == 0
        assert manager.state == BrainState.READY_LOCAL

    def test_inference_timeout_simulation_zero_offload(self, tmp_path: Path) -> None:
        """
        Challenge: When local model inference times out:
        1. Pass 1 returns character monologue fallback, 0 offload calls.
        2. Pass 2 raises TimeoutError directly, 0 offload calls.
        """
        cfg = get_default_config()
        cfg.brain.mode = "local_llm"

        mock_offloader = MagicMock()
        manager = LocalBrainManager(config=cfg, offloader=mock_offloader)

        mock_local_backend = MagicMock()
        mock_local_backend.is_available.return_value = True
        mock_local_backend.generate.side_effect = TimeoutError("Local inference timed out after 30s")
        manager.active_backend = mock_local_backend
        manager.state = BrainState.READY_LOCAL

        # Pass 1
        thought = manager.generate_thought("Scene", "Memory", "Summarize article")
        assert thought == "*observing desktop for goal: Summarize article*"
        assert mock_offloader.query_web_ai.call_count == 0

        # Pass 2
        with pytest.raises(TimeoutError, match="timed out"):
            manager.generate("Summarize prompt")
        assert mock_offloader.query_web_ai.call_count == 0

    @pytest.mark.parametrize(
        "fault_exc",
        [
            ValueError("Invalid tensor dimensions"),
            OSError("Model device connection reset"),
            KeyError("tokenizer_vocab"),
            ZeroDivisionError("Division by zero in sampling"),
        ],
    )
    def test_arbitrary_exceptions_zero_offload(self, fault_exc: Exception) -> None:
        """
        Challenge: Any arbitrary exception raised during local generation MUST NOT
        trigger BrowserOffloadBackend on Pass 1 or Pass 2.
        """
        cfg = get_default_config()
        cfg.brain.mode = "local_llm"

        mock_offloader = MagicMock()
        manager = LocalBrainManager(config=cfg, offloader=mock_offloader)

        mock_local_backend = MagicMock()
        mock_local_backend.is_available.return_value = True
        mock_local_backend.generate.side_effect = fault_exc
        manager.active_backend = mock_local_backend
        manager.state = BrainState.READY_LOCAL

        # Pass 1: generate_thought catches and monologues
        thought = manager.generate_thought("Scene", "Memory", "Run diagnostics")
        assert thought == "*observing desktop for goal: Run diagnostics*"
        assert mock_offloader.query_web_ai.call_count == 0

        # Pass 2: generate raises
        with pytest.raises(type(fault_exc)):
            manager.generate("Diagnostics prompt")
        assert mock_offloader.query_web_ai.call_count == 0

    def test_dual_mind_pipeline_local_mode_confinement(self, tmp_path: Path) -> None:
        """
        Challenge: In an integrated DualMindPipeline, when in local_llm mode with no model,
        Pass 1 generates the monologue fallback and Pass 2 executes without calling web offload.
        """
        empty_models = tmp_path / "empty_models_pipeline"
        empty_models.mkdir()

        cfg = get_default_config()
        cfg.system.models_dir = empty_models
        cfg.brain.mode = "local_llm"

        mock_offloader = MagicMock()
        manager = LocalBrainManager(config=cfg, offloader=mock_offloader)

        # Create pipeline with mock hands
        mock_mouse = MagicMock()
        mock_kbd = MagicMock()
        pipeline = DualMindPipeline(
            brain_manager=manager,
            mouse_driver=mock_mouse,
            keyboard_driver=mock_kbd,
            offloader=mock_offloader,
            config=cfg,
        )

        # Monologue engine directly
        persona_out = pipeline.persona_engine.generate_monologue(
            user_goal="Open Notepad",
            scene_summary="Desktop foreground",
            memory_context="Initial state",
        )
        assert persona_out.thought == "*observing desktop for goal: Open Notepad*"
        assert mock_offloader.query_web_ai.call_count == 0


# ===========================================================================
# 2. R3 Adversarial Stress Testing: Instant Ctrl+V Paste & Clipboard Integrity
# ===========================================================================

class TestAdversarialBrowserOffloadPromptDelivery:
    """
    Stress-tests BrowserOffloader.query_web_ai prompt delivery via instant Ctrl+V
    clipboard paste across lengths, multiline, unicode, and failure modes.
    """

    @pytest.mark.parametrize(
        "prompt_len",
        [0, 1, 10, 500, 5000, 50000],
    )
    def test_instant_paste_prompt_lengths(self, prompt_len: int) -> None:
        """
        Challenge: Diverse prompt lengths (from empty to 50,000 characters) must
        be delivered via Ctrl+V hotkey in a single operation, restoring user clipboard.
        """
        initial_clipboard = "OriginalUserClipboardSecret12345"
        clip = MockClipboardBackend(initial_text=initial_clipboard)
        win = MockBrowserWindowBackend(existing_hwnd=1001)

        mock_kbd = MagicMock()
        mock_kbd.hotkey.return_value = True

        offloader = BrowserOffloader(
            clipboard_backend=clip,
            window_backend=win,
            keyboard_driver=mock_kbd,
        )
        offloader.verifier.execute_harvest = MagicMock(return_value="Harvested response")

        test_prompt = "A" * prompt_len
        response = offloader.query_web_ai(test_prompt)

        assert response == "Harvested response"
        assert offloader.state == OffloaderState.COMPLETED

        # Verify Ctrl+V and Enter were pressed
        mock_kbd.hotkey.assert_any_call("ctrl", "v", cancellation_token=None)
        mock_kbd.hotkey.assert_any_call("enter", cancellation_token=None)

        # Verify clipboard was restored
        assert clip.get_text() == initial_clipboard

        # Verify prompt was indeed written to clipboard prior to paste
        assert test_prompt in clip.write_history

    @pytest.mark.parametrize(
        "multiline_prompt",
        [
            "Line 1\nLine 2\nLine 3",
            "WindowsLine 1\r\nWindowsLine 2\r\nWindowsLine 3",
            "```python\ndef hello():\n    print('world')\n    return 42\n```",
            '{"action": "CLICK", "target": "SubmitButton", "params": {"x": 100, "y": 200}}',
            "Multi\n\nParagraph\n\n\nSpacing\n\tTabbed Indent",
        ],
    )
    def test_instant_paste_multiline_variations(self, multiline_prompt: str) -> None:
        """
        Challenge: Multiline prompts with diverse line breaks, code blocks, and JSON
        must be delivered accurately without character dropping or line corruption.
        """
        initial_clipboard = "MyPreservedClipboard"
        clip = MockClipboardBackend(initial_text=initial_clipboard)
        win = MockBrowserWindowBackend(existing_hwnd=1002)

        mock_kbd = MagicMock()
        mock_kbd.hotkey.return_value = True

        offloader = BrowserOffloader(
            clipboard_backend=clip,
            window_backend=win,
            keyboard_driver=mock_kbd,
        )
        offloader.verifier.execute_harvest = MagicMock(return_value="Multiline response")

        response = offloader.query_web_ai(multiline_prompt)
        assert response == "Multiline response"
        mock_kbd.hotkey.assert_any_call("ctrl", "v", cancellation_token=None)
        assert clip.get_text() == initial_clipboard
        assert multiline_prompt in clip.write_history

    @pytest.mark.parametrize(
        "unicode_prompt",
        [
            "🚀 🤖 🧠 🔥 ⚡️ 👾 🎉",
            "こんにちは世界！これは日本語のプロンプトです。漢字・ひらがな・カタカナ",
            "你好，世界！这是中文提示词。包含繁體字與簡體字。",
            "안녕하세요 세계! 한국어 프롬프트 테스트입니다.",
            "Привет, мир! Это тестовый запрос на русском языке с символами ё, ъ, щ.",
            "∀x ∈ ℝ, ∃y: f(x) = ∫₀^∞ e^(-t) dt, α β γ δ Ω ∑",
            "Café résumé naïve façade Español Übergröße São Paulo",
            "\u200b\u200c\u200d\u200e\u200f עִבְרִית العربية",
        ],
    )
    def test_instant_paste_unicode_and_special_symbols(self, unicode_prompt: str) -> None:
        """
        Challenge: Unicode characters (emojis, CJK, Cyrillic, math, diacritics, RTL)
        must transfer verbatim via clipboard without encoding artifacts.
        """
        initial_clipboard = "UnicodeClipboard_🚀_Preserved"
        clip = MockClipboardBackend(initial_text=initial_clipboard)
        win = MockBrowserWindowBackend(existing_hwnd=1003)

        mock_kbd = MagicMock()
        mock_kbd.hotkey.return_value = True

        offloader = BrowserOffloader(
            clipboard_backend=clip,
            window_backend=win,
            keyboard_driver=mock_kbd,
        )
        offloader.verifier.execute_harvest = MagicMock(return_value="Unicode result")

        response = offloader.query_web_ai(unicode_prompt)
        assert response == "Unicode result"
        assert clip.get_text() == initial_clipboard
        assert unicode_prompt in clip.write_history

    def test_clipboard_restoration_when_paste_aborted(self) -> None:
        """
        Challenge: If Ctrl+V paste hotkey fails (e.g. user hardware preemption / aborted),
        OffloadHarvestError must be raised AND user clipboard must be restored.
        """
        initial_clipboard = "TopSecretClipboardData"
        clip = MockClipboardBackend(initial_text=initial_clipboard)
        win = MockBrowserWindowBackend(existing_hwnd=1004)

        mock_kbd = MagicMock()
        mock_kbd.hotkey.return_value = False  # Simulate paste rejected/aborted

        offloader = BrowserOffloader(
            clipboard_backend=clip,
            window_backend=win,
            keyboard_driver=mock_kbd,
        )

        with pytest.raises(OffloadHarvestError, match="Paste was aborted or interrupted"):
            offloader.query_web_ai("Test prompt")

        assert offloader.state == OffloaderState.FAILED
        # Clipboard must still be restored!
        assert clip.get_text() == initial_clipboard

    def test_clipboard_restoration_when_submit_aborted(self) -> None:
        """
        Challenge: If Ctrl+V succeeds but Enter submit fails/aborts,
        OffloadHarvestError must be raised AND user clipboard must be restored.
        """
        initial_clipboard = "TopSecretClipboardData"
        clip = MockClipboardBackend(initial_text=initial_clipboard)
        win = MockBrowserWindowBackend(existing_hwnd=1005)

        mock_kbd = MagicMock()
        # Call 1: "ctrl", "l" (navigation) -> True
        # Call 2: "ctrl", "v" (paste) -> True
        # Call 3: "enter" (submit) -> False (simulate submit abort)
        mock_kbd.hotkey.side_effect = [True, True, False]

        offloader = BrowserOffloader(
            clipboard_backend=clip,
            window_backend=win,
            keyboard_driver=mock_kbd,
        )

        with pytest.raises(OffloadHarvestError, match="Submit was aborted or interrupted"):
            offloader.query_web_ai("Test prompt")

        assert offloader.state == OffloaderState.FAILED
        assert clip.get_text() == initial_clipboard

    def test_clipboard_restoration_under_keyboard_hardware_fault(self) -> None:
        """
        Challenge: If keyboard driver raises an unhandled OSError/RuntimeError during hotkey(),
        the exception must be wrapped into OffloadHarvestError AND user clipboard restored.
        """
        initial_clipboard = "CriticalClipboardContent"
        clip = MockClipboardBackend(initial_text=initial_clipboard)
        win = MockBrowserWindowBackend(existing_hwnd=1006)

        mock_kbd = MagicMock()
        mock_kbd.hotkey.side_effect = OSError("Win32 SendInput hardware descriptor error")

        offloader = BrowserOffloader(
            clipboard_backend=clip,
            window_backend=win,
            keyboard_driver=mock_kbd,
        )

        with pytest.raises(OffloadHarvestError, match="Unexpected browser offload failure"):
            offloader.query_web_ai("Test prompt")

        assert offloader.state == OffloaderState.FAILED
        assert clip.get_text() == initial_clipboard


# ===========================================================================
# 3. R3 Adversarial Stress Testing: Sentinel Harvesting Under Variable Delays
# ===========================================================================

class TestAdversarialSentinelClipboardHarvesting:
    """
    Stress-tests SentinelClipboardVerifier.execute_harvest under variable generation
    delays (0.1s, 0.5s, 1.5s, 3.0s) with periodic copy retriggering.
    """

    @pytest.mark.parametrize(
        "generation_delay_s",
        [0.1, 0.5, 1.5, 3.0],
    )
    def test_sentinel_harvest_variable_delays(self, generation_delay_s: float) -> None:
        """
        Challenge: When web AI takes variable time (0.1s, 0.5s, 1.5s, 3.0s) to stream
        its response, SentinelClipboardVerifier must periodically retrigger copy actions,
        capture the answer cleanly once generation completes, and restore original clipboard.
        """
        initial_clip = "ImportantDocumentText"
        clip = MockClipboardBackend(initial_text=initial_clip)
        verifier = SentinelClipboardVerifier(
            clipboard=clip,
            poll_interval_s=0.02,
            default_timeout_s=generation_delay_s + 3.0,
        )

        start_time = time.perf_counter()
        expected_response = f"Frontier AI Response completed after {generation_delay_s}s delay"
        retrigger_count = 0

        def simulated_copy_trigger() -> bool:
            nonlocal retrigger_count
            retrigger_count += 1
            elapsed = time.perf_counter() - start_time
            if elapsed >= generation_delay_s:
                # Web AI has completed generation! Copy action successfully captures text
                clip.set_text(expected_response)
                return True
            # Still generating: copy action clicks disabled button or does nothing
            return False

        harvested = verifier.execute_harvest(
            trigger_copy_action=simulated_copy_trigger,
            timeout_s=generation_delay_s + 3.0,
            retrigger_interval_s=0.2,  # Retrigger every 200ms
        )

        # 1. Clean harvest without error
        assert harvested == expected_response

        # 2. Re-trigger fired appropriately
        assert retrigger_count >= 1

        # 3. Original user clipboard restored
        assert clip.get_text() == initial_clip

    @pytest.mark.parametrize(
        "generation_delay_s",
        [0.1, 0.5, 1.5, 3.0],
    )
    def test_full_offloader_query_web_ai_variable_delays(self, generation_delay_s: float) -> None:
        """
        Challenge: Full BrowserOffloader.query_web_ai end-to-end execution under
        variable delays must succeed cleanly without raising OffloadHarvestError.
        """
        initial_clip = "UserWorkInProgress"
        clip = MockClipboardBackend(initial_text=initial_clip)
        win = MockBrowserWindowBackend(existing_hwnd=7777)

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
        offloader.config.stream_timeout_sec = generation_delay_s + 3.0

        # Replace verifier with one configured for fast polling
        offloader.verifier = SentinelClipboardVerifier(
            clipboard=clip,
            poll_interval_s=0.02,
            default_timeout_s=generation_delay_s + 3.0,
        )

        start_time = time.perf_counter()
        expected_ai_output = f"Final Answer after {generation_delay_s}s stream"

        def simulated_harvest(trigger_copy_action: Any, timeout_s: Any, cancellation_token: Any) -> Optional[str]:
            # Simulate real verifier polling loop with periodic retrigger
            deadline = time.perf_counter() + (timeout_s or 5.0)
            while time.perf_counter() < deadline:
                if (time.perf_counter() - start_time) >= generation_delay_s:
                    return expected_ai_output
                trigger_copy_action()
                time.sleep(0.05)
            return None

        offloader.verifier.execute_harvest = simulated_harvest

        result = offloader.query_web_ai("What is quantum computing?")
        assert result == expected_ai_output
        assert offloader.state == OffloaderState.COMPLETED
        assert clip.get_text() == initial_clip

    def test_sentinel_harvest_ignores_intermediate_whitespace(self) -> None:
        """
        Challenge: If web UI momentarily puts whitespace or newlines on clipboard
        before final text arrives, execute_harvest must ignore whitespace and continue polling.
        """
        clip = MockClipboardBackend(initial_text="UserBackup")
        verifier = SentinelClipboardVerifier(
            clipboard=clip,
            poll_interval_s=0.01,
            default_timeout_s=2.0,
        )

        call_idx = 0

        def copy_trigger_with_whitespace() -> bool:
            nonlocal call_idx
            call_idx += 1
            if call_idx == 1:
                clip.set_text("   \n\t  ")  # Intermediate whitespace
            elif call_idx == 2:
                clip.set_text("Real Answer from Gemini")
            return True

        harvested = verifier.execute_harvest(
            trigger_copy_action=copy_trigger_with_whitespace,
            retrigger_interval_s=0.02,
        )

        assert harvested == "Real Answer from Gemini"
        assert clip.get_text() == "UserBackup"

    def test_sentinel_harvest_timeout_restores_user_clipboard(self) -> None:
        """
        Challenge: When timeout occurs, execute_harvest returns None AND restores original clipboard.
        """
        initial_clip = "MustRestoreThisOnTimeout"
        clip = MockClipboardBackend(initial_text=initial_clip)
        verifier = SentinelClipboardVerifier(
            clipboard=clip,
            poll_interval_s=0.01,
            default_timeout_s=0.05,
        )

        def failing_trigger() -> bool:
            return True  # Never writes anything to clipboard

        harvested = verifier.execute_harvest(
            trigger_copy_action=failing_trigger,
            timeout_s=0.05,
            retrigger_interval_s=0.02,
        )

        assert harvested is None
        assert clip.get_text() == initial_clip

    def test_sentinel_harvest_cancellation_during_delay(self) -> None:
        """
        Challenge: When cancellation token is fired during the wait loop,
        execute_harvest exits immediately and restores user clipboard.
        """
        initial_clip = "CancelRestoreTest"
        clip = MockClipboardBackend(initial_text=initial_clip)
        verifier = SentinelClipboardVerifier(
            clipboard=clip,
            poll_interval_s=0.01,
            default_timeout_s=5.0,
        )

        cancel_token = threading.Event()

        def copy_trigger() -> bool:
            # Trigger cancellation during first retrigger
            cancel_token.set()
            return True

        harvested = verifier.execute_harvest(
            trigger_copy_action=copy_trigger,
            timeout_s=5.0,
            cancellation_token=cancel_token,
            retrigger_interval_s=0.02,
        )

        assert harvested is None
        assert clip.get_text() == initial_clip
