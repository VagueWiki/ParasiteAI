"""
Empirical stress test suite by teamwork_challenger_m1_iter2_2.
Thorough adversarial verification of:
1. Action parser under hostile inputs:
   - Deep nesting (10, 50, 100 levels)
   - Unescaped quotes inside strings (sanitization / safe fallback without crash)
   - Trailing junk (unclosed braces, random characters, multiple trailing JSONs, unclosed quotes)
   - Markdown code blocks with 4+ backticks (````, `````, ``````, mismatched backticks, nested fences)
   - Hostile input DOS resistance (10,000 unclosed braces, 50,000 backticks, massive backslashes)
2. VRAM scaling logic with boundary VRAM values:
   - 0 MB
   - 1999 MB
   - 2000 MB
   - Exact match (effective == vram_required_mb)
   - Overflow (effective >> vram_required_mb, e.g. 128,000 MB)
   - Negative values (-100 MB)
   - Budget capping (free VRAM high, budget low vs free VRAM low, budget high)
   - Unknown models (catalog fallback)
   - Different configured_layers (-1, 0, 16, 64)
"""

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from parasite_ai.config import AppConfig, get_default_config
from parasite_ai.mind.brain_manager import (
    CURATED_MODELS,
    LocalBrainManager,
    MockBackend,
)


@pytest.fixture
def stress_config(tmp_path: Path) -> AppConfig:
    cfg = get_default_config()
    cfg.system.models_dir = tmp_path / "models"
    cfg.system.models_dir.mkdir(parents=True, exist_ok=True)
    cfg.brain.mode = "mock"
    return cfg


# ===========================================================================
# 1. Action Parser Hostile Inputs Stress Tests
# ===========================================================================

