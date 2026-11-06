import ctypes
class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", ctypes.c_uint), ("wParamL", ctypes.c_ushort), ("wParamH", ctypes.c_ushort)]
class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort), ("wScan", ctypes.c_ushort), ("dwFlags", ctypes.c_uint), ("time", ctypes.c_uint), ("dwExtraInfo", ctypes.c_size_t)]
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long), ("mouseData", ctypes.c_uint), ("dwFlags", ctypes.c_uint), ("time", ctypes.c_uint), ("dwExtraInfo", ctypes.c_size_t)]
class INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]
class INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_uint), ("u", INPUT_UNION)]
print(f'MOUSEINPUT={ctypes.sizeof(MOUSEINPUT)} KEYBDINPUT={ctypes.sizeof(KEYBDINPUT)} HARDWAREINPUT={ctypes.sizeof(HARDWAREINPUT)} INPUT_UNION={ctypes.sizeof(INPUT_UNION)} INPUT={ctypes.sizeof(INPUT)}')
print(f'INPUT offset={INPUT.u.offset}')
