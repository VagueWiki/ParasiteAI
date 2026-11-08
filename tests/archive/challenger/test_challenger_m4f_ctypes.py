"""
tests/test_challenger_m4f_ctypes.py - Adversarial 64-bit ABI Verification & Ctypes Stress Suite.

Milestone 4F (Challenger 1 / VERIF-9):
Adversarially tests and stress-tests:
  1. 64-bit Windows ABI memory layouts, alignments, and pointer widths.
  2. Structure packing, field offsets, and compiler padding invariants.
  3. Padding byte poisoning and non-interference.
  4. Union overlap permutations, memory interleaving, and little-endian arithmetic.
  5. Contiguous array allocations and stride verification for SendInput batches.
  6. Bitmask injection stress (LLMHF_INJECTED, LLKHF_INJECTED) under hostile bit patterns.
  7. Multi-monitor negative coordinate signedness and wheel delta wrapping.
  8. Full 64-bit pointer and handle address preservation (>4GB space).
  9. ctypes.memmove, ctypes.string_at, and buffer serialization round-trips.
 10. Module export uniformity and singleton class identity.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import pytest

# 1. Imports from parasite_ai.input.types (central catalog)
from parasite_ai.input.types import (
    POINT,
    RECT,
    MSLLHOOKSTRUCT,
    KBDLLHOOKSTRUCT,
    MOUSEINPUT,
    KEYBDINPUT,
    HARDWAREINPUT,
    INPUT_UNION,
    INPUT,
    GUITHREADINFO,
)

# 2. Imports from parasite_ai.input (__init__.py re-export)
import parasite_ai.input as input_pkg

# 3. Direct imports from authoritative source modules
import parasite_ai.safety.interrupt_guard as ig
import parasite_ai.safety.window_guard as wg
import parasite_ai.hands.keyboard as kb
import parasite_ai.mind.dual_mind as dm


# ===========================================================================
# 1. 64-bit ABI Structure Sizing, Alignment & Pointer Widths
# ===========================================================================

class Test64BitStructureSizingAndAlignment:
    """Verifies that all 10 Win32 structures strictly adhere to 64-bit Windows ABI specifications."""

    @pytest.mark.parametrize(
        "struct_cls,expected_size,expected_align",
        [
            (POINT, 8, 4),
            (RECT, 16, 4),
            (MSLLHOOKSTRUCT, 32, 8),
            (KBDLLHOOKSTRUCT, 24, 8),
            (MOUSEINPUT, 32, 8),
            (KEYBDINPUT, 24, 8),
            (HARDWAREINPUT, 8, 4),
            (INPUT_UNION, 32, 8),
            (INPUT, 40, 8),
            (GUITHREADINFO, 72, 8),
        ],
    )
    def test_struct_exact_size_and_alignment(self, struct_cls, expected_size, expected_align):
        """Every structure must match exact byte size and alignment on 64-bit Windows."""
        actual_size = ctypes.sizeof(struct_cls)
        actual_align = ctypes.alignment(struct_cls)
        assert actual_size == expected_size, (
            f"{struct_cls.__name__} size mismatch: expected {expected_size}B, got {actual_size}B"
        )
        assert actual_align == expected_align, (
            f"{struct_cls.__name__} alignment mismatch: expected {expected_align}B, got {actual_align}B"
        )

    def test_64bit_pointer_and_handle_widths(self):
        """Pointer, ULONG_PTR, and HWND types must be exactly 8 bytes on 64-bit ABI."""
        assert ctypes.sizeof(ctypes.c_size_t) == 8, "c_size_t (ULONG_PTR) must be 8 bytes on x64"
        assert ctypes.sizeof(ctypes.c_void_p) == 8, "c_void_p must be 8 bytes on x64"
        assert ctypes.sizeof(wintypes.HWND) == 8, "wintypes.HWND must be 8 bytes on x64"
        assert ctypes.sizeof(wintypes.LPARAM) == 8, "wintypes.LPARAM must be 8 bytes on x64"
        assert ctypes.sizeof(wintypes.WPARAM) == 8, "wintypes.WPARAM must be 8 bytes on x64"
        assert ctypes.sizeof(ig.HOOKPROC) == 8, "HOOKPROC function pointer must be 8 bytes on x64"


# ===========================================================================
# 2. Field Offsets and Compiler Padding Invariants
# ===========================================================================

class TestCompilerPaddingAndFieldOffsets:
    """Verifies internal compiler padding and exact byte offsets for every struct member."""

    def test_point_offsets(self):
        assert POINT.x.offset == 0
        assert POINT.y.offset == 4

    def test_rect_offsets(self):
        assert RECT.left.offset == 0
        assert RECT.top.offset == 4
        assert RECT.right.offset == 8
        assert RECT.bottom.offset == 12

    def test_msllhookstruct_offsets_and_padding(self):
        assert MSLLHOOKSTRUCT.pt.offset == 0
        assert MSLLHOOKSTRUCT.mouseData.offset == 8
        assert MSLLHOOKSTRUCT.flags.offset == 12
        assert MSLLHOOKSTRUCT.time.offset == 16
        # Compiler padding: 4 bytes at offset 20..24 before 8-byte dwExtraInfo
        assert MSLLHOOKSTRUCT.dwExtraInfo.offset == 24
        padding_bytes = MSLLHOOKSTRUCT.dwExtraInfo.offset - (MSLLHOOKSTRUCT.time.offset + ctypes.sizeof(wintypes.DWORD))
        assert padding_bytes == 4, f"MSLLHOOKSTRUCT must have exactly 4 bytes compiler padding, got {padding_bytes}"

    def test_kbdllhookstruct_offsets_and_padding(self):
        assert KBDLLHOOKSTRUCT.vkCode.offset == 0
        assert KBDLLHOOKSTRUCT.scanCode.offset == 4
        assert KBDLLHOOKSTRUCT.flags.offset == 8
        assert KBDLLHOOKSTRUCT.time.offset == 12
        # No internal padding: 4x DWORD = 16 bytes, which is 8-byte aligned
        assert KBDLLHOOKSTRUCT.dwExtraInfo.offset == 16
        internal_gap = KBDLLHOOKSTRUCT.dwExtraInfo.offset - (KBDLLHOOKSTRUCT.time.offset + ctypes.sizeof(wintypes.DWORD))
        assert internal_gap == 0, f"KBDLLHOOKSTRUCT must have 0 internal padding bytes, got {internal_gap}"

    def test_mouseinput_offsets_and_padding(self):
        assert MOUSEINPUT.dx.offset == 0
        assert MOUSEINPUT.dy.offset == 4
        assert MOUSEINPUT.mouseData.offset == 8
        assert MOUSEINPUT.dwFlags.offset == 12
        assert MOUSEINPUT.time.offset == 16
        # Compiler padding: 4 bytes at offset 20..24 before 8-byte dwExtraInfo
        assert MOUSEINPUT.dwExtraInfo.offset == 24
        padding_bytes = MOUSEINPUT.dwExtraInfo.offset - (MOUSEINPUT.time.offset + ctypes.sizeof(wintypes.DWORD))
        assert padding_bytes == 4, f"MOUSEINPUT must have exactly 4 bytes compiler padding, got {padding_bytes}"

    def test_keybdinput_offsets_and_padding(self):
        assert KEYBDINPUT.wVk.offset == 0
        assert KEYBDINPUT.wScan.offset == 2
        assert KEYBDINPUT.dwFlags.offset == 4
        assert KEYBDINPUT.time.offset == 8
        # Compiler padding: 4 bytes at offset 12..16 before 8-byte dwExtraInfo
        assert KEYBDINPUT.dwExtraInfo.offset == 16
        padding_bytes = KEYBDINPUT.dwExtraInfo.offset - (KEYBDINPUT.time.offset + ctypes.sizeof(wintypes.DWORD))
        assert padding_bytes == 4, f"KEYBDINPUT must have exactly 4 bytes compiler padding, got {padding_bytes}"

    def test_hardwareinput_offsets(self):
        assert HARDWAREINPUT.uMsg.offset == 0
        assert HARDWAREINPUT.wParamL.offset == 4
        assert HARDWAREINPUT.wParamH.offset == 6

    def test_input_offsets_and_union_padding(self):
        assert INPUT.type.offset == 0
        # Compiler padding: 4 bytes at offset 4..8 before 8-byte aligned INPUT_UNION
        assert INPUT.u.offset == 8
        padding_bytes = INPUT.u.offset - (INPUT.type.offset + ctypes.sizeof(wintypes.DWORD))
        assert padding_bytes == 4, f"INPUT must have exactly 4 bytes padding before union, got {padding_bytes}"

    def test_guithreadinfo_offsets(self):
        assert GUITHREADINFO.cbSize.offset == 0
        assert GUITHREADINFO.flags.offset == 4
        assert GUITHREADINFO.hwndActive.offset == 8
        assert GUITHREADINFO.hwndFocus.offset == 16
        assert GUITHREADINFO.hwndCapture.offset == 24
        assert GUITHREADINFO.hwndMenuOwner.offset == 32
        assert GUITHREADINFO.hwndMoveSize.offset == 40
        assert GUITHREADINFO.hwndCaret.offset == 48
        assert GUITHREADINFO.rcCaret.offset == 56


# ===========================================================================
# 3. Padding Byte Poisoning & Non-Interference
# ===========================================================================

class TestCompilerPaddingPoisoning:
    """
    Ensures that compiler padding bytes in MSLLHOOKSTRUCT, MOUSEINPUT, KEYBDINPUT,
    and INPUT remain uncorrupted and do not bleed into field reads/writes.
    """

    def test_msllhookstruct_padding_poison_invariance(self):
        raw = bytearray(b"\x00" * 32)
        poison = b"\xDE\xAD\xBE\xEF"
        raw[20:24] = poison  # Poison the padding bytes

        struct = MSLLHOOKSTRUCT.from_buffer(raw)
        struct.pt.x = 100
        struct.pt.y = 200
        struct.mouseData = 0x1234
        struct.flags = ig.LLMHF_INJECTED
        struct.time = 0x55667788
        struct.dwExtraInfo = 0x8877665544332211

        # Verify fields read correctly
        assert struct.time == 0x55667788
        assert struct.dwExtraInfo == 0x8877665544332211
        # Verify padding bytes were not altered by ctypes writes
        assert bytes(raw[20:24]) == poison

    def test_mouseinput_padding_poison_invariance(self):
        raw = bytearray(b"\x00" * 32)
        poison = b"\xCA\xFE\xBA\xBE"
        raw[20:24] = poison

        mi = MOUSEINPUT.from_buffer(raw)
        mi.dx = -50
        mi.dy = 120
        mi.mouseData = 0x0078
        mi.dwFlags = 0x8001
        mi.time = 0xAABBCCDD
        mi.dwExtraInfo = 0x1122334455667788

        assert mi.time == 0xAABBCCDD
        assert mi.dwExtraInfo == 0x1122334455667788
        assert bytes(raw[20:24]) == poison

    def test_keybdinput_padding_poison_invariance(self):
        raw = bytearray(b"\x00" * 24)
        poison = b"\xAA\x55\xAA\x55"
        raw[12:16] = poison  # Padding between time and dwExtraInfo

        ki = KEYBDINPUT.from_buffer(raw)
        ki.wVk = 0x41
        ki.wScan = 0x1E
        ki.dwFlags = 0x0002
        ki.time = 0x12345678
        ki.dwExtraInfo = 0x9988776655443322

        assert ki.time == 0x12345678
        assert ki.dwExtraInfo == 0x9988776655443322
        assert bytes(raw[12:16]) == poison

    def test_input_padding_poison_invariance(self):
        raw = bytearray(b"\x00" * 40)
        poison_union_gap = b"\xF0\x0D\xF0\x0D"
        poison_ki_gap = b"\xBA\xAD\xF0\x0D"
        raw[4:8] = poison_union_gap    # Padding before union
        raw[20:24] = poison_ki_gap     # Padding inside KEYBDINPUT (8 + 12 = 20)

        inp = INPUT.from_buffer(raw)
        inp.type = 1  # INPUT_KEYBOARD
        inp.ki.wVk = 0x1B  # VK_ESCAPE
        inp.ki.time = 0x77777777
        inp.ki.dwExtraInfo = 0x0123456789ABCDEF

        assert inp.type == 1
        assert inp.ki.wVk == 0x1B
        assert inp.ki.dwExtraInfo == 0x0123456789ABCDEF
        assert bytes(raw[4:8]) == poison_union_gap
        assert bytes(raw[20:24]) == poison_ki_gap


# ===========================================================================
# 4. Union Overlap Permutations & Little-Endian Memory Interleaving
# ===========================================================================

class TestUnionOverlapsAndMemoryInterleaving:
    """Adversarially tests overlapping memory representations in INPUT_UNION."""

    def test_union_zero_offset_overlap(self):
        assert INPUT_UNION.mi.offset == 0
        assert INPUT_UNION.ki.offset == 0
        assert INPUT_UNION.hi.offset == 0

    def test_mi_dx_overlaps_ki_wvk_wscan(self):
        """
        LONG dx (4 bytes at offset 0) overlaps with:
        wVk (2 bytes, offset 0..2) and wScan (2 bytes, offset 2..4).
        On x64 little-endian:
        0x12345678 -> wVk = 0x5678, wScan = 0x1234.
        """
        inp = INPUT()
        inp.mi.dx = 0x12345678
        assert inp.ki.wVk == 0x5678
        assert inp.ki.wScan == 0x1234

        # Mutate wVk in-place
        inp.ki.wVk = 0x00FF
        assert inp.mi.dx == 0x123400FF

    def test_mi_dy_overlaps_ki_dwflags_and_hi_wparam(self):
        """
        LONG dy (offset 4..8) overlaps with:
        KEYBDINPUT.dwFlags (offset 4..8),
        HARDWAREINPUT.wParamL (offset 4..6),
        HARDWAREINPUT.wParamH (offset 6..8).
        """
        inp = INPUT()
        inp.mi.dy = -1  # 0xFFFFFFFF
        assert inp.ki.dwFlags == 0xFFFFFFFF
        assert inp.hi.wParamL == 0xFFFF
        assert inp.hi.wParamH == 0xFFFF

        # Mutate wParamH in-place
        inp.hi.wParamH = 0x1234
        assert inp.ki.dwFlags == 0x1234FFFF

    def test_mi_mousedata_overlaps_ki_time(self):
        """DWORD mouseData (offset 8..12) overlaps KEYBDINPUT.time (offset 8..12)."""
        inp = INPUT()
        inp.mi.mouseData = 0x99887766
        assert inp.ki.time == 0x99887766

    def test_dwextrainfo_disjoint_offsets_in_union(self):
        """
        Critical 64-bit ABI divergence:
        In KEYBDINPUT, dwExtraInfo is at offset 16..24.
        In MOUSEINPUT, dwExtraInfo is at offset 24..32.
        Writing to ki.dwExtraInfo must NOT mutate mi.dwExtraInfo!
        Instead, the low 32 bits of ki.dwExtraInfo overlap mi.time (offset 16..20).
        """
        inp = INPUT()
        inp.ki.dwExtraInfo = 0xFEDCBA9876543210

        # mi.dwExtraInfo is at offset 24..32 and must remain 0
        assert inp.mi.dwExtraInfo == 0
        # mi.time is at offset 16..20 and receives the low 32 bits
        assert inp.mi.time == 0x76543210

    def test_input_property_accessors_in_place_mutation(self):
        """Property accessors inp.ki, inp.mi, inp.hi must directly mutate backing memory."""
        inp = INPUT()
        inp.type = 1
        inp.ki.wVk = 0x4B
        inp.ki.dwFlags = 0x0002

        # Verify mutation visible via direct union access
        assert inp.u.ki.wVk == 0x4B
        assert inp.u.ki.dwFlags == 0x0002

        # Verify mutation visible in raw buffer
        raw = bytes(inp)
        # inp.u starts at offset 8; ki.wVk is at offset 8, ki.dwFlags is at offset 12
        assert raw[8:10] == b"\x4B\x00"
        assert raw[12:16] == b"\x02\x00\x00\x00"


# ===========================================================================
# 5. Contiguous Array Allocations & Stride Verification (SendInput Batching)
# ===========================================================================

class TestArrayAllocationAndStride64Bit:
    """Verifies that ctypes arrays of Win32 structs maintain contiguous memory strides."""

    def test_input_array_stride_and_batch_sendinput_contract(self):
        count = 10
        input_array = (INPUT * count)()
        assert ctypes.sizeof(input_array) == count * 40
        base_addr = ctypes.addressof(input_array[0])

        for i in range(count):
            elem_addr = ctypes.addressof(input_array[i])
            expected_addr = base_addr + (i * 40)
            assert elem_addr == expected_addr, f"INPUT[{i}] not at offset {i * 40}"

    def test_msllhookstruct_array_stride(self):
        count = 4
        arr = (MSLLHOOKSTRUCT * count)()
        assert ctypes.sizeof(arr) == count * 32
        base = ctypes.addressof(arr[0])
        for i in range(count):
            assert ctypes.addressof(arr[i]) == base + (i * 32)

    def test_kbdllhookstruct_array_stride(self):
        count = 4
        arr = (KBDLLHOOKSTRUCT * count)()
        assert ctypes.sizeof(arr) == count * 24
        base = ctypes.addressof(arr[0])
        for i in range(count):
            assert ctypes.addressof(arr[i]) == base + (i * 24)

    def test_guithreadinfo_array_stride(self):
        count = 3
        arr = (GUITHREADINFO * count)()
        assert ctypes.sizeof(arr) == count * 72
        base = ctypes.addressof(arr[0])
        for i in range(count):
            assert ctypes.addressof(arr[i]) == base + (i * 72)


# ===========================================================================
# 6. Bitmask Injection Stress (LLMHF_INJECTED, LLKHF_INJECTED)
# ===========================================================================

class TestBitmaskInjectionAdversarial:
    """
    Stress-tests physical vs synthetic input discrimination using LLMHF_INJECTED and
    LLKHF_INJECTED under hostile, high-bit, and adversarial bitmask configurations.
    """

    @pytest.mark.parametrize(
        "flags,expected_injected",
        [
            (0x00000000, False),  # Clean physical mouse touch
            (0x00000001, True),   # Exact LLMHF_INJECTED
            (0x00000002, False),  # LLMHF_LOWER_IL_INJECTED without bit 0 = Physical
            (0x00000003, True),   # Both bits set = Injected
            (0x80000000, False),  # Highest bit set (sign bit) without bit 0 = Physical
            (0x80000001, True),   # High bit set + bit 0 = Injected
            (0xFFFFFFFE, False),  # All bits except bit 0 = Physical
            (0xFFFFFFFF, True),   # All bits set = Injected
        ],
    )
    def test_mouse_ll_hook_injected_discrimination(self, flags, expected_injected):
        struct = MSLLHOOKSTRUCT()
        struct.flags = flags
        is_injected = bool(struct.flags & ig.LLMHF_INJECTED)
        assert is_injected is expected_injected, (
            f"Failed for mouse flags=0x{flags:08X}: expected {expected_injected}, got {is_injected}"
        )

    @pytest.mark.parametrize(
        "flags,expected_injected",
        [
            (0x00000000, False),  # Clean physical keypress
            (0x00000010, True),   # Exact LLKHF_INJECTED (bit 4)
            (0x00000001, False),  # LLKHF_EXTENDED = Physical
            (0x00000020, False),  # LLKHF_ALTDOWN = Physical
            (0x00000080, False),  # LLKHF_UP = Physical
            (0x000000A1, False),  # EXTENDED | ALTDOWN | UP (0x01 | 0x20 | 0x80) = Physical
            (0x000000B1, True),   # EXTENDED | INJECTED | ALTDOWN | UP (0x01 | 0x10 | 0x20 | 0x80) = Injected
            (0x80000000, False),  # High sign bit = Physical
            (0x80000010, True),   # High sign bit + bit 4 = Injected
            (0xFFFFFFEF, False),  # All bits except bit 4 = Physical
            (0xFFFFFFFF, True),   # All bits set = Injected
        ],
    )
    def test_keyboard_ll_hook_injected_discrimination(self, flags, expected_injected):
        struct = KBDLLHOOKSTRUCT()
        struct.flags = flags
        is_injected = bool(struct.flags & ig.LLKHF_INJECTED)
        assert is_injected is expected_injected, (
            f"Failed for keyboard flags=0x{flags:08X}: expected {expected_injected}, got {is_injected}"
        )

    def test_hook_payload_pointer_casting_simulation(self):
        """Simulates Win32 hook procedure LPARAM pointer casting and payload decoding."""
        # 1. Simulate mouse hook event
        mouse_payload = MSLLHOOKSTRUCT()
        mouse_payload.pt.x = -1920
        mouse_payload.pt.y = -1080
        mouse_payload.mouseData = 0x0078
        mouse_payload.flags = ig.LLMHF_INJECTED
        mouse_payload.time = 987654
        mouse_payload.dwExtraInfo = 0xFEEDFACECAFEBEEF

        l_param = ctypes.addressof(mouse_payload)
        decoded_mouse = ctypes.cast(l_param, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
        assert decoded_mouse.pt.x == -1920
        assert decoded_mouse.pt.y == -1080
        assert decoded_mouse.flags == ig.LLMHF_INJECTED
        assert bool(decoded_mouse.flags & ig.LLMHF_INJECTED) is True
        assert decoded_mouse.dwExtraInfo == 0xFEEDFACECAFEBEEF

        # 2. Simulate keyboard hook event
        kbd_payload = KBDLLHOOKSTRUCT()
        kbd_payload.vkCode = 0x4B  # VK_K
        kbd_payload.scanCode = 0x25
        kbd_payload.flags = ig.LLKHF_INJECTED | ig.LLKHF_ALTDOWN
        kbd_payload.time = 554433
        kbd_payload.dwExtraInfo = 0x0123456789ABCDEF

        l_param_k = ctypes.addressof(kbd_payload)
        decoded_kbd = ctypes.cast(l_param_k, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
        assert decoded_kbd.vkCode == 0x4B
        assert decoded_kbd.scanCode == 0x25
        assert bool(decoded_kbd.flags & ig.LLKHF_INJECTED) is True
        assert bool(decoded_kbd.flags & ig.LLKHF_ALTDOWN) is True
        assert decoded_kbd.dwExtraInfo == 0x0123456789ABCDEF


# ===========================================================================
# 7. Extreme Values, Signedness & Multi-Monitor Geometry
# ===========================================================================

class TestExtremeValuesAndSignedness64Bit:
    """Verifies handling of negative coordinate spaces, wheel wrapping, and >4GB pointer values."""

    def test_point_negative_coordinates_multimonitor(self):
        pt = POINT()
        pt.x = -3840
        pt.y = -1080
        assert pt.x == -3840
        assert pt.y == -1080

    def test_rect_negative_coordinates_multimonitor(self):
        rc = RECT()
        rc.left = -3840
        rc.top = -1080
        rc.right = 0
        rc.bottom = 0
        assert rc.left == -3840
        assert rc.top == -1080
        assert rc.right == 0
        assert rc.bottom == 0

    def test_mouseinput_relative_flicks_negative(self):
        mi = MOUSEINPUT()
        mi.dx = -32768
        mi.dy = -32768
        assert mi.dx == -32768
        assert mi.dy == -32768

    def test_mouseinput_wheel_delta_wrapping(self):
        """Win32 WHEEL_DELTA down (-120) wraps into DWORD as 0xFFFFFF88 without overflow."""
        mi = MOUSEINPUT()
        mi.mouseData = -120
        assert mi.mouseData == 4294967176  # 0xFFFFFF88

    def test_guithreadinfo_64bit_handles_above_4gb(self):
        """HWND handles in 64-bit address space (>4GB) must not be truncated."""
        info = GUITHREADINFO()
        ptr_active = 0x00007FFF12345678
        ptr_caret = 0x00007FFF87654321
        info.hwndActive = ptr_active
        info.hwndCaret = ptr_caret
        assert info.hwndActive == ptr_active
        assert info.hwndCaret == ptr_caret

    def test_cbsize_contracts(self):
        """Win32 API contracts requiring exact sizeof matching."""
        info = GUITHREADINFO()
        info.cbSize = ctypes.sizeof(GUITHREADINFO)
        assert info.cbSize == 72, "GetGUIThreadInfo fails if cbSize != 72 on x64"

        inp = INPUT()
        assert ctypes.sizeof(inp) == 40, "SendInput cbSize must be exactly 40 on x64"


# ===========================================================================
# 8. ctypes.memmove, ctypes.string_at & Buffer Round-Trip Serialization
# ===========================================================================

class TestBufferSerializationAndRoundTrip:
    """Verifies that all structures can be serialized, copied, and round-tripped byte-for-byte."""

    def test_msllhookstruct_roundtrip_buffer_copy(self):
        s1 = MSLLHOOKSTRUCT()
        s1.pt.x = -150
        s1.pt.y = 350
        s1.mouseData = 0x0078
        s1.flags = ig.LLMHF_INJECTED
        s1.time = 99999
        s1.dwExtraInfo = 0xDEADBEEFCAFEFACE

        raw_bytes = bytes(s1)
        assert len(raw_bytes) == 32
        s2 = MSLLHOOKSTRUCT.from_buffer_copy(raw_bytes)

        assert s2.pt.x == s1.pt.x
        assert s2.pt.y == s1.pt.y
        assert s2.mouseData == s1.mouseData
        assert s2.flags == s1.flags
        assert s2.time == s1.time
        assert s2.dwExtraInfo == s1.dwExtraInfo

    def test_input_roundtrip_memmove(self):
        inp1 = INPUT()
        inp1.type = 1
        inp1.ki.wVk = 0x41
        inp1.ki.wScan = 0x1E
        inp1.ki.dwFlags = 0x0002
        inp1.ki.time = 123456
        inp1.ki.dwExtraInfo = 0x9988776655443322

        inp2 = INPUT()
        ctypes.memmove(ctypes.byref(inp2), ctypes.byref(inp1), ctypes.sizeof(INPUT))

        assert inp2.type == inp1.type
        assert inp2.ki.wVk == inp1.ki.wVk
        assert inp2.ki.wScan == inp1.ki.wScan
        assert inp2.ki.dwFlags == inp1.ki.dwFlags
        assert inp2.ki.time == inp1.ki.time
        assert inp2.ki.dwExtraInfo == inp1.ki.dwExtraInfo

    def test_guithreadinfo_roundtrip_string_at(self):
        g1 = GUITHREADINFO()
        g1.cbSize = 72
        g1.flags = dm.GUI_CARETBLINKING
        g1.hwndActive = 0x7FFF11112222
        g1.hwndCaret = 0x7FFF33334444
        g1.rcCaret.left = 100
        g1.rcCaret.top = 200
        g1.rcCaret.right = 105
        g1.rcCaret.bottom = 220

        raw = ctypes.string_at(ctypes.byref(g1), ctypes.sizeof(GUITHREADINFO))
        assert len(raw) == 72
        g2 = GUITHREADINFO.from_buffer_copy(raw)

        assert g2.cbSize == 72
        assert g2.flags == dm.GUI_CARETBLINKING
        assert g2.hwndActive == 0x7FFF11112222
        assert g2.hwndCaret == 0x7FFF33334444
        assert g2.rcCaret.left == 100
        assert g2.rcCaret.top == 200
        assert g2.rcCaret.right == 105
        assert g2.rcCaret.bottom == 220


# ===========================================================================
# 9. Module Export Uniformity and Singleton Class Identity
# ===========================================================================

class TestExportUniformityAndIdentity:
    """Verifies that parasite_ai.input.types re-exports the exact identical class objects."""

    def test_input_pkg_reexports_all_types(self):
        names = [
            "POINT", "RECT", "MSLLHOOKSTRUCT", "KBDLLHOOKSTRUCT",
            "MOUSEINPUT", "KEYBDINPUT", "HARDWAREINPUT", "INPUT_UNION",
            "INPUT", "GUITHREADINFO",
        ]
        for name in names:
            assert hasattr(input_pkg, name), f"parasite_ai.input missing {name}"
            assert getattr(input_pkg, name) is getattr(input_pkg.types, name), (
                f"parasite_ai.input.{name} does not match parasite_ai.input.types.{name}"
            )

    def test_authoritative_module_identities(self):
        assert POINT is ig.POINT
        assert MSLLHOOKSTRUCT is ig.MSLLHOOKSTRUCT
        assert KBDLLHOOKSTRUCT is ig.KBDLLHOOKSTRUCT
        assert RECT is wg.RECT
        assert MOUSEINPUT is kb.MOUSEINPUT
        assert KEYBDINPUT is kb.KEYBDINPUT
        assert HARDWAREINPUT is kb.HARDWAREINPUT
        assert INPUT_UNION is kb.INPUT_UNION
        assert INPUT is kb.INPUT
        assert GUITHREADINFO is dm.GUITHREADINFO
