"""Render previously obtained real responses locally; makes no model requests."""
import json
from pathlib import Path
from PySide6.QtWidgets import QApplication
from studycopilot.memory.database import Database
from studycopilot.ui.sidebar import Sidebar
from studycopilot.ui.controller import SidebarController
from studycopilot.capture.active_window import ActiveWindow
from PySide6.QtGui import QImage
root=Path(__file__).resolve().parents[1]
evidence=root/"test-results/v03-live-94b9be68"
out=root/"test-results/v03-display"
out.mkdir(exist_ok=True)
app=QApplication([])
db=Database(out/"study.db")
view=Sidebar()
c=SidebarController(view,db,auto_connect=False)
view.auto_translate.blockSignals(True)
view.auto_translate.setChecked(True)
view.auto_translate.blockSignals(False)
c.reading.enabled=True
c.reading.update_privacy()
view.connection_info.setText("已连接 ChatGPT 订阅")
view.show()
rows=json.loads((evidence/"results.json").read_text(encoding="utf-8"))
for n in (1,2,8,9):
    c.reading.enabled=False
    c.accept_screenshot(QImage(str(evidence/f"source-{n:02}.png")),(0,0,1100,320),rows[n-1]["task"],ActiveWindow())
    c.reading.enabled=True
    view.result.show_answer(rows[n-1]["answer"])
    view.result_status.setText("已完成 · "+str(rows[n-1]["total_seconds"])+" 秒")
    view.copy_translation.setEnabled(True)
    app.processEvents()
    view.grab().save(str(out/f"result-{n:02}.png"))
    if n==8:
        assert "<table" in view.result.toHtml()
    assert view.send_question.mapTo(view,view.send_question.rect().bottomRight()).y()<view.status.y()
view.close()
db.close()
print("Rendered four real saved results; follow-up visible; table rendered.")
