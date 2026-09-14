import json
import sqlite3
from dataclasses import replace
from uuid import uuid4

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QListWidget, QPlainTextEdit, QMessageBox, QScrollArea

from test_reading import reading, capture, FakeProvider
from studycopilot.context.manager import ContextManager
from studycopilot.context.models import StudyContext
from studycopilot.context.reading_memory import MAX_MEMORIES, MAX_MEMORY_CHARS, ReadingContextSnapshot
from studycopilot.integrations.reading import format_reading
from studycopilot.knowledge.concepts import ConceptStore
from studycopilot.memory.database import Database
from studycopilot.memory.migrations import MIGRATIONS, SCHEMA_VERSION
from studycopilot.memory.retrieval import FTSMemoryRetriever
from studycopilot.memory.store import MemoryStore
from studycopilot.projects.manager import ProjectManager
from studycopilot.ui.controller import SidebarController
from studycopilot.ui.dialogs import MemoryDialog
from studycopilot.ui.sidebar import Sidebar


def build(db, project, query, **kwargs):
    return ContextManager(db, FTSMemoryRetriever(db)).build(StudyContext(
        selected_text=query, project_id=project["id"], strict_project_memory=True, **kwargs))


def payload(request):
    return json.loads(request.prompt.split("资料数据：", 1)[1])


def wire_memories(memories):
    return [{"content": m["content"], "concept": m.get("concept", ""),
             "status": m.get("status", "pending"),
             "source": {k: m.get("source", {}).get(k, "") for k in ("title", "location")}}
            for m in memories]


def test_relevant_alias_unrelated_and_project_only(db, project, memories):
    concept = ConceptStore(db).create("transconductance", chinese_name="跨导", aliases=("gm",))
    item = memories.save("跨导的单位怎么得到？", project_id=project["id"], concept_id=concept["id"])
    other = ProjectManager(db).create_project("另一个项目")
    memories.save("同名概念的私密问题", project_id=other["id"], concept_id=concept["id"])
    memories.save("gm global private", scope="global", concept_id=concept["id"])
    assert [m["id"] for m in build(db, project, "gm 是什么").relevant_memories] == [item["id"]]
    assert build(db, project, "如何求傅里叶变换").relevant_memories == []
    assert build(db, project, "为什么这个问题仍不理解").relevant_memories == []
    assert [m["content"] for m in build(db, other, "gm 是什么").relevant_memories] == ["同名概念的私密问题"]


def test_content_retrieval_without_registered_concept(db, project, memories):
    item = memories.save("负反馈为什么使电路稳定？", project_id=project["id"])
    assert build(db, project, "这里的负反馈方向？").relevant_memories[0]["id"] == item["id"]
    assert not build(db, project, "为什么这个电路没有输出？").relevant_memories


def test_edits_status_delete_affect_next_context_and_fts(db, project, memories):
    item = memories.save("transconductance 疑问", project_id=project["id"])
    assert build(db, project, "transconductance").relevant_memories
    memories.update(item["id"], project["id"], "capacitance 疑问", "pending")
    assert not build(db, project, "transconductance").relevant_memories
    assert build(db, project, "capacitance").relevant_memories
    memories.update(item["id"], project["id"], "capacitance 疑问", "resolved")
    assert not build(db, project, "capacitance", manual_memory_ids=(item["id"],)).relevant_memories
    memories.update(item["id"], project["id"], "capacitance 疑问", "pending")
    assert build(db, project, "capacitance").relevant_memories
    memories.delete(item["id"], project["id"])
    assert not build(db, project, "capacitance").relevant_memories
    assert not FTSMemoryRetriever(db).search("capacitance", project["id"])


def test_disabled_has_no_long_term_memory_but_keeps_question(db, project, memories):
    item = memories.save("长期记忆独有字符串", project_id=project["id"])
    memories.save("私人学习习惯独有字符串", scope="user")
    package = build(db, project, "current text", question="当前疑问",
                    recent_context=["本图的正常上下文"], use_project_memory=False,
                    manual_memory_ids=(item["id"],))
    text = format_reading(package)
    assert "长期记忆独有字符串" not in text and "私人学习习惯独有字符串" not in text
    assert "当前疑问" in text and "本图的正常上下文" in text


