"""
Tests for parasite_ai.mind.brain_manager module.
Verifies GGUF validation, pluggable backends, streaming downloads, zero-VRAM browser offload,
and dual-mind inference dispatch.
"""

import time
import struct
from pathlib import Path
from typing import Any, Dict, List
import pytest

from parasite_ai.config import AppConfig, get_default_config
from parasite_ai.mind.brain_manager import (
    BrainMode,
    BrainState,
    BrainStatus,
    DownloadProgress,
    LocalBrainManager,
    MockBackend,
    BrowserOffloadBackend,
    OpenAIEndpointBackend,
    validate_gguf_header,
    check_vram_headroom,
    format_bytes,
)


def create_mock_gguf(file_path: Path, version: int = 3, extra_bytes: int = 128) -> None:
    """Helper to write a binary file with valid GGUF magic bytes and version."""
    magic = b"GGUF"
    ver_bytes = struct.pack("<I", version)
    payload = b"\x00" * extra_bytes
    file_path.write_bytes(magic + ver_bytes + payload)


def test_models_dir_creation(tmp_path: Path):
    """Verify LocalBrainManager creates models directory if missing."""
    models_dir = tmp_path / "custom_models"
    assert not models_dir.exists()

    cfg = get_default_config()
    cfg.system.models_dir = models_dir

    manager = LocalBrainManager(cfg)
    assert models_dir.exists()
    assert models_dir.is_dir()


def test_scan_models_empty(tmp_path: Path):
    """Verify scan_models reports catalog models as not downloaded when directory is empty."""
    models_dir = tmp_path / "models_empty"
    models_dir.mkdir()

    cfg = get_default_config()
    cfg.system.models_dir = models_dir

    manager = LocalBrainManager(cfg)
    models = manager.scan_models()
    assert len(models) >= 3

    # None should be downloaded yet
    for m in models:
        assert m.is_downloaded is False
        assert m.is_valid_gguf is False
        assert m.file_path is None


def test_gguf_header_validation(tmp_path: Path):
    """Verify binary GGUF header checking with valid, corrupt, and edge-case inputs."""
    # 1. Valid GGUF v2 and v3
    v2_file = tmp_path / "valid_v2.gguf"
    create_mock_gguf(v2_file, version=2)
    assert validate_gguf_header(v2_file) is True

    v3_file = tmp_path / "valid_v3.gguf"
    create_mock_gguf(v3_file, version=3)
    assert validate_gguf_header(v3_file) is True

    # 2. Corrupt magic bytes
    bad_magic = tmp_path / "bad_magic.gguf"
    bad_magic.write_bytes(b"NOTG" + struct.pack("<I", 3) + b"\x00" * 32)
    assert validate_gguf_header(bad_magic) is False

    # 3. Unsupported GGUF version (e.g. version 1 or 4)
    bad_version = tmp_path / "bad_version.gguf"
    create_mock_gguf(bad_version, version=1)
    assert validate_gguf_header(bad_version) is False

    bad_version_4 = tmp_path / "bad_version_4.gguf"
    create_mock_gguf(bad_version_4, version=4)
    assert validate_gguf_header(bad_version_4) is False

    # 4. Truncated file (< 8 bytes)
    truncated = tmp_path / "truncated.gguf"
    truncated.write_bytes(b"GGUF\x03")
    assert validate_gguf_header(truncated) is False

    # 5. Non-existent file
    missing = tmp_path / "non_existent.gguf"
    assert validate_gguf_header(missing) is False


def test_scan_models_populated(tmp_path: Path):
    """Verify scan_models discovers valid GGUF files on disk."""
    models_dir = tmp_path / "models_pop"
    models_dir.mkdir()

    # Create one curated model
    curated_file = models_dir / "qwen2.5-3b-instruct-q4_k_m.gguf"
    create_mock_gguf(curated_file, version=3)

    # Create an arbitrary custom model
    custom_file = models_dir / "custom_expert.gguf"
    create_mock_gguf(custom_file, version=3)

    cfg = get_default_config()
    cfg.system.models_dir = models_dir

    manager = LocalBrainManager(cfg)
    models = manager.scan_models()

    matched_curated = next((m for m in models if m.filename == "qwen2.5-3b-instruct-q4_k_m.gguf"), None)
    assert matched_curated is not None
    assert matched_curated.is_downloaded is True
    assert matched_curated.is_valid_gguf is True
    assert matched_curated.file_path == str(curated_file)

    matched_custom = next((m for m in models if m.filename == "custom_expert.gguf"), None)
    assert matched_custom is not None
    assert matched_custom.is_downloaded is True
    assert matched_custom.is_valid_gguf is True


