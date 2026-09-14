from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import logging
import sqlite3
import time
from uuid import uuid4

from PySide6.QtCore import QObject, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication

from studycopilot.integrations.reading import format_reading
from studycopilot.context.reading_memory import ReadingContextSnapshot
from studycopilot.memory.database import now
from studycopilot.memory.reading import ReadingStore
from studycopilot.providers.codex import CodexProvider
from studycopilot.providers.reading import ReadingRequest


logger = logging.getLogger(__name__)


class ReadingWorkflow(QObject):
    def __init__(self, controller, provider=None, auto_connect=True):
        super().__init__(controller.view)
        self.controller, self.view, self.db = controller, controller.view, controller.db
        data_dir = controller.visual.store.data_dir
        self.provider = provider or CodexProvider(data_dir / "translation-runtime", self)
        self.store = ReadingStore(self.db)
        self.current_id = None
        self.input_key = None
        self.package = None
        self.snapshot = None
        self.sent = False
        self.completed_id = None
        self.answer = ""
        self.history = []
        self.history_memories = []
        self.last_auto_key = None
        self.last_question = ""
        self.last_task = "translate"
        self.started_at = 0.0
        self.generation_state = "idle"
        self.enabled = self.preference("auto_translate_enabled", "false") == "true"
        self.model = self.preference("reading_model", "")
        self.closed = False
        self._ui_text = ""
        self.wait_phase = "preparing"
        self.wait_timer = QTimer(self)
        self.wait_timer.setInterval(500)
        self.wait_timer.timeout.connect(self.wait_status)
        self.render_timer = QTimer(self)
        self.render_timer.setSingleShot(True)
        self.render_timer.setInterval(65)
        self.render_timer.timeout.connect(self._render)
        self.view.auto_translate.setChecked(self.enabled)
        self.view.auto_translate.toggled.connect(self.toggle)
        self.view.connect_ai.clicked.connect(self.provider.connect_service)
        self.view.login_ai.clicked.connect(self.provider.login)
        self.view.model_choice.currentIndexChanged.connect(self.model_changed)
        self.view.send_question.clicked.connect(self.ask)
        self.view.followup.returnPressed.connect(self.ask)
        self.view.translate_now.clicked.connect(lambda: self.submit())
        self.view.explain_current.clicked.connect(self.explain)
        self.view.retry_translation.clicked.connect(lambda: self.submit(self.last_task))
        self.view.stop_translation.clicked.connect(self.stop)
        self.view.copy_translation.clicked.connect(self.copy)
        self.provider.request_submitted.connect(self.submitted)
        self.provider.request_progress.connect(self.progress)
        self.provider.connection_changed.connect(self.connection)
        self.provider.models_changed.connect(self.models)
        self.provider.text_changed.connect(self.text)
        self.provider.completed.connect(self.complete)
        self.provider.failed.connect(self.fail)
        self.provider.login_url.connect(lambda url: QDesktopServices.openUrl(QUrl(url)))
        self.clear_display()
        self.update_privacy()
        if self.enabled and auto_connect:
            QTimer.singleShot(0, lambda: self.provider.connect_service() if self.enabled and not self.closed else None)

    def preference(self, key, default=""):
        row = self.db.one("SELECT value FROM user_preferences WHERE key=?", (key,))
        return row["value"] if row else default

    def persist(self, key, value):
        self.db.execute("""INSERT INTO user_preferences VALUES (?,?,?,?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at""",
            (str(uuid4()), key, value, now()))

    def toggle(self, enabled):
        self.enabled = enabled
        self.persist("auto_translate_enabled", "true" if enabled else "false")
        self.update_privacy()
        if enabled:
            self.provider.connect_service()
        else:
            self.stop()

    def update_privacy(self):
        self.view.privacy.setText("主动框选即发送所选区域 · 使用订阅额度" if self.enabled
                                  else "仅主动截图 · 自动发送已关闭")
        self.view.auto_notice.setText("开启后，所选截图与当前项目必要上下文会发送给已连接服务。可随时关闭。")

    def model_changed(self):
        value = self.view.model_choice.currentData()
        if value is not None:
            self.model = value
            self.persist("reading_model", value)

    def models(self, items):
        self.view.model_choice.blockSignals(True)
        self.view.model_choice.clear()
        self.view.model_choice.addItem("服务默认视觉模型", "")
        for item in items:
            self.view.model_choice.addItem(item.get("displayName") or item["model"], item["model"])
        index = self.view.model_choice.findData(self.model)
        if index < 0 and self.model:
            self.view.model_choice.addItem(self.model + "（暂不可用）", self.model)
            index = self.view.model_choice.count() - 1
        self.view.model_choice.setCurrentIndex(max(0, index))
        self.view.model_choice.blockSignals(False)

    def connection(self, state, message):
        logger.info("reading connection state=%s", state)
        self.view.connection_info.setText(message)
        if self.current_id and state in {"connecting", "ready"}:
            self.wait_phase = "connecting" if state == "connecting" else "preparing"
            self.wait_status()

    def submitted(self, request_id):
        if request_id == self.current_id and self.key() == self.input_key:
            self.sent = True
            self.show_memory_usage()

    def progress(self, request_id, phase):
        if request_id == self.current_id:
            self.wait_phase = phase
            self.wait_status()

    def wait_status(self):
        if not self.current_id or self.generation_state != "sending":
            self.wait_timer.stop()
            return
        elapsed = int(time.monotonic() - self.started_at)
        label = {"connecting": "正在连接服务", "preparing": "正在准备请求",
                 "waiting": "等待首段译文" if self.last_task == "translate" else "等待首段解释"}
        message = label.get(self.wait_phase, "等待服务响应") + f" · {elapsed} 秒"
        if elapsed >= 10:
            message += " · 服务响应较慢，可等待或停止"
        self.view.result_status.setText(message)

    def key(self):
        c = self.controller
        session = c.context.session
        shot = c.visual.current
        return (self.view.projects.currentData(), self.view.sources.currentData(),
                session["id"] if session else None, shot.id if shot else None,
                self.view.selection.toPlainText())

    def sync(self):
        if self.closed:
            return
        current_key = self.key()
        if self.input_key is not None and current_key != self.input_key:
            self.reset()
        self.input_key = current_key
        has_input = self.controller.package is not None
        self.view.translate_now.setEnabled(has_input and not self.controller.capture_busy and not self.current_id)
        self.view.explain_current.setEnabled(has_input and not self.controller.capture_busy and not self.current_id)
        self.view.send_question.setEnabled(has_input and not self.controller.capture_busy and not self.current_id)

    def auto_submit(self):
        if self.enabled and self.last_auto_key == self.key():
            return
        self.reset()
        self.view.scroll.verticalScrollBar().setValue(0)
        self.input_key = self.key()
        if self.enabled and self.controller.package and self.last_auto_key != self.input_key:
            self.last_auto_key = self.input_key
            self.submit()
        elif self.controller.package:
            self.view.result_status.setText("自动发送已关闭 · 在“更多”中点击“翻译当前内容”")

    def submit(self, task_type=None):
        if self.closed or self.current_id or self.controller.capture_busy:
            return
        c = self.controller
        c.rebuild()
        if not c.package:
            return
        self.input_key = self.key()
        selected = c.package.relevant_memories
        history = []
        for (q, a), memories in zip(self.history[-2:], self.history_memories[-2:]):
            # Do not reintroduce removed/disabled memory through a prior generated answer.
            if all(m in selected for m in memories):
                history.append(f"问题：{q}\n回答：{a[:4000]}")
            else:
                history.append(f"问题：{q}")
        self.package = replace(c.package, recent_context=[
            *c.package.recent_context[-1:], *history
        ][-3:])
        if task_type:
            self.package = replace(self.package, task_type=task_type)
        self.current_id = str(uuid4())
        self.snapshot = ReadingContextSnapshot.from_package(self.current_id, self.package)
        self.sent = False
        self.view.used_memory.setText("本次请求尚未确认发送")
        self.view.used_memory.setEnabled(False)
        self.completed_id = None
        self.last_question = self.package.question
        self.last_task = self.package.task_type
        self.answer = ""
        self._ui_text = ""
        self.started_at = time.monotonic()
        self.generation_state = "sending"
        self.wait_phase = "preparing"
        self.wait_timer.start()
        self.view.result.clear()
        self.view.result_status.setText("正在解释……" if self.package.task_type == "explain" else "正在翻译……")
        self.view.copy_translation.setEnabled(False)
        self.view.stop_translation.setEnabled(True)
        self.view.retry_translation.hide()
        self.view.translate_now.setEnabled(False)
        self.view.send_question.setEnabled(False)
        self.view.explain_current.setEnabled(False)
        try:
            path = c.visual.store.path(c.visual.current) if c.visual.current else None
            request = ReadingRequest(self.current_id, format_reading(self.package), path,
                                     self.package.task_type, self.model)
            self.provider.submit(request)
        except (ValueError, OSError):
            self.fail(self.current_id, "input", "图片准备失败，请重新截图。")

    def ask(self):
        if self.view.followup.text().strip():
            self.submit("explain")
        else:
            self.controller.message("输入问题后按 Enter；Shift+Enter 换行。")

    def explain(self):
        self.submit("explain")

    def text(self, request_id, value):
        if request_id != self.current_id or self.key() != self.input_key:
            return
        self.submitted(request_id)
        self.answer = value
        self._ui_text = value
        self.generation_state = "generating"
        self.view.result_status.setText("译文生成中……" if self.package.task_type == "translate" else "解释生成中……")
        if not self.render_timer.isActive():
            self.render_timer.start()

    def _render(self):
        self.view.result.show_answer(self._ui_text)

    def complete(self, request_id, value, model):
        if request_id != self.current_id or self.key() != self.input_key:
            return
        self.wait_timer.stop()
        self.render_timer.stop()
        self.submitted(request_id)
        self.answer = value
        self._ui_text = value
        self._render()
        self.generation_state = "completed"
        elapsed = time.monotonic() - self.started_at
        self.view.result_status.setText(f"已完成 · {elapsed:.1f} 秒")
        self.view.copy_translation.setEnabled(True)
        self.view.stop_translation.setEnabled(False)
        self.view.retry_translation.hide()
        try:
            self.store.save(request_id, self.package, value, model, self.snapshot)
            self.completed_id = request_id
        except (sqlite3.Error, ValueError):
            self.view.result_status.setText("回答已完成；本地记录未保存。可复制译文或重试保存记忆。")
        self.history.append((self.last_question or self.package.task_type, value))
        self.history = self.history[-2:]
        self.history_memories.append(self.snapshot.memories)
        self.history_memories = self.history_memories[-2:]
        self.current_id = None
        if self.view.followup.text().strip() == self.last_question.strip():
            self.view.followup.clear()
        self.controller.rebuild()
        self.controller.message("已完成，可直接追问或继续截图。")

    def fail(self, request_id, code, message):
        if request_id != self.current_id:
            return
        self.wait_timer.stop()
        self.render_timer.stop()
        if self.answer:
            self._ui_text = self.answer
            self._render()
        self.current_id = None
        self.generation_state = code
        self.view.result_status.setText(("未完成 · " if self.answer else "") + message)
        self.view.stop_translation.setEnabled(False)
        self.view.copy_translation.setEnabled(False)
        self.view.retry_translation.show()
        self.sync()
        self.controller.message(message)

    def stop(self):
        if self.current_id:
            self.current_id = None  # invalidate before any cancellation callback
            self.provider.cancel()
            self.wait_timer.stop()
            self.render_timer.stop()
            self.generation_state = "cancelled"
            self.view.result_status.setText("已停止 · 部分文字尚未完成" if self.answer else "已停止，可重试")
            self.view.stop_translation.setEnabled(False)
            self.view.copy_translation.setEnabled(False)
            self.view.retry_translation.show()
            self.sync()

    def reset(self):
        self.current_id = None
        if getattr(self.provider, "current", None) is not None:
            self.provider.cancel()
        self.wait_timer.stop()
        self.render_timer.stop()
        self.input_key = None
        self.answer = ""
        self.history = []
        self.history_memories = []
        self.package = None
        self.snapshot = None
        self.sent = False
        self.completed_id = None
        self.clear_display()

    def clear_display(self):
        self.generation_state = "idle"
        self.last_question = ""
        self.view.used_memory.setText("尚未发送请求")
        self.view.used_memory.setEnabled(False)
        self.view.result.clear()
        self.view.result_status.setText("框选教材，译文将显示在这里")
        self.view.stop_translation.setEnabled(False)
        self.view.copy_translation.setEnabled(False)
        self.view.retry_translation.hide()

    def restore(self):
        self.reset()
        self.input_key = self.key()
        project, source, session, shot, _ = self.input_key
        saved = self.store.latest(shot, project, source, session)
        if saved:
            self.snapshot = ReadingContextSnapshot.from_json(saved["context_snapshot"])
            self.sent = bool(self.snapshot)
            self.completed_id = saved["id"]
            self.last_question = saved["question"]
            self.last_task = saved["task_type"]
            self.show_memory_usage(historical=True)
            self.answer = saved["answer"]
            self._ui_text = self.answer
            self._render()
            self.generation_state = "completed"
            self.view.copy_translation.setEnabled(True)
            self.view.result_status.setText("最近回答 · " + saved["model"])
            self.history = [(saved["question"] or saved["task_type"], self.answer)]
            # Legacy results lack provenance: do not carry their answers into new requests.
            self.history_memories = [self.snapshot.memories if self.snapshot else [{"legacy": True}]]

    def show_memory_usage(self, historical=False):
        if self.snapshot is None:
            self.view.used_memory.setText("旧回答未记录所用记忆")
            self.view.used_memory.setEnabled(False)
            return
        count = len(self.snapshot.memories)
        self.view.used_memory.setText(
            f"本次使用 {count} 条学习记忆 · 查看来源" if count else "本次未使用历史学习记忆")
        self.view.used_memory.setEnabled(True)
        self.view.used_memory.setToolTip(
            "项目：" + (self.snapshot.project or {}).get("name", "未指定") +
            " · 资料：" + (self.snapshot.source or {}).get("title", "未指定"))

    def copy(self):
        if self.generation_state == "completed" and self.answer:
            QApplication.clipboard().setText(self.answer)
            self.controller.message("译文已复制。")

    def close(self):
        self.closed = True
        self.current_id = None
        self.wait_timer.stop()
        self.render_timer.stop()
        self.provider.close()
