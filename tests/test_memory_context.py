import json
import pytest
from studycopilot.context.manager import ContextManager
from studycopilot.context.models import StudyContext
from studycopilot.integrations.fallback import ClipboardIntegration
from studycopilot.knowledge.concepts import ConceptStore
from studycopilot.memory.retrieval import FTSMemoryRetriever, index_text
from studycopilot.projects.manager import ProjectManager


def test_scope_priority_and_isolation(db, project, memories):
    other = ProjectManager(db).create_project("ArduPilot")
    memories.save("negative feedback 已掌握", "global")
    local = memories.save("negative feedback 尚不稳定", project_id=project["id"])
    memories.save("negative feedback unrelated private project", project_id=other["id"])
    memories.save("解释先直觉", "user")
    result = FTSMemoryRetriever(db).search("The negative feedback reduces gain.", project["id"])
    assert len(result) == 2
    assert result[0]["id"] == local["id"]
    assert all(m["project_id"] != other["id"] for m in result)
    assert len(FTSMemoryRetriever(db).search("negative feedback")) == 1


def test_source_priority(db, project, memories):
    source = ProjectManager(db).create_source(project["id"], "教材")
    memories.save("transconductance first", project_id=project["id"])
    matched = memories.save("transconductance current source", project_id=project["id"], source_id=source["id"])
    result = FTSMemoryRetriever(db).search("transconductance", project["id"], source_id=source["id"])
    assert result[0]["id"] == matched["id"]


def test_chinese_retrieval_and_fts_update_delete(db, project, memories):
    item = memories.save("我仍不理解负反馈的物理意义", project_id=project["id"])
    retriever = FTSMemoryRetriever(db)
    assert retriever.search("为什么这里是负反馈？", project["id"])[0]["id"] == item["id"]
    db.execute("UPDATE memories SET content=?,search_text=? WHERE id=?",
               ("transconductance", index_text("transconductance"), item["id"]))
    assert not retriever.search("负反馈", project["id"])
    assert retriever.search("transconductance", project["id"])
    db.execute("DELETE FROM memories WHERE id=?", (item["id"],))
    assert not retriever.search("transconductance", project["id"])


def test_concept_memory_bridge_without_cross_project_leak(db, project, memories):
    concept = ConceptStore(db).create("transconductance", chinese_name="跨导", aliases=("gm",))
    item = memories.save("已理解跨导的物理含义", project_id=project["id"], concept_id=concept["id"])
    other = ProjectManager(db).create_project("other")
    memories.save("不要泄漏", project_id=other["id"], concept_id=concept["id"])
    package = ContextManager(db, FTSMemoryRetriever(db)).build(StudyContext("gm", project["id"]))
    assert [m["id"] for m in package.relevant_memories] == [item["id"]]


@pytest.mark.parametrize("query", ["", " ", '" OR * NOT (NEAR(foo))', "- : ?", "the and a of"])
def test_empty_or_hostile_fts_input(db, query):
    assert FTSMemoryRetriever(db).search(query) == []


def test_invalid_scope_and_source(db, project, memories):
    other = ProjectManager(db).create_project("other")
    source = ProjectManager(db).create_source(other["id"], "other book")
    for arguments in [dict(content=""), dict(content="x", scope="wrong"),
                      dict(content="x", scope="project"),
                      dict(content="x", scope="global", project_id=project["id"]),
                      dict(content="x", project_id=project["id"], source_id=source["id"])]:
        with pytest.raises(ValueError):
            memories.save(**arguments)


def test_partial_context_fallback_and_text_roundtrip(db, memories):
    memories.seed_preferences()
    memories.save("公式不要跳步", "user")
    text = 'The source resistance introduces negative feedback.\nV_o = -g_m v_gs [V]\n"中文"'
    package = ContextManager(db, FTSMemoryRetriever(db)).build(StudyContext(selected_text=text))
    assert package.project is None and package.window_title is None
    assert json.loads(package.to_json())["selected_text"] == text
    assert "公式不要跳步" in package.user_preferences["user_memories"]
    outputs = []
    prompt = ClipboardIntegration().copy(package, outputs.append)
    assert outputs == [prompt]
    assert "不总结" in prompt and "保留公式" in prompt
    payload = json.loads(prompt.split("Context Package（JSON 数据）：\n", 1)[1])
    assert payload["selected_text"] == text


def test_context_bounds_and_wrong_source(db, project, memories):
    manager = ContextManager(db, FTSMemoryRetriever(db))
    for text in ("", " ", "x" * 24001):
        with pytest.raises(ValueError):
            manager.build(StudyContext(text))
    for number in range(8):
        memories.save(f"transconductance {number}", project_id=project["id"])
    package = manager.build(StudyContext("transconductance", project["id"], recent_context=["x" * 5000] * 10))
    assert len(package.relevant_memories) == 5
    assert len(package.recent_context) == 2 and all(len(t) == 1000 for t in package.recent_context)
    other = ProjectManager(db).create_project("other")
    source = ProjectManager(db).create_source(other["id"], "other book")
    with pytest.raises(ValueError):
        manager.build(StudyContext("text", project["id"], source["id"]))