def test_count_and_serialized_length_bounded_without_partial_memory(db, project, memories):
    for i in range(8):
        memories.save(f"transconductance {i}", project_id=project["id"])
    selected = build(db, project, "transconductance").relevant_memories
    assert len(selected) == MAX_MEMORIES
    for item in memories.list_project(project["id"]):
        memories.update(item["id"], project["id"], "transconductance " + "正文" * 950, "pending")
    selected = build(db, project, "transconductance").relevant_memories
    assert 0 < len(selected) < MAX_MEMORIES
    assert len(json.dumps(selected, ensure_ascii=False, separators=(",", ":"))) <= MAX_MEMORY_CHARS
    assert all(m["content"].endswith("正文") and len(m["content"]) > 1900 for m in selected)


def test_manual_screenshot_selection_no_extra_model_call(reading, db, monkeypatch):
    v, c, p = reading
    item = c.memory.save("手动指定的疑问", project_id=v.projects.currentData())
    other = ProjectManager(db).create_project("other")
    foreign = c.memory.save("外项目秘密", project_id=other["id"])
    capture(c)
    assert not c.package.relevant_memories
    def select_dialog(dialog):
        assert dialog.windowTitle() == "指定本次相关记忆"
        rows = dialog.findChild(QListWidget)
        assert rows.count() == 1
        rows.item(0).setCheckState(Qt.CheckState.Checked)
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(QDialog, "exec", select_dialog)
    v.select_memory.click()
    assert not p.requests
    assert c.manual_memory_ids == (item["id"],)
    c.manual_memory_ids += (foreign["id"], "deleted")
    v.translate_now.click()
    assert len(p.requests) == 1
    assert [m["content"] for m in payload(p.current)["相关记忆"]] == [item["content"]]
    assert "外项目秘密" not in p.current.prompt


def test_screenshot_concept_hint_without_recognition(reading, db):
    v, c, p = reading
    concept = ConceptStore(db).create("transconductance", aliases=("gm",))
    item = c.memory.save("概念关联疑问", project_id=v.projects.currentData(), concept_id=concept["id"])
    capture(c)
    c.memory_concept = "gm"
    v.translate_now.click()
    assert len(p.requests) == 1
    assert payload(p.current)["相关记忆"][0]["content"] == item["content"]


def test_sent_snapshot_survives_edits_and_restores_exactly(reading, db, monkeypatch):
    v, c, p = reading
    source = ProjectManager(db).create_source(v.projects.currentData(), "原教材")
    c.refresh_sources(source["id"])
    c.source_changed()
    item = c.memory.save("transconductance 原疑问", project_id=v.projects.currentData(), source_id=source["id"],
                         source_snapshot={"location": "第 7 页"})
    capture(c)
    v.followup.setText("transconductance")
    v.send_question.click()
    request = p.current
    expected = c.reading.snapshot.to_json()
    assert payload(request)["相关记忆"] == wire_memories(c.reading.snapshot.memories)
    assert "1 条" in v.used_memory.text()
    c.memory.update(item["id"], v.projects.currentData(), "编辑后独有字符串", "resolved")
    c.rebuild()
    assert c.reading.snapshot.to_json() == expected
    assert not c.package.relevant_memories
    p.finish("正常回答")
    assert db.one("SELECT context_snapshot FROM reading_results")["context_snapshot"] == expected
    c.reading.restore()
    assert c.reading.snapshot.to_json() == expected
    def inspect(dialog):
        detail = dialog.findChild(QPlainTextEdit).toPlainText()
        assert item["content"] in detail and "编辑后独有字符串" not in detail
        assert "原教材" in detail and "第 7 页" in detail
        return QDialog.DialogCode.Rejected
    monkeypatch.setattr(QDialog, "exec", inspect)
    v.used_memory.click()
    assert len(p.requests) == 1


def test_switch_memory_off_filters_memory_bearing_previous_answer(reading):
    v, c, p = reading
    item = c.memory.save("transconductance 只应本次携带", project_id=v.projects.currentData())
    capture(c)
    v.followup.setText("transconductance")
    v.send_question.click()
    p.finish("引用此前记忆：" + item["content"])
    v.use_memory.setChecked(False)
    v.followup.setText("请解释单位")
    v.send_question.click()
    assert item["content"] not in p.current.prompt
    assert "请解释单位" in p.current.prompt
    assert "相关记忆" not in payload(p.current)
    assert v.used_memory.text() == "本次未使用历史学习记忆"


