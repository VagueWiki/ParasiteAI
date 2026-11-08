"""
Empirical stress tests for concurrency, race conditions, re-entrancy,
and cancellation safety in LocalBrainManager.
"""

import time
import struct
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List
import pytest
import httpx

from parasite_ai.config import get_default_config
from parasite_ai.mind.brain_manager import (
    BrainMode,
    BrainState,
    DownloadProgress,
    LocalBrainManager,
    MockBackend,
)


class MockChunkStream:
    """Simulates an active streaming response yielding chunks with a delay."""
    def __init__(self, total_size: int = 100_000, chunk_size: int = 1024, delay: float = 0.01):
        self.total_size = total_size
        self.chunk_size = chunk_size
        self.delay = delay
        self.headers = {"content-length": str(total_size)}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def raise_for_status(self):
        pass

    def iter_bytes(self, chunk_size=None):
        bytes_sent = 0
        while bytes_sent < self.total_size:
            chunk = b"GGUF" + struct.pack("<I", 3) + b"\x00" * (self.chunk_size - 8)
            bytes_sent += len(chunk)
            time.sleep(self.delay)
            yield chunk


# ===========================================================================
# 1. Concurrent start_download() Contention
# ===========================================================================

def test_concurrent_start_download_mutual_exclusion(tmp_path: Path, monkeypatch):
    """
    Stress-test: Launch 20 concurrent threads all calling start_download() at the exact same instant.
    Empirical expectation: Exactly 1 thread gets True, 19 get False. No crashes or duplicate threads.
    """
    models_dir = tmp_path / "concurrent_dl"
    models_dir.mkdir()

    cfg = get_default_config()
    cfg.system.models_dir = models_dir
    manager = LocalBrainManager(cfg)

    monkeypatch.setattr(
        "httpx.stream",
        lambda *args, **kwargs: MockChunkStream(total_size=500_000, delay=0.05),
    )

    barrier = threading.Barrier(20)
    results = []

    def attempt_download(thread_idx: int):
        barrier.wait()  # synchronize release
        success = manager.start_download("Qwen/Qwen2.5-3B-Instruct-GGUF")
        return success

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(attempt_download, i) for i in range(20)]
        for f in as_completed(futures):
            results.append(f.result())

    # Cancel active download before asserting
    manager.cancel_download()

    assert results.count(True) == 1, f"Expected exactly 1 True, got {results.count(True)}"
    assert results.count(False) == 19


# ===========================================================================
# 2. Cancel Download from Inside Progress Callback (Re-entrancy)
# ===========================================================================

def test_cancel_download_from_within_progress_callback(tmp_path: Path, monkeypatch):
    """
    Stress-test: Calling cancel_download() directly from within the progress_callback
    which executes on the download worker thread.
    Vulnerability check: If cancel_download() attempts to join the current thread,
    Python raises RuntimeError: cannot join current thread.
    """
    models_dir = tmp_path / "reentrant_cancel"
    models_dir.mkdir()

    cfg = get_default_config()
    cfg.system.models_dir = models_dir
    manager = LocalBrainManager(cfg)

    monkeypatch.setattr(
        "httpx.stream",
        lambda *args, **kwargs: MockChunkStream(total_size=100_000, delay=0.01),
    )

    callback_exceptions = []

    def on_progress(p: DownloadProgress):
        # Progress callback running on worker thread attempts to cancel
        if p.bytes_downloaded > 0:
            try:
                manager.cancel_download()
            except Exception as exc:
                callback_exceptions.append(exc)

    manager.start_download("Qwen/Qwen2.5-3B-Instruct-GGUF", progress_callback=on_progress)

    time.sleep(0.3)
    # Ensure worker stopped
    if manager._download_thread:
        manager._download_thread.join(timeout=2.0)

    # Check if re-entrancy crashed with RuntimeError
    if callback_exceptions:
        pytest.fail(f"cancel_download crashed when called from callback: {callback_exceptions}")

    # Check cleanup
    tmp_files = list(models_dir.glob("*.tmp"))
    assert len(tmp_files) == 0


# ===========================================================================
# 3. Rapid Start/Cancel Thrashing Hammer
# ===========================================================================

