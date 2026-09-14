"""Wire existing Windows capture to the screenshot-first UI; no database code here."""
from __future__ import annotations

import logging
import os

from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QApplication

from .active_window import ActiveWindow, get_active_window
from .clipboard import SelectionCapture
from .hotkeys import GlobalHotkey
from .region import RegionCapture
from .windows import WindowsAPI

logger = logging.getLogger(__name__)


class CaptureRuntime(QObject):
    def __init__(self, app, controller, no_hotkey=False):
        super().__init__(controller.view)
        self.app, self.controller, self.view = app, controller, controller.view
        self.api = WindowsAPI() if os.name == "nt" else None
        self.region = RegionCapture(self)
        self.region.captured.connect(self.region_captured)
        self.region.cancelled.connect(lambda: controller.message("已取消截图，保留之前的内容。"))
        self.region.failed.connect(controller.message)
        self.region.busy_changed.connect(controller.set_busy)
        self.active_window = ActiveWindow()
        self.text = None
        self.hotkeys = []
        self.text_delay = QTimer(self)
        self.text_delay.setSingleShot(True)
        self.text_delay.timeout.connect(self.start_text)
        if self.api:
            self.text = SelectionCapture(app.clipboard(), self.api, self)
            self.text.shortcut = "Alt+Shift+Q"
            self.text.captured.connect(controller.captured)
            self.text.failed.connect(controller.message)
            self.text.busy_changed.connect(controller.set_busy)
        self.view.screenshot_translate.clicked.connect(lambda: self.start_region("translate"))
        self.view.screenshot_explain.clicked.connect(lambda: self.start_region("explain"))
        self.view.text_capture.clicked.connect(self.delayed_text)
        self.view.closing.connect(self.close)
        descriptions = []
        if self.api and not no_hotkey:
            for preferred, fallback, identifier, callback in (
                ("Alt+Q", "Ctrl+Alt+Q", 0x4A61, lambda: self.start_region("translate")),
                ("Alt+A", "Ctrl+Alt+A", 0x4A62, lambda: self.start_region("explain")),
                ("Alt+Shift+Q", None, 0x4A63, self.start_text),
            ):
                chosen = None
                for shortcut in [preferred] + ([fallback] if fallback else []):
                    hotkey = GlobalHotkey(app, self.api, callback, shortcut, identifier)
                    try:
                        hotkey.register()
                        chosen = shortcut
                        self.hotkeys.append(hotkey)
                        logger.info("hotkey registered shortcut=%s", shortcut)
                        break
                    except OSError:
                        continue
                descriptions.append((preferred, chosen))
        mapping = dict(descriptions)
        self.view.shortcut_hint.setText(
            f"翻译 {mapping.get('Alt+Q') or '点击按钮'} · 解释 {mapping.get('Alt+A') or '点击按钮'}")
        self.view.shortcut_hint.setToolTip(
            f"文字采集 {mapping.get('Alt+Shift+Q') or '更多 → 辅助文字 → 手动粘贴'}")
        controller.capture_shortcut = mapping.get("Alt+Shift+Q")
        self.view.set_capture_shortcut(controller.capture_shortcut)
        conflicts = [f"{p} → {c or '使用按钮'}" for p, c in descriptions if p != c]
        controller.message("快捷键冲突：" + "；".join(conflicts) if conflicts else "框选教材区域，译文将直接显示在侧栏。")

    def start_region(self, task_type):
        if self.controller.capture_busy or self.app.activeModalWidget():
            return
        window = get_active_window(self.api) if self.api else ActiveWindow()
        self.active_window = window if window.process_id != os.getpid() else ActiveWindow()
        self.text_delay.stop()
        self.controller.rebuild()
        self.region.start(task_type)

    def region_captured(self, image, region, task_type):
        self.controller.accept_screenshot(image, region, task_type, self.active_window)

    def start_text(self):
        self.text_delay.stop()
        if self.text and not self.controller.capture_busy and not self.app.activeModalWidget():
            self.text.start()

    def delayed_text(self):
        if self.text_delay.isActive() or self.controller.capture_busy:
            return
        self.controller.message("请在 3 秒内切回阅读器并选中文字。")
        self.text_delay.start(3000)

    def close(self):
        self.text_delay.stop()
        for hotkey in self.hotkeys:
            hotkey.close()
        self.hotkeys.clear()
        self.region.cancel()
        if self.text:
            self.text.cancel()
