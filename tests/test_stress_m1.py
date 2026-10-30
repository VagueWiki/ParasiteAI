"""
Empirical stress and adversarial test harness for ParasiteAI Milestone M1.

Evaluates:
1. Dual-mind action extraction under hostile LLM outputs:
   - Nested code fences (4+ backticks, multiple fence blocks)
   - Malformed JSON (syntax errors, unclosed objects, trailing commas)
   - Markdown tables (tables alone, tables alongside JSON)
   - Multiple actions / objects (preambles with braces, nested JSON objects)
   - Escape characters, raw control characters, and unicode
2. Memory/VRAM budget calculation under mock hardware environments:
   - Fallback when nvidia-smi fails, times out, or is missing
   - Non-standard / malformed nvidia-smi outputs (multi-GPU, N/A, empty)
   - Low VRAM thresholds (< 2000 MB triggers cpu fallback)
3. Zero-VRAM browser offload toggle latency and state machine idempotency:
   - Repeated idempotent toggling
   - High-frequency switching latency
   - Concurrent inference during mode toggles
"""

import json
import time
import subprocess
import threading
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

from parasite_ai.config import AppConfig, get_default_config
from parasite_ai.mind.brain_manager import (
    BrainMode,
    BrainState,
    CURATED_MODELS,
    LocalBrainManager,
    MockBackend,
    check_vram_headroom,
    validate_gguf_header,
)


@pytest.fixture
def stress_config(tmp_path: Path) -> AppConfig:
    cfg = get_default_config()
    cfg.system.models_dir = tmp_path / "models"
    cfg.system.models_dir.mkdir(parents=True, exist_ok=True)
    cfg.brain.mode = "mock"
    return cfg


# ===========================================================================
# 1. Dual-Mind Action Extraction under Hostile LLM Outputs
# ===========================================================================

