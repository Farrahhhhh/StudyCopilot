"""Offline widget rendering; synthetic material only, no model/desktop capture."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
import json
from uuid import uuid4

from PySide6.QtGui import QImage, QPainter, QColor, QFontDatabase
from PySide6.QtWidgets import QApplication, QDialog

from studycopilot.capture.active_window import ActiveWindow
from studycopilot.memory.database import Database
from studycopilot.providers.reading import ReadingProvider
from studycopilot.ui.sidebar import Sidebar
from studycopilot.ui.controller import SidebarController

class OfflineProvider(ReadingProvider):
    def __init__(self):
        super().__init__()
        self.current = None
    def connect_service(self):
        pass
    def login(self):
        pass
    def submit(self, request):
        self.current = request
        self.request_submitted.emit(request.id)
    def cancel(self):
        self.current = None
    def close(self):
        self.current = None

def main():
    output = Path("test-results") / ("memory-ui-" + uuid4().hex[:8])
    output.mkdir(parents=True)
    app = QApplication.instance() or QApplication([])
    for font in ("msyh.ttc", "msyhbd.ttc", "segoeui.ttf"):
        QFontDatabase.addApplicationFont(str(Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / font))
    db = Database(output / "study.db")
    provider = OfflineProvider()
    view = Sidebar()
    c = SidebarController(view, db, provider, auto_connect=False)
    project = c.projects.create_project("模拟电子技术")
    c.refresh_projects(project["id"])
    source = c.projects.create_source(project["id"], "Microelectronic Circuits")
    c.refresh_sources(source["id"])
    c.source_changed()
    image = QImage(420, 160, QImage.Format.Format_RGB32)
    image.fill(QColor("white"))
    painter = QPainter(image)
    painter.setPen(QColor("black"))
    painter.drawText(16, 55, "Offline fixture: transconductance")
    painter.drawText(16, 100, "i_d = g_m * v_gs")
    painter.end()
    c.accept_screenshot(image, (0, 0, 420, 160), "explain", ActiveWindow())
    memory = c.memory.save("为什么跨导 gm 的单位是西门子？", project_id=project["id"],
        source_id=source["id"], screenshot_id=c.visual.current.id,
        source_snapshot={"location": "第 9 页（测试输入）"})
    c.visual.current = c.visual.store.get(c.visual.current.id)
    c.manual_memory_ids = (memory["id"],)
    view.followup.setText("gm 与电压增益有什么区别？")
    c.reading.ask()
    request = provider.current
    provider.current = None
    provider.completed.emit(request.id, "离线界面检查 · 模拟回答\n\n跨导描述栅源电压变化引起的漏极电流变化。\n\n**g_m = ∂i_D / ∂v_GS**\n\n这里只检查排版与记忆来源，不代表真实模型验证。", "offline-test")
    view.show()
    app.processEvents()
    view.grab().save(str(output / "sidebar.png"))
    geometry = {
        "viewport_height": view.scroll.viewport().height(),
        "followup_bottom": view.followup.mapTo(view.scroll.viewport(), view.followup.rect().bottomLeft()).y(),
        "result_height": view.result.height(),
    }
    original_exec = QDialog.exec
    counter = 0
    def render_dialog(dialog):
        nonlocal counter
        counter += 1
        dialog.show()
        app.processEvents()
        dialog.grab().save(str(output / f"dialog-{counter}.png"))
        dialog.reject()
        return QDialog.DialogCode.Rejected
    QDialog.exec = render_dialog
    try:
        c.memory_ui.used()
        c.memory_ui.manage()
        c.memory_ui.edit()
        c.memory_ui.show_source(c.memory.source(memory), project["id"])
        c.memory_ui.select()
    finally:
        QDialog.exec = original_exec
        view.close()
        db.close()
    (output / "geometry.json").write_text(json.dumps(geometry), encoding="utf-8")
    print(output.resolve())
    print(geometry)

if __name__ == "__main__":
    main()
