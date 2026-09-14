import pytest
from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from studycopilot.capture.region import RegionCapture, RegionOverlay, crop_region


def frame(width=600, height=400):
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(QColor("#e4ac21"))
    return image


@pytest.mark.parametrize("ratio", [1, 1.25, 1.5, 2])
def test_crop_uses_physical_pixels_at_scaling(ratio):
    image = frame(round(600 * ratio), round(400 * ratio))
    cropped = crop_region(image, QSize(600, 400), QRectF(40, 20, 160, 80))
    assert cropped.size() == QSize(round(160 * ratio), round(80 * ratio))
    assert cropped.devicePixelRatio() == 1
    assert cropped.pixelColor(0, 0) == QColor("#e4ac21")


def test_reverse_drag_and_screen_clipping():
    cropped = crop_region(frame(), QSize(600, 400), QRectF(100, 100, -120, -130))
    assert cropped.size() == QSize(100, 100)


@pytest.mark.parametrize("rectangle", [QRectF(0, 0, 1, 20), QRectF(0, 0, 20, 7),
                                       QRectF(-100, -100, 10, 10), QRectF()])
def test_tiny_or_outside_region_is_ignored(rectangle):
    with pytest.raises(ValueError):
        crop_region(frame(), QSize(600, 400), rectangle)


def test_capture_never_starts_automatically_and_pending_cancel_restores(qapp):
    calls, results = [], []
    capture = RegionCapture(grab=lambda screen: calls.append(screen) or frame())
    window = QWidget()
    window.show()
    qapp.processEvents()
    assert not capture.busy and calls == []
    capture.captured.connect(lambda *args: results.append(args))
    assert capture.start()
    assert not window.isVisible()
    assert not capture.start("explain")
    capture.cancel()
    QTest.qWait(200)
    assert calls == [] and results == []
    assert window.isVisible() and not capture.busy
    assert not capture.start()  # debounce after cancellation
    window.close()
    capture.deleteLater()


@pytest.mark.parametrize("method", ["escape", "right"])
def test_overlay_cancel_events(qapp, method):
    overlay = RegionOverlay(frame(), QRect(-600, 0, 600, 400))
    cancelled = []
    overlay.cancelled.connect(lambda: cancelled.append(True))
    overlay.show()
    if method == "escape":
        QTest.keyClick(overlay, Qt.Key.Key_Escape)
    else:
        QTest.mouseClick(overlay, Qt.MouseButton.RightButton, pos=QPoint(20, 20))
    assert cancelled == [True]
    overlay.close()


def test_capture_crop_uses_original_pixels_and_negative_screen_origin(qapp):
    capture = RegionCapture()
    overlay = RegionOverlay(frame(), QRect(-600, 50, 600, 400))
    capture.busy = True
    capture.task_type = "explain"
    capture.overlays = [overlay]
    results = []
    capture.captured.connect(lambda *args: results.append(args))
    overlay.chosen.connect(lambda rect: capture._chosen(overlay, rect))
    overlay.show()
    QTest.mousePress(overlay, Qt.MouseButton.LeftButton, pos=QPoint(30, 40))
    QTest.mouseMove(overlay, QPoint(190, 120))
    QTest.mouseRelease(overlay, Qt.MouseButton.LeftButton, pos=QPoint(190, 120))
    image, region, task = results[0]
    assert image.size() == QSize(160, 80)
    assert image.pixelColor(0, 0) == QColor("#e4ac21")  # no dimming or selection border
    assert region == (-570, 90, 160, 80) and task == "explain"
    assert not capture.busy and capture.overlays == []


def test_freeze_occurs_before_overlay_and_handles_failure(qapp):
    calls = []
    capture = RegionCapture(screens=lambda: qapp.screens())
    capture.grab = lambda screen: calls.append(len(capture.overlays)) or frame(
        screen.geometry().width(), screen.geometry().height())
    assert capture.start()
    capture._begin(capture.generation)
    assert calls and set(calls) == {0}
    assert capture.overlays
    capture.cancel()
    capture.last_finished = float("-inf")
    capture.grab = lambda screen: QImage()
    failures = []
    capture.failed.connect(failures.append)
    assert capture.start()
    capture._begin(capture.generation)
    assert failures and not capture.busy
