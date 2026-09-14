"""User-triggered, single-display region selection across independently scaled monitors."""
from __future__ import annotations

import math
import time

from PySide6.QtCore import QObject, QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QImage, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget


def crop_region(image: QImage, logical_size: QSize, rectangle: QRectF, minimum=8) -> QImage:
    """Use actual framebuffer ratios; Qt screen coordinates are logical, pixels are physical."""
    bounds = QRectF(0, 0, logical_size.width(), logical_size.height())
    rect = rectangle.normalized().intersected(bounds)
    if image.isNull() or min(logical_size.width(), logical_size.height()) <= 0:
        raise ValueError("屏幕图像不可用。")
    if rect.width() < minimum or rect.height() < minimum:
        raise ValueError("选区太小，已取消。")
    sx, sy = image.width() / bounds.width(), image.height() / bounds.height()
    left, top = math.floor(rect.left() * sx), math.floor(rect.top() * sy)
    right, bottom = math.ceil(rect.right() * sx), math.ceil(rect.bottom() * sy)
    result = image.copy(left, top, min(image.width(), right) - left, min(image.height(), bottom) - top)
    result.setDevicePixelRatio(1.0)
    return result


class RegionOverlay(QWidget):
    chosen = Signal(object)
    cancelled = Signal()

    def __init__(self, image: QImage, geometry, screen=None):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool |
                         Qt.WindowType.WindowStaysOnTopHint)
        self.image = image
        self.origin: QPointF | None = None
        self.pointer = QPointF()
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setGeometry(geometry)
        if screen is not None:
            self.winId()
            self.windowHandle().setScreen(screen)
            self.setGeometry(geometry)

    def selection(self) -> QRectF:
        if self.origin is None:
            return QRectF()
        return QRectF(self.origin, self.pointer).normalized().intersected(QRectF(self.rect()))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawImage(QRectF(self.rect()), self.image)
        painter.fillRect(self.rect(), QColor(9, 18, 30, 115))
        rect = self.selection()
        if not rect.isEmpty():
            painter.save()
            painter.setClipRect(rect)
            painter.drawImage(QRectF(self.rect()), self.image)
            painter.restore()
            painter.setPen(QPen(QColor("#75b8ff"), 2))
            painter.drawRect(rect)
        painter.setPen(QColor("white"))
        painter.drawText(18, 30, "拖动框选 · 松开完成 · Esc / 右键取消 · 每次选择一个显示器")
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.cancelled.emit()
        elif event.button() == Qt.MouseButton.LeftButton:
            self.origin = event.position()
            self.pointer = event.position()
            self.update()

    def mouseMoveEvent(self, event):
        self.pointer = event.position()
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.origin is not None:
            self.pointer = event.position()
            self.chosen.emit(self.selection())

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
        else:
            super().keyPressEvent(event)


class RegionCapture(QObject):
    captured = Signal(object, object, str)
    cancelled = Signal()
    failed = Signal(str)
    busy_changed = Signal(bool)

    def __init__(self, parent=None, screens=None, grab=None, clock=time.monotonic):
        super().__init__(parent)
        self.screens = screens or QApplication.screens
        self.grab = grab or (lambda screen: screen.grabWindow(0).toImage())
        self.clock = clock
        self.busy = False
        self.overlays: list[RegionOverlay] = []
        self.hidden_windows: list[QWidget] = []
        self.task_type = "translate"
        self.last_finished = float("-inf")
        self.generation = 0
        self.deadline = QTimer(self)
        self.deadline.setSingleShot(True)
        self.deadline.timeout.connect(self.cancel)
        app = QApplication.instance()
        if app:
            app.screenRemoved.connect(lambda _: self.cancel() if self.busy else None)

    def start(self, task_type="translate") -> bool:
        if self.busy or self.clock() - self.last_finished < 0.5:
            return False
        if task_type not in {"translate", "explain"}:
            raise ValueError("未知截图任务。")
        self.task_type = task_type
        self.busy = True
        self.generation += 1
        generation = self.generation
        self.busy_changed.emit(True)
        self.hidden_windows = [w for w in QApplication.topLevelWidgets() if w.isVisible()]
        for window in self.hidden_windows:
            window.hide()
        # Allow compositor to remove the sidebar before freezing pixels. No overlay exists yet.
        QTimer.singleShot(160, lambda: self._begin(generation))
        self.deadline.start(120000)
        return True

    def _begin(self, generation: int) -> None:
        if not self.busy or generation != self.generation:
            return
        try:
            frozen = []
            for screen in self.screens():
                image = self.grab(screen)
                if image.isNull():
                    raise ValueError("无法读取屏幕。请检查是否处于锁屏、远程限制或受保护内容界面。")
                frozen.append((screen, image))
            if not frozen:
                raise ValueError("没有可用的显示器。")
            # Grab ALL screens before showing ANY overlay, avoiding mask contamination.
            for screen, image in frozen:
                overlay = RegionOverlay(image, screen.geometry(), screen)
                overlay.chosen.connect(lambda rect, item=overlay: self._chosen(item, rect))
                overlay.cancelled.connect(self.cancel)
                self.overlays.append(overlay)
            for overlay in self.overlays:
                overlay.show()
            target = next((o for o in self.overlays if o.geometry().contains(QCursor.pos())), self.overlays[0])
            target.raise_()
            target.activateWindow()
            target.setFocus()
        except (OSError, ValueError, RuntimeError):
            self._finish()
            self.failed.emit("截图准备失败。可重试，或使用辅助文字输入。")

    def _chosen(self, overlay: RegionOverlay, rect: QRectF) -> None:
        if not self.busy:
            return
        try:
            image = crop_region(overlay.image, overlay.size(), rect)
            global_rect = rect.translated(overlay.geometry().topLeft())
            region = (round(global_rect.x()), round(global_rect.y()),
                      round(global_rect.width()), round(global_rect.height()))
        except ValueError:
            self.cancel()
            return
        task_type = self.task_type
        self._finish()
        self.captured.emit(image, region, task_type)

    def _finish(self) -> None:
        self.deadline.stop()
        self.generation += 1
        for overlay in self.overlays:
            overlay.close()
            overlay.deleteLater()
        self.overlays.clear()  # Drop full-screen pixel buffers; only the chosen crop survives.
        for window in self.hidden_windows:
            window.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
            window.show()
            window.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
        self.hidden_windows.clear()
        self.busy = False
        self.last_finished = self.clock()
        self.busy_changed.emit(False)

    def cancel(self) -> None:
        if self.busy:
            self._finish()
            self.cancelled.emit()
