from __future__ import annotations

from studycopilot.knowledge.concepts import ConceptStore
from studycopilot.memory.database import Database, new_id, now
from studycopilot.memory.retrieval import MemoryRetriever
from studycopilot.memory.store import MemoryStore
from studycopilot.projects.manager import ProjectManager

from .models import StudyContext
from .package import ContextPackage


def compact(item: dict | None, keys: tuple[str, ...]) -> dict | None:
    return {key: item[key] for key in keys} if item else None


class ContextManager:
    def __init__(self, db: Database, retriever: MemoryRetriever):
        self.db, self.retriever = db, retriever
        self.projects = ProjectManager(db)
        self.session: dict | None = None

    def ensure_session(self, project_id: str, source_id: str | None = None,
                       topic_id: str | None = None) -> dict:
        self.projects.project(project_id)
        if source_id:
            self.projects.source(source_id, project_id)
        if topic_id and not self.db.one(
            "SELECT id FROM topics WHERE id=? AND project_id=? AND source_id IS ?",
            (topic_id, project_id, source_id),
        ):
            raise ValueError("Topic 不属于当前资料与项目。")
        key = (project_id, source_id, topic_id)
        if self.session and tuple(self.session[k] for k in ("project_id", "source_id", "topic_id")) == key:
            return self.session
        self.end_session()
        identifier, timestamp = new_id(), now()
        self.db.execute("INSERT INTO study_sessions VALUES (?,?,?,?,?,NULL)",
                        (identifier, project_id, source_id, topic_id, timestamp))
        if source_id:
            self.db.execute("UPDATE sources SET last_opened_at=? WHERE id=?", (timestamp, source_id))
        self.session = self.db.one("SELECT * FROM study_sessions WHERE id=?", (identifier,))
        return self.session

    def end_session(self) -> None:
        if self.session:
            self.db.execute("UPDATE study_sessions SET ended_at=? WHERE id=?", (now(), self.session["id"]))
            self.session = None

    def build(self, context: StudyContext, task_type: str = "translate") -> ContextPackage:
        text = context.selected_text or ""
        if not text.strip() and context.current_screenshot is None:
            raise ValueError("请先框选截图，或输入辅助文字。")
        if len(text) > 24000:
            raise ValueError("选文超过 24000 个字符，请分段选择。原文不会被静默截断。")
        if task_type not in {"translate", "explain"}:
            raise ValueError("未知任务类型。")
        if len(context.question) > 1000:
            raise ValueError("问题请控制在 1000 字符内。")
        project = self.projects.project(context.project_id) if context.project_id else None
        if context.source_id and not project:
            raise ValueError("有 Source 时必须指定所属 Project。")
        source = self.projects.source(context.source_id, context.project_id) if context.source_id else None
        topic = None
        if context.topic_id:
            topic = self.db.one("SELECT * FROM topics WHERE id=? AND project_id=? AND source_id IS ?",
                                (context.topic_id, context.project_id, context.source_id))
            if not topic:
                raise ValueError("Topic 不属于当前资料与项目。")
        if context.session_id and not self.db.one(
            "SELECT id FROM study_sessions WHERE id=? AND project_id IS ? AND source_id IS ? AND topic_id IS ?",
            (context.session_id, context.project_id, context.source_id, context.topic_id),
        ):
            raise ValueError("Session 与当前上下文不一致。")
        shot = context.current_screenshot
        if shot and (shot.project_id, shot.source_id, shot.topic_id, shot.session_id) != (
            context.project_id, context.source_id, context.topic_id, context.session_id
        ):
            raise ValueError("截图与当前项目、资料或 Session 不一致。")
        # No OCR: visual retrieval uses only explicit topic/question/optional text.
        query = text + " " + context.question + " " + context.memory_concept + " " + (topic["name"] if topic else "")
        concepts = ConceptStore(self.db).match(query)
        if not context.use_project_memory:
            memories = []
        elif context.strict_project_memory:
            from .reading_memory import select_project_memories
            memories = select_project_memories(self.db, self.retriever, context.project_id,
                                               query, context.manual_memory_ids)
        else:
            memories = self.retriever.search(query, context.project_id,
                                             [c["id"] for c in concepts], 5, context.source_id)
        preferences = MemoryStore(self.db).preferences()
        if context.strict_project_memory or not context.use_project_memory:
            preferences.pop("user_memories", None)
        return ContextPackage(
            task_type=task_type, selected_text=text,
            project=compact(project, ("id", "name")), source=compact(source, ("id", "title", "source_type")),
            topic=compact(topic, ("id", "name")), current_app=context.current_app or context.process_name,
            window_title=context.window_title,
            # V0.1 keeps recent context empty by default. Caller-supplied snippets are bounded.
            recent_context=[text[:1000] for text in context.recent_context[-2:]],
            related_concepts=[compact(c, ("id", "canonical_name", "english_name", "chinese_name")) for c in concepts],
            relevant_memories=memories if context.strict_project_memory else [
                compact(m, ("id", "scope", "content", "concept_id")) for m in memories],
            user_preferences=preferences,
            current_screenshot=shot.to_dict() if shot else None,
            recent_screenshots=[s.to_dict() for s in context.recent_screenshots[-2:]
                if s.id != (shot.id if shot else None) and
                (s.project_id, s.source_id, s.session_id) ==
                (context.project_id, context.source_id, context.session_id)],
            session={"id": context.session_id} if context.session_id else None,
            question=context.question,
            attachments=[{"id": shot.id, "file_path": shot.file_path,
                          "media_type": "image/png", "role": "current",
                          "width": shot.width, "height": shot.height}] if shot else [],
            metadata={"timestamp": context.timestamp, "session_id": context.session_id,
                      "process_name": context.process_name, "schema_version": 2},
        )
