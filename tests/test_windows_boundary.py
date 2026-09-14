import ctypes
from ctypes import wintypes
import os
from types import SimpleNamespace

import pytest

from studycopilot.capture.hotkeys import GlobalHotkey
from studycopilot.capture.windows import INPUT, WindowsAPI


class FakeUser32:
    def __init__(self):
        self.registered = False
        self.unregistered = False
        self.allowed = True

    def RegisterHotKey(self, *args):
        self.registered = self.allowed
        return self.allowed

    def UnregisterHotKey(self, *args):
        self.unregistered = True
        return True


def test_hotkey_native_message_and_unregister(qapp):
    api = SimpleNamespace(user32=FakeUser32())
    calls = []
    hotkey = GlobalHotkey(qapp, api, lambda: calls.append("triggered"))
    hotkey.register()
    message = wintypes.MSG()
    message.message = 0x0312
    message.wParam = hotkey.HOTKEY_ID
    handled = hotkey.nativeEventFilter(b"windows_dispatcher_MSG", ctypes.addressof(message))
    assert handled == (True, 0) and calls == ["triggered"]
    message.message = 0x1234
    assert hotkey.nativeEventFilter(b"windows_generic_MSG", ctypes.addressof(message)) == (False, 0)
    hotkey.close()
    assert api.user32.unregistered


def test_hotkey_conflict_is_reported(qapp):
    api = SimpleNamespace(user32=FakeUser32())
    api.user32.allowed = False
    hotkey = GlobalHotkey(qapp, api, lambda: None)
    with pytest.raises(OSError, match="Alt\\+Q"):
        hotkey.register()
    assert not hotkey.registered


@pytest.mark.skipif(os.name != "nt", reason="Windows ABI only")
def test_windows_api_abi_and_readonly_probe():
    api = WindowsAPI()
    assert ctypes.sizeof(INPUT) == (40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28)
    assert isinstance(api.sequence(), int)
    assert isinstance(api.foreground_handle(), int)
