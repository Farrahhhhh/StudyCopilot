from __future__ import annotations

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
             memory_type: str = "note", importance: float = 1, screenshot_id: str | None = None) -> dict:
        content = content.strip()
        if not content or len(content) > 2000:
            raise ValueError("Memory 请输入 1–2000 个字符，只保存有长期价值的信息。")
        if scope not in {"project", "global", "user"}:
            raise ValueError("未知 Memory scope。")
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
            self.db.connection.execute("INSERT INTO memories VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (identifier, scope, project_id, source_id, concept_id, memory_type, content,
                 index_text(content), importance, timestamp, timestamp))
            if screenshot_id:
                self.db.connection.execute("INSERT INTO memory_screenshots VALUES (?,?)", (identifier, screenshot_id))
                self.db.connection.execute("UPDATE screenshots SET is_persistent=1 WHERE id=?", (screenshot_id,))
        return self.db.one("SELECT * FROM memories WHERE id=?", (identifier,))

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
