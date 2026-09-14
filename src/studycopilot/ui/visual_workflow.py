from __future__ import annotations

import logging
import sqlite3
from PySide6.QtCore import Qt, QUrl, QTimer
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QScrollArea, QVBoxLayout

from studycopilot.context.models import StudyContext
from studycopilot.context.recent import RecentContextStore
from studycopilot.memory.screenshots import ScreenshotStore

logger = logging.getLogger(__name__)


class VisualWorkflow:
    def __init__(self, controller):
        self.controller, self.view = controller, controller.view
        self.store = ScreenshotStore(controller.db)
        self.recent = RecentContextStore(controller.db)
        self.current = None
        self.task_type = "translate"
        self.last_context = None
        self.prepared = None
        self.dialogs = []
        self.view.prepare_button.clicked.connect(self.prepare)
        self.view.copy_image_button.clicked.connect(self.copy_image)
        self.view.keep_image.clicked.connect(self.keep)
        self.view.clear_image.clicked.connect(self.clear)
        self.view.enlarge_image.clicked.connect(self.enlarge)
        self.view.followup.textChanged.connect(controller.invalidate)
        self.view.recent_images.activated.connect(self.choose_recent)
        self.view.open_ai.clicked.connect(self.open_ai)

    def reset(self):
        if self.controller.reading:
            self.controller.reading.reset()
        self.current = None
        self.prepared = None
        self.last_context = None
        self.task_type = "translate"
        self.view.followup.clear()
        self.view.handoff_panel.hide()
        self.view.set_image(None)
        self.view.screenshot_info.setText("当前没有截图")
        self.view.recent_images.clear()
        self.view.recent_images.addItem("本次学习的最近截图", None)
        for button in (self.view.enlarge_image, self.view.keep_image, self.view.clear_image):
            button.setEnabled(False)

    def clear(self):
        self.reset()
        self.controller.rebuild()
        self.controller.message("已清除当前截图；最近截图暂存和已保留图片不受影响。")

    def inputs(self, project_id, source_id, topic_id, session_id) -> dict:
        if self.current and (self.current.source_id, self.current.topic_id, self.current.session_id) != (
            source_id, topic_id, session_id
        ):
            if self.current.is_persistent:
                self.reset()
            else:
                self.current = self.store.rebind(self.current.id, project_id, source_id, topic_id, session_id)
        shots = self.store.recent(project_id, source_id, session_id)
        self.view.recent_images.blockSignals(True)
        self.view.recent_images.clear()
        self.view.recent_images.addItem("本次学习的最近截图", None)
        for shot in shots:
            self.view.recent_images.addItem(
                f"{shot.created_at[11:19]} · {'解释' if shot.task_type == 'explain' else '翻译'} · {shot.width}×{shot.height}", shot.id)
        self.view.recent_images.blockSignals(False)
        recent = self.recent.list(project_id, source_id, session_id, limit=2)
        snippets = [f"{r['task_type']}: {r['selected_text']}\n{r['question']}".strip()
                    for r in reversed(recent) if r["selected_text"] or r["question"]]
        return {"current_screenshot": self.current, "recent_screenshots": list(reversed(shots)),
                "recent_context": snippets, "question": self.view.followup.text()}

    def accept(self, image, region, task_type, window):
        controller = self.controller
        try:
            controller.rebuild()  # Ensure current project/source/topic Session exists.
            session = controller.context.session
            shot = self.store.save_image(image, region, task_type,
                self.view.projects.currentData(), self.view.sources.currentData(),
                session["topic_id"], session["id"])
            self.current = shot
            self.task_type = task_type
            self.view.followup.clear()
            self.view.selection.clear()
            controller.window = window
            controller.update_window(window)
            self.view.handoff_panel.hide()
            controller.rebuild()
            if controller.package and self.last_context:
                self.recent.record(self.last_context, task_type)
            self.store.cleanup_temporary(protected_ids=(shot.id,))
            self.render()
            controller.message("截图已就绪。")
            controller.reading.auto_submit()
            self.view.show()
            self.view.raise_()
            self.view.activateWindow()
            logger.info("screenshot captured id=%s width=%d height=%d", shot.id, shot.width, shot.height)
        except (ValueError, OSError, sqlite3.Error) as error:
            controller.message(str(error))

    def render(self):
        if self.current:
            pixmap = QPixmap(str(self.store.path(self.current)))
            self.view.set_image(pixmap)
            self.view.screenshot_info.setText(
                f"{self.current.width} × {self.current.height} · " +
                ("已保留" if self.current.is_persistent else "临时截图 · 最多保留最近 20 张"))
        for button in (self.view.enlarge_image, self.view.keep_image, self.view.clear_image):
            button.setEnabled(self.current is not None and not self.controller.capture_busy)
        task = "explain" if self.view.followup.text().strip() else self.task_type
        self.view.task_label.setText("当前任务 · " + ("解释" if task == "explain" else "翻译"))
        self.view.prepare_button.setEnabled(self.controller.package is not None and not self.controller.capture_busy)

    def prepare(self):
        controller = self.controller
        if controller.capture_busy:
            return
        controller.rebuild()
        if not controller.package:
            return
        try:
            path = self.store.path(self.current) if self.current else None
            self.prepared = controller.integration.prepare(controller.package, path)
            if self.current:
                if not self.copy_image():
                    self.prepared = None
                    self.view.handoff_panel.hide()
                    return
                self.view.handoff_hint.setText(
                    "① 图片已复制：切到 AI 对话，Ctrl+V 附图。\n"
                    "② 回到这里点“复制说明”，再到同一对话 Ctrl+V，确认图片和说明齐全后发送。")
            else:
                controller.copy()
                self.view.handoff_hint.setText("文字说明已复制：切到 AI 对话，粘贴并发送。")
            self.view.copy_image_button.setVisible(self.current is not None)
            self.view.more_toggle.setChecked(True)
            self.view.handoff_panel.show()
            QTimer.singleShot(0, lambda: self.view.scroll.ensureWidgetVisible(self.view.handoff_panel, 0, 12))
            if self.last_context:
                self.recent.record(self.last_context, controller.package.task_type, self.view.followup.text())
        except (ValueError, OSError, sqlite3.Error) as error:
            controller.message(str(error))

    def copy_image(self):
        if not self.current or not self.controller.package:
            return
        try:
            prepared = self.controller.integration.prepare(
                self.controller.package, self.store.path(self.current))
            self.controller.integration.copy_image(prepared, QApplication.clipboard())
            self.controller.message("图片已复制。先粘贴到 AI，再回来复制说明。")
            return True
        except (ValueError, OSError, sqlite3.Error) as error:
            self.controller.message(str(error))

    def keep(self):
        if self.current:
            try:
                self.current = self.store.promote(self.current.id)
                self.controller.rebuild()
                self.controller.message("截图已保留，不会按临时截图策略清理。")
            except (ValueError, OSError, sqlite3.Error) as error:
                self.controller.message(str(error))

    def choose_recent(self, index):
        identifier = self.view.recent_images.itemData(index)
        if identifier:
            self.current = self.store.get(identifier)
            self.task_type = self.current.task_type
            self.view.followup.clear()
            self.view.selection.clear()
            self.view.handoff_panel.hide()
            from studycopilot.capture.active_window import ActiveWindow
            self.controller.window = ActiveWindow()
            self.controller.update_window(self.controller.window)
            self.controller.rebuild()
            self.render()
            self.controller.reading.restore()

    def enlarge(self):
        if not self.current:
            return
        dialog = QDialog(self.view)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.setWindowTitle("当前截图 · 原始像素")
        layout = QVBoxLayout(dialog)
        scroll = QScrollArea()
        label = QLabel()
        label.setPixmap(QPixmap(str(self.store.path(self.current))))
        scroll.setWidget(label)
        layout.addWidget(scroll)
        screen = self.view.screen().availableGeometry()
        dialog.resize(min(1000, screen.width() - 80), min(800, screen.height() - 80))
        self.dialogs.append(dialog)
        dialog.destroyed.connect(lambda: self.dialogs.remove(dialog) if dialog in self.dialogs else None)
        dialog.open()

    def open_ai(self):
        url = "https://chatgpt.com/" if self.view.ai_target.currentText() == "ChatGPT" else "https://claude.ai/"
        QDesktopServices.openUrl(QUrl(url))
