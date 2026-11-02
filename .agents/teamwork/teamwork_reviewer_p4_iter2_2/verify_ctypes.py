import ctypes
from ctypes import wintypes
import sys

from parasite_ai.safety.interrupt_guard import POINT, MSLLHOOKSTRUCT, KBDLLHOOKSTRUCT
from parasite_ai.hands.keyboard import MOUSEINPUT, KEYBDINPUT, HARDWAREINPUT, INPUT_UNION, INPUT
from parasite_ai.mind.dual_mind import GUITHREADINFO

# RECT from wintypes
RECT = wintypes.RECT

expected = {
    "POINT": (8, 4),
    "RECT": (16, 4),
    "MSLLHOOKSTRUCT": (32, 8),
    "KBDLLHOOKSTRUCT": (24, 8),
    "MOUSEINPUT": (32, 8),
    "KEYBDINPUT": (24, 8),
    "HARDWAREINPUT": (8, 4),
    "INPUT_UNION": (32, 8),
    "INPUT": (40, 8),
    "GUITHREADINFO": (72, 8),
}

structs = {
    "POINT": POINT,
    "RECT": RECT,
    "MSLLHOOKSTRUCT": MSLLHOOKSTRUCT,
    "KBDLLHOOKSTRUCT": KBDLLHOOKSTRUCT,
    "MOUSEINPUT": MOUSEINPUT,
    "KEYBDINPUT": KEYBDINPUT,
    "HARDWAREINPUT": HARDWAREINPUT,
    "INPUT_UNION": INPUT_UNION,
    "INPUT": INPUT,
    "GUITHREADINFO": GUITHREADINFO,
}

print("Verifying 10 Win32 ctypes structures on Python 64-bit...")
all_ok = True
for name, cls in structs.items():
    sz = ctypes.sizeof(cls)
    align = ctypes.alignment(cls)
    exp_sz, exp_align = expected[name]
    ok = (sz == exp_sz and align == exp_align)
    if not ok:
        all_ok = False
        print(f"FAIL {name}: size={sz} (exp {exp_sz}), align={align} (exp {exp_align})")
    else:
        print(f"PASS {name}: size={sz}, align={align}")

# Check offsets for critical structs
print("\nChecking field offsets...")
offsets_to_check = {
    "MSLLHOOKSTRUCT": [("pt", 0), ("mouseData", 8), ("flags", 12), ("time", 16), ("dwExtraInfo", 24)],
    "KBDLLHOOKSTRUCT": [("vkCode", 0), ("scanCode", 4), ("flags", 8), ("time", 12), ("dwExtraInfo", 16)],
    "MOUSEINPUT": [("dx", 0), ("dy", 4), ("mouseData", 8), ("dwFlags", 12), ("time", 16), ("dwExtraInfo", 24)],
    "KEYBDINPUT": [("wVk", 0), ("wScan", 2), ("dwFlags", 4), ("time", 8), ("dwExtraInfo", 16)],
    "HARDWAREINPUT": [("uMsg", 0), ("wParamL", 4), ("wParamH", 6)],
    "INPUT": [("type", 0), ("u", 8)],
    "GUITHREADINFO": [("cbSize", 0), ("flags", 4), ("hwndActive", 8), ("hwndFocus", 16), ("hwndCapture", 24), ("hwndMenuOwner", 32), ("hwndMoveSize", 40), ("hwndCaret", 48), ("rcCaret", 56)],
}

for struct_name, field_offsets in offsets_to_check.items():
    cls = structs[struct_name]
    for field_name, exp_offset in field_offsets:
        actual_offset = getattr(cls, field_name).offset
        if actual_offset != exp_offset:
            all_ok = False
            print(f"FAIL {struct_name}.{field_name} offset: {actual_offset} (expected {exp_offset})")
        else:
            print(f"PASS {struct_name}.{field_name} offset: {actual_offset}")

if all_ok:
    print("\nALL 10 Win32 CTYPES STRUCTURES VERIFIED EXACTLY MATCHING 64-BIT ABI!")
else:
    sys.exit(1)
