"""Unit tests for Win32 CF_DIB packing, lock retry, and clipboard snapshot/restore."""

from __future__ import annotations

import logging
import struct
import numpy as np
import pytest

from parasite_ai.hands.clipboard import (
    BI_RGB,
    CF_DIB,
    CF_UNICODETEXT,
    ClipboardError,
    ClipboardLockedError,
    DibPackError,
    MockWin32ClipboardAPI,
    Win32ImageClipboard,
    pack_dib,
)

pytestmark = pytest.mark.unit


def _unpack_header(dib: bytes) -> tuple:
    return struct.unpack("<IiiHHIIiiII", dib[:40])


def test_pack_dib_header_fields_exact() -> None:
    frame = np.zeros((10, 12, 3), dtype=np.uint8)
    dib = pack_dib(frame)
    header = _unpack_header(dib)
    assert header == (40, 12, 10, 1, 24, BI_RGB, 36 * 10, 0, 0, 0, 0)
    assert len(dib) == 40 + 36 * 10


@pytest.mark.parametrize(
    "width,expected_stride",
    [
        (4, 12),   # 12 % 4 == 0
        (5, 16),   # 15 -> 16 (W % 4 == 1)
        (6, 20),   # 18 -> 20 (W % 4 == 2)
        (7, 24),   # 21 -> 24 (W % 4 == 3)
    ],
)
def test_pack_dib_stride_padding_all_mod4(width: int, expected_stride: int) -> None:
    height = 3
    frame = np.full((height, width, 3), 255, dtype=np.uint8)
    dib = pack_dib(frame)
    header = _unpack_header(dib)
    assert header[1] == width
    assert header[2] == height
    assert header[6] == expected_stride * height
    assert len(dib) == 40 + expected_stride * height

    row_bytes = width * 3
    for r in range(height):
        start = 40 + r * expected_stride
        pad_tail = dib[start + row_bytes : start + expected_stride]
        assert pad_tail == b"\x00" * (expected_stride - row_bytes)


def test_pack_dib_bottom_up_and_rgb_to_bgr() -> None:
    # 2x2 RGB: top-left=(10,20,30), top-right=(40,50,60),
    # bottom-left=(70,80,90), bottom-right=(100,110,120)
    frame = np.array(
        [
            [[10, 20, 30], [40, 50, 60]],
            [[70, 80, 90], [100, 110, 120]],
        ],
        dtype=np.uint8,
    )
    dib = pack_dib(frame)
    # stride for W=2 is ((6 + 3)//4)*4 == 8 (2 zero pad bytes per row)
    row0 = dib[40:48]  # Bottom row of image in BGR
    row1 = dib[48:56]  # Top row of image in BGR
    assert row0[:6] == bytes([90, 80, 70, 120, 110, 100])
    assert row0[6:] == b"\x00\x00"
    assert row1[:6] == bytes([30, 20, 10, 60, 50, 40])
    assert row1[6:] == b"\x00\x00"


def test_pack_dib_drops_rgba_alpha_cleanly() -> None:
    frame = np.zeros((4, 4, 4), dtype=np.uint8)
    frame[0, 0] = [12, 34, 56, 200]
    dib = pack_dib(frame)
    assert _unpack_header(dib)[4] == 24
    assert len(dib) == 40 + 12 * 4
    # Top-left RGBA(12,34,56,200) -> last row BGR(56,34,12)
    last_row_start = 40 + 3 * 12
    assert dib[last_row_start : last_row_start + 3] == bytes([56, 34, 12])


@pytest.mark.parametrize(
    "bad_frame",
    [
        "not an array",
        np.zeros((4, 4), dtype=np.uint8),            # grayscale 2D
        np.zeros((4, 4, 1), dtype=np.uint8),         # 1-channel
        np.zeros((4, 4, 3), dtype=np.float32),       # wrong dtype
        np.zeros((0, 4, 3), dtype=np.uint8),         # zero height
        np.zeros((4, 0, 3), dtype=np.uint8),         # zero width
    ],
)
def test_pack_dib_rejects_invalid_inputs(bad_frame) -> None:
    with pytest.raises(DibPackError):
        pack_dib(bad_frame)  # type: ignore[arg-type]


