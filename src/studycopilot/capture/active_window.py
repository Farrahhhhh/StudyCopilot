from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import PureWindowsPath

from .windows import WindowsAPI


@dataclass(frozen=True)
class ActiveWindow:
    handle: int = 0
    process_id: int | None = None
    process_name: str | None = None
    window_title: str | None = None


def get_active_window(api: WindowsAPI) -> ActiveWindow:
    handle = api.foreground_handle()
    if not handle:
        return ActiveWindow()
    size = min(api.user32.GetWindowTextLengthW(handle) + 1, 4096)
    title = ctypes.create_unicode_buffer(max(size, 1))
    api.user32.GetWindowTextW(handle, title, len(title))
    pid = wintypes.DWORD()
    api.user32.GetWindowThreadProcessId(handle, ctypes.byref(pid))
    process_name = None
    process = api.kernel32.OpenProcess(0x1000, False, pid.value)
    if process:
        try:
            path = ctypes.create_unicode_buffer(32768)
            length = wintypes.DWORD(len(path))
            if api.kernel32.QueryFullProcessImageNameW(process, 0, path, ctypes.byref(length)):
                process_name = PureWindowsPath(path.value).name
        finally:
            api.kernel32.CloseHandle(process)
    return ActiveWindow(handle, pid.value or None, process_name, title.value or None)