@pytest.mark.parametrize("action", ["project", "source", "session"])
def test_pending_request_scope_change_clears_memory_snapshot(reading, db, action):
    v, c, p = reading
    item = c.memory.save("transconductance secret", project_id=v.projects.currentData())
    capture(c)
    v.followup.setText("transconductance")
    v.send_question.click()
    old = p.current.id
    if action == "project":
        other = ProjectManager(db).create_project("新项目")
        c.refresh_projects(other["id"])
    elif action == "source":
        source = ProjectManager(db).create_source(v.projects.currentData(), "新资料")
        c.refresh_sources(source["id"])
        c.source_changed()
    else:
        c.context.end_session()
        c.rebuild()
    p.completed.emit(old, "STALE", "test")
    p.text_changed.emit(old, "STALE")
    assert not v.result.toPlainText()
    assert c.reading.snapshot is None
    assert v.used_memory.text() == "尚未发送请求"
    assert not db.all("SELECT * FROM reading_results")
    assert c.memory.get_project(item["id"], item["project_id"])


def test_save_question_from_answer_then_restart_view_and_edit(reading, db, qapp, monkeypatch):
    v, c, p = reading
    capture(c)
    v.followup.setText("为什么跨导的单位是西门子？")
    v.send_question.click()
    p.finish("测试回答，不自动保存")
    saved_question = c.reading.last_question
    def save(dialog):
        assert dialog.content.toPlainText() == saved_question
        assert not dialog.scope.isEnabled()
        dialog.concept_name.setText("跨导")
        dialog.aliases.setText("gm, transconductance")
        dialog.source_location.setText("第 9 页")
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(MemoryDialog, "exec", save)
    v.save_memory.click()
    item = c.memory.list_project(v.projects.currentData())[0]
    assert item["reading_result_id"] == c.reading.completed_id
    assert c.visual.current.is_persistent
    project_id = item["project_id"]
    path = db.connection.execute("PRAGMA database_list").fetchone()[2]
    v.close()
    db.close()
    restarted_db = Database(path)
    view = Sidebar()
    restarted = SidebarController(view, restarted_db, FakeProvider(), auto_connect=False)
    restarted.refresh_projects(project_id)
    try:
        persisted = restarted.memory.get_project(item["id"], project_id)
        assert persisted["content"] == saved_question
        def edit(dialog):
            assert dialog.content.toPlainText() == saved_question
            assert "创建" in dialog.timestamps.text()
            dialog.content.setPlainText("编辑后的跨导问题")
            dialog.status.setCurrentIndex(1)
            return QDialog.DialogCode.Accepted
        monkeypatch.setattr(MemoryDialog, "exec", edit)
        restarted.memory_ui.edit(persisted)
        updated = restarted.memory.get_project(item["id"], project_id)
        assert updated["content"] == "编辑后的跨导问题" and updated["status"] == "resolved"
        assert updated["created_at"] == persisted["created_at"]
        assert restarted_db.one("SELECT id FROM reading_results WHERE id=?", (item["reading_result_id"],))
    finally:
        view.close()
        restarted_db.close()


def test_history_pruning_and_missing_screenshot_preserve_memory(reading, db, monkeypatch):
    v, c, p = reading
    capture(c)
    v.translate_now.click()
    p.finish("原始回答")
    result_id = c.reading.completed_id
    shot = c.visual.current
    item = c.memory.save("transconductance 疑问", project_id=v.projects.currentData(),
        screenshot_id=shot.id, reading_result_id=result_id,
        source_snapshot={"reading_result_id": result_id, "location": "用户填写章节"})
    for i in range(61):
        c.reading.store.save(str(uuid4()), c.package, str(i), "mock")
    item = c.memory.get_project(item["id"], v.projects.currentData())
    assert item["reading_result_id"] is None
    assert not db.connection.execute("PRAGMA foreign_key_check").fetchall()
    assert c.memory.source(item)["original_reading_id"] == result_id
    c.visual.store.path(shot).unlink()
    source = c.memory.source(item)
    def inspect(dialog):
        assert "已清理或缺失" in dialog.findChild(QPlainTextEdit).toPlainText()
        from PySide6.QtWidgets import QLabel
        assert any("截图缺失" in label.text() for label in dialog.findChildren(QLabel))
        return QDialog.DialogCode.Rejected
    monkeypatch.setattr(QDialog, "exec", inspect)
    c.memory_ui.show_source(source, v.projects.currentData())
    c.manual_memory_ids = (item["id"],)
    c.rebuild()
    assert c.package.relevant_memories[0]["content"] == item["content"]
    c.memory.delete(item["id"], v.projects.currentData())
    assert len(db.all("SELECT * FROM reading_results")) == 60
    assert db.one("SELECT is_persistent FROM screenshots WHERE id=?", (shot.id,))["is_persistent"]


