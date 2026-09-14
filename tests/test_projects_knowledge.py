import sqlite3
import pytest
from studycopilot.context.manager import ContextManager
from studycopilot.knowledge.concepts import ConceptStore
from studycopilot.memory.retrieval import FTSMemoryRetriever
from studycopilot.projects.manager import ProjectManager, suggest_source


def test_project_source_and_ownership(db, project):
    manager = ProjectManager(db)
    other = manager.create_project("ArduPilot")
    source = manager.create_source(project["id"], "Microelectronic Circuits", "book")
    assert source["project_id"] == project["id"]
    assert manager.list_sources(other["id"]) == []
    with pytest.raises(ValueError):
        manager.source(source["id"], other["id"])
    with pytest.raises(ValueError):
        manager.create_project("   ")
    with pytest.raises(sqlite3.IntegrityError):
        manager.create_project("模拟电子技术")


@pytest.mark.parametrize("title,expected", [
    (None, ""), ("", ""), ("Untitled application", ""),
    ("Microelectronic Circuits.pdf - Foxit PDF Reader", "Microelectronic Circuits.pdf"),
    ("Microelectronic Circuits.pdf - Microsoft Edge", "Microelectronic Circuits.pdf"),
    ("Parameters - Plane - Microsoft Edge", "Parameters - Plane"),
])
def test_source_suggestion(title, expected):
    assert suggest_source(title) == expected


def test_concept_aliases_links_and_no_substring_collision(db, project):
    store = ConceptStore(db)
    concept = store.create("MOSFET output resistance", chinese_name="输出电阻", aliases=("ro", "r_o"))
    store.add_alias(concept["id"], "RO")
    assert len(store.match("What happens to r_o?")) == 1
    assert store.match("ArduPilot output channel") == []
    assert store.match("process control") == []
    assert store.match("输出电阻是什么")[0]["id"] == concept["id"]
    other = store.create("channel-length modulation")
    store.add_link(other["id"], concept["id"], "related_to")
    assert len(db.all("SELECT * FROM concept_links")) == 1
    with pytest.raises(sqlite3.IntegrityError):
        store.add_link(other["id"], concept["id"], "invalid_relation")
    source = ProjectManager(db).create_source(project["id"], "教材")
    store.attach_source(source["id"], concept["id"])
    assert len(db.all("SELECT * FROM source_concepts")) == 1


def test_session_reuse_switch_and_close(db, project):
    manager = ContextManager(db, FTSMemoryRetriever(db))
    first = manager.ensure_session(project["id"])
    assert manager.ensure_session(project["id"])["id"] == first["id"]
    source = ProjectManager(db).create_source(project["id"], "教材")
    topic = ProjectManager(db).topic(project["id"], source["id"], "MOSFET")
    second = manager.ensure_session(project["id"], source["id"], topic["id"])
    assert second["id"] != first["id"]
    assert db.one("SELECT ended_at FROM study_sessions WHERE id=?", (first["id"],))["ended_at"]
    manager.end_session()
    assert db.one("SELECT ended_at FROM study_sessions WHERE id=?", (second["id"],))["ended_at"]