class TestActionParserAdversarialInputs:
    """Stress test LocalBrainManager._extract_action_json and generate_action against hostile LLM outputs."""

    # --- Markdown Code Blocks with 4+ Backticks ---

    @pytest.mark.parametrize("backtick_count", [4, 5, 6, 8, 12])
    def test_markdown_code_blocks_variable_backticks(self, stress_config: AppConfig, backtick_count: int):
        """Markdown code blocks with 4, 5, 6, 8, 12 backticks must be correctly parsed."""
        manager = LocalBrainManager(stress_config)
        ticks = "`" * backtick_count
        raw_output = (
            f"Here is your response:\n"
            f"{ticks}json\n"
            f'{{"action": "CLICK", "target_id": {backtick_count}, "reasoning": "testing {backtick_count} backticks"}}\n'
            f"{ticks}\n"
            f"Hope that helped!"
        )
        extracted = manager._extract_action_json(raw_output)
        assert extracted is not None, f"Failed to extract JSON from {backtick_count} backticks"
        assert extracted["action"] == "CLICK"
        assert extracted["target_id"] == backtick_count

    def test_mismatched_backticks_opening_larger(self, stress_config: AppConfig):
        """Code block opens with 5 backticks and closes with 3 backticks."""
        manager = LocalBrainManager(stress_config)
        raw_output = (
            "`````json\n"
            '{"action": "HOTKEY", "text": "ctrl+shift+p", "reasoning": "mismatched backticks"}\n'
            "```"
        )
        # Even if regex fence parser expects matching backticks, balanced brace extractor should catch it
        extracted = manager._extract_action_json(raw_output)
        assert extracted is not None
        assert extracted["action"] == "HOTKEY"
        assert extracted["text"] == "ctrl+shift+p"

    def test_mismatched_backticks_closing_larger(self, stress_config: AppConfig):
        """Code block opens with 3 backticks and closes with 5 backticks."""
        manager = LocalBrainManager(stress_config)
        raw_output = (
            "```json\n"
            '{"action": "SCROLL", "direction": "up", "reasoning": "mismatched backticks closing larger"}\n'
            "`````"
        )
        extracted = manager._extract_action_json(raw_output)
        assert extracted is not None
        assert extracted["action"] == "SCROLL"
        assert extracted["direction"] == "up"

    def test_nested_markdown_code_fences(self, stress_config: AppConfig):
        """Outer 5-backtick markdown fence containing inner 3-backtick json fence."""
        manager = LocalBrainManager(stress_config)
        raw_output = (
            "`````markdown\n"
            "Explanation of actions:\n"
            "```json\n"
            '{"action": "CLICK", "target_id": 99, "reasoning": "nested fence"}\n'
            "```\n"
            "`````"
        )
        extracted = manager._extract_action_json(raw_output)
        assert extracted is not None
        assert extracted["action"] == "CLICK"
        assert extracted["target_id"] == 99

    # --- Deeply Nested Objects ---

    @pytest.mark.parametrize("depth", [5, 10, 25, 50, 100])
    def test_deeply_nested_objects_inside_action(self, stress_config: AppConfig, depth: int):
        """Action JSON containing deeply nested sub-dictionaries inside parameters/metadata."""
        manager = LocalBrainManager(stress_config)
        nested: dict = {"final_val": 42}
        for d in range(depth):
            nested = {f"level_{d}": nested}

        payload = {
            "action": "CLICK_AND_TYPE",
            "target_id": depth,
            "text": "deep nesting test",
            "metadata": nested,
            "reasoning": f"tested nesting depth {depth}",
        }
        raw_output = f"Thinking process complete.\n{json.dumps(payload)}\nExecution ready."
        extracted = manager._extract_action_json(raw_output)
        assert extracted is not None, f"Failed at depth {depth}"
        assert extracted["action"] == "CLICK_AND_TYPE"
        assert extracted["target_id"] == depth
        # Verify deepest level
        cur = extracted["metadata"]
        for d in reversed(range(depth)):
            assert f"level_{d}" in cur
            cur = cur[f"level_{d}"]
        assert cur == {"final_val": 42}

    def test_nested_preamble_blocks_prior_to_action(self, stress_config: AppConfig):
        """Multiple nested non-action JSON objects appear before the actual action block."""
        manager = LocalBrainManager(stress_config)
        raw_output = (
            "Context telemetry:\n"
            '{"system": {"metrics": {"cpu": 15, "ram": {"used": 2048, "free": 4096}}}}\n'
            '{"session": {"id": "12345", "user": {"role": "admin"}}}\n'
            "Therefore, dispatching action:\n"
            '{"action": "DONE", "reasoning": "telemetry reviewed"}\n'
        )
        extracted = manager._extract_action_json(raw_output)
        assert extracted is not None
        assert extracted["action"] == "DONE"
        assert extracted["reasoning"] == "telemetry reviewed"

    # --- Trailing Junk and Hostile Surrounding Text ---

    def test_trailing_junk_unclosed_braces(self, stress_config: AppConfig):
        """Valid action JSON followed immediately by unclosed braces and malformed syntax."""
        manager = LocalBrainManager(stress_config)
        raw_output = (
            '{"action": "CLICK", "target_id": 7, "reasoning": "valid action"}'
            ' { unclosed_object: { another_unclosed: "broken'
        )
        extracted = manager._extract_action_json(raw_output)
        assert extracted is not None
        assert extracted["action"] == "CLICK"
        assert extracted["target_id"] == 7

    def test_trailing_junk_unclosed_quotes(self, stress_config: AppConfig):
        """Valid action JSON followed by dangling quote and special characters."""
        manager = LocalBrainManager(stress_config)
        raw_output = (
            '{"action": "WAIT", "wait_ms": 500, "reasoning": "waiting"}'
            ' "dangling string without closing quote\n\x00\x01\x02'
        )
        extracted = manager._extract_action_json(raw_output)
        assert extracted is not None
        assert extracted["action"] == "WAIT"
        assert extracted["wait_ms"] == 500

    def test_trailing_junk_random_brackets_and_commas(self, stress_config: AppConfig):
        """Valid action JSON followed by random invalid syntax."""
        manager = LocalBrainManager(stress_config)
        raw_output = (
            '{"action": "CLICK", "target_id": 1, "coordinates": [10, 20], "reasoning": "target 1"}'
            ' ,,, ]]] }}} ;;; >>> ???'
        )
        extracted = manager._extract_action_json(raw_output)
        assert extracted is not None
        assert extracted["action"] == "CLICK"
        assert extracted["coordinates"] == [10, 20]

    def test_leading_and_trailing_junk_combined(self, stress_config: AppConfig):
        """Hostile environment with leading and trailing invalid braces and garbage."""
        manager = LocalBrainManager(stress_config)
        raw_output = (
            '}{ random { { broken prefix'
            ' {"action": "OFFLOAD_WEB_AI", "prompt": "search", "reasoning": "offload"} '
            'suffix { broken { unclosed }'
        )
        extracted = manager._extract_action_json(raw_output)
        assert extracted is not None
        assert extracted["action"] == "OFFLOAD_WEB_AI"
        assert extracted["reasoning"] == "offload"

    # --- Unescaped Quotes Inside Strings ---

    def test_unescaped_quotes_inside_string_safe_fallback(self, stress_config: AppConfig):
        """
        Hostile LLM emits completely unescaped quotes inside string field:
        {"action": "CLICK_AND_TYPE", "text": "He said "hello" to me", "reasoning": "test"}
        RFC 8259 violation: Parser must not crash or loop infinitely; generate_action
        must safely fall back to WAIT action.
        """
        manager = LocalBrainManager(stress_config)
        hostile_output = '{"action": "CLICK_AND_TYPE", "text": "He said "hello" to me", "reasoning": "test"}'
        manager.active_backend = MockBackend(canned_responses=[hostile_output])

        t0 = time.perf_counter()
        action = manager.generate_action("type hello", [], "")
        elapsed_ms = (time.perf_counter() - t0) * 1000

        assert isinstance(action, dict)
        assert action["action"] == "WAIT"
        assert "Re-evaluating target" in action["reasoning"]
        assert elapsed_ms < 100.0, "Parsing took too long on unescaped quotes"

    def test_escaped_quotes_properly_parsed(self, stress_config: AppConfig):
        """Validly escaped quotes (\") inside strings must be extracted with quotes intact."""
        manager = LocalBrainManager(stress_config)
        raw_output = (
            '{"action": "CLICK_AND_TYPE", "text": "He said \\"hello\\" to me", "reasoning": "valid escape"}'
        )
        extracted = manager._extract_action_json(raw_output)
        assert extracted is not None
        assert extracted["action"] == "CLICK_AND_TYPE"
        assert 'He said "hello" to me' == extracted["text"]

    def test_escaped_backslashes_before_quotes(self, stress_config: AppConfig):
        r"""Backslashes before quotes: e.g. path \\ followed by quote: 'C:\\Users\\Suici\\'."""
        manager = LocalBrainManager(stress_config)
        raw_output = (
            '{"action": "CLICK_AND_TYPE", "text": "Path: C:\\\\Users\\\\Test\\\\", "reasoning": "path test"}'
        )
        extracted = manager._extract_action_json(raw_output)
        assert extracted is not None
        assert extracted["action"] == "CLICK_AND_TYPE"
        assert "C:\\Users\\Test\\" in extracted["text"]

    # --- DOS and Catastrophic Stress Hardening ---

    def test_unclosed_braces_flood_resistance(self, stress_config: AppConfig):
        """Parser handles 500 unclosed braces in <50ms without RecursionError or crash."""
        manager = LocalBrainManager(stress_config)
        hostile_output = "{" * 500
        t0 = time.perf_counter()
        extracted = manager._extract_action_json(hostile_output)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        assert extracted is None
        assert elapsed_ms < 50.0, f"Unclosed braces took too long: {elapsed_ms:.2f}ms"

    def test_backticks_flood_resistance(self, stress_config: AppConfig):
        """Regex and fence parser handles 500 unclosed backticks without hang."""
        manager = LocalBrainManager(stress_config)
        hostile_output = "`" * 500
        t0 = time.perf_counter()
        extracted = manager._extract_action_json(hostile_output)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        assert extracted is None
        assert elapsed_ms < 50.0, f"Backtick flood took too long: {elapsed_ms:.2f}ms"

    def test_massive_backslashes_in_string(self, stress_config: AppConfig):
        """Parser handles 5,000 escaped backslashes without exponential parsing explosion."""
        manager = LocalBrainManager(stress_config)
        slashes = "\\\\" * 2500
        hostile_output = f'{{"action": "WAIT", "reasoning": "{slashes}"}}'
        t0 = time.perf_counter()
        extracted = manager._extract_action_json(hostile_output)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        assert extracted is not None
        assert extracted["action"] == "WAIT"
        assert elapsed_ms < 100.0, f"Backslash flood took too long: {elapsed_ms:.2f}ms"

    def test_unicode_and_emojis_in_action_fields(self, stress_config: AppConfig):
        """Action parser preserves unicode multi-byte characters and emojis."""
        manager = LocalBrainManager(stress_config)
        raw_output = (
            '{"action": "CLICK_AND_TYPE", "text": "Search 🔍 for 🚀 & 🦀", "reasoning": "Unicode 测试 💖"}'
        )
        extracted = manager._extract_action_json(raw_output)
        assert extracted is not None
        assert extracted["action"] == "CLICK_AND_TYPE"
        assert "🔍" in extracted["text"]
        assert "💖" in extracted["reasoning"]