class TestHostileActionExtraction:
    """Adversarial challenge for LocalBrainManager._extract_action_json and generate_action."""

    def test_nested_code_fences_quadruple_backticks(self, stress_config: Path):
        """Hostile LLM wraps markdown code fence within 4-backtick fence."""
        manager = LocalBrainManager(stress_config)
        hostile_output = (
            "````markdown\n"
            "Here is the action command:\n"
            "```json\n"
            '{"action": "CLICK", "target_id": 4, "reasoning": "quadruple fence test"}\n'
            "```\n"
            "````"
        )
        extracted = manager._extract_action_json(hostile_output)
        assert extracted is not None
        assert extracted.get("action") == "CLICK"
        assert extracted.get("target_id") == 4

    def test_code_fence_with_trailing_backticks(self, stress_config: Path):
        """LLM emits 4 or 5 backticks on the code fence directly."""
        manager = LocalBrainManager(stress_config)
        hostile_output = (
            "````json\n"
            '{"action": "HOTKEY", "text": "ctrl+c", "reasoning": "4-backtick fence"}\n'
            "````"
        )
        extracted = manager._extract_action_json(hostile_output)
        # Should extract valid action or safely fall back without crash
        action = manager.generate_action("copy", [], "")
        assert isinstance(action, dict)
        assert "action" in action

    def test_malformed_json_trailing_comma(self, stress_config: Path):
        """Hostile LLM emits JSON with trailing comma (invalid RFC 8259)."""
        manager = LocalBrainManager(stress_config)
        hostile_output = (
            '{"action": "CLICK", "target_id": 2, "coordinates": [100, 200],}'
        )
        # Standard json.loads fails on trailing comma.
        # generate_action must safely handle and return fallback WAIT without raising exception
        backend = MockBackend(canned_responses=[hostile_output])
        manager.active_backend = backend
        action = manager.generate_action("click button", [], "")
        assert isinstance(action, dict)
        assert action["action"] == "WAIT"
        assert "Re-evaluating target" in action["reasoning"]

    def test_malformed_json_unquoted_keys(self, stress_config: Path):
        """Hostile LLM emits JS object notation instead of JSON."""
        manager = LocalBrainManager(stress_config)
        hostile_output = "{action: 'CLICK', target_id: 1, reasoning: 'unquoted keys'}"
        backend = MockBackend(canned_responses=[hostile_output])
        manager.active_backend = backend
        action = manager.generate_action("click", [], "")
        assert isinstance(action, dict)
        assert action["action"] == "WAIT"

    def test_malformed_json_truncated_output(self, stress_config: Path):
        """Hostile LLM runs out of tokens and truncates mid-JSON."""
        manager = LocalBrainManager(stress_config)
        hostile_output = '{"action": "CLICK_AND_TYPE", "target_id": 5, "text": "hello wo'
        backend = MockBackend(canned_responses=[hostile_output])
        manager.active_backend = backend
        action = manager.generate_action("type text", [], "")
        assert isinstance(action, dict)
        assert action["action"] == "WAIT"

    def test_markdown_table_only(self, stress_config: Path):
        """Hostile LLM outputs only a markdown table instead of JSON."""
        manager = LocalBrainManager(stress_config)
        table_output = (
            "| Action | Target | Coordinates | Reasoning |\n"
            "|---|---|---|---|\n"
            "| CLICK | 1 | [500, 300] | Target submit button |\n"
        )
        backend = MockBackend(canned_responses=[table_output])
        manager.active_backend = backend
        action = manager.generate_action("submit", [], "")
        assert isinstance(action, dict)
        assert action["action"] == "WAIT"

    def test_markdown_table_with_embedded_json(self, stress_config: Path):
        """Hostile LLM outputs markdown table followed by valid JSON block."""
        manager = LocalBrainManager(stress_config)
        mixed_output = (
            "Here is the evaluation matrix:\n\n"
            "| Option | Score |\n"
            "| Option A | 9/10 |\n\n"
            "Therefore my selected action is:\n"
            "```json\n"
            '{"action": "SCROLL", "direction": "down", "reasoning": "found below fold"}\n'
            "```"
        )
        extracted = manager._extract_action_json(mixed_output)
        assert extracted is not None
        assert extracted["action"] == "SCROLL"
        assert extracted["direction"] == "down"

    def test_preamble_with_multiple_braces_and_nested_json(self, stress_config: Path):
        """
        LLM output has conversational text with curly braces,
        AND the actual JSON object itself has nested objects/dictionaries.
        """
        manager = LocalBrainManager(stress_config)
        hostile_output = (
            "I checked condition {state: active} and {flag: true}.\n"
            "Here is the command:\n"
            "{\n"
            '  "action": "CLICK_AND_TYPE",\n'
            '  "target_id": 12,\n'
            '  "coordinates": [250, 400],\n'
            '  "metadata": {"nested_key": "nested_value", "depth": 2},\n'
            '  "reasoning": "nested object test"\n'
            "}\n"
        )
        extracted = manager._extract_action_json(hostile_output)
        # Empirical test: Does the extractor successfully recover the valid action?
        assert extracted is not None, f"Failed to extract valid action JSON from output with preamble braces and nested JSON: {extracted}"
        assert extracted.get("action") == "CLICK_AND_TYPE"

    def test_multiple_action_objects_in_single_response(self, stress_config: Path):
        """
        LLM provides multiple sequential JSON actions.
        The extractor should pick a valid action without crashing.
        """
        manager = LocalBrainManager(stress_config)
        hostile_output = (
            '{"step_1": "prepare"}\n'
            '{"action": "CLICK", "target_id": 3, "reasoning": "first action"}\n'
            '{"action": "WAIT", "wait_ms": 500, "reasoning": "second action"}\n'
        )
        extracted = manager._extract_action_json(hostile_output)
        assert extracted is not None
        assert extracted["action"] in ("CLICK", "WAIT")

    def test_escape_characters_and_newlines(self, stress_config: Path):
        """LLM outputs escape characters, quotes within strings, and regex patterns."""
        manager = LocalBrainManager(stress_config)
        hostile_output = json.dumps({
            "action": "CLICK_AND_TYPE",
            "target_id": 7,
            "text": "Special symbols: \\n \\t \\\\ \"quotes\" and unicode: \u2764 \u30c4",
            "reasoning": "Escaped string content with path C:\\Users\\Suici\\AppData",
        })
        extracted = manager._extract_action_json(hostile_output)
        assert extracted is not None
        assert extracted["action"] == "CLICK_AND_TYPE"
        assert "\u2764" in extracted["text"]
        assert "quotes" in extracted["text"]

    def test_massive_hostile_llm_response(self, stress_config: Path):
        """LLM generates 100KB of hallucinated rambling surrounding a tiny JSON block."""
        manager = LocalBrainManager(stress_config)
        padding = "Nonsense reasoning narrative word words. " * 3000  # ~120KB
        hostile_output = (
            f"{padding}\n"
            "```json\n"
            '{"action": "DONE", "reasoning": "completed task"}\n'
            "```\n"
            f"{padding}"
        )
        t0 = time.perf_counter()
        extracted = manager._extract_action_json(hostile_output)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        assert extracted is not None
        assert extracted["action"] == "DONE"
        assert elapsed_ms < 500  # Must not hang or succumb to catastrophic backtracking (ReDoS)


