"""
Empirical stress test suite by teamwork_challenger_m1_iter4_1.
Adversarial verification of Iteration 4 two-sided stream bounds check:
1. Early loop break under high chunk sizes:
   - Infinite chunk generator terminates immediately on overflow
   - Giant single-chunk overflow
   - Multi-chunk overflow halts generator consumption (subsequent chunks never read)
   - Single-byte overflow boundary (real_total + 1)
   - Non-positive content length with data rejected
2. Multi-threaded cancel while overflowing:
   - Concurrent hammering of cancel_download during active overflow streaming
   - Reentrant cancellation inside progress_callback during overflow
3. Socket dropouts and network interruptions:
   - Exception (ConnectionResetError / httpx.RemoteProtocolError) on overflow chunk
   - Exception (httpx.ReadTimeout) halfway through stream
   - Socket dropout combined with concurrent cancel
4. Exact boundary verification:
   - Exact size with valid GGUF header promotes to MODEL_READY_ON_DISK
   - Exact size with corrupted GGUF header rejects and cleans up
"""

import struct
import threading
import time
from pathlib import Path
from typing import Iterator
import pytest
import httpx

from parasite_ai.config import get_default_config
from parasite_ai.mind.brain_manager import (
    BrainState,
    DownloadProgress,
    LocalBrainManager,
)


class MockChunkStream:
    """Mock streaming response yielding predetermined chunks with optional callback/exception."""

    def __init__(
        self,
        content_length: int,
        chunks: list[bytes],
        raise_at_chunk_index: int = -1,
        exception_to_raise: Exception = httpx.RemoteProtocolError("Connection dropped"),
        chunk_yield_callback=None,
    ):
        self.headers = {"content-length": str(content_length)}
        self.chunks = chunks
        self.raise_at_chunk_index = raise_at_chunk_index
        self.exception_to_raise = exception_to_raise
        self.chunk_yield_callback = chunk_yield_callback
        self.yielded_chunks_count = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def raise_for_status(self):
        pass

    def iter_bytes(self, chunk_size=None) -> Iterator[bytes]:
        for idx, chunk in enumerate(self.chunks):
            if idx == self.raise_at_chunk_index:
                raise self.exception_to_raise
            self.yielded_chunks_count += 1
            if self.chunk_yield_callback:
                self.chunk_yield_callback(idx, chunk)
            yield chunk


class InfiniteOverflowStream:
    """Mock streaming response that generates endless chunks until aborted."""

    def __init__(self, content_length: int, chunk_payload: bytes):
        self.headers = {"content-length": str(content_length)}
        self.chunk_payload = chunk_payload
        self.chunks_yielded = 0
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.closed = True

    def raise_for_status(self):
        pass

    def iter_bytes(self, chunk_size=None) -> Iterator[bytes]:
        header = b"GGUF" + struct.pack("<I", 3) + b"\x00" * 8
        first = True
        while not self.closed:
            self.chunks_yielded += 1
            if first:
                first = False
                yield header + self.chunk_payload[len(header):]
            else:
                yield self.chunk_payload


# ============================================================================
# 1. Early Loop Break Under High Chunk Sizes
# ============================================================================

