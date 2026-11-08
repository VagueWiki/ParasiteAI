"""
Empirical stress tests for GGUF parsing and validation under corrupted,
truncated, and adversarial binary inputs.
"""

import struct
from pathlib import Path
import pytest

from parasite_ai.config import get_default_config
from parasite_ai.mind.brain_manager import (
    BrainMode,
    BrainState,
    LocalBrainManager,
    validate_gguf_header,
)


# ===========================================================================
# 1. Short Binary Files & Truncated Headers
# ===========================================================================

@pytest.mark.parametrize("size", [0, 1, 2, 3, 4, 5, 6, 7])
def test_short_binary_files_rejected(tmp_path: Path, size: int):
    """Verify any file shorter than 8 bytes is rejected without crashing."""
    short_file = tmp_path / f"short_{size}.gguf"
    # Write prefix of b"GGUF\x03\x00\x00\x00" up to length `size`
    content = b"GGUF\x03\x00\x00\x00"[:size]
    short_file.write_bytes(content)

    assert validate_gguf_header(short_file) is False


def test_empty_file_rejected(tmp_path: Path):
    """Verify an empty 0-byte file is rejected cleanly."""
    empty_file = tmp_path / "empty.gguf"
    empty_file.touch()

    assert validate_gguf_header(empty_file) is False


def test_truncated_header_after_magic(tmp_path: Path):
    """Verify file with valid magic but truncated version bytes is rejected."""
    f = tmp_path / "trunc_magic.gguf"
    f.write_bytes(b"GGUF\x03\x00")  # 6 bytes
    assert validate_gguf_header(f) is False


# ===========================================================================
# 2. Invalid Magic Bytes
# ===========================================================================

@pytest.mark.parametrize("magic", [
    b"gguf",          # lowercase
    b"GGML",          # legacy GGML
    b"GGJT",          # legacy GGJT
    b"\x00\x00\x00\x00",  # all zeroes
    b"\xff\xff\xff\xff",  # all ones
    b"RIFF",          # WAV/AVI container
    b"%PDF",          # PDF header
    b"\x7fELF",       # ELF binary
    b"MZ\x90\x00",    # Windows PE header
    b"PK\x03\x04",    # ZIP archive
])
def test_invalid_magic_bytes_rejected(tmp_path: Path, magic: bytes):
    """Verify files with non-'GGUF' magic bytes are rejected."""
    f = tmp_path / "bad_magic.gguf"
    f.write_bytes(magic + struct.pack("<I", 3) + b"\x00" * 32)
    assert validate_gguf_header(f) is False


# ===========================================================================
# 3. Invalid & Edge-Case Version Integers
# ===========================================================================

@pytest.mark.parametrize("version", [
    0,
    1,
    4,
    5,
    100,
    65535,
    2**31 - 1,
    2**32 - 1,
])
def test_unsupported_versions_rejected(tmp_path: Path, version: int):
    """Verify only GGUF v2 and v3 are accepted; all other versions rejected."""
    f = tmp_path / f"ver_{version}.gguf"
    f.write_bytes(b"GGUF" + struct.pack("<I", version) + b"\x00" * 32)
    assert validate_gguf_header(f) is False


@pytest.mark.parametrize("valid_version", [2, 3])
def test_supported_versions_accepted(tmp_path: Path, valid_version: int):
    """Verify GGUF v2 and v3 are properly accepted."""
    f = tmp_path / f"ver_{valid_version}.gguf"
    f.write_bytes(b"GGUF" + struct.pack("<I", valid_version) + b"\x00" * 32)
    assert validate_gguf_header(f) is True


# ===========================================================================
# 4. Filesystem Edge Cases & Anomaly Injection
# ===========================================================================

def test_directory_named_as_gguf(tmp_path: Path):
    """Verify passing a directory path ending in .gguf does not crash and returns False."""
    dir_as_file = tmp_path / "fake_model.gguf"
    dir_as_file.mkdir()

    assert validate_gguf_header(dir_as_file) is False


def test_nonexistent_file(tmp_path: Path):
    """Verify checking a missing file returns False cleanly."""
    missing = tmp_path / "ghost_file.gguf"
    assert validate_gguf_header(missing) is False


def test_unicode_and_special_character_filenames(tmp_path: Path):
    """Verify filenames with unicode, spaces, and emojis are handled properly."""
    unicode_file = tmp_path / "模型_model_🚀.gguf"
    unicode_file.write_bytes(b"GGUF" + struct.pack("<I", 3) + b"\x00" * 64)

    assert validate_gguf_header(unicode_file) is True


