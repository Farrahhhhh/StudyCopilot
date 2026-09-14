"""Probe a requested shortcut without sending input or changing another app."""
import ctypes
import json
from studycopilot.capture.windows import WindowsAPI

api = WindowsAPI()
report = {}
for label, modifiers in (("Alt+Q", 0x4001), ("Alt+Shift+Q", 0x4005)):
    ctypes.set_last_error(0)
    registered = api.user32.RegisterHotKey(None, 0x4A52, modifiers, 0x51)
    code = ctypes.get_last_error()
    report[label] = {"available": bool(registered), "win32_error": code}
    if registered:
        api.user32.UnregisterHotKey(None, 0x4A52)
print(json.dumps(report, ensure_ascii=False))