def test_management_delete_and_resolution_leave_history(reading, db, monkeypatch):
    v, c, p = reading
    capture(c)
    v.translate_now.click()
    p.finish("阅读记录")
    item = c.memory.save("手动管理问题", project_id=v.projects.currentData())
    from PySide6.QtWidgets import QPushButton
    def inspect(dialog):
        assert dialog.findChild(QListWidget).count() == 1
        buttons = {b.text(): b for b in dialog.findChildren(QPushButton)}
        buttons["解决／重新打开"].click()
        assert c.memory.get_project(item["id"], v.projects.currentData())["status"] == "resolved"
        buttons["删除"].click()
        assert not c.memory.list_project(v.projects.currentData())
        return QDialog.DialogCode.Rejected
    monkeypatch.setattr(QDialog, "exec", inspect)
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Yes)
    v.manage_memory.click()
    assert len(db.all("SELECT * FROM reading_results")) == 1


def test_old_v3_database_upgrade_preserves_all_old_rows(tmp_path):
    path = tmp_path / "study.db"
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript("".join(MIGRATIONS[i] for i in (1, 2, 3)) + "PRAGMA user_version=3;")
    conn.execute("INSERT INTO projects VALUES ('p','旧项目','','before','before')")
    conn.execute("INSERT INTO memories VALUES ('m','project','p',NULL,NULL,'note','旧记忆','旧记忆',1,'before','before')")
    conn.execute("INSERT INTO translation_history VALUES ('t','p',NULL,NULL,NULL,'old text','old translation','[]',NULL,'before')")
    conn.execute("INSERT INTO reading_results VALUES ('r',NULL,'p',NULL,NULL,'explain','旧问题','旧回答','mock','before')")
    conn.commit()
    tables = ("projects", "memories", "translation_history", "reading_results")
    before = {t: conn.execute("SELECT * FROM " + t).fetchall() for t in tables}
    conn.close()
    db = Database(path)
    for table in tables:
        rows = db.connection.execute("SELECT * FROM " + table).fetchall()
        assert [tuple(row)[:len(before[table][0])] for row in rows] == before[table]
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    assert not db.connection.execute("PRAGMA foreign_key_check").fetchall()
    assert db.one("SELECT context_snapshot FROM reading_results")["context_snapshot"] == ""
    db.close()
    backup = sqlite3.connect(next((tmp_path / "backups").glob("study-v3-*.db")))
    assert backup.execute("PRAGMA user_version").fetchone()[0] == 3
    assert backup.execute("SELECT content FROM memories").fetchone()[0] == "旧记忆"
    backup.close()


def test_v4_failed_migration_rolls_back(tmp_path, monkeypatch):
    path = tmp_path / "study.db"
    conn = sqlite3.connect(path)
    conn.executescript("".join(MIGRATIONS[i] for i in (1, 2, 3)) + "PRAGMA user_version=3;")
    conn.close()
    monkeypatch.setitem(MIGRATIONS, 4, "ALTER TABLE memories ADD COLUMN partial TEXT; INVALID SQL;")
    with pytest.raises(sqlite3.Error):
        Database(path)
    conn = sqlite3.connect(path)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 3
    assert "partial" not in [row[1] for row in conn.execute("PRAGMA table_info(memories)")]
    conn.close()