# ===========================================================================
# 2. Memory / VRAM Budget Calculation Under Mock Hardware
# ===========================================================================

class TestVRAMBudgetMockHardware:
    """Adversarial challenge for VRAM detection and low-memory fallback."""

    def test_nvidia_smi_missing_falls_back_cleanly(self):
        """When nvidia-smi executable is absent, check_vram_headroom returns safe fallback."""
        with patch("subprocess.run", side_effect=FileNotFoundError("nvidia-smi not found")):
            used_mb, free_mb = check_vram_headroom()
            assert used_mb == 2500
            assert free_mb == 5688

    def test_nvidia_smi_timeout_handled_cleanly(self):
        """When nvidia-smi hangs (>2s timeout), check_vram_headroom does not block."""
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="nvidia-smi", timeout=2)):
            used_mb, free_mb = check_vram_headroom()
            assert used_mb == 2500
            assert free_mb == 5688

    def test_nvidia_smi_multi_gpu_output(self):
        """Multi-GPU machine returns multiple lines from nvidia-smi."""
        mock_output = MagicMock()
        mock_output.stdout = "1200, 6800\n4500, 3500\n"
        with patch("subprocess.run", return_value=mock_output):
            used_mb, free_mb = check_vram_headroom()
            # Primary GPU (line 0) should be parsed
            assert used_mb == 1200
            assert free_mb == 6800

    def test_nvidia_smi_malformed_string_output(self):
        """nvidia-smi outputs non-integer or error messages."""
        mock_output = MagicMock()
        mock_output.stdout = "N/A, [Unknown]\n"
        with patch("subprocess.run", return_value=mock_output):
            used_mb, free_mb = check_vram_headroom()
            # Catches ValueError and returns safe default
            assert used_mb == 2500
            assert free_mb == 5688

    def test_nvidia_smi_empty_output(self):
        """nvidia-smi outputs completely empty string."""
        mock_output = MagicMock()
        mock_output.stdout = "   \n"
        with patch("subprocess.run", return_value=mock_output):
            used_mb, free_mb = check_vram_headroom()
            assert used_mb == 2500
            assert free_mb == 5688

    def test_low_vram_triggers_gpu_layers_zero(self, stress_config: AppConfig, tmp_path: Path):
        """
        When free VRAM is under 2000 MB (e.g. 1500 MB), local model initialization
        must downgrade gpu_layers to 0 to prevent CUDA OOM.
        """
        model_file = tmp_path / "models" / "test_model.gguf"
        # Write valid GGUF header
        with open(model_file, "wb") as f:
            f.write(b"GGUF")
            f.write((3).to_bytes(4, byteorder="little", signed=False))
            f.write(b"\x00" * 32)

        manager = LocalBrainManager(stress_config)

        # Mock check_vram_headroom to return 1500MB free
        with patch("parasite_ai.mind.brain_manager.check_vram_headroom", return_value=(6500, 1500)):
            with patch("parasite_ai.mind.brain_manager.LlamaCppBackend") as mock_llama:
                mock_instance = MagicMock()
                mock_instance.is_available.return_value = True
                mock_llama.return_value = mock_instance

                success = manager._instantiate_local_engine(model_file)
                assert success is True
                # Verify LlamaCppBackend was called with n_gpu_layers=0
                mock_llama.assert_called_once()
                call_kwargs = mock_llama.call_args[1]
                assert call_kwargs["n_gpu_layers"] == 0

    def test_ample_vram_preserves_gpu_layers(self, stress_config: AppConfig, tmp_path: Path):
        """When free VRAM is >= 2000 MB (e.g. 6000 MB), configured gpu_layers is preserved."""
        model_file = tmp_path / "models" / "test_model.gguf"
        with open(model_file, "wb") as f:
            f.write(b"GGUF")
            f.write((3).to_bytes(4, byteorder="little", signed=False))
            f.write(b"\x00" * 32)

        manager = LocalBrainManager(stress_config)

        with patch("parasite_ai.mind.brain_manager.check_vram_headroom", return_value=(2000, 6000)):
            with patch("parasite_ai.mind.brain_manager.LlamaCppBackend") as mock_llama:
                mock_instance = MagicMock()
                mock_instance.is_available.return_value = True
                mock_llama.return_value = mock_instance

                success = manager._instantiate_local_engine(model_file)
                assert success is True
                call_kwargs = mock_llama.call_args[1]
                assert call_kwargs["n_gpu_layers"] == manager.config.brain.local_model.gpu_layers

    def test_vram_budget_exceeded_by_model_headroom(self, stress_config: AppConfig, tmp_path: Path):
        """
        When free VRAM (2500 MB) is less than the model required VRAM (5200 MB for 7B)
        or less than configured vram_budget_mb (4000 MB), the engine must not attempt
        full GPU offload (-1 layers) which triggers CUDA OOM.
        """
        stress_config.brain.local_model.vram_budget_mb = 4000
        stress_config.brain.local_model.gpu_layers = -1

        model_file = tmp_path / "models" / "qwen2.5-7b-instruct-q4_k_m.gguf"
        with open(model_file, "wb") as f:
            f.write(b"GGUF")
            f.write((3).to_bytes(4, byteorder="little", signed=False))
            f.write(b"\x00" * 32)

        manager = LocalBrainManager(stress_config)

        # Mock check_vram_headroom to return 2500MB free (less than 4000 budget and less than 5200 required)
        with patch("parasite_ai.mind.brain_manager.check_vram_headroom", return_value=(5500, 2500)):
            with patch("parasite_ai.mind.brain_manager.LlamaCppBackend") as mock_llama:
                mock_instance = MagicMock()
                mock_instance.is_available.return_value = True
                mock_llama.return_value = mock_instance

                manager._instantiate_local_engine(model_file)
                mock_llama.assert_called_once()
                call_kwargs = mock_llama.call_args[1]
                assert call_kwargs["n_gpu_layers"] != -1, (
                    "Engine attempted full GPU offload (n_gpu_layers=-1) despite free VRAM (2500MB) "
                    "being lower than the model requirement (5200MB) and budget (4000MB)"
                )


