from dataclasses import replace
from datetime import datetime, timezone
import json
import re
import sqlite3

import pytest
from PySide6.QtGui import QColor, QImage

from studycopilot.context.manager import ContextManager
from studycopilot.context.models import StudyContext
from studycopilot.context.recent import RecentContextStore
from studycopilot.context.screenshot import ScreenshotContext
from studycopilot.integrations.fallback import ClipboardIntegration
from studycopilot.memory.database import Database
from studycopilot.memory.migrations import MIGRATIONS
from studycopilot.memory.retrieval import FTSMemoryRetriever
from studycopilot.memory.screenshots import ScreenshotStore, screenshot_filename
from studycopilot.memory.store import MemoryStore
from studycopilot.projects.manager import ProjectManager


@pytest.fixture
def pixels():
    image = QImage(240, 160, QImage.Format.Format_RGB32)
    image.fill(QColor("#13579b"))
    return image


@pytest.fixture
def visual(db, project, pixels):
    manager = ContextManager(db, FTSMemoryRetriever(db))
    source = ProjectManager(db).create_source(project["id"], "Microelectronic Circuits", "book")
    session = manager.ensure_session(project["id"], source["id"])
    store = ScreenshotStore(db)
    shot = store.save_image(pixels, (-600, 40, 160, 107), "translate",
                            project["id"], source["id"], None, session["id"])
    context = StudyContext(selected_text=None, project_id=project["id"], source_id=source["id"],
                           session_id=session["id"], current_screenshot=shot)
    return manager, store, shot, context


def test_metadata_roundtrip_and_unique_relative_path(visual):
    _, store, shot, _ = visual
    assert store.get(shot.id) == shot
    assert shot.screen_region == (-600, 40, 160, 107)
    assert re.fullmatch(r"screenshots/\d{8}_\d{6}_[a-f0-9]{32}\.png", shot.file_path)
    assert store.path(shot).is_file()
    image = QImage(str(store.path(shot)))
    assert (image.width(), image.height()) == (240, 160)
    assert image.pixelColor(50, 50) == QColor("#13579b")
    assert screenshot_filename("a-b", datetime(2026, 9, 10, tzinfo=timezone.utc)) == "20260910_000000_ab.png"


@pytest.mark.parametrize("change", [{"width": 0}, {"height": -1}, {"screen_region": (0, 0, 0, 10)},
                                    {"task_type": "summarize"}])
def test_invalid_metadata(visual, change):
    with pytest.raises(ValueError):
        replace(visual[2], **change)


@pytest.mark.parametrize("text", [None, "", "Source degeneration"])
def test_visual_package_without_text_or_with_text(visual, text):
    manager, _, shot, context = visual
    package = manager.build(replace(context, selected_text=text))
    payload = json.loads(package.to_json())
    assert payload["selected_text"] == (text or "")
    assert payload["current_screenshot"]["id"] == shot.id
    assert payload["attachments"][0]["media_type"] == "image/png"
    assert payload["attachments"][0]["width"] == 240
    assert "image_url" not in payload["attachments"][0]
    assert payload["session"]["id"] == context.session_id


@pytest.mark.parametrize("project_present", [False, True])
def test_partial_project_and_source_context(db, project, pixels, project_present):
    store = ScreenshotStore(db)
    pid = project["id"] if project_present else None
    shot = store.save_image(pixels, (0, 0, 240, 160), project_id=pid)
    package = ContextManager(db, FTSMemoryRetriever(db)).build(
        StudyContext(project_id=pid, current_screenshot=shot))
    assert package.source is None
    assert bool(package.project) == project_present


def test_unknown_owner_rejected_without_orphan_file(db, pixels, tmp_path):
    store = ScreenshotStore(db)
    with pytest.raises(ValueError):
        store.save_image(pixels, (0, 0, 240, 160), project_id="missing")
    assert not list(tmp_path.rglob("*.png"))


def test_cross_project_visual_context_rejected(visual, db):
    manager, store, shot, context = visual
    other = ProjectManager(db).create_project("Unrelated")
    with pytest.raises(ValueError):
        manager.build(replace(context, project_id=other["id"]))
    with pytest.raises(ValueError):
        store.rebind(shot.id, other["id"], None, None, None)


def test_file_boundary_and_failed_save_cleanup(visual, pixels, monkeypatch):
    _, store, shot, _ = visual
    with pytest.raises(ValueError):
        store.path(replace(shot, file_path="../outside.png"))
    original = list(store.directory.iterdir())
    monkeypatch.setattr(store.db, "execute", lambda *a: (_ for _ in ()).throw(sqlite3.OperationalError("full")))
    with pytest.raises(sqlite3.Error):
        store.save_image(pixels, (0, 0, 240, 160))
    assert list(store.directory.iterdir()) == original