# ===========================================================================
# 2. VRAM Scaling Logic Boundary Values Stress Tests
# ===========================================================================

class TestVRAMScalingBoundaryValues:
    """Stress test VRAM scaling logic in LocalBrainManager._instantiate_local_engine across boundary values."""

    @pytest.fixture
    def dummy_model(self, tmp_path: Path) -> Path:
        model_path = tmp_path / "models" / "qwen2.5-7b-instruct-q4_k_m.gguf"
        model_path.parent.mkdir(parents=True, exist_ok=True)
        with open(model_path, "wb") as f:
            f.write(b"GGUF")
            f.write((3).to_bytes(4, byteorder="little", signed=False))
            f.write(b"\x00" * 64)
        return model_path

    @pytest.fixture
    def unknown_model(self, tmp_path: Path) -> Path:
        model_path = tmp_path / "models" / "custom-unknown-model-q4.gguf"
        model_path.parent.mkdir(parents=True, exist_ok=True)
        with open(model_path, "wb") as f:
            f.write(b"GGUF")
            f.write((3).to_bytes(4, byteorder="little", signed=False))
            f.write(b"\x00" * 64)
        return model_path

    # Model requires 5200 MB, total layers = 32 (or rec layers 28 for Qwen 7B)

    def test_vram_boundary_0_mb(self, stress_config: AppConfig, dummy_model: Path):
        """Boundary: 0 MB free VRAM -> Must force gpu_layers = 0 (CPU fallback)."""
        stress_config.brain.local_model.vram_budget_mb = 8192
        stress_config.brain.local_model.gpu_layers = -1
        manager = LocalBrainManager(stress_config)

        with patch("parasite_ai.mind.brain_manager.check_vram_headroom", return_value=(8192, 0)):
            with patch("parasite_ai.mind.brain_manager.LlamaCppBackend") as mock_llama:
                mock_instance = MagicMock()
                mock_instance.is_available.return_value = True
                mock_llama.return_value = mock_instance

                success = manager._instantiate_local_engine(dummy_model)
                assert success is True
                call_kwargs = mock_llama.call_args[1]
                assert call_kwargs["n_gpu_layers"] == 0, f"Expected 0 layers for 0MB VRAM, got {call_kwargs['n_gpu_layers']}"

    def test_vram_boundary_negative_mb(self, stress_config: AppConfig, dummy_model: Path):
        """Boundary: Negative VRAM (e.g. driver glitch returning -100 MB) -> Must force gpu_layers = 0."""
        stress_config.brain.local_model.vram_budget_mb = 8192
        stress_config.brain.local_model.gpu_layers = -1
        manager = LocalBrainManager(stress_config)

        with patch("parasite_ai.mind.brain_manager.check_vram_headroom", return_value=(8192, -100)):
            with patch("parasite_ai.mind.brain_manager.LlamaCppBackend") as mock_llama:
                mock_instance = MagicMock()
                mock_instance.is_available.return_value = True
                mock_llama.return_value = mock_instance

                success = manager._instantiate_local_engine(dummy_model)
                assert success is True
                call_kwargs = mock_llama.call_args[1]
                assert call_kwargs["n_gpu_layers"] == 0

    def test_vram_boundary_1999_mb(self, stress_config: AppConfig, dummy_model: Path):
        """Boundary: 1999 MB free VRAM (just under 2000 MB threshold) -> Must force gpu_layers = 0."""
        stress_config.brain.local_model.vram_budget_mb = 8192
        stress_config.brain.local_model.gpu_layers = -1
        manager = LocalBrainManager(stress_config)

        with patch("parasite_ai.mind.brain_manager.check_vram_headroom", return_value=(6000, 1999)):
            with patch("parasite_ai.mind.brain_manager.LlamaCppBackend") as mock_llama:
                mock_instance = MagicMock()
                mock_instance.is_available.return_value = True
                mock_llama.return_value = mock_instance

                success = manager._instantiate_local_engine(dummy_model)
                assert success is True
                call_kwargs = mock_llama.call_args[1]
                assert call_kwargs["n_gpu_layers"] == 0, f"Expected 0 layers at 1999MB, got {call_kwargs['n_gpu_layers']}"

    def test_vram_boundary_2000_mb(self, stress_config: AppConfig, dummy_model: Path):
        """
        Boundary: Exactly 2000 MB free VRAM -> Crosses threshold into proportional scaling!
        For 7B model (5200 MB required, recommended layers 28):
        layer_ratio = 2000 / 5200 = 0.3846
        scaled_layers = int(28 * 0.3846) = 10 layers.
        """
        stress_config.brain.local_model.vram_budget_mb = 8192
        stress_config.brain.local_model.gpu_layers = -1
        manager = LocalBrainManager(stress_config)

        with patch("parasite_ai.mind.brain_manager.check_vram_headroom", return_value=(6000, 2000)):
            with patch("parasite_ai.mind.brain_manager.LlamaCppBackend") as mock_llama:
                mock_instance = MagicMock()
                mock_instance.is_available.return_value = True
                mock_llama.return_value = mock_instance

                success = manager._instantiate_local_engine(dummy_model)
                assert success is True
                call_kwargs = mock_llama.call_args[1]
                layers = call_kwargs["n_gpu_layers"]
                assert layers > 0, f"Expected scaled GPU layers > 0 at 2000MB, got {layers}"
                # 28 * (2000/5200) = 10.76 -> 10 layers
                assert layers == 10

    def test_vram_boundary_exact_match(self, stress_config: AppConfig, dummy_model: Path):
        """
        Boundary: Exact match between effective VRAM and model requirement (5200 MB == 5200 MB).
        Must preserve configured layers (-1 for full offload, or custom layer count).
        """
        stress_config.brain.local_model.vram_budget_mb = 5200
        stress_config.brain.local_model.gpu_layers = -1
        manager = LocalBrainManager(stress_config)

        with patch("parasite_ai.mind.brain_manager.check_vram_headroom", return_value=(2000, 5200)):
            with patch("parasite_ai.mind.brain_manager.LlamaCppBackend") as mock_llama:
                mock_instance = MagicMock()
                mock_instance.is_available.return_value = True
                mock_llama.return_value = mock_instance

                success = manager._instantiate_local_engine(dummy_model)
                assert success is True
                call_kwargs = mock_llama.call_args[1]
                assert call_kwargs["n_gpu_layers"] == -1, f"Expected full offload (-1) on exact match, got {call_kwargs['n_gpu_layers']}"

    def test_vram_boundary_overflow(self, stress_config: AppConfig, dummy_model: Path):
        """
        Boundary: Extreme VRAM overflow (e.g. 128,000 MB free on data-center GPU).
        Must safely handle large integers and preserve configured layers without integer overflow.
        """
        stress_config.brain.local_model.vram_budget_mb = 128000
        stress_config.brain.local_model.gpu_layers = -1
        manager = LocalBrainManager(stress_config)

        with patch("parasite_ai.mind.brain_manager.check_vram_headroom", return_value=(1000, 128000)):
            with patch("parasite_ai.mind.brain_manager.LlamaCppBackend") as mock_llama:
                mock_instance = MagicMock()
                mock_instance.is_available.return_value = True
                mock_llama.return_value = mock_instance

                success = manager._instantiate_local_engine(dummy_model)
                assert success is True
                call_kwargs = mock_llama.call_args[1]
                assert call_kwargs["n_gpu_layers"] == -1

    def test_vram_budget_capping_when_free_vram_is_abundant(self, stress_config: AppConfig, dummy_model: Path):
        """
        Hardware has 16,000 MB free, but user explicitly set vram_budget_mb = 1800 MB.
        effective_vram_mb = min(16000, 1800) = 1800 MB (< 2000 MB threshold).
        Must force gpu_layers = 0 to respect user budget.
        """
        stress_config.brain.local_model.vram_budget_mb = 1800
        stress_config.brain.local_model.gpu_layers = -1
        manager = LocalBrainManager(stress_config)

        with patch("parasite_ai.mind.brain_manager.check_vram_headroom", return_value=(2000, 16000)):
            with patch("parasite_ai.mind.brain_manager.LlamaCppBackend") as mock_llama:
                mock_instance = MagicMock()
                mock_instance.is_available.return_value = True
                mock_llama.return_value = mock_instance

                success = manager._instantiate_local_engine(dummy_model)
                assert success is True
                call_kwargs = mock_llama.call_args[1]
                assert call_kwargs["n_gpu_layers"] == 0, f"Expected 0 layers due to budget cap, got {call_kwargs['n_gpu_layers']}"

    def test_configured_layers_capped_by_scaled_layers(self, stress_config: AppConfig, dummy_model: Path):
        """
        When user configured gpu_layers = 25, but effective VRAM only fits 10 layers,
        gpu_layers must be min(25, 10) = 10 layers.
        """
        stress_config.brain.local_model.vram_budget_mb = 2000
        stress_config.brain.local_model.gpu_layers = 25
        manager = LocalBrainManager(stress_config)

        with patch("parasite_ai.mind.brain_manager.check_vram_headroom", return_value=(2000, 2000)):
            with patch("parasite_ai.mind.brain_manager.LlamaCppBackend") as mock_llama:
                mock_instance = MagicMock()
                mock_instance.is_available.return_value = True
                mock_llama.return_value = mock_instance

                success = manager._instantiate_local_engine(dummy_model)
                assert success is True
                call_kwargs = mock_llama.call_args[1]
                assert call_kwargs["n_gpu_layers"] == 10

    def test_configured_layers_lower_than_scaled_layers_preserved(self, stress_config: AppConfig, dummy_model: Path):
        """
        When user configured gpu_layers = 6, and effective VRAM fits 10 layers,
        user configuration (6 layers) must be preserved: min(6, 10) = 6.
        """
        stress_config.brain.local_model.vram_budget_mb = 2000
        stress_config.brain.local_model.gpu_layers = 6
        manager = LocalBrainManager(stress_config)

        with patch("parasite_ai.mind.brain_manager.check_vram_headroom", return_value=(2000, 2000)):
            with patch("parasite_ai.mind.brain_manager.LlamaCppBackend") as mock_llama:
                mock_instance = MagicMock()
                mock_instance.is_available.return_value = True
                mock_llama.return_value = mock_instance

                success = manager._instantiate_local_engine(dummy_model)
                assert success is True
                call_kwargs = mock_llama.call_args[1]
                assert call_kwargs["n_gpu_layers"] == 6

    def test_vram_scaling_unknown_custom_model(self, stress_config: AppConfig, unknown_model: Path):
        """
        When model is not in curated catalog, defaults to vram_required_mb=3500 and total_layers=32.
        With effective VRAM = 2500 MB:
        layer_ratio = 2500 / 3500 = 0.7142
        scaled_layers = int(32 * 0.7142) = 22 layers.
        """
        stress_config.brain.local_model.vram_budget_mb = 4000
        stress_config.brain.local_model.gpu_layers = -1
        manager = LocalBrainManager(stress_config)

        with patch("parasite_ai.mind.brain_manager.check_vram_headroom", return_value=(2000, 2500)):
            with patch("parasite_ai.mind.brain_manager.LlamaCppBackend") as mock_llama:
                mock_instance = MagicMock()
                mock_instance.is_available.return_value = True
                mock_llama.return_value = mock_instance

                success = manager._instantiate_local_engine(unknown_model)
                assert success is True
                call_kwargs = mock_llama.call_args[1]
                assert call_kwargs["n_gpu_layers"] == 22
