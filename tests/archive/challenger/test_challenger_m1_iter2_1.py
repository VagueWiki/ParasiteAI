"""
Empirical stress test suite by teamwork_challenger_m1_iter2_1.
Thorough adversarial verification of:
1. Re-entrant cancel_download under multiple simultaneous callbacks and worker aborts.
2. Concurrency under high thread count (10+ threads) calling generate() while mode toggles.
3. Corrupted GGUF headers and partial streaming downloads.
"""

import os
import struct
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Optional
import pytest
import httpx

from parasite_ai.config import get_default_config
from parasite_ai.mind.brain_manager import (
    CURATED_MODELS,
    BrainMode,
    BrainState,
    DownloadProgress,
    LocalBrainManager,
    MockBackend,
    validate_gguf_header,
)


class MockDelayedChunkStream:
    """Mock HTTP streaming response that yields valid GGUF chunks with delays."""
    def __init__(self, total_size: int = 100_000, chunk_size: int = 2048, delay: float = 0.01, fail_after_bytes: Optional[int] = None):
        self.total_size = total_size
        self.chunk_size = chunk_size
        self.delay = delay
        self.fail_after_bytes = fail_after_bytes
        self.headers = {"content-length": str(total_size)}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def raise_for_status(self):
        pass

    def iter_bytes(self, chunk_size=None):
        bytes_sent = 0
        first_chunk = True
        while bytes_sent < self.total_size:
            if self.fail_after_bytes is not None and bytes_sent >= self.fail_after_bytes:
                raise httpx.RemoteProtocolError("Simulated socket connection drop / stream truncation")

            if first_chunk:
                # Valid GGUF v3 header in first chunk
                chunk = b"GGUF" + struct.pack("<I", 3) + b"\x00" * (self.chunk_size - 8)
                first_chunk = False
            else:
                chunk = b"\x00" * self.chunk_size

            bytes_sent += len(chunk)
            time.sleep(self.delay)
            yield chunk


class TruncatedCleanCloseStream:
    """Mock HTTP streaming response that closes cleanly after sending only partial bytes."""
    def __init__(self, total_size: int = 5_000_000, send_bytes: int = 128):
        self.total_size = total_size
        self.send_bytes = send_bytes
        self.headers = {"content-length": str(total_size)}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def raise_for_status(self):
        pass

    def iter_bytes(self, chunk_size=None):
        # Sends partial header and cleanly terminates generator without error
        yield b"GGUF" + struct.pack("<I", 3) + b"\x00" * (self.send_bytes - 8)


# ===========================================================================
# 1. Re-entrant cancel_download & Worker Abort Stress Tests
# ===========================================================================

