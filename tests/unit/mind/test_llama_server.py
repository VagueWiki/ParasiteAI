"""
Tests for ParasiteAI - Persistent llama-server Supervisor & LlamaServerBackend.
"""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from parasite_ai.config import AppConfig, LocalModelConfig
from parasite_ai.mind.brain_manager import (
    CURATED_MODELS,
    BrainMode,
    BrainState,
    LlamaServerBackend,
    LocalBrainManager,
    ModelMetadata,
)


def test_llama_server_config_defaults() -> None:
    """Verifies LocalModelConfig schema includes llama-server supervisor fields."""
    cfg = LocalModelConfig()
    assert cfg.server_host == "127.0.0.1"
    assert cfg.server_port == 8080
    assert cfg.auto_start_server is True
    assert cfg.server_startup_timeout_sec == 60.0
    assert "llama-server" in cfg.server_binary_path


def test_uitars_curated_catalog_entries() -> None:
    """Verifies that UI-TARS-1.5-7B GGUF models are present in CURATED_MODELS with accurate metadata."""
    uitars_entries = [m for m in CURATED_MODELS if "UI-TARS-1.5-7B" in m.get("filename", "")]
    assert len(uitars_entries) >= 2, "Expected IQ4_XS and Q4_K_M UI-TARS entries"

    iq4 = next((m for m in uitars_entries if "IQ4_XS" in m["filename"]), None)
    assert iq4 is not None
    assert iq4["mmproj_filename"] == "UI-TARS-1.5-7B.mmproj-Q8_0.gguf"
    assert iq4["vram_required_mb"] <= 5500, "Must fit under 6,500 MB budget"

    q4 = next((m for m in uitars_entries if "Q4_K_M" in m["filename"]), None)
    assert q4 is not None
    assert q4["vram_required_mb"] <= 5600


def test_llama_server_health_check_ok() -> None:
    """Verifies check_health() parses status 'ok' and sets is_available True."""
    mock_client = MagicMock(spec=httpx.Client)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "ok"}
    mock_client.get.return_value = mock_resp

    backend = LlamaServerBackend(auto_start=False, client=mock_client)
    assert backend.check_health()["status"] == "ok"
    assert backend.is_available() is True


def test_llama_server_health_check_loading_and_unreachable() -> None:
    """Verifies check_health() handles model loading (503) and unreachable server gracefully."""
    mock_client = MagicMock(spec=httpx.Client)

    # 503 Loading model
    mock_resp_503 = MagicMock()
    mock_resp_503.status_code = 503
    mock_client.get.return_value = mock_resp_503
    backend = LlamaServerBackend(auto_start=False, client=mock_client)
    assert backend.check_health()["status"] == "loading model"
    assert backend.is_available() is False

    # Connection error
    mock_client.get.side_effect = httpx.ConnectError("Connection refused")
    assert backend.check_health()["status"] == "unreachable"
    assert backend.is_available() is False


def test_llama_server_attach_mode_zero_cold_start() -> None:
    """Verifies that an already-running server attaches instantly without spawning a process."""
    mock_client = MagicMock(spec=httpx.Client)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "ok"}
    mock_client.get.return_value = mock_resp

    with patch.object(LlamaServerBackend, "start_server_daemon") as mock_start:
        backend = LlamaServerBackend(auto_start=True, client=mock_client)
        assert backend.is_available() is True
        assert backend._is_external is True
        mock_start.assert_not_called()


def test_llama_server_generate_text_and_vision_payload() -> None:
    """Verifies generate() sends correct OpenAI chat payload for text and multimodal base64."""
    mock_client = MagicMock(spec=httpx.Client)
    # Health check returns ok
    mock_health_resp = MagicMock()
    mock_health_resp.status_code = 200
    mock_health_resp.json.return_value = {"status": "ok"}
    mock_client.get.return_value = mock_health_resp

    # Chat completion response
    mock_chat_resp = MagicMock()
    mock_chat_resp.status_code = 200
    mock_chat_resp.json.return_value = {
        "choices": [
            {"message": {"content": "Thought: Ready. Action: click(start_box='(500,500)')"}}
        ]
    }
    mock_client.post.return_value = mock_chat_resp

    backend = LlamaServerBackend(
        auto_start=False,
        client=mock_client,
        mmproj_path=Path("models/fake_mmproj.gguf"),
    )
    backend._is_external = True

    # Force supports_vision to True for test
    with patch.object(backend, "supports_vision", return_value=True):
        resp = backend.generate(
            prompt="Click on target",
            system_prompt="You are UI-TARS.",
            max_tokens=256,
            temperature=0.2,
            stop_sequences=["<|endoftext|>"],
            image_base64="AAAA",
        )

    assert "click" in resp
    # Inspect the payload posted to /v1/chat/completions
    assert mock_client.post.called
    call_args = mock_client.post.call_args
    assert call_args[0][0] == "http://127.0.0.1:8080/v1/chat/completions"
    payload = call_args[1]["json"]
    assert payload["max_tokens"] == 256
    assert payload["temperature"] == 0.2
    assert payload["stop"] == ["<|endoftext|>"]
    messages = payload["messages"]
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == "You are UI-TARS."
    assert messages[1]["role"] == "user"
    assert isinstance(messages[1]["content"], list)
    # Prefix-stable ordering: text before image_url
    assert messages[1]["content"][0]["type"] == "text"
    assert messages[1]["content"][0]["text"] == "Click on target"
    assert messages[1]["content"][1]["type"] == "image_url"
    assert messages[1]["content"][1]["image_url"]["url"].startswith("data:image/jpeg;base64,AAAA")


