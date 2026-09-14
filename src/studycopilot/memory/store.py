from __future__ import annotations

import json

from studycopilot.projects.manager import ProjectManager

from .database import Database, new_id, now
from .retrieval import index_text

DEFAULT_PREFERENCES = {
    "preferred_language": "中文，保留重要英文专业术语",
    "preferred_explanation_style": "先物理/工程直觉，再电路因果与结构，最后数学关系",
    "preferred_translation_style": "准确自然，采用中国大陆高校电子类教材术语；不总结、不扩写",
    "preferred_depth": "公式不跳过关键步骤，不自动总结整章",
    "terminology_preferences": "transconductance=跨导；source degeneration=源极退化；Q-point=静态工作点",
}


class MemoryStore:
    def __init__(self, db: Database):
        self.db = db

    def save(self, content: str, scope: str = "project", project_id: str | None = None,
             source_id: str | None = None, concept_id: str | None = None,
             memory_type: str = "note", importance: float = 1, screenshot_id: str | None = None,
             status: str = "pending", reading_result_id: str | None = None,
             source_snapshot: dict | None = None) -> dict:
        content = content.strip()
        if not content or len(content) > 2000:
            raise ValueError("Memory 请输入 1–2000 个字符，只保存有长期价值的信息。")
        if scope not in {"project", "global", "user"}:
            raise ValueError("未知 Memory scope。")
        if status not in {"pending", "resolved"}:
            raise ValueError("未知疑问状态。")
        if reading_result_id:
            result = self.db.one("SELECT id FROM reading_results WHERE id=? AND project_id IS ? AND source_id IS ?",
                                 (reading_result_id, project_id, source_id))
            if scope != "project" or not result:
                raise ValueError("阅读来源不属于此项目与资料。")
        if scope == "project":
            if not project_id:
                raise ValueError("项目记忆需要选择项目。")
            manager = ProjectManager(self.db)
            manager.project(project_id)
            if source_id:
                manager.source(source_id, project_id)
        elif project_id or source_id:
            raise ValueError("全局知识和学习偏好不绑定项目或资料。")
        if screenshot_id:
            from .screenshots import ScreenshotStore
            screenshots = ScreenshotStore(self.db)
            shot = screenshots.get(screenshot_id)
            if scope == "project" and shot.project_id != project_id:
                raise ValueError("截图不属于当前记忆的项目。")
            if not screenshots.path(shot).is_file():
                raise ValueError("截图文件缺失。")
        identifier, timestamp = new_id(), now()
        with self.db.connection:
            self.db.connection.execute("""INSERT INTO memories
                (id,scope,project_id,source_id,concept_id,memory_type,content,search_text,importance,
                 created_at,updated_at,status,reading_result_id,source_snapshot)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (identifier, scope, project_id, source_id, concept_id, memory_type, content,
                 index_text(content), importance, timestamp, timestamp, status, reading_result_id,
                 json.dumps(source_snapshot or {}, ensure_ascii=False)))
            if screenshot_id:
                self.db.connection.execute("INSERT INTO memory_screenshots VALUES (?,?)", (identifier, screenshot_id))
                self.db.connection.execute("UPDATE screenshots SET is_persistent=1 WHERE id=?", (screenshot_id,))
        return self.db.one("SELECT * FROM memories WHERE id=?", (identifier,))

    def list_project(self, project_id: str) -> list[dict]:
        return self.db.all("""SELECT * FROM memories WHERE scope='project' AND project_id=?
            ORDER BY status,updated_at DESC,id""", (project_id,))

    def get_project(self, identifier: str, project_id: str) -> dict:
        item = self.db.one("SELECT * FROM memories WHERE id=? AND scope='project' AND project_id=?",
                           (identifier, project_id))
        if not item:
            raise ValueError("此项目中没有这条记忆，可能已删除。")
        return item

    def update(self, identifier: str, project_id: str, content: str, status: str,
               concept_id: str | None = None, location: str | None = None) -> dict:
        item = self.get_project(identifier, project_id)
        content = content.strip()
        if not content or len(content) > 2000:
            raise ValueError("记忆正文请输入 1–2000 个字符。")
        if status not in {"pending", "resolved"}:
            raise ValueError("未知疑问状态。")
        snapshot = json.loads(item["source_snapshot"])
        if location is not None:
            snapshot["location"] = location[:200]
        self.db.execute("""UPDATE memories SET content=?,search_text=?,status=?,concept_id=?,
            source_snapshot=?,updated_at=? WHERE id=? AND project_id=?""",
            (content, index_text(content), status, concept_id, json.dumps(snapshot, ensure_ascii=False),
             now(), identifier, project_id))
        return self.get_project(identifier, project_id)

    def delete(self, identifier: str, project_id: str) -> None:
        self.get_project(identifier, project_id)
        self.db.execute("DELETE FROM memories WHERE id=? AND project_id=?", (identifier, project_id))

    def source(self, item: dict) -> dict:
        """Missing reading rows never invalidate the memory body."""
        saved = json.loads(item["source_snapshot"])
        source = self.db.one("SELECT title FROM sources WHERE id=? AND project_id=?",
                             (item["source_id"], item["project_id"]))
        shots = self.db.all("""SELECT s.id FROM screenshots s JOIN memory_screenshots ms
            ON s.id=ms.screenshot_id WHERE ms.memory_id=? AND s.project_id IS ?""",
            (item["id"], item["project_id"]))
        if item["reading_result_id"]:
            reading = self.db.one("""SELECT screenshot_id FROM reading_results
                WHERE id=? AND project_id IS ? AND source_id IS ?""",
                (item["reading_result_id"], item["project_id"], item["source_id"]))
            if reading and reading["screenshot_id"] and not any(s["id"] == reading["screenshot_id"] for s in shots):
                shots.append({"id": reading["screenshot_id"]})
        return {"source_id": item["source_id"],
                "title": (source or {}).get("title", saved.get("title", ""))[:200],
                "location": saved.get("location", "")[:200], "reading_result_id": item["reading_result_id"],
                "original_reading_id": saved.get("reading_result_id"),
                "screenshot_ids": [s["id"] for s in shots][:3]}

    def seed_preferences(self) -> None:
        for key, value in DEFAULT_PREFERENCES.items():
            self.db.execute("INSERT OR IGNORE INTO user_preferences VALUES (?,?,?,?)",
                            (new_id(), key, value, now()))

    def preferences(self) -> dict:
        values = {row["key"]: row["value"] for row in self.db.all("SELECT key,value FROM user_preferences")
                  if row["key"] in DEFAULT_PREFERENCES}
        values["user_memories"] = [row["content"] for row in self.db.all(
            "SELECT content FROM memories WHERE scope='user' ORDER BY importance DESC,updated_at DESC LIMIT 3")]
        return values
