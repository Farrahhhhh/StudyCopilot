import json
from PySide6.QtWidgets import QDialog
from studycopilot.capture.active_window import ActiveWindow
from studycopilot.knowledge.concepts import ConceptStore
from studycopilot.memory.store import MemoryStore
from studycopilot.projects.manager import ProjectManager
from studycopilot.ui.controller import SidebarController
from studycopilot.ui.sidebar import Sidebar
from studycopilot.ui import controller as controller_module


def test_sidebar_full_local_workflow(qapp, db, monkeypatch):
    ConceptStore(db).seed_terminology()
    MemoryStore(db).seed_preferences()
    view = Sidebar()
    controller = SidebarController(view, db)
    view.show()
    qapp.processEvents()
    monkeypatch.setattr(controller_module.QInputDialog, "getText", lambda *a: ("模拟电子技术", True))
    view.new_project.click()
    project_id = view.projects.currentData()
    assert view.projects.currentText() == "模拟电子技术"

    def source_exec(dialog):
        dialog.title.setText("Microelectronic Circuits")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(controller_module.SourceDialog, "exec", source_exec)
    view.new_source.click()
    source_id = view.sources.currentData()
    assert source_id
    controller.captured("The source resistance introduces negative feedback.",
                        ActiveWindow(123, 999, "reader.exe", "Microelectronic Circuits.pdf - Reader"))
    assert controller.package.project["id"] == project_id
    assert controller.package.source["id"] == source_id
    assert controller.package.related_concepts[0]["canonical_name"] == "negative feedback"

    def memory_exec(dialog):
        dialog.content.setPlainText("negative feedback 的物理意义仍不稳定")
        dialog.concept.setCurrentIndex(1)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(controller_module.MemoryDialog, "exec", memory_exec)
    view.save_memory.click()
    assert len(controller.package.relevant_memories) == 1
    view.copy_button.click()
    prompt = qapp.clipboard().text()
    payload = json.loads(prompt.split("Context Package（JSON 数据）：\n", 1)[1])
    assert payload["project"]["name"] == "模拟电子技术"
    assert payload["source"]["title"] == "Microelectronic Circuits"
    assert payload["relevant_memories"][0]["scope"] == "project"
    assert "negative feedback" in payload["selected_text"]
    assert "已复制" in view.status.text()

    other = ProjectManager(db).create_project("ArduPilot")
    controller.refresh_projects(other["id"])
    assert controller.package is None
    assert not view.copy_button.isEnabled()
    assert not view.selection.toPlainText()
    controller.captured("negative feedback", ActiveWindow())
    assert controller.package.relevant_memories == []
    view.close()
    qapp.processEvents()
    assert controller.context.session is None


def test_manual_edit_invalidates_preview_and_capture_locks_project(qapp, db):
    view = Sidebar()
    controller = SidebarController(view, db)
    view.selection.setPlainText("hello")
    controller.rebuild()
    assert view.copy_button.isEnabled()
    view.selection.setPlainText("new selection")
    assert not view.copy_button.isEnabled() and controller.package is None
    controller.rebuild()
    assert controller.package.selected_text == "new selection"
    controller.set_busy(True)
    assert not view.projects.isEnabled() and not view.copy_button.isEnabled()
    controller.set_busy(False)
    view.selection.clear()
    controller.rebuild()
    assert controller.package is None
    view.close()
