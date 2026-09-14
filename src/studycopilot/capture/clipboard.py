"""Event-driven selection capture. QClipboard is accessed only on the Qt GUI thread."""
from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable

from PySide6.QtCore import QMimeData, QObject, QTimer, Signal
from PySide6.QtGui import QClipboard, QImage, QPixmap

from .active_window import ActiveWindow, get_active_window
from .windows import WindowsAPI

logger = logging.getLogger(__name__)


def clone_mime(source: QMimeData | None, max_bytes: int = 8 * 1024 * 1024) -> QMimeData:
    snapshot = QMimeData()
    size = 0
    if source is not None:
        for mime in source.formats():
            if mime == "application/x-qt-image" and source.hasImage():
                continue
            data = source.data(mime)
            size += data.size()
            if size > max_bytes:
                raise ValueError("原剪贴板内容过大，已取消自动采集。请手动复制选文并粘贴到侧栏。")
            snapshot.setData(mime, data)
        if source.hasImage():
            image = source.imageData()
            if isinstance(image, QPixmap):
                image = image.toImage()
            if isinstance(image, QImage):
                size += image.sizeInBytes()
                if size > max_bytes:
                    raise ValueError("原剪贴板图片过大，已取消采集。请手动粘贴选文。")
                snapshot.setImageData(image.copy())
    return snapshot


class SelectionCapture(QObject):
    captured = Signal(str, object)
    failed = Signal(str)
    busy_changed = Signal(bool)

    def __init__(self, clipboard: QClipboard, api: WindowsAPI, parent: QObject | None = None,
                 window_reader: Callable = get_active_window, clock: Callable = time.monotonic,
                 timeout_ms: int = 2200):
        super().__init__(parent)
        self.clipboard, self.api = clipboard, api
        self.window_reader, self.clock = window_reader, clock
        self.timeout = timeout_ms / 1000
        self.timer = QTimer(self)
        self.timer.setInterval(40)
        self.timer.timeout.connect(self._tick)
        self.busy = False
        self.shortcut = "Alt+Q"
        self.last_finished = float("-inf")
        self.snapshot: QMimeData | None = None
        self.window = ActiveWindow()
        self.baseline = 0
        self.sent_at: float | None = None
        self.started_at = 0.0

    def start(self) -> None:
        if self.busy or self.clock() - self.last_finished < 0.5:
            return
        try:
            self.window = self.window_reader(self.api)
            if not self.window.handle or self.window.process_id == os.getpid():
                raise ValueError(f"请先在外部阅读器中选中文字，再按 {self.shortcut}；侧栏内容可直接编辑。")
            self.snapshot = clone_mime(self.clipboard.mimeData())
            self.baseline = self.api.sequence()
            self.started_at = self.clock()
            self.sent_at = None
            self.busy = True
            self.busy_changed.emit(True)
            self.timer.start()
        except (ValueError, OSError, RuntimeError) as error:
            self.snapshot = None
            self.failed.emit(str(error))

    def _tick(self) -> None:
        if not self.busy:
            return
        try:
            elapsed = self.clock() - self.started_at
            if self.api.foreground_handle() != self.window.handle:
                self._finish(error=f"采集期间前台窗口改变，已取消。请重新选择文字并按 {self.shortcut}。")
                return
            if self.sent_at is None:
                if self.api.modifiers_down():
                    if elapsed > 1.2:
                        self._finish(error="请松开 Alt、Q 和其他修饰键后重试。")
                    return
                # A user clipboard write during the key-release wait must not be overwritten.
                if self.api.sequence() != self.baseline:
                    self._finish(error="等待期间剪贴板已变化，已取消；请重新采集。")
                    return
                self.api.copy_selection()
                self.sent_at = self.clock()
                return
            sequence = self.api.sequence()
            if sequence != self.baseline:
                text = self.clipboard.text()
                captured_sequence = self.api.sequence()
                self._restore(captured_sequence)
                if not text.strip():
                    self._finish(error="没有获得文字，可能选中的是图片或阅读器禁止复制。请手动粘贴。")
                elif len(text) > 24000:
                    self._finish(error="选文超过 24000 个字符，请分段选择。")
                else:
                    self._finish(text=text)
                return
            waiting = self.clock() - self.sent_at
            if waiting >= self.timeout:
                # No clipboard change: leave the original clipboard untouched.
                self._finish(error="未收到复制内容。请确认已选中文字；扫描 PDF 暂不支持，或尝试手动粘贴。")
            # Retry reads, never Ctrl+C: a second delayed copy could overwrite
            # the restored clipboard after the first response has completed.
        except (OSError, RuntimeError) as error:
            logger.warning("capture failed kind=%s", type(error).__name__)
            self._finish(error="采集失败，请重试或手动粘贴。")

    def _restore(self, captured_sequence: int) -> None:
        if self.snapshot is not None and self.api.sequence() == captured_sequence:
            snapshot, self.snapshot = self.snapshot, None
            self.clipboard.setMimeData(snapshot)

    def _finish(self, text: str | None = None, error: str | None = None) -> None:
        self.timer.stop()
        self.busy = False
        self.snapshot = None
        self.last_finished = self.clock()
        self.busy_changed.emit(False)
        if error:
            logger.info("capture failed")
            self.failed.emit(error)
        elif text is not None:
            logger.info("capture success length=%d", len(text))
            self.captured.emit(text, self.window)

    def cancel(self) -> None:
        if self.busy:
            self._finish(error="采集已取消。")