def test_header_validation_custom_min_bytes(tmp_path: Path):
    """Verify min_bytes parameter enforces minimum payload size when specified."""
    f = tmp_path / "small.gguf"
    f.write_bytes(b"GGUF" + struct.pack("<I", 3))  # exactly 8 bytes

    # Default min_bytes=8 -> True
    assert validate_gguf_header(f, min_bytes=8) is True
    # If caller demands at least 1024 bytes -> False
    assert validate_gguf_header(f, min_bytes=1024) is False


# ===========================================================================
# 5. LocalBrainManager Integration under Corrupted GGUF Conditions
# ===========================================================================

def test_scan_models_with_corrupt_files(tmp_path: Path):
    """Verify scan_models gracefully categorizes corrupt, truncated, and empty files."""
    models_dir = tmp_path / "models_stress"
    models_dir.mkdir()

    # 1. 0-byte file
    (models_dir / "zero.gguf").touch()

    # 2. Corrupt magic
    (models_dir / "corrupt_magic.gguf").write_bytes(b"BAD!" + struct.pack("<I", 3))

    # 3. Truncated
    (models_dir / "truncated.gguf").write_bytes(b"GGUF\x03")

    # 4. Subdirectory with .gguf name
    (models_dir / "dir_model.gguf").mkdir()

    # 5. Legitimate GGUF v3
    (models_dir / "valid_model.gguf").write_bytes(b"GGUF" + struct.pack("<I", 3) + b"\x00" * 64)

    cfg = get_default_config()
    cfg.system.models_dir = models_dir

    manager = LocalBrainManager(cfg)
    models = manager.scan_models()

    valid_discovered = [m for m in models if m.is_downloaded and m.is_valid_gguf]
    invalid_discovered = [m for m in models if m.is_downloaded and not m.is_valid_gguf]

    # Only valid_model.gguf should be marked valid
    assert len(valid_discovered) == 1
    assert valid_discovered[0].filename == "valid_model.gguf"

    # All corrupt files must be recognized as downloaded but invalid
    invalid_filenames = {m.filename for m in invalid_discovered}
    assert "zero.gguf" in invalid_filenames
    assert "corrupt_magic.gguf" in invalid_filenames
    assert "truncated.gguf" in invalid_filenames


def test_load_corrupted_model_fails_safely(tmp_path: Path):
    """Verify calling load_model on a corrupted GGUF returns False and sets NO_MODEL_PRESENT."""
    models_dir = tmp_path / "models_corrupt_load"
    models_dir.mkdir()

    corrupt_file = models_dir / "bad.gguf"
    corrupt_file.write_bytes(b"CORRUPTED_BYTES" * 10)

    cfg = get_default_config()
    cfg.system.models_dir = models_dir
    cfg.brain.mode = "local_llm"

    manager = LocalBrainManager(cfg)
    assert manager.load_model("bad.gguf") is False
    assert manager.state == BrainState.NO_MODEL_PRESENT


def test_load_directory_as_model_fails_safely(tmp_path: Path):
    """Verify load_model on a directory does not raise an exception and returns False."""
    models_dir = tmp_path / "models_dir_load"
    models_dir.mkdir()

    fake_dir = models_dir / "folder.gguf"
    fake_dir.mkdir()

    cfg = get_default_config()
    cfg.system.models_dir = models_dir

    manager = LocalBrainManager(cfg)
    assert manager.load_model("folder.gguf") is False
    assert manager.state == BrainState.NO_MODEL_PRESENT


def test_download_corrupted_stream_validation_failure(tmp_path: Path, monkeypatch):
    """
    Verify that if a completed download stream contains corrupt non-GGUF bytes,
    the manager flags state as DOWNLOAD_FAILED and progress as failed.
    """
    models_dir = tmp_path / "models_corrupt_stream"
    models_dir.mkdir()

    cfg = get_default_config()
    cfg.system.models_dir = models_dir

    manager = LocalBrainManager(cfg)

    # Server sends 10KB of invalid non-GGUF data
    corrupted_data = b"NOT_GGUF_CORRUPTED_STREAM_DATA" * 500

    class CorruptStreamResponse:
        def __init__(self):
            self.headers = {"content-length": str(len(corrupted_data))}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

        def raise_for_status(self):
            pass

        def iter_bytes(self, chunk_size=256):
            yield corrupted_data

    monkeypatch.setattr("httpx.stream", lambda *args, **kwargs: CorruptStreamResponse())

    events = []
    manager.start_download(
        model_id="Qwen/Qwen2.5-3B-Instruct-GGUF",
        progress_callback=lambda p: events.append(p),
    )

    if manager._download_thread:
        manager._download_thread.join(timeout=3.0)

    # Download must fail validation
    assert manager.state == BrainState.DOWNLOAD_FAILED
    assert len(events) > 0
    assert events[-1].status == "failed"

