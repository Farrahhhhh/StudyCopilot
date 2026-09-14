import ctypes
from types import SimpleNamespace

import pytest

from studycopilot.capture.hotkeys import register_with_fallback
from studycopilot.capture.windows import INPUT, WindowsAPI


class FakeNativeHotkeys:
    def __init__(self, allow_shift=True):
        self.modifiers = []
        self.allow_shift = allow_shift
        self.closed = False

    def RegisterHotKey(self, handle, identifier, modifiers, key):
        self.modifiers.append(modifiers)
        return bool(modifiers & 4) and self.allow_shift

    def UnregisterHotKey(self, handle, identifier):
        self.closed = True
        return True


def test_conflicting_alt_q_uses_visible_alternative(qapp, monkeypatch):
    native = FakeNativeHotkeys()
    monkeypatch.setattr(ctypes, "get_last_error", lambda: 1409, raising=False)
    hotkey = register_with_fallback(qapp, SimpleNamespace(user32=native), lambda: None)
    assert hotkey.shortcut == "Alt+Shift+Q"
    assert native.modifiers == [0x4001, 0x4005]
    hotkey.close()
    assert native.closed


@pytest.mark.parametrize("error_code,expected_attempts", [(1409, 2), (5, 1)])
def test_unavailable_shortcuts_or_other_errors_reported(qapp, monkeypatch, error_code, expected_attempts):
    native = FakeNativeHotkeys(allow_shift=False)
    monkeypatch.setattr(ctypes, "get_last_error", lambda: error_code, raising=False)
    with pytest.raises(OSError):
        register_with_fallback(qapp, SimpleNamespace(user32=native), lambda: None)
    assert len(native.modifiers) == expected_attempts


def test_sendinput_layout_and_ctrl_c_release_without_real_input():
    calls = []

    def send_input(count, events, size):
        calls.append([(events[i].ki.wVk, events[i].ki.dwFlags) for i in range(count)])
        assert size == ctypes.sizeof(INPUT)
        return count

    api = WindowsAPI.__new__(WindowsAPI)
    api.user32 = SimpleNamespace(SendInput=send_input)
    api.copy_selection()
    assert calls == [[(0x11, 0), (0x43, 0), (0x43, 2), (0x11, 2)]]
