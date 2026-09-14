"""Render only our own synthetic Qt widget, never the user's desktop."""
import json
import os
import sys
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "windows" if "--native" in sys.argv else "offscreen"

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase
from studycopilot.capture.active_window import ActiveWindow
from studycopilot.capture.clipboard import clone_mime
from studycopilot.config import Settings
from studycopilot.main import initialize
from studycopilot.ui.sidebar import Sidebar
from studycopilot.ui.controller import SidebarController

root = Path(__file__).resolve().parents[1]
output = root / "test-results"
output.mkdir(exist_ok=True)
app = QApplication([])
if app.platformName() == 'offscreen' and os.name == 'nt':
    for font_name in ('msyh.ttc', 'msyhbd.ttc', 'segoeui.ttf'):
        QFontDatabase.addApplicationFont(str(Path(os.environ['WINDIR']) / 'Fonts' / font_name))
clipboard_snapshot = clone_mime(app.clipboard().mimeData()) if app.platformName() != "offscreen" else None
db = initialize(Settings(output / "render-data"))
view = Sidebar()
controller = SidebarController(view, db)
manager = controller.projects
projects = manager.list_projects()
project = next((p for p in projects if p["name"] == "模拟电子技术"), None)
project = project or manager.create_project("模拟电子技术")
controller.refresh_projects(project["id"])
sources = manager.list_sources(project["id"])
source = sources[0] if sources else manager.create_source(project["id"], "Microelectronic Circuits")
controller.refresh_sources(source["id"])
if not db.one("SELECT id FROM memories WHERE scope='project'"):
    controller.memory.save("negative feedback 的直觉需要结合电路再理解。", project_id=project["id"])
view.topic.setText("MOSFET Amplifiers")
controller.captured(
    "The source resistance introduces negative feedback.\n"
    "The small-signal transconductance is denoted by g_m.",
    ActiveWindow(handle=1, process_id=-1, process_name="TestReader.exe",
                 window_title="Microelectronic Circuits.pdf - Test Reader"),
)
view.resize(430, 850)
view.show()
app.processEvents()
view.grab().save(str(output / "sidebar.png"))
view.tabs.setCurrentIndex(2)
app.processEvents()
view.grab().save(str(output / "prompt-preview.png"))
assert controller.package and controller.package.related_concepts
assert controller.package.relevant_memories
assert view.copy_button.isEnabled()
view.copy_button.click()
assert "Context Package" in app.clipboard().text()
(output / "ui-result.json").write_text(json.dumps({
    "synthetic_ui_flow": "passed",
    "width": view.width(),
    "height": view.height(),
    "concept_count": len(controller.package.related_concepts),
    "memory_count": len(controller.package.relevant_memories),
    "scope": f"{app.platformName()} Qt with synthetic input; does not validate external PDF readers",
}, ensure_ascii=False, indent=2), encoding="utf-8")
if clipboard_snapshot is not None:
    app.clipboard().setMimeData(clipboard_snapshot)
view.close()
controller.close()
db.close()
print("Synthetic UI rendering and copy flow passed.")