def test_browser_only_mode_toggle(tmp_path: Path):
    """Verify 1-click toggling between Zero-VRAM Browser Offload and Local GPU mode."""
    models_dir = tmp_path / "models_toggle"
    models_dir.mkdir()

    cfg = get_default_config()
    cfg.system.models_dir = models_dir
    cfg.brain.mode = "browser_offload"

    manager = LocalBrainManager(cfg)
    assert manager.mode == BrainMode.BROWSER_OFFLOAD
    assert manager.state == BrainState.READY_BROWSER_OFFLOAD
    assert isinstance(manager.active_backend, BrowserOffloadBackend)

    # Toggle browser only mode ON (already on, ensures stability)
    manager.toggle_browser_only_mode(True)
    assert manager.mode == BrainMode.BROWSER_OFFLOAD
    assert manager.state == BrainState.READY_BROWSER_OFFLOAD

    # Toggle browser only mode OFF without any model on disk
    manager.toggle_browser_only_mode(False)
    assert manager.mode == BrainMode.LOCAL_LLM
    assert manager.state == BrainState.NO_MODEL_PRESENT

    # Add a valid model and toggle OFF again
    model_file = models_dir / "qwen2.5-3b-instruct-q4_k_m.gguf"
    create_mock_gguf(model_file, version=3)

    manager.toggle_browser_only_mode(False)
    assert manager.mode == BrainMode.LOCAL_LLM
    assert manager.state == BrainState.READY_LOCAL


def test_download_streaming_and_callbacks(tmp_path: Path, monkeypatch):
    """Verify non-blocking download streams chunks, validates GGUF header, and fires callbacks."""
    models_dir = tmp_path / "models_dl"
    models_dir.mkdir()

    cfg = get_default_config()
    cfg.system.models_dir = models_dir

    manager = LocalBrainManager(cfg)

    # Mock httpx.stream to produce binary chunks of a valid GGUF file
    valid_data = b"GGUF" + struct.pack("<I", 3) + b"\x00" * 2048

    class MockStreamResponse:
        def __init__(self):
            self.headers = {"content-length": str(len(valid_data))}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

        def raise_for_status(self):
            pass

        def iter_bytes(self, chunk_size=256):
            # Yield in smaller slices to trigger multi-chunk updates
            for i in range(0, len(valid_data), 512):
                yield valid_data[i : i + 512]
                time.sleep(0.02)

    monkeypatch.setattr("httpx.stream", lambda *args, **kwargs: MockStreamResponse())

    progress_events: List[DownloadProgress] = []

    def on_progress(p: DownloadProgress):
        progress_events.append(p)

    success = manager.start_download(
        model_id="Qwen/Qwen2.5-3B-Instruct-GGUF",
        progress_callback=on_progress,
    )
    assert success is True

    # Wait for background thread to complete
    if manager._download_thread:
        manager._download_thread.join(timeout=5.0)

    # Check progress callbacks fired
    assert len(progress_events) > 0
    last_event = progress_events[-1]
    assert last_event.status == "completed"
    assert last_event.percentage == 100.0

    # Target file must exist and be a valid GGUF
    target_file = models_dir / "qwen2.5-3b-instruct-q4_k_m.gguf"
    assert target_file.exists()
    assert validate_gguf_header(target_file) is True
    assert manager.state == BrainState.MODEL_READY_ON_DISK


def test_download_cancellation(tmp_path: Path, monkeypatch):
    """Verify aborting an active download terminates thread and cleans up .tmp file."""
    models_dir = tmp_path / "models_cancel"
    models_dir.mkdir()

    cfg = get_default_config()
    cfg.system.models_dir = models_dir

    manager = LocalBrainManager(cfg)

    # Mock an endless stream that respects cancellation
    class EndlessStreamResponse:
        def __init__(self):
            self.headers = {"content-length": "100000000"}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

        def raise_for_status(self):
            pass

        def iter_bytes(self, chunk_size=256):
            while True:
                yield b"A" * 1024
                time.sleep(0.01)

    monkeypatch.setattr("httpx.stream", lambda *args, **kwargs: EndlessStreamResponse())

    events: List[DownloadProgress] = []
    manager.start_download(
        model_id="Qwen/Qwen2.5-3B-Instruct-GGUF",
        progress_callback=lambda p: events.append(p),
    )

    time.sleep(0.05)
    manager.cancel_download()

    if manager._download_thread:
        manager._download_thread.join(timeout=3.0)

    # Verify state and cleanup
    assert manager.state == BrainState.NO_MODEL_PRESENT
    tmp_files = list(models_dir.glob("*.tmp"))
    assert len(tmp_files) == 0