# ===========================================================================
# 3. Zero-VRAM Browser Offload Toggle Latency & State Machine Idempotency
# ===========================================================================

class TestBrowserOffloadToggleStress:
    """Stress testing toggle latency, state machine idempotency, and concurrent access."""

    def test_toggle_browser_only_mode_idempotent_true(self, stress_config: AppConfig):
        """Calling toggle_browser_only_mode(True) multiple times leaves state clean."""
        manager = LocalBrainManager(stress_config)
        for _ in range(5):
            manager.toggle_browser_only_mode(True)
            assert manager.mode == BrainMode.BROWSER_OFFLOAD
            assert manager.state == BrainState.READY_BROWSER_OFFLOAD
            assert manager.active_backend.__class__.__name__ == "BrowserOffloadBackend"

    def test_toggle_browser_only_mode_idempotent_false_no_model(self, stress_config: AppConfig):
        """Calling toggle_browser_only_mode(False) with no model on disk consistently sets NO_MODEL_PRESENT."""
        manager = LocalBrainManager(stress_config)
        for _ in range(5):
            manager.toggle_browser_only_mode(False)
            assert manager.mode == BrainMode.LOCAL_LLM
            assert manager.state == BrainState.NO_MODEL_PRESENT

    def test_toggle_browser_only_mode_idempotent_false_with_model(self, stress_config: AppConfig, tmp_path: Path):
        """Calling toggle_browser_only_mode(False) with valid GGUF consistently loads model."""
        model_file = tmp_path / "models" / "qwen.gguf"
        with open(model_file, "wb") as f:
            f.write(b"GGUF")
            f.write((3).to_bytes(4, byteorder="little", signed=False))
            f.write(b"\x00" * 32)

        manager = LocalBrainManager(stress_config)
        for _ in range(5):
            manager.toggle_browser_only_mode(False)
            assert manager.mode == BrainMode.LOCAL_LLM
            assert manager.state == BrainState.READY_LOCAL

    def test_rapid_toggle_latency_budget(self, stress_config: AppConfig):
        """
        Zero-VRAM toggle should be instantaneous (< 50ms per toggle).
        Benchmark 50 toggles to confirm deterministic bounds and no memory leaks.
        """
        manager = LocalBrainManager(stress_config)
        latencies: List[float] = []

        for i in range(50):
            enable = (i % 2 == 0)
            t0 = time.perf_counter()
            manager.toggle_browser_only_mode(enable)
            dt_ms = (time.perf_counter() - t0) * 1000
            latencies.append(dt_ms)

        max_latency = max(latencies)
        avg_latency = sum(latencies) / len(latencies)

        assert avg_latency < 20.0, f"Average toggle latency {avg_latency:.2f}ms exceeds 20ms"
        assert max_latency < 100.0, f"Max toggle latency {max_latency:.2f}ms exceeds 100ms"

    def test_concurrent_toggle_and_status_polling(self, stress_config: AppConfig):
        """
        Multithreaded stress test: 4 threads polling get_status() while 2 threads
        continuously toggle mode back and forth. Verifies thread-safety and no deadlocks.
        """
        manager = LocalBrainManager(stress_config)
        stop_event = threading.Event()
        errors: List[Exception] = []

        def toggle_worker():
            try:
                toggle = True
                while not stop_event.is_set():
                    manager.toggle_browser_only_mode(toggle)
                    toggle = not toggle
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        def status_worker():
            try:
                while not stop_event.is_set():
                    status = manager.get_status()
                    assert status.mode in (BrainMode.BROWSER_OFFLOAD, BrainMode.LOCAL_LLM, BrainMode.MOCK)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=toggle_worker),
            threading.Thread(target=toggle_worker),
            threading.Thread(target=status_worker),
            threading.Thread(target=status_worker),
            threading.Thread(target=status_worker),
            threading.Thread(target=status_worker),
        ]

        for t in threads:
            t.start()

        time.sleep(1.0)
        stop_event.set()

        for t in threads:
            t.join(timeout=2.0)

        assert not errors, f"Concurrent stress test encountered errors: {errors}"

    def test_state_machine_generate_and_toggle_interleaving(self, stress_config: AppConfig):
        """
        Empirically test whether concurrent toggle during generate() leaves
        the manager in a valid state.
        """
        manager = LocalBrainManager(stress_config)
        slow_backend = MockBackend()
        # Add a delay inside generate to simulate inference
        original_generate = slow_backend.generate
        def slow_generate(*args, **kwargs):
            time.sleep(0.05)
            return original_generate(*args, **kwargs)
        slow_backend.generate = slow_generate
        manager.active_backend = slow_backend
        manager.mode = BrainMode.LOCAL_LLM
        manager.state = BrainState.READY_LOCAL

        # Run generate on background thread
        gen_thread = threading.Thread(target=lambda: manager.generate("test prompt"))
        gen_thread.start()

        # While generate is running, toggle mode
        time.sleep(0.01)
        manager.toggle_browser_only_mode(True)

        gen_thread.join(timeout=2.0)

        # Inspect resulting state
        # In browser offload mode, manager.mode is BROWSER_OFFLOAD.
        # Check if state and mode are mutually consistent.
        status = manager.get_status()
        assert status.mode == BrainMode.BROWSER_OFFLOAD
        assert status.state == BrainState.READY_BROWSER_OFFLOAD, f"State corrupted! Mode is {status.mode} but state is {status.state}"