class TestEarlyLoopBreakHighChunkSizes:

    def test_infinite_generator_overflow_aborts_immediately(self, tmp_path: Path, monkeypatch):
        """
        Stress test: Infinite stream generator sending 2MB chunks for a 1MB model.
        Verifies: Early break stops the generator after the first chunk exceeding real_total,
        preventing infinite loop, OOM, or disk fill.
        """
        models_dir = tmp_path / "models_infinite"
        models_dir.mkdir()

        cfg = get_default_config()
        cfg.system.models_dir = models_dir
        manager = LocalBrainManager(cfg)

        chunk_2mb = b"A" * (2 * 1024 * 1024)
        mock_stream = InfiniteOverflowStream(content_length=1_000_000, chunk_payload=chunk_2mb)
        monkeypatch.setattr("httpx.stream", lambda *args, **kwargs: mock_stream)

        events = []
        started = manager.start_download(
            "Qwen/Qwen2.5-3B-Instruct-GGUF",
            progress_callback=lambda p: events.append(p),
        )
        assert started is True

        manager._download_thread.join(timeout=3.0)
        assert not manager._download_thread.is_alive(), "Download thread hung in infinite loop!"

        # Generator must have been aborted after the first chunk (2MB > 1MB)
        assert mock_stream.chunks_yielded == 1, (
            f"Expected generator to stop at 1 chunk, but yielded {mock_stream.chunks_yielded}"
        )

        # Target file must not exist
        assert len(list(models_dir.glob("*.gguf"))) == 0
        # Staging file must be unlinked
        assert len(list(models_dir.glob("*.tmp"))) == 0
        # Final state must be DOWNLOAD_FAILED
        assert manager.state == BrainState.DOWNLOAD_FAILED
        assert events[-1].status == "failed"

    def test_giant_chunk_overflow_exceeding_content_length(self, tmp_path: Path, monkeypatch):
        """
        Stress test: A single giant chunk (10MB) sent for a 50KB model.
        Verifies: Immediate overflow break, disk cleanup, state transition to DOWNLOAD_FAILED.
        """
        models_dir = tmp_path / "models_giant_chunk"
        models_dir.mkdir()

        cfg = get_default_config()
        cfg.system.models_dir = models_dir
        manager = LocalBrainManager(cfg)

        giant_chunk = b"GGUF" + struct.pack("<I", 3) + b"\x00" * 8 + b"X" * (10 * 1024 * 1024)
        mock_stream = MockChunkStream(content_length=50_000, chunks=[giant_chunk])
        monkeypatch.setattr("httpx.stream", lambda *args, **kwargs: mock_stream)

        manager.start_download("Qwen/Qwen2.5-3B-Instruct-GGUF")
        manager._download_thread.join(timeout=3.0)

        assert len(list(models_dir.glob("*.gguf"))) == 0
        assert len(list(models_dir.glob("*.tmp"))) == 0
        assert manager.state == BrainState.DOWNLOAD_FAILED

    def test_multi_chunk_overflow_stops_consuming_generator(self, tmp_path: Path, monkeypatch):
        """
        Stress test: 20 chunks of 512KB (10MB total) for a 1MB model.
        Verifies: Stream breaks at chunk 3 (1.5MB > 1MB) and chunks 4..20 are NEVER consumed.
        """
        models_dir = tmp_path / "models_multi_chunk"
        models_dir.mkdir()

        cfg = get_default_config()
        cfg.system.models_dir = models_dir
        manager = LocalBrainManager(cfg)

        chunk_512k = b"\x00" * (512 * 1024)
        chunks = [b"GGUF" + struct.pack("<I", 3) + b"\x00" * 8 + chunk_512k[16:]] + [chunk_512k] * 19

        mock_stream = MockChunkStream(content_length=1_000_000, chunks=chunks)
        monkeypatch.setattr("httpx.stream", lambda *args, **kwargs: mock_stream)

        manager.start_download("Qwen/Qwen2.5-3B-Instruct-GGUF")
        manager._download_thread.join(timeout=3.0)

        # Chunks 1 and 2 = 1,024,000 bytes > 1,000,000 bytes. Chunk 2 triggers break.
        # Chunks consumed must be <= 3, definitely not 20!
        assert mock_stream.yielded_chunks_count <= 3, (
            f"Generator consumed {mock_stream.yielded_chunks_count} chunks, expected early break <= 3"
        )
        assert len(list(models_dir.glob("*.gguf"))) == 0
        assert len(list(models_dir.glob("*.tmp"))) == 0
        assert manager.state == BrainState.DOWNLOAD_FAILED

    def test_single_byte_overflow_boundary(self, tmp_path: Path, monkeypatch):
        """
        Boundary test: Exactly real_total + 1 byte sent (tightest overflow boundary).
        Verifies: Rejected, unlinked, state is DOWNLOAD_FAILED.
        """
        models_dir = tmp_path / "models_plus_1"
        models_dir.mkdir()

        cfg = get_default_config()
        cfg.system.models_dir = models_dir
        manager = LocalBrainManager(cfg)

        content_length = 5000
        payload = b"GGUF" + struct.pack("<I", 3) + b"\x00" * (content_length + 1 - 8)
        mock_stream = MockChunkStream(content_length=content_length, chunks=[payload])
        monkeypatch.setattr("httpx.stream", lambda *args, **kwargs: mock_stream)

        manager.start_download("Qwen/Qwen2.5-3B-Instruct-GGUF")
        manager._download_thread.join(timeout=3.0)

        assert len(list(models_dir.glob("*.gguf"))) == 0
        assert len(list(models_dir.glob("*.tmp"))) == 0
        assert manager.state == BrainState.DOWNLOAD_FAILED


