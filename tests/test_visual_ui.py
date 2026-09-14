from PySide6.QtGui import QColor, QImage
from studycopilot.capture.active_window import ActiveWindow
from studycopilot.projects.manager import ProjectManager
from studycopilot.ui.sidebar import Sidebar
from studycopilot.ui.controller import SidebarController


def setup_visual(qapp, db):
    view = Sidebar()
    controller = SidebarController(view, db)
    image = QImage(320, 180, QImage.Format.Format_RGB32)
    image.fill(QColor("#87aacc"))
    view.show()
    controller.accept_screenshot(image, (50, 50, 320, 180), "translate", ActiveWindow())
    qapp.processEvents()
    return view, controller


def test_normal_view_and_image_question_handoff(qapp, db):
    view, controller = setup_visual(qapp, db)
    try:
        assert not view.details_panel.isVisible()
        assert not view.settings_panel.isVisible()
        assert not view.text_panel.isVisible()
        assert controller.package.current_screenshot
        assert controller.package.selected_text == ""
        original = controller.visual.current.id
        view.prepare_button.click()
        assert view.handoff_panel.isVisible()
        assert qapp.clipboard().mimeData().hasImage()
        view.followup.setText("为什么可以忽略 r_o？")
        assert not view.handoff_panel.isVisible()
        controller.rebuild()
        assert controller.package.task_type == "explain"
        assert controller.package.current_screenshot["id"] == original
        view.prepare_button.click()
        view.copy_button.click()
        assert "为什么可以忽略 r_o" in qapp.clipboard().text()
        assert controller.visual.recent.list(view.projects.currentData(),
                view.sources.currentData(), controller.context.session["id"])[0]["question"]
        view.keep_image.click()
        assert controller.package.current_screenshot["is_persistent"]
    finally:
        view.close()


def test_missing_or_corrupt_file_never_claims_image_copied(qapp, db):
    view, controller = setup_visual(qapp, db)
    try:
        path = controller.visual.store.path(controller.visual.current)
        path.write_bytes(b"invalid png")
        view.prepare_button.click()
        assert not view.handoff_panel.isVisible()
        assert "读取失败" in view.status.text()
        path.unlink()
        view.prepare_button.click()
        assert "缺失" in view.status.text()
        assert not view.handoff_panel.isVisible()
    finally:
        view.close()


def test_source_correction_rebinds_temporary_image_and_project_switch_clears(qapp, db):
    view, controller = setup_visual(qapp, db)
    try:
        original = controller.visual.current.id
        project = view.projects.currentData()
        source = ProjectManager(db).create_source(project, "Textbook", "book")
        controller.refresh_sources(source["id"])
        controller.source_changed()
        assert controller.visual.current.id == original
        assert controller.visual.current.source_id == source["id"]
        assert controller.package.source["id"] == source["id"]
        assert controller.visual.recent.list(project, source["id"], controller.context.session["id"])
        other = ProjectManager(db).create_project("Other project")
        controller.refresh_projects(other["id"])
        assert controller.package is None and controller.visual.current is None
        assert not view.followup.text()
        assert not view.prepare_button.isEnabled()
    finally:
        view.close()


def test_recent_question_is_bounded_and_reset_by_new_session(qapp, db):
    view, controller = setup_visual(qapp, db)
    try:
        view.followup.setText("为什么可以忽略 r_o？")
        controller.visual.prepare()
        view.followup.setText("那么电压增益如何变化？")
        controller.rebuild()
        assert any("忽略 r_o" in item for item in controller.package.recent_context)
        view.selection.setPlainText("Auxiliary caption")
        controller.rebuild()
        assert controller.package.current_screenshot and controller.package.selected_text
        controller.visual.clear()
        assert controller.package.current_screenshot is None
    finally:
        view.close()