def test_rapid_start_cancel_hammer(tmp_path: Path, monkeypatch):
    """
    Stress-test: Rapidly iterate start_download() and cancel_download() 15 times
    in tight succession to test file locking, thread leaks, and state integrity.
    """
    models_dir = tmp_path / "hammer_dl"
    models_dir.mkdir()

    cfg = get_default_config()
    cfg.system.models_dir = models_dir
    manager = LocalBrainManager(cfg)

    monkeypatch.setattr(
        "httpx.stream",
        lambda *args, **kwargs: MockChunkStream(total_size=100_000, delay=0.005),
    )

    for i in range(15):
        started = manager.start_download("Qwen/Qwen2.5-3B-Instruct-GGUF")
        # Tiny jitter before cancelling
        time.sleep(0.01)
        manager.cancel_download()

    # After thrashing, manager should be capable of starting cleanly and reaching safe state
    assert manager.state in (BrainState.NO_MODEL_PRESENT, BrainState.DOWNLOADING)
    manager.cancel_download()
    assert manager.state == BrainState.NO_MODEL_PRESENT

    # No leftover .tmp files
    tmp_files = list(models_dir.glob("*.tmp"))
    assert len(tmp_files) == 0


# ===========================================================================
# 4. Spurious Cancellation & Double Cancellation
# ===========================================================================

def test_cancel_when_no_download_active(tmp_path: Path):
    """Verify cancel_download() when idle does not crash or corrupt state."""
    models_dir = tmp_path / "idle_cancel"
    models_dir.mkdir()

    cfg = get_default_config()
    cfg.system.models_dir = models_dir
    manager = LocalBrainManager(cfg)

    initial_state = manager.state
    # Call cancel twice when idle
    manager.cancel_download()
    manager.cancel_download()

    assert manager.state == initial_state


# ===========================================================================
# 5. Mode Toggle During Active Download
# ===========================================================================

def test_toggle_browser_mode_during_download(tmp_path: Path, monkeypatch):
    """
    Stress-test: While a download is in progress, toggle browser only mode ON.
    Verify: Does the system crash or handle the state transition gracefully?
    """
    models_dir = tmp_path / "toggle_during_dl"
    models_dir.mkdir()

    cfg = get_default_config()
    cfg.system.models_dir = models_dir
    manager = LocalBrainManager(cfg)

    monkeypatch.setattr(
        "httpx.stream",
        lambda *args, **kwargs: MockChunkStream(total_size=200_000, delay=0.01),
    )

    started = manager.start_download("Qwen/Qwen2.5-3B-Instruct-GGUF")
    assert started is True
    assert manager.state == BrainState.DOWNLOADING

    time.sleep(0.05)
    # User switches to browser offload mid-download
    manager.toggle_browser_only_mode(True)
    assert manager.mode == BrainMode.BROWSER_OFFLOAD

    # Clean up
    manager.cancel_download()


# ===========================================================================
# 6. Concurrent generate() Calls & State Machine Race Condition
# ===========================================================================

def test_concurrent_generate_state_race():
    """
    Stress-test: Verify whether concurrent calls to generate() properly preserve
    the manager's state after all calls complete, or if a race condition leaves
    the manager permanently stuck in BrainState.INFERRING.
    """
    cfg = get_default_config()
    cfg.brain.mode = "mock"
    manager = LocalBrainManager(cfg)
    assert manager.state == BrainState.READY_LOCAL

    # Create a backend that simulates inference latency
    class SlowMockBackend(MockBackend):
        def generate(self, *args, **kwargs):
            time.sleep(0.05)
            return super().generate(*args, **kwargs)

    manager.active_backend = SlowMockBackend()

    # Launch 10 concurrent threads all calling generate()
    num_threads = 10
    barrier = threading.Barrier(num_threads)
    results = []

    def call_generate():
        barrier.wait()
        return manager.generate("Simulated user prompt")

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(call_generate) for _ in range(num_threads)]
        for f in as_completed(futures):
            results.append(f.result())

    assert len(results) == num_threads

    # EMPIRICAL CHECK: After all inference threads complete,
    # what is manager.state? Must be READY_LOCAL, NOT INFERRING!
    assert manager.state == BrainState.READY_LOCAL, (
        f"Race condition detected! manager.state was left as {manager.state} "
        f"instead of READY_LOCAL after concurrent inference finished."
    )
