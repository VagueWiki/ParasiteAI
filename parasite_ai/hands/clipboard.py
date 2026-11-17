"""
parasite_ai/hands/clipboard.py - Win32 CF_DIB & Unicode Clipboard Driver.

Zero third-party dependencies beyond NumPy and Python's ctypes. Configures explicit
64-bit ctypes argtypes/restype for user32/kernel32 clipboard calls, handles retry
backoff on clipboard lock contention, snapshots/restores CF_UNICODETEXT + CF_DIB
with non-restorable custom format diagnostics, and provides MockWin32ClipboardAPI
so tests never touch the live desktop clipboard.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass, field
import logging
import struct
import time
from typing import Callable, Dict, List, Optional, Protocol

import numpy as np

logger = logging.getLogger(__name__)

# Win32 Clipboard & Memory Constants
CF_DIB = 8
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002
BI_RGB = 0
_BITMAPINFOHEADER_SIZE = 40
_BITMAPINFOHEADER_FMT = "<IiiHHIIiiII"


class ClipboardError(RuntimeError):
    """Base error raised on Win32 clipboard failures."""


class ClipboardLockedError(ClipboardError):
    """Raised when OpenClipboard fails after exhausting retries."""


class DibPackError(ValueError):
    """Raised when a frame cannot be packed into a valid CF_DIB buffer."""


@dataclass
class ClipboardSnapshot:
    """Captured clipboard state before ParasiteSkill clipboard mutations."""

    unicode_text: Optional[str] = None
    dib_bytes: Optional[bytes] = None
    other_formats: List[int] = field(default_factory=list)


def pack_dib(frame: np.ndarray) -> bytes:
    """
    Packs an HxWxC (C in {3, 4}) uint8 RGB/RGBA frame into a Win32 CF_DIB buffer:
    40-byte BITMAPINFOHEADER (positive height -> bottom-up) followed by
    4-byte aligned bottom-up BGR pixel rows (alpha dropped if present).
    """
    if not isinstance(frame, np.ndarray):
        raise DibPackError("Frame must be a numpy.ndarray.")
    if frame.dtype != np.uint8:
        raise DibPackError(f"Frame dtype must be uint8, got {frame.dtype}.")
    if frame.ndim != 3 or frame.shape[2] not in (3, 4):
        raise DibPackError(
            f"Frame shape must be HxWx3 or HxWx4, got {tuple(frame.shape)}."
        )

    height, width, _ = frame.shape
    if height <= 0 or width <= 0:
        raise DibPackError(f"Frame dimensions must be positive, got {width}x{height}.")

    # Flip vertically for bottom-up DIB orientation and swap RGB -> BGR (drop alpha)
    bgr_bottom_up = np.ascontiguousarray(frame[::-1, :, 2::-1])
    row_bytes = width * 3
    stride = ((row_bytes + 3) // 4) * 4

    if stride == row_bytes:
        pixel_bytes = bgr_bottom_up.tobytes()
    else:
        padded = np.zeros((height, stride), dtype=np.uint8)
        padded[:, :row_bytes] = bgr_bottom_up.reshape(height, row_bytes)
        pixel_bytes = padded.tobytes()

    image_size = stride * height
    header = struct.pack(
        _BITMAPINFOHEADER_FMT,
        _BITMAPINFOHEADER_SIZE,
        width,
        height,  # Positive height => bottom-up DIB
        1,       # biPlanes
        24,      # biBitCount
        BI_RGB,
        image_size,
        0,       # biXPelsPerMeter
        0,       # biYPelsPerMeter
        0,       # biClrUsed
        0,       # biClrImportant
    )
    return header + pixel_bytes


def pack_unicode_text(text: str) -> bytes:
    """Encodes Python text as null-terminated UTF-16LE bytes for CF_UNICODETEXT."""
    return (text or "").encode("utf-16-le") + b"\x00\x00"


def unpack_unicode_text(raw: bytes) -> str:
    """Decodes UTF-16LE CF_UNICODETEXT payload up to the first NUL terminator."""
    if not raw:
        return ""
    even_len = len(raw) - (len(raw) % 2)
    text = raw[:even_len].decode("utf-16-le", errors="replace")
    return text.split("\x00", 1)[0]


class IWin32ClipboardAPI(Protocol):
    """Low-level Win32 clipboard API abstraction for dependency injection and testing."""

    def open_clipboard(self, hwnd: int = 0) -> bool: ...
    def close_clipboard(self) -> bool: ...
    def empty_clipboard(self) -> bool: ...
    def global_alloc(self, flags: int, size: int) -> int: ...
    def global_lock(self, hmem: int) -> int: ...
    def write_memory(self, ptr: int, data: bytes) -> None: ...
    def read_memory(self, ptr: int, size: int) -> bytes: ...
    def global_unlock(self, hmem: int) -> bool: ...
    def global_free(self, hmem: int) -> int: ...
    def global_size(self, hmem: int) -> int: ...
    def set_clipboard_data(self, fmt: int, hmem: int) -> int: ...
    def get_clipboard_data(self, fmt: int) -> int: ...
    def is_clipboard_format_available(self, fmt: int) -> bool: ...
    def enum_clipboard_formats(self, fmt: int = 0) -> int: ...


class Win32ClipboardAPI:
    """Real ctypes Win32 clipboard backend with explicit 64-bit argtypes/restype."""

    def __init__(self) -> None:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        user32.OpenClipboard.argtypes = [wintypes.HWND]
        user32.OpenClipboard.restype = wintypes.BOOL
        user32.CloseClipboard.argtypes = []
        user32.CloseClipboard.restype = wintypes.BOOL
        user32.EmptyClipboard.argtypes = []
        user32.EmptyClipboard.restype = wintypes.BOOL
        user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
        user32.SetClipboardData.restype = wintypes.HANDLE
        user32.GetClipboardData.argtypes = [wintypes.UINT]
        user32.GetClipboardData.restype = wintypes.HANDLE
        user32.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
        user32.IsClipboardFormatAvailable.restype = wintypes.BOOL
        user32.EnumClipboardFormats.argtypes = [wintypes.UINT]
        user32.EnumClipboardFormats.restype = wintypes.UINT

        kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
        kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
        kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalUnlock.restype = wintypes.BOOL
        kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalFree.restype = wintypes.HGLOBAL
        kernel32.GlobalSize.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalSize.restype = ctypes.c_size_t

        self._user32 = user32
        self._kernel32 = kernel32

    def open_clipboard(self, hwnd: int = 0) -> bool:
        return bool(self._user32.OpenClipboard(hwnd or None))

    def close_clipboard(self) -> bool:
        return bool(self._user32.CloseClipboard())

    def empty_clipboard(self) -> bool:
        return bool(self._user32.EmptyClipboard())

    def global_alloc(self, flags: int, size: int) -> int:
        return int(self._kernel32.GlobalAlloc(flags, size) or 0)

    def global_lock(self, hmem: int) -> int:
        return int(self._kernel32.GlobalLock(hmem) or 0)

    def write_memory(self, ptr: int, data: bytes) -> None:
        if data:
            ctypes.memmove(ptr, data, len(data))

    def read_memory(self, ptr: int, size: int) -> bytes:
        if size <= 0 or not ptr:
            return b""
        return ctypes.string_at(ptr, size)

    def global_unlock(self, hmem: int) -> bool:
        return bool(self._kernel32.GlobalUnlock(hmem))

    def global_free(self, hmem: int) -> int:
        return int(self._kernel32.GlobalFree(hmem) or 0)

    def global_size(self, hmem: int) -> int:
        return int(self._kernel32.GlobalSize(hmem) or 0)

    def set_clipboard_data(self, fmt: int, hmem: int) -> int:
        return int(self._user32.SetClipboardData(fmt, hmem) or 0)

    def get_clipboard_data(self, fmt: int) -> int:
        return int(self._user32.GetClipboardData(fmt) or 0)

    def is_clipboard_format_available(self, fmt: int) -> bool:
        return bool(self._user32.IsClipboardFormatAvailable(fmt))

    def enum_clipboard_formats(self, fmt: int = 0) -> int:
        return int(self._user32.EnumClipboardFormats(fmt) or 0)


class MockWin32ClipboardAPI:
    """In-memory mock of Win32 clipboard calls recording exact call order."""

    def __init__(self) -> None:
        self.call_history: List[str] = []
        self.is_open: bool = False
        self.fail_open_remaining: int = 0
        self.always_fail_open: bool = False
        self.fail_set_clipboard_data: bool = False
        self.fail_global_lock: bool = False
        self.raise_on_write: Optional[Exception] = None

        self._next_handle: int = 0x1000
        self._allocs: Dict[int, bytearray] = {}
        self._freed_handles: List[int] = []
        self._clipboard: Dict[int, bytes] = {}
        self._custom_formats: List[int] = []

    def seed_format(self, fmt: int, data: Optional[bytes] = None) -> None:
        """Seeds initial clipboard formats (including custom formats) for snapshot tests."""
        if data is not None:
            self._clipboard[fmt] = data
        if fmt not in (CF_DIB, CF_UNICODETEXT) and fmt not in self._custom_formats:
            self._custom_formats.append(fmt)

    def open_clipboard(self, hwnd: int = 0) -> bool:
        self.call_history.append("OpenClipboard")
        if self.always_fail_open:
            return False
        if self.fail_open_remaining > 0:
            self.fail_open_remaining -= 1
            return False
        if self.is_open:
            return False
        self.is_open = True
        return True

    def close_clipboard(self) -> bool:
        self.call_history.append("CloseClipboard")
        self.is_open = False
        return True

    def empty_clipboard(self) -> bool:
        self.call_history.append("EmptyClipboard")
        self._clipboard.clear()
        self._custom_formats.clear()
        return True

    def global_alloc(self, flags: int, size: int) -> int:
        self.call_history.append("GlobalAlloc")
        handle = self._next_handle
        self._next_handle += 16
        self._allocs[handle] = bytearray(size)
        return handle

    def global_lock(self, hmem: int) -> int:
        self.call_history.append("GlobalLock")
        if self.fail_global_lock or hmem not in self._allocs:
            return 0
        # Use handle as synthetic pointer address in the mock
        return hmem

    def write_memory(self, ptr: int, data: bytes) -> None:
        self.call_history.append("memmove")
        if self.raise_on_write is not None:
            raise self.raise_on_write
        buf = self._allocs[ptr]
        buf[: len(data)] = data

    def read_memory(self, ptr: int, size: int) -> bytes:
        self.call_history.append("read_memory")
        return bytes(self._allocs.get(ptr, b"")[:size])

    def global_unlock(self, hmem: int) -> bool:
        self.call_history.append("GlobalUnlock")
        return True

    def global_free(self, hmem: int) -> int:
        self.call_history.append("GlobalFree")
        self._allocs.pop(hmem, None)
        self._freed_handles.append(hmem)
        return 0

    def global_size(self, hmem: int) -> int:
        return len(self._allocs.get(hmem, b""))

    def set_clipboard_data(self, fmt: int, hmem: int) -> int:
        self.call_history.append("SetClipboardData")
        if self.fail_set_clipboard_data or hmem not in self._allocs:
            return 0
        self._clipboard[fmt] = bytes(self._allocs[hmem])
        return hmem

    def get_clipboard_data(self, fmt: int) -> int:
        self.call_history.append("GetClipboardData")
        data = self._clipboard.get(fmt)
        if data is None:
            return 0
        handle = self._next_handle
        self._next_handle += 16
        self._allocs[handle] = bytearray(data)
        return handle

    def is_clipboard_format_available(self, fmt: int) -> bool:
        self.call_history.append("IsClipboardFormatAvailable")
        return fmt in self._clipboard or fmt in self._custom_formats

    def enum_clipboard_formats(self, fmt: int = 0) -> int:
        self.call_history.append("EnumClipboardFormats")
        ordered = list(self._clipboard.keys()) + [
            f for f in self._custom_formats if f not in self._clipboard
        ]
        if fmt == 0:
            return ordered[0] if ordered else 0
        try:
            idx = ordered.index(fmt)
            return ordered[idx + 1] if idx + 1 < len(ordered) else 0
        except ValueError:
            return 0


class IImageClipboard(Protocol):
    """Clipboard interface supporting CF_DIB images, UTF-16LE text, and snapshot/restore."""

    def set_image_dib(self, frame: np.ndarray) -> None: ...
    def set_unicode_text(self, text: str) -> None: ...
    def snapshot(self) -> ClipboardSnapshot: ...
    def restore(self, snap: ClipboardSnapshot) -> None: ...
    def get_text(self) -> str: ...
    def set_text(self, text: str) -> None: ...


class Win32ImageClipboard:
    """
    Safe Win32 clipboard manager for raw CF_DIB bitmaps and CF_UNICODETEXT.
    Compatible with SentinelClipboardVerifier (get_text / set_text).
    """

    def __init__(
        self,
        api: Optional[IWin32ClipboardAPI] = None,
        max_retries: int = 5,
        retry_delay_s: float = 0.02,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        self._api: IWin32ClipboardAPI = api if api is not None else Win32ClipboardAPI()
        self.max_retries = max(1, int(max_retries))
        self.retry_delay_s = max(0.0, float(retry_delay_s))
        self._sleep = sleep_fn

    def _open_clipboard(self) -> None:
        for attempt in range(self.max_retries):
            if self._api.open_clipboard(0):
                return
            if attempt < self.max_retries - 1 and self.retry_delay_s > 0:
                self._sleep(self.retry_delay_s)
        raise ClipboardLockedError(
            f"Failed to acquire Win32 clipboard lock after {self.max_retries} attempts."
        )

    def _write_format_locked(self, fmt: int, payload: bytes) -> None:
        hmem = self._api.global_alloc(GMEM_MOVEABLE, len(payload))
        if not hmem:
            raise ClipboardError(f"GlobalAlloc failed for clipboard format {fmt}.")

        transferred = False
        try:
            ptr = self._api.global_lock(hmem)
            if not ptr:
                raise ClipboardError(f"GlobalLock failed for clipboard format {fmt}.")
            try:
                self._api.write_memory(ptr, payload)
            finally:
                self._api.global_unlock(hmem)

            res = self._api.set_clipboard_data(fmt, hmem)
            if not res:
                raise ClipboardError(f"SetClipboardData failed for format {fmt}.")
            transferred = True
        finally:
            if not transferred:
                self._api.global_free(hmem)

    def _read_format_locked(self, fmt: int) -> Optional[bytes]:
        if not self._api.is_clipboard_format_available(fmt):
            return None
        hmem = self._api.get_clipboard_data(fmt)
        if not hmem:
            return None
        size = self._api.global_size(hmem)
        if size <= 0:
            return b""
        ptr = self._api.global_lock(hmem)
        if not ptr:
            return None
        try:
            return self._api.read_memory(ptr, size)
        finally:
            self._api.global_unlock(hmem)

    def _set_single_format(self, fmt: int, payload: bytes) -> None:
        self._open_clipboard()
        try:
            if not self._api.empty_clipboard():
                raise ClipboardError("EmptyClipboard failed.")
            self._write_format_locked(fmt, payload)
        finally:
            self._api.close_clipboard()

    def set_image_dib(self, frame: np.ndarray) -> None:
        """Packs frame as CF_DIB and writes it cleanly into the Win32 clipboard."""
        dib_payload = pack_dib(frame)
        self._set_single_format(CF_DIB, dib_payload)

    def set_unicode_text(self, text: str) -> None:
        """Writes UTF-16LE text to CF_UNICODETEXT."""
        self._set_single_format(CF_UNICODETEXT, pack_unicode_text(text))

    def get_text(self) -> str:
        """Reads current CF_UNICODETEXT string (IClipboardBackend compatible)."""
        try:
            self._open_clipboard()
        except ClipboardLockedError:
            return ""
        try:
            raw = self._read_format_locked(CF_UNICODETEXT)
            return unpack_unicode_text(raw) if raw else ""
        finally:
            self._api.close_clipboard()

    def set_text(self, text: str) -> None:
        """Writes text to CF_UNICODETEXT (IClipboardBackend compatible)."""
        self.set_unicode_text(text)

    def snapshot(self) -> ClipboardSnapshot:
        """Captures current CF_UNICODETEXT and CF_DIB payloads plus custom format IDs."""
        self._open_clipboard()
        try:
            text: Optional[str] = None
            raw_text = self._read_format_locked(CF_UNICODETEXT)
            if raw_text is not None:
                text = unpack_unicode_text(raw_text)

            dib = self._read_format_locked(CF_DIB)

            other: List[int] = []
            fmt = self._api.enum_clipboard_formats(0)
            seen = 0
            while fmt != 0 and seen < 64:
                if fmt not in (CF_UNICODETEXT, CF_DIB) and fmt not in other:
                    other.append(fmt)
                fmt = self._api.enum_clipboard_formats(fmt)
                seen += 1

            return ClipboardSnapshot(
                unicode_text=text,
                dib_bytes=dib,
                other_formats=other,
            )
        finally:
            self._api.close_clipboard()

    def restore(self, snap: ClipboardSnapshot) -> None:
        """Restores captured CF_DIB and CF_UNICODETEXT state (empty if neither existed)."""
        if snap.other_formats:
            logger.debug(
                "Non-restorable custom clipboard formats present prior to capture: %s",
                snap.other_formats,
            )

        self._open_clipboard()
        try:
            if not self._api.empty_clipboard():
                raise ClipboardError("EmptyClipboard failed during restore.")
            if snap.dib_bytes is not None:
                self._write_format_locked(CF_DIB, snap.dib_bytes)
            if snap.unicode_text is not None:
                self._write_format_locked(CF_UNICODETEXT, pack_unicode_text(snap.unicode_text))
        finally:
            self._api.close_clipboard()
