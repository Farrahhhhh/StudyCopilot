from __future__ import annotations

import ctypes
from ctypes import wintypes
from typing import Callable

from PySide6.QtCore import QAbstractNativeEventFilter
from PySide6.QtWidgets import QApplication

from .windows import WindowsAPI

SHORTCUTS = {"Alt+Q": 1, "Alt+Shift+Q": 5, "Alt+A": 1, "Ctrl+Alt+Q": 3, "Ctrl+Alt+A": 3}


class GlobalHotkey(QAbstractNativeEventFilter):
    HOTKEY_ID = 0x4A51

    def __init__(self, app: QApplication, api: WindowsAPI, callback: Callable[[], None],
                 shortcut: str = "Alt+Q", identifier: int | None = None):
        super().__init__()
        if shortcut not in SHORTCUTS:
            raise ValueError("仅支持 Alt+Q 或 Alt+Shift+Q。")
        self.app, self.api, self.callback = app, api, callback
        self.shortcut = shortcut
        self.HOTKEY_ID = identifier if identifier is not None else type(self).HOTKEY_ID
        self.registered = False

    def register(self) -> None:
        if self.registered:
            return
        modifiers = SHORTCUTS[self.shortcut] | 0x4000
        if not self.api.user32.RegisterHotKey(None, self.HOTKEY_ID, modifiers, ord(self.shortcut[-1])):
            code = getattr(ctypes, "get_last_error", lambda: 0)()
            raise OSError(code, f"{self.shortcut} 注册失败，可能已被占用。可使用手动粘贴。")
        self.app.installNativeEventFilter(self)
        self.registered = True

    def nativeEventFilter(self, event_type, message):
        if bytes(event_type) in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == 0x0312 and msg.wParam == self.HOTKEY_ID:
                self.callback()
                return True, 0
        return False, 0

    def close(self) -> None:
        if self.registered:
            self.api.user32.UnregisterHotKey(None, self.HOTKEY_ID)
            self.app.removeNativeEventFilter(self)
            self.registered = False


def register_with_fallback(app: QApplication, api: WindowsAPI, callback: Callable[[], None],
                           preferred: str = "Alt+Q") -> GlobalHotkey:
    hotkey = GlobalHotkey(app, api, callback, preferred)
    try:
        hotkey.register()
    except OSError as error:
        if preferred != "Alt+Q" or error.errno != 1409:
            raise
        hotkey = GlobalHotkey(app, api, callback, "Alt+Shift+Q")
        hotkey.register()
    return hotkey