# ============================================================================
# 2. Multi-Threaded Cancel While Overflowing
# ============================================================================

class TestMultiThreadedCancelWhileOverflowing:

    def test_hammer_cancel_during_oversized_stream(self, tmp_path: Path, monkeypatch):
        """
        Stress test: 10 threads concurrently hammer cancel_download() while an overflowing stream
        is being received with slight delays.
        Verifies: No deadlocks, no exceptions raised, no file promotion, clean disk state.
        """
        models_dir = tmp_path / "models_hammer_cancel"
        models_dir.mkdir()

        cfg = get_default_config()
        cfg.system.models_dir = models_dir
        manager = LocalBrainManager(cfg)

        def slow_chunk(idx, chunk):
            time.sleep(0.01)

        chunks = [b"GGUF" + struct.pack("<I", 3) + b"\x00" * 8] + [b"O" * 50_000] * 10
        mock_stream = MockChunkStream(
            content_length=100_000,
            chunks=chunks,
            chunk_yield_callback=slow_chunk,
        )
        monkeypatch.setattr("httpx.stream", lambda *args, **kwargs: mock_stream)

        manager.start_download("Qwen/Qwen2.5-3B-Instruct-GGUF")

        cancel_errors = []

        def cancel_hammer():
            try:
                for _ in range(10):
                    manager.cancel_download()
                    time.sleep(0.005)
            except Exception as e:
                cancel_errors.append(e)

        threads = [threading.Thread(target=cancel_hammer) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=3.0)

        if manager._download_thread:
            manager._download_thread.join(timeout=3.0)

        assert not cancel_errors, f"Errors during cancel hammering: {cancel_errors}"
        assert len(list(models_dir.glob("*.gguf"))) == 0
        assert len(list(models_dir.glob("*.tmp"))) == 0
        assert manager.state in (BrainState.NO_MODEL_PRESENT, BrainState.DOWNLOAD_FAILED)

    def test_cancel_inside_callback_during_overflow(self, tmp_path: Path, monkeypatch):
        """
        Stress test: The progress callback itself invokes cancel_download() at the moment
        bytes_downloaded exceeds total_bytes.
        Verifies: Thread-safety of cancel_download when triggered from within the download thread's callback.
        """
        models_dir = tmp_path / "models_callback_cancel"
        models_dir.mkdir()

        cfg = get_default_config()
        cfg.system.models_dir = models_dir
        manager = LocalBrainManager(cfg)

        callback_errors = []

        def on_progress(p: DownloadProgress):
            if p.bytes_downloaded > 50_000:
                try:
                    manager.cancel_download()
                except Exception as exc:
                    callback_errors.append(exc)

        # Chunks exceeding 50,000 bytes
        chunks = [b"GGUF" + struct.pack("<I", 3) + b"\x00" * 8 + b"B" * 60_000]
        mock_stream = MockChunkStream(content_length=50_000, chunks=chunks)
        monkeypatch.setattr("httpx.stream", lambda *args, **kwargs: mock_stream)

        manager.start_download("Qwen/Qwen2.5-3B-Instruct-GGUF", progress_callback=on_progress)
        manager._download_thread.join(timeout=3.0)

        assert not callback_errors, f"Callback cancel raised exceptions: {callback_errors}"
        assert len(list(models_dir.glob("*.gguf"))) == 0
        assert len(list(models_dir.glob("*.tmp"))) == 0
        assert manager.state in (BrainState.NO_MODEL_PRESENT, BrainState.DOWNLOAD_FAILED)


