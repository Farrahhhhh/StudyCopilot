from __future__ import annotations

from datetime import datetime
import logging
import sqlite3

from PySide6.QtCore import QObject, QTimer, Qt
from PySide6.QtWidgets import QApplication, QDialog, QInputDialog, QLineEdit, QMessageBox

from studycopilot.capture.active_window import ActiveWindow
from studycopilot.context.manager import ContextManager
from studycopilot.context.models import StudyContext
from studycopilot.integrations.fallback import ClipboardIntegration
from studycopilot.memory.database import Database
from studycopilot.memory.retrieval import FTSMemoryRetriever
from studycopilot.memory.store import MemoryStore
from studycopilot.projects.manager import ProjectManager, suggest_source

from .dialogs import MemoryDialog, SourceDialog
from .sidebar import Sidebar
from .visual_workflow import VisualWorkflow
from .reading_workflow import ReadingWorkflow

logger = logging.getLogger(__name__)


class SidebarController(QObject):
    def __init__(self, view: Sidebar, db: Database, provider=None, auto_connect=True):
        super().__init__(view)
        self.view, self.db = view, db
        self.projects, self.memory = ProjectManager(db), MemoryStore(db)
        self.context = ContextManager(db, FTSMemoryRetriever(db))
        self.integration = ClipboardIntegration()
        self.window = ActiveWindow()
        self.package = None
        self.capture_busy = False
        self.capture_shortcut: str | None = "Alt+Q"
        self.suggested_title = ""
        self.manual_memory_ids = ()
        self.memory_concept = ""
        self.rebuild_timer = QTimer(self)
        self.rebuild_timer.setSingleShot(True)
        self.rebuild_timer.setInterval(250)
        self.rebuild_timer.timeout.connect(self.rebuild)
        view.projects.currentIndexChanged.connect(self.project_changed)
        view.sources.currentIndexChanged.connect(self.source_changed)
        view.new_project.clicked.connect(self.create_project)
        view.new_source.clicked.connect(lambda: self.create_source())
        view.suggestion.clicked.connect(lambda: self.create_source(self.suggested_title))
        view.selection.textChanged.connect(self.invalidate)
        view.topic.textChanged.connect(self.invalidate)
        view.save_memory.clicked.connect(self.save_memory)
        from .memory_workflow import MemoryWorkflow
        self.memory_ui = MemoryWorkflow(self)
        view.use_memory.toggled.connect(self.invalidate)
        view.copy_button.clicked.connect(self.copy)
        view.closing.connect(self.close)
        self.reading = None
        self.visual = VisualWorkflow(self)
        self.reading = ReadingWorkflow(self, provider, auto_connect)
        self.refresh_projects()

    def message(self, text: str) -> None:
        self.view.status.setText(text)

    def refresh_projects(self, selected: str | None = None) -> None:
        items = self.projects.list_projects()
        if not items:
            items = [self.projects.create_project("未分类")]
        self.view.projects.blockSignals(True)
        self.view.projects.clear()
        for item in items:
            self.view.projects.addItem(item["name"], item["id"])
        index = self.view.projects.findData(selected)
        self.view.projects.setCurrentIndex(max(index, 0))
        self.view.projects.blockSignals(False)
        self.project_changed()

    def project_changed(self) -> None:
        self.memory_ui.clear_selection()
        self.visual.reset()
        self.view.selection.clear()
        self.view.topic.clear()
        self.window = ActiveWindow()
        self.view.window_info.setText("当前应用：待采集\n窗口：未知也可以继续")
        self.suggested_title = ""
        self.view.suggestion.hide()
        self.refresh_sources()
        self.rebuild()

    def refresh_sources(self, selected: str | None = None) -> None:
        self.view.sources.blockSignals(True)
        self.view.sources.clear()
        self.view.sources.addItem("未指定资料（仍可翻译）", None)
        for source in self.projects.list_sources(self.view.projects.currentData()):
            self.view.sources.addItem(source["title"], source["id"])
        self.view.sources.setCurrentIndex(max(0, self.view.sources.findData(selected)))
        self.view.sources.blockSignals(False)

    def source_changed(self) -> None:
        self.memory_ui.clear_selection()
        self.view.topic.clear()
        self.rebuild()

    def create_project(self) -> None:
        name, accepted = QInputDialog.getText(self.view, "新建项目", "项目名称（最多 200 字）",
                                              QLineEdit.EchoMode.Normal)
        if accepted:
            try:
                item = self.projects.create_project(name)
                self.refresh_projects(item["id"])
                self.message("已创建并选择项目。")
            except (ValueError, sqlite3.Error) as error:
                self.show_error(error)

    def create_source(self, suggested: str = "") -> None:
        dialog = SourceDialog(self.view, suggested)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                project_id = self.view.projects.currentData()
                title = dialog.title.text().strip()
                existing = next((s for s in self.projects.list_sources(project_id) if s["title"] == title), None)
                source = existing or self.projects.create_source(project_id, title, dialog.kind.currentData())
                self.refresh_sources(source["id"])
                self.view.suggestion.hide()
                self.source_changed()
                self.message("已选择资料；Topic 可选填。")
            except (ValueError, sqlite3.Error) as error:
                self.show_error(error)

    def invalidate(self) -> None:
        self.view.prepare_button.setEnabled(False)
        self.view.handoff_panel.hide()
        self.package = None
        self.view.copy_button.setEnabled(False)
        self.view.preview.clear()
        self.rebuild_timer.start()

    def set_busy(self, busy: bool) -> None:
        self.capture_busy = busy
        for widget in (self.view.projects, self.view.sources, self.view.topic, self.view.selection,
                       self.view.new_project, self.view.new_source, self.view.suggestion, self.view.save_memory,
                       self.view.screenshot_translate, self.view.screenshot_explain, self.view.followup,
                       self.view.clear_image, self.view.keep_image, self.view.enlarge_image,
                       self.view.text_capture, self.view.recent_images, self.view.copy_image_button):
            widget.setEnabled(not busy)
        self.view.copy_button.setEnabled(not busy and self.package is not None)
        self.visual.render()
        self.reading.sync()
        if busy:
            self.message("正在采集，请松开快捷键；截图时拖动框选，Esc 取消。")

    def update_window(self, window: ActiveWindow) -> None:
        self.view.window_info.setText(f"当前应用：{window.process_name or '未知'}\n窗口：{window.window_title or '未知'}")
        self.suggested_title = suggest_source(window.window_title)
        if self.suggested_title and self.suggested_title != self.view.sources.currentText():
            short_title = self.suggested_title[:33] + ("…" if len(self.suggested_title) > 33 else "")
            self.view.suggestion.setText("资料建议：" + short_title + "  ›")
            self.view.suggestion.setToolTip(self.suggested_title + "（点击确认或修改）")
            self.view.suggestion.show()
        else:
            self.view.suggestion.hide()

    def captured(self, text: str, window: ActiveWindow) -> None:
        self.visual.reset()
        self.window = window
        self.update_window(window)
        self.view.selection.setPlainText(text)
        self.view.text_toggle.setChecked(True)
        self.rebuild()
        if self.package and self.visual.last_context:
            self.visual.recent.record(self.visual.last_context, "translate")
        self.message("选文已获取。")
        self.reading.auto_submit()
        self.view.show()
        self.view.raise_()
        self.view.activateWindow()

    def accept_screenshot(self, image, region, task_type, window) -> None:
        self.visual.accept(image, region, task_type, window)

    def rebuild(self) -> None:
        self.rebuild_timer.stop()
        self.package = None
        self.view.copy_button.setEnabled(False)
        self.view.prepare_button.setEnabled(False)
        self.view.preview.clear()
        self.view.knowledge.setPlainText("暂无匹配概念。")
        self.view.memories.setPlainText("待发送候选：暂无相关记忆。实际使用情况请查看回答上方。")
        try:
            project_id, source_id = self.view.projects.currentData(), self.view.sources.currentData()
            topic = self.projects.topic(project_id, source_id, self.view.topic.text())
            session = self.context.ensure_session(project_id, source_id, topic["id"] if topic else None)
            started = datetime.fromisoformat(session["started_at"]).astimezone().strftime("%H:%M")
            self.view.session.setText(f"Session · 本次学习开始于 {started}")
            location = self.view.projects.currentText() + " · " + (self.view.sources.currentText() if source_id else "未指定资料")
            self.view.location.setText(self.view.location.fontMetrics().elidedText(location, Qt.TextElideMode.ElideRight, self.view.width() - 75))
            self.view.location.setToolTip(location)
            visual_inputs = self.visual.inputs(project_id, source_id, topic["id"] if topic else None, session["id"])
            text = self.view.selection.toPlainText()
            if not text.strip() and not self.visual.current:
                self.view.package_info.setText("翻译模式 · 只提供当前选文与必要上下文")
                self.message("点击截图翻译，或在辅助文字中输入内容。")
                self.visual.render()
                if self.reading:
                    self.reading.sync()
                return
            context = StudyContext(selected_text=text, project_id=project_id, source_id=source_id,
                topic_id=topic["id"] if topic else None, session_id=session["id"],
                process_name=self.window.process_name, current_app=self.window.process_name,
                window_title=self.window.window_title, use_project_memory=self.view.use_memory.isChecked(),
                strict_project_memory=True, memory_concept=self.memory_concept,
                manual_memory_ids=self.manual_memory_ids, **visual_inputs)
            self.visual.last_context = context
            task_type = "explain" if self.view.followup.text().strip() else self.visual.task_type
            self.package = self.context.build(context, task_type)
            self.view.preview.setPlainText(self.integration.format(self.package))
            concepts = self.package.related_concepts
            if concepts:
                self.view.knowledge.setPlainText("\n\n".join(
                    f"{c['chinese_name']}\n{c['canonical_name']}" for c in concepts))
            memories = self.package.relevant_memories
            if memories:
                self.view.memories.setPlainText("待发送候选（非已使用记录）\n\n" + "\n\n".join(f"[{m['scope']}] {m['content']}" for m in memories))
            self.view.package_info.setText(f"选文 {len(text)} 字符 · {len(concepts)} 个概念 · {len(memories)} 条记忆")
            self.view.copy_button.setEnabled(not self.capture_busy)
            self.visual.render()
            if self.reading:
                self.reading.sync()
            self.message("可直接追问，或继续截图。")
        except (ValueError, sqlite3.Error) as error:
            self.message(str(error) if isinstance(error, ValueError) else "数据库操作失败，请检查数据目录权限。")
            logger.warning("context failed kind=%s", type(error).__name__)

    def copy(self) -> None:
        if self.capture_busy:
            return
        self.rebuild()
        if self.package:
            self.integration.copy(self.package, QApplication.clipboard().setText)
            self.message("说明已复制。请到同一 AI 对话中粘贴，确认附图后发送。")
            logger.info("context copied project_id=%s source_id=%s",
                        self.view.projects.currentData(), self.view.sources.currentData())

    def save_memory(self) -> None:
        self.memory_ui.edit(dialog_class=MemoryDialog)

    def show_error(self, error: Exception) -> None:
        message = str(error) if isinstance(error, ValueError) else "名称可能已存在，或数据库暂时不可写。请换一个名称或稍后重试。"
        QMessageBox.warning(self.view, "操作未完成", message)

    def close(self) -> None:
        self.rebuild_timer.stop()
        if self.reading:
            self.reading.close()
        self.context.end_session()