def test_inference_dispatch_mock():
    """Verify unified inference dispatch produces expected Pass 1 thoughts and Pass 2 actions."""
    cfg = get_default_config()
    cfg.brain.mode = "mock"

    manager = LocalBrainManager(cfg)
    assert manager.mode == BrainMode.MOCK
    assert isinstance(manager.active_backend, MockBackend)

    # Test Pass 1: Persona monologue thought
    thought = manager.generate_thought(
        scene_summary="Desktop foreground: Notepad window",
        memory_context="Previous: Clicked notepad",
        user_goal="Write a greeting note",
    )
    assert isinstance(thought, str)
    assert len(thought) > 10

    # Test Pass 2: Structured Action generation
    action = manager.generate_action(
        persona_intent="Click the text editor area to begin typing",
        som_elements=[{"id": 1, "label": "Text Editor", "bbox": [100, 100, 400, 300]}],
        memory_context="No recent actions",
    )
    assert isinstance(action, dict)
    assert "action" in action
    assert action["action"] == "CLICK"
    assert action["target_id"] == 1


def test_action_json_resilience():
    """Verify resilient parsing handles markdown fences, preambles, and malformed outputs."""
    cfg = get_default_config()
    cfg.brain.mode = "mock"
    manager = LocalBrainManager(cfg)
    mock_backend: MockBackend = manager.active_backend  # type: ignore

    # Case 1: Markdown code fences
    mock_backend.enqueue_response(
        "```json\n"
        "{\n"
        '  "action": "CLICK_AND_TYPE",\n'
        '  "target_id": 2,\n'
        '  "text": "Hello World",\n'
        '  "reasoning": "Focus search box and type"\n'
        "}\n"
        "```"
    )
    action1 = manager.generate_action("Type search text", [], "")
    assert action1["action"] == "CLICK_AND_TYPE"
    assert action1["target_id"] == 2
    assert action1["text"] == "Hello World"

    # Case 2: Conversational preamble before JSON
    mock_backend.enqueue_response(
        "I will now proceed with clicking the button.\n"
        '{"action": "CLICK", "target_id": 5, "coordinates": [250, 400], "reasoning": "Click confirm"}'
    )
    action2 = manager.generate_action("Click confirm", [], "")
    assert action2["action"] == "CLICK"
    assert action2["target_id"] == 5

    # Case 3: Completely broken non-JSON output -> triggers safe WAIT fallback
    mock_backend.enqueue_response("Sorry, I cannot perform this action right now due to uncertainty.")
    action3 = manager.generate_action("Perform action", [], "")
    assert action3["action"] == "WAIT"
    assert action3["wait_ms"] == 1000
    assert "Re-evaluating target" in action3["reasoning"]


def test_vram_budget_evaluation():
    """Verify VRAM headroom check and budget telemetry."""
    used_mb, free_mb = check_vram_headroom()
    assert isinstance(used_mb, int)
    assert isinstance(free_mb, int)
    assert used_mb >= 0
    assert free_mb >= 0

    cfg = get_default_config()
    manager = LocalBrainManager(cfg)
    status: BrainStatus = manager.get_status()
    assert status.vram_budget_mb == 5500
    assert status.vram_used_mb is not None
    assert status.vram_free_mb is not None


def test_format_bytes():
    """Verify format_bytes utility formatting."""
    assert format_bytes(0) == "0 B"
    assert format_bytes(512) == "512.00 B"
    assert format_bytes(1024 * 1024) == "1.00 MB"
    assert format_bytes(2328221696) == "2.17 GB"


def test_action_json_resilience_with_braces_in_preamble():
    """Verify multi-pass JSON extractor correctly parses actions when preamble contains braces."""
    cfg = get_default_config()
    cfg.brain.mode = "mock"
    manager = LocalBrainManager(cfg)
    mock_backend: MockBackend = manager.active_backend  # type: ignore

    # Preamble contains braces like {window: active} followed by markdown code block
    mock_backend.enqueue_response(
        "I observed {window: active} and {focus: true} on screen.\n"
        "```json\n"
        "{\n"
        '  "action": "CLICK",\n'
        '  "target_id": 4,\n'
        '  "coordinates": [320, 480],\n'
        '  "reasoning": "Click search submit button"\n'
        "}\n"
        "```"
    )
    action = manager.generate_action("Submit search", [], "")
    assert action["action"] == "CLICK"
    assert action["target_id"] == 4
    assert action["coordinates"] == [320, 480]