# ============================================================================
# 3. Socket Dropouts and Network Interruptions
# ============================================================================

class TestSocketDropoutsAndNetworkExceptions:

    def test_socket_dropout_on_overflow_chunk(self, tmp_path: Path, monkeypatch):
        """
        Stress test: Socket drops (ConnectionResetError) exactly when the overflowing chunk is yielded.
        Verifies: Exception is cleanly caught, temp file unlinked, state is DOWNLOAD_FAILED.
        """
        models_dir = tmp_path / "models_drop_overflow"
        models_dir.mkdir()

        cfg = get_default_config()
        cfg.system.models_dir = models_dir
        manager = LocalBrainManager(cfg)

        chunks = [
            b"GGUF" + struct.pack("<I", 3) + b"\x00" * 8 + b"C" * 40_000,
            b"D" * 80_000,  # This chunk would overflow
        ]
        mock_stream = MockChunkStream(
            content_length=50_000,
            chunks=chunks,
            raise_at_chunk_index=1,
            exception_to_raise=ConnectionResetError("WSAECONNRESET: Connection reset by peer"),
        )
        monkeypatch.setattr("httpx.stream", lambda *args, **kwargs: mock_stream)

        manager.start_download("Qwen/Qwen2.5-3B-Instruct-GGUF")
        manager._download_thread.join(timeout=3.0)

        assert len(list(models_dir.glob("*.gguf"))) == 0
        assert len(list(models_dir.glob("*.tmp"))) == 0
        assert manager.state == BrainState.DOWNLOAD_FAILED

    def test_socket_read_timeout_during_streaming(self, tmp_path: Path, monkeypatch):
        """
        Stress test: httpx.ReadTimeout occurs halfway through download.
        Verifies: Caught cleanly, temp file unlinked, state is DOWNLOAD_FAILED.
        """
        models_dir = tmp_path / "models_timeout"
        models_dir.mkdir()

        cfg = get_default_config()
        cfg.system.models_dir = models_dir
        manager = LocalBrainManager(cfg)

        chunks = [
            b"GGUF" + struct.pack("<I", 3) + b"\x00" * 8 + b"E" * 20_000,
            b"F" * 20_000,
        ]
        mock_stream = MockChunkStream(
            content_length=100_000,
            chunks=chunks,
            raise_at_chunk_index=1,
            exception_to_raise=httpx.ReadTimeout("Socket read timed out after 30s"),
        )
        monkeypatch.setattr("httpx.stream", lambda *args, **kwargs: mock_stream)

        manager.start_download("Qwen/Qwen2.5-3B-Instruct-GGUF")
        manager._download_thread.join(timeout=3.0)

        assert len(list(models_dir.glob("*.gguf"))) == 0
        assert len(list(models_dir.glob("*.tmp"))) == 0
        assert manager.state == BrainState.DOWNLOAD_FAILED

    def test_socket_dropout_with_concurrent_cancel(self, tmp_path: Path, monkeypatch):
        """
        Stress test: Network drops simultaneously with user cancelling.
        Verifies: No unhandled race condition, cleanup succeeds.
        """
        models_dir = tmp_path / "models_drop_cancel"
        models_dir.mkdir()

        cfg = get_default_config()
        cfg.system.models_dir = models_dir
        manager = LocalBrainManager(cfg)

        def raise_and_cancel(idx, chunk):
            manager.cancel_download()
            raise httpx.NetworkError("Network unreachable")

        chunks = [b"GGUF" + struct.pack("<I", 3) + b"\x00" * 8]
        mock_stream = MockChunkStream(
            content_length=100_000,
            chunks=chunks,
            chunk_yield_callback=raise_and_cancel,
        )
        monkeypatch.setattr("httpx.stream", lambda *args, **kwargs: mock_stream)

        manager.start_download("Qwen/Qwen2.5-3B-Instruct-GGUF")
        manager._download_thread.join(timeout=3.0)

        assert len(list(models_dir.glob("*.gguf"))) == 0
        assert len(list(models_dir.glob("*.tmp"))) == 0
        assert manager.state in (BrainState.NO_MODEL_PRESENT, BrainState.DOWNLOAD_FAILED)