def test_win32_call_sequence_for_set_image_dib() -> None:
    api = MockWin32ClipboardAPI()
    cb = Win32ImageClipboard(api=api, sleep_fn=lambda _: None)
    cb.set_image_dib(np.zeros((2, 4, 3), dtype=np.uint8))

    assert api.call_history == [
        "OpenClipboard",
        "EmptyClipboard",
        "GlobalAlloc",
        "GlobalLock",
        "memmove",
        "GlobalUnlock",
        "SetClipboardData",
        "CloseClipboard",
    ]
    assert not api.is_open
    assert CF_DIB in api._clipboard


def test_global_free_called_when_set_clipboard_data_fails() -> None:
    api = MockWin32ClipboardAPI()
    api.fail_set_clipboard_data = True
    cb = Win32ImageClipboard(api=api, sleep_fn=lambda _: None)

    with pytest.raises(ClipboardError, match="SetClipboardData failed"):
        cb.set_unicode_text("hello")

    assert "GlobalFree" in api.call_history
    assert len(api._freed_handles) == 1
    assert api.call_history[-1] == "CloseClipboard"
    assert not api.is_open


def test_close_clipboard_in_finally_on_memory_write_exception() -> None:
    api = MockWin32ClipboardAPI()
    api.raise_on_write = RuntimeError("simulated memmove boom")
    cb = Win32ImageClipboard(api=api, sleep_fn=lambda _: None)

    with pytest.raises(RuntimeError, match="simulated memmove boom"):
        cb.set_unicode_text("boom")

    assert "GlobalUnlock" in api.call_history
    assert "GlobalFree" in api.call_history
    assert api.call_history[-1] == "CloseClipboard"
    assert not api.is_open


def test_open_clipboard_retries_and_succeeds() -> None:
    api = MockWin32ClipboardAPI()
    api.fail_open_remaining = 3
    delays = []
    cb = Win32ImageClipboard(
        api=api, max_retries=5, retry_delay_s=0.01, sleep_fn=delays.append
    )

    cb.set_unicode_text("retried-ok")
    assert api.call_history.count("OpenClipboard") == 4
    assert len(delays) == 3
    assert cb.get_text() == "retried-ok"


def test_open_clipboard_raises_locked_after_exhausting_retries() -> None:
    api = MockWin32ClipboardAPI()
    api.always_fail_open = True
    cb = Win32ImageClipboard(api=api, max_retries=4, retry_delay_s=0.0, sleep_fn=lambda _: None)

    with pytest.raises(ClipboardLockedError):
        cb.set_image_dib(np.zeros((2, 2, 3), dtype=np.uint8))

    assert api.call_history.count("OpenClipboard") == 4


def test_snapshot_restore_roundtrip_text_and_dib() -> None:
    api = MockWin32ClipboardAPI()
    cb = Win32ImageClipboard(api=api, sleep_fn=lambda _: None)

    orig_dib = pack_dib(np.full((2, 2, 3), 42, dtype=np.uint8))
    api._clipboard[CF_DIB] = orig_dib
    api._clipboard[CF_UNICODETEXT] = "original text".encode("utf-16-le") + b"\x00\x00"

    snap = cb.snapshot()
    assert snap.unicode_text == "original text"
    assert snap.dib_bytes == orig_dib

    # Mutate clipboard completely
    cb.set_unicode_text("temporary replacement")
    assert cb.get_text() == "temporary replacement"
    assert CF_DIB not in api._clipboard

    cb.restore(snap)
    assert cb.get_text() == "original text"
    assert api._clipboard.get(CF_DIB) == orig_dib


def test_snapshot_restore_empty_clipboard_clears_mutations() -> None:
    api = MockWin32ClipboardAPI()
    cb = Win32ImageClipboard(api=api, sleep_fn=lambda _: None)

    snap = cb.snapshot()
    assert snap.unicode_text is None
    assert snap.dib_bytes is None

    cb.set_unicode_text("dirty")
    assert cb.get_text() == "dirty"

    cb.restore(snap)
    assert cb.get_text() == ""
    assert CF_UNICODETEXT not in api._clipboard
    assert CF_DIB not in api._clipboard


def test_snapshot_records_and_logs_non_restorable_custom_formats(caplog) -> None:
    api = MockWin32ClipboardAPI()
    api.seed_format(0xC001, b"custom_html")
    cb = Win32ImageClipboard(api=api, sleep_fn=lambda _: None)

    snap = cb.snapshot()
    assert 0xC001 in snap.other_formats

    with caplog.at_level(logging.DEBUG, logger="parasite_ai.hands.clipboard"):
        cb.restore(snap)
    assert any("Non-restorable custom clipboard formats" in rec.message for rec in caplog.records)