def test_temp_cleanup_protects_persistent_memory_and_current(visual, pixels):
    _, store, shot, context = visual
    memory = MemoryStore(store.db).save("跨导需要结合图理解", project_id=context.project_id,
                                        screenshot_id=shot.id)
    persistent = store.save_image(pixels, (0, 0, 240, 160))
    store.promote(persistent.id)
    protected = store.save_image(pixels, (0, 0, 240, 160))
    old = store.save_image(pixels, (0, 0, 240, 160))
    newest = store.save_image(pixels, (0, 0, 240, 160))
    assert store.cleanup_temporary(keep=1, protected_ids=(protected.id,)) == 1
    assert not store.path(old).exists()
    for retained in (shot, persistent, protected, newest):
        assert store.path(retained).is_file()
    assert store.get(shot.id).is_persistent
    assert store.db.one("SELECT * FROM memory_screenshots WHERE memory_id=?", (memory["id"],))
    with pytest.raises(ValueError):
        store.rebind(shot.id, context.project_id, None, None, None)


def test_memory_image_transaction_rolls_back(visual):
    _, store, shot, context = visual
    with pytest.raises(sqlite3.IntegrityError):
        MemoryStore(store.db).save("invalid concept", project_id=context.project_id,
                                  concept_id="missing", screenshot_id=shot.id)
    assert not store.get(shot.id).is_persistent
    assert not store.db.all("SELECT * FROM memory_screenshots")
    assert not store.db.all("SELECT * FROM memories")


def test_recent_storage_bounded_and_session_isolated(visual):
    manager, store, shot, context = visual
    recent = RecentContextStore(store.db)
    for i in range(25):
        recent.record(context, "explain", f"question {i}")
    rows = recent.list(context.project_id, context.source_id, context.session_id, 100)
    assert len(rows) == 20 and rows[0]["question"] == "question 24"
    assert rows[0]["screenshot_id"] == shot.id
    assert recent.list("other", context.source_id, context.session_id) == []
    assert recent.list(context.project_id, None, context.session_id) == []
    manager.end_session()
    session = manager.ensure_session(context.project_id, context.source_id)
    assert recent.list(context.project_id, context.source_id, session["id"]) == []
    assert store.recent(context.project_id, context.source_id, session["id"]) == []
    with pytest.raises(ValueError):
        recent.record(replace(context, source_id=None), "explain")


def test_visual_handoff_and_missing_image(visual, qapp):
    manager, store, shot, context = visual
    integration = ClipboardIntegration()
    package = manager.build(replace(context, question="为什么可以忽略 r_o？"), "explain")
    prepared = integration.prepare(package, store.path(shot))
    assert "为什么可以忽略 r_o" in prepared.prompt
    assert "截图" in prepared.prompt
    integration.copy_image(prepared, qapp.clipboard())
    mime = qapp.clipboard().mimeData()
    assert mime.hasImage() and mime.hasFormat("image/png") and not mime.hasText()
    integration.copy(package, qapp.clipboard().setText)
    assert "Context Package" in qapp.clipboard().text()
    store.path(shot).unlink()
    with pytest.raises(ValueError):
        integration.prepare(package, store.path(shot))


def test_translation_prompt_no_summary_and_no_invented_ocr(visual):
    manager, _, _, context = visual
    package = manager.build(context)
    assert package.related_concepts == []
    prompt = ClipboardIntegration().format(package)
    assert "不自动总结" in prompt or "不总结" in prompt
    assert "保留公式" in prompt
    assert "下标" in prompt


def make_v1(path):
    connection = sqlite3.connect(path)
    connection.executescript(MIGRATIONS[1] + "\nPRAGMA user_version=1;")
    connection.execute("INSERT INTO projects VALUES (?,?,?,?,?)",
                       ("old-project", "Existing", "", "before", "before"))
    connection.commit()
    connection.close()


def test_v1_upgrade_preserves_data_and_creates_readable_backup(tmp_path):
    path = tmp_path / "study.db"
    make_v1(path)
    db = Database(path)
    assert db.one("SELECT name FROM projects WHERE id='old-project'")["name"] == "Existing"
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == max(MIGRATIONS)
    assert db.connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert db.connection.execute("PRAGMA foreign_key_check").fetchall() == []
    db.close()
    backups = list((tmp_path / "backups").glob("*.db"))
    assert len(backups) == 1
    backup = sqlite3.connect(backups[0])
    assert backup.execute("PRAGMA user_version").fetchone()[0] == 1
    assert backup.execute("SELECT name FROM projects").fetchone()[0] == "Existing"
    backup.close()
    Database(path).close()
    assert len(list((tmp_path / "backups").glob("*.db"))) == 1


def test_v2_migration_failure_leaves_v1_intact(tmp_path, monkeypatch):
    path = tmp_path / "study.db"
    make_v1(path)
    monkeypatch.setitem(MIGRATIONS, 2, "CREATE TABLE partial(id); INVALID SQL;")
    with pytest.raises(sqlite3.Error):
        Database(path)
    connection = sqlite3.connect(path)
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
    assert connection.execute("SELECT name FROM projects").fetchone()[0] == "Existing"
    assert not connection.execute("SELECT name FROM sqlite_master WHERE name='partial'").fetchone()
    connection.close()
