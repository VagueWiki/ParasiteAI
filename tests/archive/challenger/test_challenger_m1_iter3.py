"""
Empirical stress test suite by teamwork_challenger_m1_iter3_1.
Verifies completeness and integrity of streaming downloads against adversarial payload variations:
1. 0 bytes streamed
2. 1 byte streamed
3. Header-only (16 bytes) streamed
4. real_total - 1 bytes streamed (truncation near boundary)
5. real_total + 100 bytes streamed (oversized payload / stream smuggling / connection corruption)

Verifies:
- State transitions to BrainState.DOWNLOAD_FAILED (never MODEL_READY_ON_DISK)
- Clean cleanup of all temporary .tmp files on disk
- No premature promotion to destination model .gguf file
- Final progress status is 'failed'
"""

import struct
from pathlib import Path
from typing import Optional
import pytest
import httpx

from parasite_ai.config import get_default_config
from parasite_ai.mind.brain_manager import (
    BrainState,
    DownloadProgress,
    LocalBrainManager,
)


class AdversarialStreamingResponse:
    """
    Mock HTTP streaming response that yields an exact number of bytes regardless
    of Content-Length header, starting with a valid GGUF v3 header if bytes permit.
    """
    def __init__(self, content_length: int, send_bytes: int, chunk_size: int = 4096):
        self.headers = {"content-length": str(content_length)}
        self.send_bytes = send_bytes
        self.chunk_size = chunk_size

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def raise_for_status(self):
        pass

    def iter_bytes(self, chunk_size=None):
        if self.send_bytes <= 0:
            return

        header = b"GGUF" + struct.pack("<I", 3) + b"\x00" * 8  # 16 bytes valid GGUF v3 header
        payload = header if self.send_bytes >= len(header) else header[:self.send_bytes]
        if self.send_bytes > len(header):
            payload += b"\x00" * (self.send_bytes - len(header))

        step = chunk_size or self.chunk_size
        for offset in range(0, len(payload), step):
            yield payload[offset : offset + step]


@pytest.mark.parametrize(
    "variation_name,content_length,send_bytes",
    [
        ("0_bytes", 1_000_000, 0),
        ("1_byte", 1_000_000, 1),
        ("16_bytes_header_only", 1_000_000, 16),
        ("real_total_minus_1", 1_000_000, 999_999),
        ("real_total_plus_100", 1_000_000, 1_000_100),
    ],
)
def test_adversarial_stream_truncation_and_overflow(
    tmp_path: Path, monkeypatch, variation_name: str, content_length: int, send_bytes: int
):
    """
    Empirically verifies that any download size mismatch (truncation, header-only,
    empty stream, or oversized stream) is strictly detected and rejected.
    """
    models_dir = tmp_path / f"models_{variation_name}"
    models_dir.mkdir()

    cfg = get_default_config()
    cfg.system.models_dir = models_dir
    manager = LocalBrainManager(cfg)

    monkeypatch.setattr(
        "httpx.stream",
        lambda *args, **kwargs: AdversarialStreamingResponse(
            content_length=content_length,
            send_bytes=send_bytes,
        ),
    )

    events = []
    manager.start_download(
        "Qwen/Qwen2.5-3B-Instruct-GGUF",
        progress_callback=lambda p: events.append(p),
    )

    if manager._download_thread:
        manager._download_thread.join(timeout=3.0)

    # Target model file must NOT exist on disk
    target_files = list(models_dir.glob("*.gguf"))
    assert len(target_files) == 0, (
        f"Vulnerability: Incomplete/mismatched stream ({variation_name}: sent {send_bytes} vs expected {content_length}) "
        f"was promoted to destination model file: {target_files}"
    )

    # Temporary download staging files must be cleanly unlinked
    temp_files = list(models_dir.glob("*.tmp"))
    assert len(temp_files) == 0, (
        f"Resource Leak: Incomplete stream left dangling temporary files: {temp_files}"
    )

    # State must transition to DOWNLOAD_FAILED, never MODEL_READY_ON_DISK
    assert manager.state != BrainState.MODEL_READY_ON_DISK, (
        f"State Violation: Mismatched stream ({variation_name}: sent {send_bytes} vs expected {content_length}) "
        f"transitioned to MODEL_READY_ON_DISK"
    )
    assert manager.state == BrainState.DOWNLOAD_FAILED, (
        f"Expected BrainState.DOWNLOAD_FAILED, got {manager.state}"
    )

    # Callback progress status must be marked failed
    assert len(events) > 0, "No progress callbacks received"
    assert events[-1].status == "failed", (
        f"Expected final progress status 'failed', got '{events[-1].status}'"
    )