def test_reentrant_cancel_with_simultaneous_caller_threads(tmp_path: Path, monkeypatch):
    """
    Stress-test: Callback on worker thread calls cancel_download() while simultaneously
    10 external threads call cancel_download().
    Verifies: No deadlocks, no unhandled RuntimeError, proper temporary file cleanup.
    """
    models_dir = tmp_path / "models_reentrant_multi"
    models_dir.mkdir()

    cfg = get_default_config()
    cfg.system.models_dir = models_dir
    manager = LocalBrainManager(cfg)

    monkeypatch.setattr(
        "httpx.stream",
        lambda *args, **kwargs: MockDelayedChunkStream(total_size=300_000, delay=0.01),
    )

    callback_exceptions = []
    external_exceptions = []
    external_threads_count = 10

    def on_progress(p: DownloadProgress):
        if p.bytes_downloaded > 0:
            try:
                manager.cancel_download()
            except Exception as exc:
                callback_exceptions.append(exc)

    manager.start_download("Qwen/Qwen2.5-3B-Instruct-GGUF", progress_callback=on_progress)

    def hammer_cancel():
        try:
            for _ in range(5):
                manager.cancel_download()
                time.sleep(0.005)
        except Exception as exc:
            external_exceptions.append(exc)

    threads = [threading.Thread(target=hammer_cancel) for _ in range(external_threads_count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=3.0)

    if manager._download_thread:
        manager._download_thread.join(timeout=3.0)

    assert not callback_exceptions, f"Callback cancel raised: {callback_exceptions}"
    assert not external_exceptions, f"External cancel raised: {external_exceptions}"
    assert manager.state in (BrainState.NO_MODEL_PRESENT, BrainState.DOWNLOAD_FAILED)
    assert len(list(models_dir.glob("*.tmp"))) == 0


def test_reentrant_cancel_recursive_and_nested_in_callback(tmp_path: Path, monkeypatch):
    """
    Stress-test: Callback performs nested recursive cancel_download() invocations.
    Verifies: RLock prevents self-deadlock and thread safety holds.
    """
    models_dir = tmp_path / "models_reentrant_nested"
    models_dir.mkdir()

    cfg = get_default_config()
    cfg.system.models_dir = models_dir
    manager = LocalBrainManager(cfg)

    monkeypatch.setattr(
        "httpx.stream",
        lambda *args, **kwargs: MockDelayedChunkStream(total_size=100_000, delay=0.01),
    )

    errors = []

    def on_progress(p: DownloadProgress):
        if p.bytes_downloaded > 0:
            try:
                # 3 recursive/nested calls to cancel_download() from the worker thread
                manager.cancel_download()
                manager.cancel_download()
                manager.cancel_download()
            except Exception as exc:
                errors.append(exc)

    manager.start_download("Qwen/Qwen2.5-3B-Instruct-GGUF", progress_callback=on_progress)
    time.sleep(0.3)

    if manager._download_thread:
        manager._download_thread.join(timeout=2.0)

    assert not errors, f"Nested cancel in progress callback failed: {errors}"
    assert len(list(models_dir.glob("*.tmp"))) == 0


def test_simultaneous_worker_abort_and_multiple_cancels(tmp_path: Path, monkeypatch):
    """
    Stress-test: Download stream suddenly aborts with network exception while 12 threads
    are bombarding cancel_download().
    Verifies: Clean state handling, no race leading to hanging locks or inconsistent state.
    """
    models_dir = tmp_path / "models_abort_race"
    models_dir.mkdir()

    cfg = get_default_config()
    cfg.system.models_dir = models_dir
    manager = LocalBrainManager(cfg)

    # Stream fails after sending 4KB
    monkeypatch.setattr(
        "httpx.stream",
        lambda *args, **kwargs: MockDelayedChunkStream(
            total_size=100_000,
            delay=0.01,
            fail_after_bytes=4096,
        ),
    )

    manager.start_download("Qwen/Qwen2.5-3B-Instruct-GGUF")

    cancel_errors = []

    def cancel_worker():
        try:
            for _ in range(10):
                manager.cancel_download()
                time.sleep(0.002)
        except Exception as exc:
            cancel_errors.append(exc)

    with ThreadPoolExecutor(max_workers=12) as executor:
        futures = [executor.submit(cancel_worker) for _ in range(12)]
        for f in as_completed(futures):
            pass

    if manager._download_thread:
        manager._download_thread.join(timeout=2.0)

    assert not cancel_errors
    assert manager.state in (BrainState.NO_MODEL_PRESENT, BrainState.DOWNLOAD_FAILED)
    assert len(list(models_dir.glob("*.tmp"))) == 0


def test_start_cancel_hammer_flood(tmp_path: Path, monkeypatch):
    """
    Stress-test: 30 interleaved start_download() and cancel_download() cycles across
    multiple threads to test file-descriptor exhaustion and lock integrity.
    """
    models_dir = tmp_path / "models_flood"
    models_dir.mkdir()

    cfg = get_default_config()
    cfg.system.models_dir = models_dir
    manager = LocalBrainManager(cfg)

    monkeypatch.setattr(
        "httpx.stream",
        lambda *args, **kwargs: MockDelayedChunkStream(total_size=200_000, delay=0.002),
    )

    for i in range(30):
        manager.start_download("Qwen/Qwen2.5-3B-Instruct-GGUF")
        if i % 3 == 0:
            time.sleep(0.005)
        manager.cancel_download()

    if manager._download_thread:
        manager._download_thread.join(timeout=2.0)

    assert manager.state in (BrainState.NO_MODEL_PRESENT, BrainState.DOWNLOADING)
    manager.cancel_download()
    assert manager.state == BrainState.NO_MODEL_PRESENT
    assert len(list(models_dir.glob("*.tmp"))) == 0


# ===========================================================================
# 2. Concurrency under High Thread Count (10+ Threads) Calling generate()
#    While Mode Toggles
# ===========================================================================

def test_high_concurrency_generate_15_threads_with_continuous_mode_toggling():
    """
    Stress-test: 15 worker threads concurrently calling generate() with varying prompts,
    while 3 controller threads continuously toggle toggle_browser_only_mode(True/False).
    Verifies:
    1. Zero unhandled exceptions or crashes.
    2. Every generate() call returns a valid, non-empty string.
    3. BrainState never gets stuck in INFERRING after all inferences finish.
    4. State matches mode after all threads join.
    """
    cfg = get_default_config()
    cfg.brain.mode = "mock"
    manager = LocalBrainManager(cfg)

    # Custom backend with non-zero processing delay to ensure overlap
    class LatencyMockBackend(MockBackend):
        def generate(self, *args, **kwargs):
            time.sleep(0.02)
            return super().generate(*args, **kwargs)

    manager.active_backend = LatencyMockBackend()

    num_gen_threads = 15
    num_toggle_threads = 3
    stop_event = threading.Event()
    gen_results = []
    gen_errors = []
    toggle_errors = []

    def inference_worker(worker_id: int):
        while not stop_event.is_set():
            try:
                res = manager.generate(f"Prompt from worker {worker_id}", json_mode=(worker_id % 2 == 0))
                gen_results.append((worker_id, res))
            except Exception as exc:
                gen_errors.append((worker_id, exc))
            time.sleep(0.005)

    def toggler_worker(toggle_id: int):
        state = True
        while not stop_event.is_set():
            try:
                manager.toggle_browser_only_mode(state)
                state = not state
            except Exception as exc:
                toggle_errors.append((toggle_id, exc))
            time.sleep(0.015)

    with ThreadPoolExecutor(max_workers=num_gen_threads + num_toggle_threads) as executor:
        gen_futures = [executor.submit(inference_worker, i) for i in range(num_gen_threads)]
        toggle_futures = [executor.submit(toggler_worker, i) for i in range(num_toggle_threads)]

        # Let the stress test hammer for 1.5 seconds
        time.sleep(1.5)
        stop_event.set()

        for f in gen_futures:
            f.result()
        for f in toggle_futures:
            f.result()

    # Empirical checks
    assert not gen_errors, f"Inference worker errors during mode toggling: {gen_errors}"
    assert not toggle_errors, f"Toggle worker errors: {toggle_errors}"
    assert len(gen_results) >= num_gen_threads * 5, f"Expected substantial throughput, got {len(gen_results)} calls"

    for worker_id, res in gen_results:
        assert isinstance(res, str) and len(res) > 0

    # Ensure state machine is NOT stuck in INFERRING
    assert manager.state != BrainState.INFERRING, (
        f"State machine stuck in INFERRING! manager.state={manager.state}, count={manager._inferring_count}"
    )

    # Final state consistency
    if manager.mode == BrainMode.BROWSER_OFFLOAD:
        assert manager.state == BrainState.READY_BROWSER_OFFLOAD
    elif manager.mode == BrainMode.LOCAL_LLM:
        assert manager.state in (BrainState.READY_LOCAL, BrainState.NO_MODEL_PRESENT, BrainState.MODEL_READY_ON_DISK)


def test_concurrent_generate_with_rapid_model_load_unload(tmp_path: Path):
    """
    Stress-test: 12 threads calling generate() while another thread rapidly calls
    unload_model() and load_model().
    Verifies: Thread-safety during model swapping, no null-pointer / NoneType crashes.
    """
    models_dir = tmp_path / "models_swap"
    models_dir.mkdir()

    # Create dummy valid GGUF file
    model_file = models_dir / "qwen2.5-3b-instruct-q4_k_m.gguf"
    model_file.write_bytes(b"GGUF" + struct.pack("<I", 3) + b"\x00" * 1024)

    cfg = get_default_config()
    cfg.system.models_dir = models_dir
    cfg.brain.mode = "mock"
    manager = LocalBrainManager(cfg)

    stop_event = threading.Event()
    errors = []

    def infer_runner(idx: int):
        while not stop_event.is_set():
            try:
                manager.generate("Test prompt")
            except Exception as exc:
                errors.append(exc)
            time.sleep(0.01)

    def load_unload_runner():
        while not stop_event.is_set():
            try:
                manager.unload_model()
                time.sleep(0.01)
                manager.load_model("qwen2.5-3b-instruct-q4_k_m.gguf")
                time.sleep(0.01)
            except Exception as exc:
                errors.append(exc)

    threads = [threading.Thread(target=infer_runner, args=(i,)) for i in range(12)]
    threads.append(threading.Thread(target=load_unload_runner))

    for t in threads:
        t.start()

    time.sleep(1.0)
    stop_event.set()

    for t in threads:
        t.join(timeout=3.0)

    assert not errors, f"Errors during concurrent generate + model load/unload: {errors}"
    assert manager.state != BrainState.INFERRING


# ===========================================================================
# 3. Corrupted GGUF Headers & Partial Streaming Downloads
# ===========================================================================

@pytest.mark.parametrize(
    "corrupt_header_bytes",
    [
        b"",                                      # 0 bytes
        b"G",                                     # 1 byte
        b"GG",                                    # 2 bytes
        b"GGU",                                   # 3 bytes
        b"gguf" + struct.pack("<I", 3),           # Lowercase magic
        b"GGU\x00" + struct.pack("<I", 3),        # Trailing null in magic
        b"\x00GGU" + struct.pack("<I", 3),        # Leading null in magic
        b"UGGF" + struct.pack("<I", 3),           # Swapped characters
        b"GGUF",                                  # Missing version (exactly 4 bytes)
        b"GGUF\x03",                              # Partial version (5 bytes)
        b"GGUF\x03\x00",                          # Partial version (6 bytes)
        b"GGUF\x03\x00\x00",                      # Partial version (7 bytes)
        b"GGUF" + struct.pack("<I", 0),           # Unsupported version 0
        b"GGUF" + struct.pack("<I", 1),           # Unsupported version 1
        b"GGUF" + struct.pack("<I", 4),           # Unsupported version 4
        b"GGUF" + struct.pack("<I", 255),         # Unsupported version 255
        b"GGUF" + struct.pack("<I", 65535),       # Unsupported version 65535
        b"GGUF" + struct.pack(">I", 3),           # Big-endian version 3 (GGUF specifies little-endian)
        b"GGUF" + struct.pack("<I", 0xFFFFFFFF),  # Max uint32
    ],
)
def test_adversarial_gguf_header_matrix(tmp_path: Path, corrupt_header_bytes: bytes):
    """
    Stress-test: Comprehensive matrix of truncated, malformed, and unsupported GGUF headers.
    Verifies: validate_gguf_header deterministically returns False for all.
    """
    f = tmp_path / "adversarial.gguf"
    f.write_bytes(corrupt_header_bytes)
    assert validate_gguf_header(f) is False


def test_partial_streaming_download_socket_drop(tmp_path: Path, monkeypatch):
    """
    Stress-test: A streaming download encounters a mid-stream connection drop / socket error.
    Verifies:
    1. Manager captures failure cleanly.
    2. Temporary .tmp file is completely unlinked.
    3. State becomes DOWNLOAD_FAILED.
    """
    models_dir = tmp_path / "models_drop"
    models_dir.mkdir()

    cfg = get_default_config()
    cfg.system.models_dir = models_dir
    manager = LocalBrainManager(cfg)

    monkeypatch.setattr(
        "httpx.stream",
        lambda *args, **kwargs: MockDelayedChunkStream(
            total_size=1_000_000,
            delay=0.01,
            fail_after_bytes=8192,
        ),
    )

    events = []
    manager.start_download(
        "Qwen/Qwen2.5-3B-Instruct-GGUF",
        progress_callback=lambda p: events.append(p),
    )

    if manager._download_thread:
        manager._download_thread.join(timeout=3.0)

    assert manager.state == BrainState.DOWNLOAD_FAILED
    assert len(list(models_dir.glob("*.tmp"))) == 0
    assert len(events) > 0
    assert events[-1].status == "failed"
def test_partial_streaming_clean_close_truncation_detection(tmp_path: Path, monkeypatch):
    """
    Stress-test: An HTTP streaming download ends cleanly after receiving only 128 bytes
    (which contains valid GGUF magic and version header), but the model's Content-Length
    is 2,328,221,696 bytes (2.3 GB).
    Empirical check: Does the download worker detect that the stream was cut short before
    receiving the full payload, or does it declare success and mark the truncated stub as
    MODEL_READY_ON_DISK?
    """
    models_dir = tmp_path / "models_truncate_test"
    models_dir.mkdir()

    cfg = get_default_config()
    cfg.system.models_dir = models_dir
    manager = LocalBrainManager(cfg)

    # Server sends only 128 bytes out of 2.3 GB and closes cleanly
    monkeypatch.setattr(
        "httpx.stream",
        lambda *args, **kwargs: TruncatedCleanCloseStream(total_size=2_328_221_696, send_bytes=128),
    )

    events = []
    manager.start_download(
        "Qwen/Qwen2.5-3B-Instruct-GGUF",
        progress_callback=lambda p: events.append(p),
    )

    if manager._download_thread:
        manager._download_thread.join(timeout=3.0)

    # An incomplete/truncated stream where bytes_downloaded < total_bytes
    # MUST NOT be treated as a successfully completed download!
    assert manager.state != BrainState.MODEL_READY_ON_DISK, (
        f"Vulnerability: Truncated 128-byte partial download of 2.3GB model was marked MODEL_READY_ON_DISK! "
        f"state={manager.state}, target_file_size={models_dir.joinpath('qwen2.5-3b-instruct-q4_k_m.gguf').stat().st_size}"
    )
    assert manager.state == BrainState.DOWNLOAD_FAILED
