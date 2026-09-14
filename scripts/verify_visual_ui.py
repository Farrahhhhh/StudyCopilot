"""Render and exercise our own synthetic textbook UI; never capture the desktop."""
import json
import os
import sys
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "windows" if "--native" in sys.argv else "offscreen"
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QImage, QPainter, QPen
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from studycopilot.capture.active_window import ActiveWindow
from studycopilot.capture.clipboard import clone_mime
from studycopilot.capture.region import RegionCapture
from studycopilot.capture.windows import WindowsAPI
from studycopilot.config import Settings
from studycopilot.main import initialize
from studycopilot.ui.controller import SidebarController
from studycopilot.ui.sidebar import Sidebar

root = Path(__file__).resolve().parents[1]
output = root / "test-results"
output.mkdir(exist_ok=True)
app = QApplication([])
if app.platformName() == "offscreen":
    for name in ("msyh.ttc", "msyhbd.ttc", "segoeui.ttf"):
        QFontDatabase.addApplicationFont(str(Path(os.environ["WINDIR"]) / "Fonts" / name))
app.setFont(QFont("Microsoft YaHei UI", 9))
api = WindowsAPI() if app.platformName() == "windows" else None
snapshot = clone_mime(app.clipboard().mimeData()) if api else None
last_sequence = None
db = initialize(Settings(output / "visual-render-data"))
view = Sidebar()
controller = SidebarController(view, db)
try:
    project = next((p for p in controller.projects.list_projects() if p["name"] == "模拟电子技术"), None)
    project = project or controller.projects.create_project("模拟电子技术")
    controller.refresh_projects(project["id"])
    sources = controller.projects.list_sources(project["id"])
    source = sources[0] if sources else controller.projects.create_source(project["id"], "Microelectronic Circuits")
    controller.refresh_sources(source["id"])
    controller.source_changed()
    view.show()
    app.processEvents()
    view.grab().save(str(output / "v02-empty.png"))

    page = QImage(1100, 680, QImage.Format.Format_RGB32)
    page.fill(QColor("#fffdf5"))
    painter = QPainter(page)
    painter.setPen(QColor("#29313a"))
    painter.setFont(QFont("Georgia", 25))
    painter.drawText(45, 65, "MOSFET Amplifiers")
    painter.setFont(QFont("Georgia", 16))
    for i, line in enumerate((
        "A source resistance introduces negative feedback.",
        "Assume the transistor operates in saturation and r_o is large.",
        "The voltage gain is reduced, while its sensitivity to g_m is improved.",
    )):
        painter.drawText(45, 115 + i * 36, line)
    painter.setFont(QFont("Cambria Math", 24))
    painter.drawText(65, 295, "Aᵥ = −gₘ Rᴅ / (1 + gₘ Rₛ)")
    painter.setFont(QFont("Georgia", 14))
    painter.drawText(45, 625, "Synthetic verification material · no textbook content is reproduced")
    painter.setPen(QPen(QColor("#29313a"), 3))
    # Simplified common-source stage, drawn solely as a screenshot fixture.
    painter.drawLine(720, 310, 720, 350)
    painter.drawRect(707, 350, 26, 50)
    painter.drawLine(720, 400, 720, 435)
    painter.drawLine(720, 435, 800, 435)
    painter.drawLine(720, 435, 720, 455)
    painter.drawLine(695, 455, 695, 495)
    painter.drawLine(705, 455, 705, 495)
    painter.drawLine(705, 460, 720, 460)
    painter.drawLine(705, 490, 720, 490)
    painter.drawLine(650, 475, 695, 475)
    painter.drawLine(720, 490, 720, 515)
    painter.drawRect(707, 515, 26, 40)
    painter.drawLine(720, 555, 720, 575)
    painter.drawLine(700, 575, 740, 575)
    painter.drawText(745, 380, "Rᴅ")
    painter.drawText(745, 540, "Rₛ")
    painter.drawText(660, 300, "Vᴅᴅ")
    painter.drawText(810, 440, "vₒ")
    painter.drawText(610, 480, "vᵢ")
    painter.end()

    controller.accept_screenshot(page, (80, 80, 1100, 680), "translate",
                                  ActiveWindow(process_name="SyntheticReader.exe", window_title="Microelectronic Circuits"))
    app.processEvents()
    assert controller.package and controller.package.current_screenshot
    assert not view.image.isNull()
    view.grab().save(str(output / "v02-reading.png"))
    controller.visual.prepare()
    last_sequence = api.sequence() if api else None
    assert app.clipboard().mimeData().hasImage()
    app.processEvents()
    view.grab().save(str(output / "v02-handoff.png"))
    controller.copy()
    last_sequence = api.sequence() if api else None
    assert "Context Package" in app.clipboard().text()
    view.followup.setText("为什么这里可以忽略 r_o？")
    controller.rebuild()
    assert controller.package.task_type == "explain"
    view.grab().save(str(output / "v02-followup.png"))

    # Native overlays with injected synthetic framebuffers: exercise Qt mouse events and restoration.
    capture = RegionCapture(view, grab=lambda screen: page.scaled(screen.geometry().size()))
    results = []
    capture.captured.connect(lambda *args: results.append(args))
    assert capture.start("explain")
    QTest.qWait(220)
    assert capture.overlays
    overlay = capture.overlays[0]
    QTest.mousePress(overlay, Qt.MouseButton.LeftButton, pos=QPoint(40, 40))
    QTest.mouseMove(overlay, QPoint(240, 160))
    QTest.mouseRelease(overlay, Qt.MouseButton.LeftButton, pos=QPoint(240, 160))
    assert len(results) == 1 and results[0][2] == "explain"
    assert results[0][0].width() == 200 and results[0][0].height() == 120
    assert view.isVisible() and not capture.busy
    capture.last_finished = float("-inf")
    assert capture.start()
    QTest.qWait(220)
    QTest.keyClick(capture.overlays[0], Qt.Key.Key_Escape)
    assert not capture.busy and len(results) == 1 and view.isVisible()
    (output / "v02-ui-result.json").write_text(json.dumps({
        "status": "passed", "platform": app.platformName(), "viewport": [view.width(), view.height()],
        "image_handoff": "image then text verified on Qt clipboard; external client paste not tested",
        "region": "native Qt overlays with injected synthetic pixels; drag and Esc passed",
        "screens": [{"logical_width": s.geometry().width(), "logical_height": s.geometry().height(),
                     "device_pixel_ratio": s.devicePixelRatio()} for s in app.screens()],
        "desktop_screenshot_taken": False,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
finally:
    if snapshot is not None and (last_sequence is None or api.sequence() == last_sequence):
        app.clipboard().setMimeData(snapshot)
    elif not api:
        app.clipboard().clear()
    view.close()
    app.processEvents()
    db.close()
print("Visual reading, two-step clipboard, follow-up and native overlay fixture passed.")
