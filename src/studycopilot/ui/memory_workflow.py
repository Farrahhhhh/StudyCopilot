"""Explicit memory actions; sources are displayed locally, never submitted by viewing."""
import json
import re
import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea, QVBoxLayout,
)

from studycopilot.knowledge.concepts import ConceptStore
from .dialogs import MemoryDialog


class MemoryWorkflow:
    def __init__(self, controller):
        self.c, self.v = controller, controller.view
        self.v.manage_memory.clicked.connect(self.manage)
        self.v.select_memory.clicked.connect(self.select)
        self.v.used_memory.clicked.connect(self.used)

    def clear_selection(self):
        self.c.manual_memory_ids = ()
        self.c.memory_concept = ""
        self.v.memory_hint.clear()
        self.v.memory_hint.hide()

    def key(self):
        return (self.v.projects.currentData(), self.v.sources.currentData(),
                (self.c.context.session or {}).get("id"))

    def select(self):
        project_id, source_id, session_id = self.key()
        dialog = QDialog(self.v)
        dialog.setWindowTitle("指定本次相关记忆")
        dialog.resize(440, 450)
        layout = QVBoxLayout(dialog)
        hint = QLabel("仅选择当前项目的待解决记忆；不识别图片、不调用模型。\n选择沿用到同一项目和资料的后续请求，可随时清空。")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        concept = QLineEdit(self.c.memory_concept)
        concept.setMaxLength(200)
        concept.setPlaceholderText("可选：当前图片的概念，例如跨导／gm")
        layout.addWidget(concept)
        items = QListWidget()
        for memory in self.c.memory.list_project(project_id):
            if memory["status"] != "pending":
                continue
            item = QListWidgetItem(memory["content"][:100])
            item.setData(Qt.ItemDataRole.UserRole, memory["id"])
            item.setToolTip(memory["content"])
            item.setCheckState(Qt.CheckState.Checked if memory["id"] in self.c.manual_memory_ids
                               else Qt.CheckState.Unchecked)
            items.addItem(item)
        layout.addWidget(items)
        clear = QPushButton("清空指定")
        clear.clicked.connect(lambda: (concept.clear(), [
            items.item(i).setCheckState(Qt.CheckState.Unchecked) for i in range(items.count())]))
        layout.addWidget(clear)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted and self.key() == (project_id, source_id, session_id):
            self.c.memory_concept = concept.text().strip()
            self.c.manual_memory_ids = tuple(items.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(items.count()) if items.item(i).checkState() == Qt.CheckState.Checked)
            self.v.memory_hint.setText(f"已指定 {len(self.c.manual_memory_ids)} 条 · 概念：{self.c.memory_concept or '未填写'}")
            self.v.memory_hint.setVisible(bool(self.c.manual_memory_ids or self.c.memory_concept))
            self.c.rebuild()

    def edit(self, item=None, dialog_class=MemoryDialog):
        c, v = self.c, self.v
        key = self.key()
        project_id, source_id, _ = key
        if item:
            item = c.memory.get_project(item["id"], project_id)
        concepts = list(c.package.related_concepts) if c.package else []
        seen = {x["id"] for x in concepts}
        concepts += [x for x in ConceptStore(c.db).list_all() if x["id"] not in seen]
        shot = c.visual.current if not item else None
        screenshot = False
        if shot:
            try:
                screenshot = c.visual.store.path(shot).is_file()
            except ValueError:
                pass
        dialog = dialog_class(concepts, v, screenshot=screenshot)
        dialog.project_label.setText(v.projects.currentText())
        dialog.project_label.setTextFormat(Qt.TextFormat.PlainText)
        # This action always saves to the current project; legacy store scopes remain readable.
        dialog.scope.setCurrentIndex(0)
        dialog.scope.setEnabled(False)
        selected = v.result.textCursor().selectedText().replace(" ", "\n")
        draft = v.followup.text().strip()
        reading = c.reading
        result_id = reading.completed_id if reading and not draft else None
        if item:
            dialog.content.setPlainText(item["content"])
            dialog.concept.setCurrentIndex(max(0, dialog.concept.findData(item["concept_id"])))
            dialog.status.setCurrentIndex(dialog.status.findData(item["status"]))
            dialog.source_location.setText(json.loads(item["source_snapshot"]).get("location", ""))
            dialog.timestamps.setText(f"创建：{item['created_at']}\n更新：{item['updated_at']}")
        else:
            text = selected or draft or (reading.last_question if reading else "") or v.selection.toPlainText()
            dialog.content.setPlainText(text[:2000])
            dialog.timestamps.setText("只保存你确认的内容；不会调用模型总结。")
        while dialog.exec() == QDialog.DialogCode.Accepted:
            if key != self.key():
                c.message("项目、资料或会话已改变，请在新位置重新保存。")
                return False
            try:
                content = dialog.content.toPlainText().strip()
                if not content or len(content) > 2000:
                    raise ValueError("记忆正文请输入 1–2000 个字符。")
                aliases = tuple(a.strip() for a in re.split("[,，;；]", dialog.aliases.text()) if a.strip())
                if any(len(a) > 200 for a in aliases):
                    raise ValueError("每个别名最多 200 个字符。")
                concept_id = dialog.concept.currentData()
                name = dialog.concept_name.text().strip()
                if aliases and not name and not concept_id:
                    raise ValueError("填写别名时请指定概念。")
                concepts_store = ConceptStore(c.db)
                if name:
                    existing = concepts_store.find_name(name)
                    concept_id = existing["id"] if existing else concepts_store.create(name)["id"]
                for alias in aliases:
                    concepts_store.add_alias(concept_id, alias)
                if item:
                    c.memory.update(item["id"], project_id, content, dialog.status.currentData(),
                                    concept_id, dialog.source_location.text())
                else:
                    # A completed source may have been pruned while the dialog was open.
                    existing_result = c.reading.store.get(result_id, project_id)
                    c.memory.save(content, project_id=project_id, source_id=source_id,
                        concept_id=concept_id, memory_type="question", status=dialog.status.currentData(),
                        screenshot_id=shot.id if screenshot and dialog.attach_screenshot.isChecked() else None,
                        reading_result_id=result_id if existing_result else None,
                        source_snapshot={"title": v.sources.currentText() if source_id else "",
                                         "location": dialog.source_location.text(),
                                         "reading_result_id": result_id})
                if c.visual.current:
                    c.visual.current = c.visual.store.get(c.visual.current.id)
                c.rebuild()
                c.message("疑问已保存在当前项目，可在“项目记忆”中查看和修改。")
                return True
            except (ValueError, OSError, sqlite3.Error) as error:
                c.show_error(error)
        return False

    def manage(self):
        project_id = self.v.projects.currentData()
        dialog = QDialog(self.v)
        dialog.setWindowTitle("项目记忆 · " + self.v.projects.currentText())
        dialog.resize(500, 550)
        layout = QVBoxLayout(dialog)
        items = QListWidget()
        detail = QPlainTextEdit()
        detail.setReadOnly(True)
        layout.addWidget(items)
        layout.addWidget(detail)
        def selected():
            current = items.currentItem()
            return self.c.memory.get_project(current.data(Qt.ItemDataRole.UserRole), project_id) if current else None
        def refresh():
            items.clear()
            for memory in self.c.memory.list_project(project_id):
                row = QListWidgetItem(("待解决" if memory["status"] == "pending" else "已解决") + " · " + memory["content"][:90])
                row.setData(Qt.ItemDataRole.UserRole, memory["id"])
                items.addItem(row)
            if items.count():
                items.setCurrentRow(0)
            else:
                detail.setPlainText("当前项目还没有学习记忆。")
        def show():
            item = selected()
            if item:
                concepts = ConceptStore(self.c.db)
                concept = concepts.get(item["concept_id"]) if item["concept_id"] else None
                aliases = concepts.aliases(item["concept_id"])
                detail.setPlainText(item["content"] + "\n\n概念：" + (concept or {}).get("canonical_name", "未指定")
                    + "\n别名：" + "、".join(aliases)
                    + f"\n创建：{item['created_at']}\n更新：{item['updated_at']}")
        items.currentRowChanged.connect(show)
        actions = QHBoxLayout()
        def perform(action):
            try:
                item = selected()
                if not item or project_id != self.v.projects.currentData():
                    return
                if action == "edit":
                    self.edit(item)
                elif action == "resolve":
                    self.c.memory.update(item["id"], project_id, item["content"],
                        "resolved" if item["status"] == "pending" else "pending", item["concept_id"])
                elif action == "delete":
                    if QMessageBox.question(dialog, "删除学习记忆", "删除这条记忆？原阅读记录和已保留截图会保留。") != QMessageBox.StandardButton.Yes:
                        return
                    self.c.memory.delete(item["id"], project_id)
                else:
                    self.show_source(self.c.memory.source(item), project_id, dialog)
                    return
                self.c.rebuild()
                refresh()
            except (ValueError, sqlite3.Error) as error:
                self.c.show_error(error)
        for label, action in [("编辑", "edit"), ("解决／重新打开", "resolve"), ("查看来源", "source"), ("删除", "delete")]:
            button = QPushButton(label)
            button.clicked.connect(lambda checked=False, a=action: perform(a))
            actions.addWidget(button)
        layout.addLayout(actions)
        refresh()
        dialog.exec()

    def used(self):
        snapshot = self.c.reading.snapshot
        if snapshot is None or not self.c.reading.sent:
            return
        dialog = QDialog(self.v)
        dialog.setWindowTitle("本次请求的学习记忆")
        dialog.resize(500, 520)
        layout = QVBoxLayout(dialog)
        text = QPlainTextEdit()
        text.setReadOnly(True)
        entries = [f"项目：{(snapshot.project or {}).get('name', '未指定')}",
                   f"资料：{(snapshot.source or {}).get('title', '未指定')}",
                   "以下是本次发送时的记忆内容；后续编辑不会改写此记录。"]
        for index, item in enumerate(snapshot.memories, 1):
            source = item.get("source", {})
            entries.append(f"\n{index}. {item['content']}\n概念：{item.get('concept', '')}\n来源："
                           + (source.get("title") or "未指定资料") + " " + source.get("location", ""))
        if not snapshot.memories:
            entries.append("\n本次未使用历史学习记忆")
        text.setPlainText("\n".join(entries))
        layout.addWidget(text)
        for index, item in enumerate(snapshot.memories, 1):
            button = QPushButton(f"查看第 {index} 条的现存来源")
            button.clicked.connect(lambda checked=False, source=item.get("source", {}):
                self.show_source(source, (snapshot.project or {}).get("id"), dialog))
            layout.addWidget(button)
        dialog.exec()

    def show_source(self, source, project_id, parent=None):
        if project_id != self.v.projects.currentData():
            self.c.message("项目已切换，请从当前项目重新查看来源。")
            return
        dialog = QDialog(parent or self.v)
        dialog.setWindowTitle("记忆来源 · 本地查看")
        dialog.resize(580, 600)
        layout = QVBoxLayout(dialog)
        text = QPlainTextEdit()
        text.setReadOnly(True)
        lines = ["资料：" + (source.get("title") or "未指定"),
                 "页码／章节：" + (source.get("location") or "未知")]
        identifier = source.get("reading_result_id") or source.get("original_reading_id")
        result = self.c.reading.store.get(identifier, project_id)
        if result:
            lines += ["来源问题：" + (result["question"] or "截图" + result["task_type"]),
                      "来源回答：\n" + result["answer"]]
        else:
            lines.append("阅读来源未关联、已清理或缺失；记忆正文仍可使用。")
        text.setPlainText("\n\n".join(lines))
        layout.addWidget(text)
        for identifier in source.get("screenshot_ids", []):
            try:
                shot = self.c.visual.store.get(identifier)
                if shot.project_id != project_id:
                    continue
                pixmap = QPixmap(str(self.c.visual.store.path(shot)))
                if pixmap.isNull():
                    raise ValueError("missing")
                image = QLabel()
                image.setPixmap(pixmap)
                scroll = QScrollArea()
                scroll.setWidget(image)
                layout.addWidget(scroll)
            except (ValueError, OSError):
                layout.addWidget(QLabel("原始截图缺失；记忆正文仍可使用。"))
        if not source.get("screenshot_ids"):
            layout.addWidget(QLabel("未关联现存截图。"))
        dialog.exec()