def test_download_network_failure(tmp_path: Path, monkeypatch):
    """Verify network or HTTP failure during download sets state to DOWNLOAD_FAILED and cleans up."""
    models_dir = tmp_path / "models_fail"
    models_dir.mkdir()

    cfg = get_default_config()
    cfg.system.models_dir = models_dir

    manager = LocalBrainManager(cfg)

    # Mock an HTTP error on stream
    def mock_stream_error(*args, **kwargs):
        raise httpx.ConnectError("Connection refused by remote host")

    monkeypatch.setattr("httpx.stream", mock_stream_error)

    events: List[DownloadProgress] = []
    success = manager.start_download(
        model_id="Qwen/Qwen2.5-3B-Instruct-GGUF",
        progress_callback=lambda p: events.append(p),
    )
    assert success is True

    if manager._download_thread:
        manager._download_thread.join(timeout=3.0)

    assert manager.state == BrainState.DOWNLOAD_FAILED
    assert len(events) > 0
    assert events[-1].status == "failed"
    tmp_files = list(models_dir.glob("*.tmp"))
    assert len(tmp_files) == 0


def test_download_already_in_progress(tmp_path: Path, monkeypatch):
    """Verify start_download returns False if a download is already actively running."""
    models_dir = tmp_path / "models_busy"
    models_dir.mkdir()

    cfg = get_default_config()
    cfg.system.models_dir = models_dir

    manager = LocalBrainManager(cfg)

    # Keep download running via sleeping generator
    class HangingStreamResponse:
        def __init__(self):
            self.headers = {"content-length": "100000"}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

        def raise_for_status(self):
            pass

        def iter_bytes(self, chunk_size=256):
            while True:
                time.sleep(0.1)
                yield b"\x00" * 100

    monkeypatch.setattr("httpx.stream", lambda *args, **kwargs: HangingStreamResponse())

    started = manager.start_download("Qwen/Qwen2.5-3B-Instruct-GGUF")
    assert started is True

    # Second call must be rejected
    second_started = manager.start_download("Qwen/Qwen2.5-3B-Instruct-GGUF")
    assert second_started is False

    # Clean up
    manager.cancel_download()


def test_load_and_unload_model(tmp_path: Path):
    """Verify load_model and unload_model handle valid and invalid files correctly."""
    models_dir = tmp_path / "models_load"
    models_dir.mkdir()

    cfg = get_default_config()
    cfg.system.models_dir = models_dir
    cfg.brain.mode = "local_llm"

    manager = LocalBrainManager(cfg)
    assert manager.state in (BrainState.READY_BROWSER_OFFLOAD, BrainState.NO_MODEL_PRESENT)

    # 1. Loading non-existent file returns False
    assert manager.load_model("non_existent.gguf") is False
    assert manager.state == BrainState.NO_MODEL_PRESENT

    # 2. Loading valid GGUF succeeds
    valid_file = models_dir / "test_model.gguf"
    create_mock_gguf(valid_file, version=3)

    assert manager.load_model("test_model.gguf") is True
    assert manager.state == BrainState.READY_LOCAL
    assert manager.current_model == "test_model.gguf"

    # 3. Unload model transitions to MODEL_READY_ON_DISK
    manager.unload_model()
    assert manager.state == BrainState.MODEL_READY_ON_DISK


def test_browser_offload_backend_delegation():
    """Verify BrowserOffloadBackend properly delegates generation to an attached offloader."""
    class MockOffloader:
        def __init__(self):
            self.last_query = None
            self.last_browser = None

        def query_web_ai(self, query: str, browser_type: str = "chrome") -> str:
            self.last_query = query
            self.last_browser = browser_type
            return "Harvested response from web AI via sentinel verification"

    offloader = MockOffloader()
    backend = BrowserOffloadBackend(offloader=offloader, preferred_browser="opera_gx")

    assert backend.is_available() is True
    result = backend.generate(prompt="What is on screen?", system_prompt="You are Parasite")

    assert result == "Harvested response from web AI via sentinel verification"
    assert offloader.last_browser == "opera_gx"
    assert "You are Parasite" in offloader.last_query
    assert "What is on screen?" in offloader.last_query


def test_openai_endpoint_backend(monkeypatch):
    """Verify OpenAIEndpointBackend queries HTTP chat completions correctly."""
    backend = OpenAIEndpointBackend(endpoint="http://127.0.0.1:8080/v1", model_name="qwen")

    # Mock client.get for /models
    class MockResponse:
        def __init__(self, status_code: int, json_data: dict):
            self.status_code = status_code
            self._json = json_data

        def raise_for_status(self):
            if self.status_code >= 400:
                raise httpx.HTTPStatusError("Error", request=None, response=self)

        def json(self):
            return self._json

    monkeypatch.setattr(
        backend._client,
        "get",
        lambda url: MockResponse(200, {"data": [{"id": "qwen"}]}),
    )
    monkeypatch.setattr(
        backend._client,
        "post",
        lambda url, json: MockResponse(
            200,
            {"choices": [{"message": {"content": "Endpoint inference result"}}]},
        ),
    )

    assert backend.is_available() is True
    reply = backend.generate("Hello world")
    assert reply == "Endpoint inference result"

    backend.unload()

