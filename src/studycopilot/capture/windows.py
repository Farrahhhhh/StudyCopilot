"""Small, typed Win32 boundary. Importable on non-Windows hosts for core tests."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import os


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]


class INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("data",)
    _fields_ = [("type", wintypes.DWORD), ("data", INPUTUNION)]


class WindowsAPI:
    def __init__(self):
        if os.name != "nt":
            raise OSError("全局快捷键和选文采集仅支持 Windows。")
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        definitions = {
            "GetForegroundWindow": ([], wintypes.HWND),
            "GetWindowTextLengthW": ([wintypes.HWND], ctypes.c_int),
            "GetWindowTextW": ([wintypes.HWND, wintypes.LPWSTR, ctypes.c_int], ctypes.c_int),
            "GetWindowThreadProcessId": ([wintypes.HWND, ctypes.POINTER(wintypes.DWORD)], wintypes.DWORD),
            "GetClipboardSequenceNumber": ([], wintypes.DWORD),
            "GetAsyncKeyState": ([ctypes.c_int], wintypes.SHORT),
            "SendInput": ([wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int], wintypes.UINT),
            "RegisterHotKey": ([wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT], wintypes.BOOL),
            "UnregisterHotKey": ([wintypes.HWND, ctypes.c_int], wintypes.BOOL),
        }
        for name, (arguments, result) in definitions.items():
            function = getattr(self.user32, name)
            function.argtypes, function.restype = arguments, result
        self.kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.kernel32.OpenProcess.restype = wintypes.HANDLE
        self.kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                                          wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
        self.kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        self.kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel32.CloseHandle.restype = wintypes.BOOL

    def foreground_handle(self) -> int:
        return self.user32.GetForegroundWindow() or 0

    def sequence(self) -> int:
        return self.user32.GetClipboardSequenceNumber()

    def modifiers_down(self) -> bool:
        return any(self.user32.GetAsyncKeyState(key) & 0x8000 for key in (0x10, 0x11, 0x12, 0x51))

    def copy_selection(self) -> None:
        events = (INPUT * 4)(
            INPUT(type=1, ki=KEYBDINPUT(wVk=0x11)),
            INPUT(type=1, ki=KEYBDINPUT(wVk=0x43)),
            INPUT(type=1, ki=KEYBDINPUT(wVk=0x43, dwFlags=2)),
            INPUT(type=1, ki=KEYBDINPUT(wVk=0x11, dwFlags=2)),
        )
        if self.user32.SendInput(4, events, ctypes.sizeof(INPUT)) != 4:
            # Best effort release if Windows accepts only part of the sequence.
            releases = (INPUT * 2)(events[2], events[3])
            self.user32.SendInput(2, releases, ctypes.sizeof(INPUT))
            raise OSError("无法发送 Ctrl+C；请确认目标阅读器没有以管理员身份运行。")
