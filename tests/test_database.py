import importlib
import sqlite3
import pytest
from studycopilot.config import Settings
from studycopilot.main import initialize
from studycopilot.memory.migrations import MIGRATIONS, SCHEMA_VERSION, migrate


@pytest.mark.parametrize("module", ["main", "ui.sidebar", "capture.clipboard", "capture.hotkeys",
                                    "providers.base", "context.package"])
def test_application_imports_without_keys(module, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    importlib.import_module("studycopilot." + module)


def test_schema_and_foreign_keys(db):
    tables = {row["name"] for row in db.all("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"projects", "sources", "study_sessions", "concepts", "concept_aliases", "concept_links",
            "memories", "memories_fts", "translation_history", "user_preferences", "topics"} <= tables
    assert db.connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION


def test_migrate_twice_preserves_data(db, project):
    migrate(db.connection)
    migrate(db.connection)
    assert db.one("SELECT name FROM projects WHERE id=?", (project["id"],))["name"] == "模拟电子技术"


def test_failed_migration_is_atomic(monkeypatch):
    connection = sqlite3.connect(":memory:")
    monkeypatch.setitem(MIGRATIONS, 1, "CREATE TABLE should_rollback(id); INVALID SQL;")
    with pytest.raises(sqlite3.Error):
        migrate(connection)
    assert not connection.execute("SELECT name FROM sqlite_master WHERE name='should_rollback'").fetchone()
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 0
    connection.close()


def test_newer_database_refused_without_modification(db):
    db.connection.execute("PRAGMA user_version=999")
    with pytest.raises(RuntimeError):
        migrate(db.connection)
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 999


def test_initialization_is_idempotent_and_persistent(tmp_path):
    settings = Settings(tmp_path)
    database = initialize(settings)
    assert len(database.all("SELECT * FROM concepts")) == 8
    database.close()
    database = initialize(settings)
    assert len(database.all("SELECT * FROM projects")) == 1
    assert len(database.all("SELECT * FROM concepts")) == 8
    assert len(database.all("SELECT * FROM user_preferences")) == 5
    database.close()