def test_llama_server_quantized_kv_cache_and_reuse_args(tmp_path: Path) -> None:
    """Verifies that LlamaServerBackend passes -ctk, -ctv, and --cache-reuse to llama-server.exe."""
    fake_exe = tmp_path / "llama-server.exe"
    fake_exe.write_bytes(b"MZ" + b"\x00" * 100)
    fake_model = tmp_path / "model.gguf"
    fake_model.write_bytes(b"GGUF" + b"\x03\x00\x00\x00" + b"\x00" * 1024)
    # Write at least 10 MB to satisfy min size guard
    fake_model.write_bytes(b"GGUF" + b"\x03\x00\x00\x00" + b"\x00" * (10 * 1024 * 1024 + 100))

    backend = LlamaServerBackend(
        server_binary=fake_exe,
        model_path=fake_model,
        auto_start=False,
        n_ctx=8192,
        kv_cache_type_k="q8_0",
        kv_cache_type_v="q8_0",
        cache_reuse_tokens=256,
    )
    assert backend.n_ctx == 8192
    assert backend.kv_cache_type_k == "q8_0"
    assert backend.kv_cache_type_v == "q8_0"
    assert backend.cache_reuse_tokens == 256

    with patch("subprocess.Popen") as mock_popen:
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc

        with patch.object(backend, "check_health", return_value={"status": "ok"}), \
             patch.dict("os.environ", {"PARASITE_TEST_REAL_LLM": "1"}):
            success = backend.start_server_daemon()
            assert success is True

        assert mock_popen.called
        cmd = mock_popen.call_args[0][0]
        assert "-c" in cmd
        assert cmd[cmd.index("-c") + 1] == "8192"
        assert "-ctk" in cmd
        assert cmd[cmd.index("-ctk") + 1] == "q8_0"
        assert "-ctv" in cmd
        assert cmd[cmd.index("-ctv") + 1] == "q8_0"
        assert "--cache-reuse" in cmd
        assert cmd[cmd.index("--cache-reuse") + 1] == "256"

    # Multimodal vision daemon: --cache-reuse must be omitted to prevent llama.cpp warnings
    mmproj_fake = tmp_path / "test.mmproj"
    mmproj_fake.write_bytes(b"GGUF_TEST_MMPROJ")
    backend_mm = LlamaServerBackend(
        server_binary=str(fake_exe),
        model_path=str(fake_model),
        mmproj_path=str(mmproj_fake),
        auto_start=False,
        cache_reuse_tokens=256,
    )
    with patch("subprocess.Popen") as mock_popen_mm:
        mock_proc_mm = MagicMock()
        mock_proc_mm.poll.return_value = None
        mock_popen_mm.return_value = mock_proc_mm

        with patch.object(backend_mm, "check_health", return_value={"status": "ok"}), \
             patch.dict("os.environ", {"PARASITE_TEST_REAL_LLM": "1"}):
            success = backend_mm.start_server_daemon()
            assert success is True

        assert mock_popen_mm.called
        cmd_mm = mock_popen_mm.call_args[0][0]
        assert "--mmproj" in cmd_mm
        assert "--cache-reuse" not in cmd_mm


def test_llama_server_unload_lifecycle() -> None:
    """Verifies that unload does not terminate external servers, but terminates managed subprocesses."""
    mock_client = MagicMock(spec=httpx.Client)
    backend = LlamaServerBackend(auto_start=False, client=mock_client)

    # 1. External attached daemon: should not terminate
    backend._is_external = True
    backend._managed_process = MagicMock(spec=subprocess.Popen)
    backend.unload()
    backend._managed_process.terminate.assert_not_called()

    # 2. Managed spawned daemon:
    # A. Default keep_alive_on_exit=True detaches without killing the server
    backend._is_external = False
    mock_proc = MagicMock(spec=subprocess.Popen)
    mock_proc.pid = 12345
    backend._managed_process = mock_proc
    backend.unload()
    mock_proc.terminate.assert_not_called()

    # B. Explicit terminate_daemon=True terminates the process
    backend._managed_process = mock_proc
    backend.unload(terminate_daemon=True)
    mock_proc.terminate.assert_called_once()
    mock_proc.wait.assert_called_once()
    assert backend._managed_process is None


def test_brain_manager_scan_models_includes_uitars(tmp_path: Path) -> None:
    """Verifies that LocalBrainManager.scan_models() detects UI-TARS models in the curated catalog."""
    cfg = AppConfig()
    cfg.system.models_dir = str(tmp_path)
    mgr = LocalBrainManager(cfg)
    models = mgr.scan_models()

    ids = [m.model_id for m in models]
    assert "mradermacher/UI-TARS-1.5-7B-GGUF" in ids
    uitars_meta = next(m for m in models if m.model_id == "mradermacher/UI-TARS-1.5-7B-GGUF")
    assert uitars_meta.vram_required_mb <= 5500
