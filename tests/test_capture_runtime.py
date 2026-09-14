from types import SimpleNamespace

from studycopilot.capture import runtime as runtime_module
from studycopilot.ui.sidebar import Sidebar
from studycopilot.ui.controller import SidebarController


def test_screenshot_and_legacy_shortcuts_are_independent(qapp, db, monkeypatch):
    created = []
    class Hotkey:
        def __init__(self, app, api, callback, shortcut, identifier):
            self.shortcut, self.identifier, self.callback = shortcut, identifier, callback
            self.closed = False
            created.append(self)
        def register(self):
            if self.shortcut == "Alt+Q":
                raise OSError(1409, "occupied")
        def close(self):
            self.closed = True
    monkeypatch.setattr(runtime_module, "WindowsAPI", lambda: SimpleNamespace())
    monkeypatch.setattr(runtime_module, "GlobalHotkey", Hotkey)
    view = Sidebar()
    controller = SidebarController(view, db)
    runtime = runtime_module.CaptureRuntime(qapp, controller)
    assert [h.shortcut for h in runtime.hotkeys] == ["Ctrl+Alt+Q", "Alt+A", "Alt+Shift+Q"]
    assert len({h.identifier for h in runtime.hotkeys}) == 3
    assert controller.capture_shortcut == "Alt+Shift+Q"
    assert "Ctrl+Alt+Q" in view.shortcut_hint.text()
    assert not runtime.region.busy  # registration alone cannot capture the screen
    runtime.close()
    assert all(h.closed for h in created if h.shortcut != "Alt+Q")
    view.close()


def test_delayed_text_is_single_and_cancelled_on_close(qapp, db, monkeypatch):
    monkeypatch.setattr(runtime_module, "WindowsAPI", lambda: SimpleNamespace())
    view = Sidebar()
    controller = SidebarController(view, db)
    runtime = runtime_module.CaptureRuntime(qapp, controller, no_hotkey=True)
    runtime.delayed_text()
    first = runtime.text_delay.timerId()
    runtime.delayed_text()
    assert runtime.text_delay.timerId() == first
    assert runtime.text_delay.isActive()
    view.close()
    assert not runtime.text_delay.isActive()