def test_pre_submission_failure_never_claims_memory_used(reading, monkeypatch):
    v, c, p = reading
    c.memory.save("transconductance draft", project_id=v.projects.currentData())
    capture(c)
    def pending(request):
        p.current = request
        p.requests.append(request)
    monkeypatch.setattr(p, "submit", pending)
    v.followup.setText("transconductance")
    v.send_question.click()
    assert not v.used_memory.isEnabled()
    assert v.used_memory.text() == "本次请求尚未确认发送"
    p.failed.emit(p.current.id, "needs_login", "请登录")
    assert not v.used_memory.isEnabled()
    assert not c.reading.sent


def test_pending_selection_not_crowded_out_by_resolved_rows(db, project, memories):
    for i in range(25):
        memories.save(f"transconductance old {i}", project_id=project["id"], status="resolved", importance=5)
    pending = memories.save("transconductance remaining", project_id=project["id"])
    assert [m["id"] for m in build(db, project, "transconductance").relevant_memories] == [pending["id"]]


def test_generic_single_english_word_is_not_reliable(db, project, memories):
    memories.save("negative feedback response", project_id=project["id"])
    assert not build(db, project, "negative voltage supply").relevant_memories


def test_wrong_project_memory_mutations_rejected(db, project, memories):
    item = memories.save("private", project_id=project["id"])
    other = ProjectManager(db).create_project("Other")
    with pytest.raises(ValueError):
        memories.update(item["id"], other["id"], "changed", "resolved")
    with pytest.raises(ValueError):
        memories.delete(item["id"], other["id"])
    assert memories.get_project(item["id"], project["id"])["content"] == "private"


def test_empty_legacy_snapshot_not_replaced_with_current_candidates(reading, db):
    v, c, p = reading
    capture(c)
    c.reading.store.save("legacy", c.package, "历史回答", "old")
    item = c.memory.save("新存的疑问", project_id=v.projects.currentData())
    c.manual_memory_ids = (item["id"],)
    c.rebuild()
    c.reading.restore()
    assert v.used_memory.text() == "旧回答未记录所用记忆"
    assert c.reading.snapshot is None
    assert not p.requests


def test_provenance_result_deleted_by_temporary_screenshot_cleanup(reading, db):
    v, c, p = reading
    first = capture(c)
    v.translate_now.click()
    p.finish("来源回答")
    old_id = c.reading.completed_id
    item = c.memory.save("transconductance question", project_id=v.projects.currentData(),
        reading_result_id=old_id, source_snapshot={"reading_result_id": old_id})
    capture(c)
    c.visual.store.cleanup_temporary(keep=1)
    assert not db.one("SELECT id FROM screenshots WHERE id=?", (first,))
    kept = c.memory.get_project(item["id"], v.projects.currentData())
    assert kept["reading_result_id"] is None
    assert not db.connection.execute("PRAGMA foreign_key_check").fetchall()
    assert build(db, {"id": v.projects.currentData()}, "transconductance").relevant_memories


def test_snapshot_store_and_ui_do_not_follow_memory_deletion(reading, db):
    v, c, p = reading
    item = c.memory.save("transconductance question", project_id=v.projects.currentData())
    capture(c)
    v.followup.setText("transconductance")
    v.send_question.click()
    expected = c.reading.snapshot.to_json()
    p.finish("回答")
    c.memory.delete(item["id"], v.projects.currentData())
    c.rebuild()
    c.reading.restore()
    assert c.reading.snapshot.to_json() == expected
    v.followup.setText("transconductance")
    v.send_question.click()
    assert "相关记忆" not in payload(p.current)


def test_offline_source_view_has_no_model_request(reading, monkeypatch):
    v, c, p = reading
    capture(c)
    v.translate_now.click()
    p.finish("原始模拟回答")
    item = c.memory.save("疑问", project_id=v.projects.currentData(), screenshot_id=c.visual.current.id,
                         reading_result_id=c.reading.completed_id)
    before = len(p.requests)
    def inspect(dialog):
        assert "原始模拟回答" in dialog.findChild(QPlainTextEdit).toPlainText()
        assert dialog.findChildren(QScrollArea)
        return QDialog.DialogCode.Rejected
    monkeypatch.setattr(QDialog, "exec", inspect)
    c.memory_ui.show_source(c.memory.source(item), v.projects.currentData())
    assert len(p.requests) == before