# ============================================================================
# 4. Exact Boundary Verification
# ============================================================================

class TestExactBoundaryIntegrity:

    def test_exact_size_with_valid_gguf_promotes_successfully(self, tmp_path: Path, monkeypatch):
        """
        Verification: Exactly matching content length and payload with valid GGUF header
        successfully verifies and promotes to MODEL_READY_ON_DISK.
        """
        models_dir = tmp_path / "models_valid_exact"
        models_dir.mkdir()

        cfg = get_default_config()
        cfg.system.models_dir = models_dir
        manager = LocalBrainManager(cfg)

        total = 50_000
        payload = b"GGUF" + struct.pack("<I", 3) + b"\x00" * (total - 8)
        mock_stream = MockChunkStream(content_length=total, chunks=[payload])
        monkeypatch.setattr("httpx.stream", lambda *args, **kwargs: mock_stream)

        events = []
        manager.start_download(
            "Qwen/Qwen2.5-3B-Instruct-GGUF",
            progress_callback=lambda p: events.append(p),
        )
        manager._download_thread.join(timeout=3.0)

        # Must promote to destination .gguf file
        target_files = list(models_dir.glob("*.gguf"))
        assert len(target_files) == 1
        assert target_files[0].stat().st_size == total
        # Temporary file unlinked
        assert len(list(models_dir.glob("*.tmp"))) == 0
        # State transitions to MODEL_READY_ON_DISK
        assert manager.state == BrainState.MODEL_READY_ON_DISK
        assert events[-1].status == "completed"

    def test_exact_size_with_corrupted_gguf_header_fails_validation(self, tmp_path: Path, monkeypatch):
        """
        Adversarial test: Exact size matches Content-Length, but header is NOT a valid GGUF header.
        Verifies: Completeness check passes, but GGUF header validation catches corruption,
        unlinks temp file, and fails.
        """
        models_dir = tmp_path / "models_corrupted_exact"
        models_dir.mkdir()

        cfg = get_default_config()
        cfg.system.models_dir = models_dir
        manager = LocalBrainManager(cfg)

        total = 50_000
        # Invalid magic bytes "BAD!"
        corrupted_payload = b"BAD!" + b"\x00" * (total - 4)
        mock_stream = MockChunkStream(content_length=total, chunks=[corrupted_payload])
        monkeypatch.setattr("httpx.stream", lambda *args, **kwargs: mock_stream)

        events = []
        manager.start_download(
            "Qwen/Qwen2.5-3B-Instruct-GGUF",
            progress_callback=lambda p: events.append(p),
        )
        manager._download_thread.join(timeout=3.0)

        assert len(list(models_dir.glob("*.gguf"))) == 0
        assert len(list(models_dir.glob("*.tmp"))) == 0
        assert manager.state == BrainState.DOWNLOAD_FAILED
        assert events[-1].status == "failed"
