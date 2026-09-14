from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from studycopilot.context.screenshot import ScreenshotContext
from studycopilot.projects.manager import ProjectManager
from .database import Database, new_id, now


def screenshot_filename(identifier: str, timestamp: datetime | None = None) -> str:
    stamp = timestamp or datetime.now(timezone.utc)
    return f"{stamp:%Y%m%d_%H%M%S}_{identifier.replace('-', '')}.png"


class ScreenshotStore:
    """Only this store manages screenshot files; paths are relative to the data directory."""

    def __init__(self, db: Database, data_dir: Path | None = None):
        self.db = db
        db_path = db.connection.execute("PRAGMA database_list").fetchone()[2]
        self.data_dir = (data_dir or Path(db_path).parent).resolve()
        self.directory = self.data_dir / "screenshots"

    def path(self, screenshot: ScreenshotContext) -> Path:
        path = (self.data_dir / screenshot.file_path).resolve()
        if not path.is_relative_to(self.directory.resolve()) or path.suffix.lower() != ".png":
            raise ValueError("截图路径不在本地截图目录中。")
        return path

    def get(self, identifier: str) -> ScreenshotContext:
        row = self.db.one("SELECT * FROM screenshots WHERE id=?", (identifier,))
        if not row:
            raise ValueError("截图不存在或已清理。")
        return ScreenshotContext.from_row(row)

    def validate_owner(self, project_id=None, source_id=None, topic_id=None, session_id=None) -> None:
        manager = ProjectManager(self.db)
        if project_id:
            manager.project(project_id)
        if source_id:
            if not project_id:
                raise ValueError("资料需要所属项目。")
            manager.source(source_id, project_id)
        if topic_id and not self.db.one(
            "SELECT id FROM topics WHERE id=? AND project_id IS ? AND source_id IS ?",
            (topic_id, project_id, source_id),
        ):
            raise ValueError("截图 Topic 归属不匹配。")
        if session_id and not self.db.one(
            "SELECT id FROM study_sessions WHERE id=? AND project_id IS ? AND source_id IS ? AND topic_id IS ?",
            (session_id, project_id, source_id, topic_id),
        ):
            raise ValueError("截图 Session 归属不匹配。")

    def save_image(self, image, region: tuple[int, int, int, int], task_type="translate",
                   project_id=None, source_id=None, topic_id=None, session_id=None) -> ScreenshotContext:
        if image.isNull():
            raise ValueError("没有获取到截图。")
        self.validate_owner(project_id, source_id, topic_id, session_id)
        identifier = new_id()
        item = ScreenshotContext(identifier, "screenshots/" + screenshot_filename(identifier),
            image.width(), image.height(), region, now(), project_id, source_id, topic_id, session_id,
            task_type=task_type)
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.path(item)
        temporary = path.with_suffix(".writing")
        try:
            if not image.save(str(temporary), "PNG"):
                raise OSError("无法写入截图，请检查磁盘空间与目录权限。")
            temporary.replace(path)
            self.db.execute("""INSERT INTO screenshots VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (identifier, project_id, source_id, topic_id, session_id, item.file_path, "region",
                 task_type, item.width, item.height, json.dumps(region), 0, item.created_at))
        except Exception:
            temporary.unlink(missing_ok=True)
            path.unlink(missing_ok=True)
            raise
        return item

    def promote(self, identifier: str) -> ScreenshotContext:
        item = self.get(identifier)
        if not self.path(item).is_file():
            raise ValueError("截图文件缺失，不能保存。")
        self.db.execute("UPDATE screenshots SET is_persistent=1 WHERE id=?", (identifier,))
        return self.get(identifier)

    def link_memory(self, screenshot_id: str, memory_id: str) -> None:
        item = self.get(screenshot_id)
        memory = self.db.one("SELECT * FROM memories WHERE id=?", (memory_id,))
        if not memory or (memory["scope"] == "project" and memory["project_id"] != item.project_id):
            raise ValueError("Memory 与截图项目不匹配。")
        if not self.path(item).is_file():
            raise ValueError("截图文件缺失。")
        with self.db.connection:
            self.db.connection.execute("INSERT OR IGNORE INTO memory_screenshots VALUES (?,?)",
                                       (memory_id, screenshot_id))
            self.db.connection.execute("UPDATE screenshots SET is_persistent=1 WHERE id=?", (screenshot_id,))

    def rebind(self, identifier: str, project_id, source_id, topic_id, session_id) -> ScreenshotContext:
        item = self.get(identifier)
        self.validate_owner(project_id, source_id, topic_id, session_id)
        if item.project_id != project_id or item.is_persistent:
            raise ValueError("已保存截图保持原归属；请重新截图。")
        with self.db.connection:
            self.db.connection.execute(
                "UPDATE screenshots SET source_id=?,topic_id=?,session_id=? WHERE id=?",
                (source_id, topic_id, session_id, identifier))
            self.db.connection.execute(
                "UPDATE recent_context SET source_id=?,session_id=? WHERE screenshot_id=?",
                (source_id, session_id, identifier))
        return self.get(identifier)

    def recent(self, project_id, source_id, session_id, limit=5) -> list[ScreenshotContext]:
        if not session_id:
            return []
        return [ScreenshotContext.from_row(row) for row in self.db.all(
            """SELECT * FROM screenshots WHERE project_id IS ? AND source_id IS ? AND session_id=?
               ORDER BY rowid DESC LIMIT ?""", (project_id, source_id, session_id, min(limit, 20)))]

    def cleanup_temporary(self, keep=20, protected_ids: tuple[str, ...] = ()) -> int:
        """Bound disk growth; never remove persistent or memory-linked images."""
        rows = self.db.all("SELECT * FROM screenshots WHERE is_persistent=0 ORDER BY rowid DESC")
        removed = 0
        for row in rows[max(1, keep):]:
            if row["id"] in protected_ids or self.db.one(
                "SELECT memory_id FROM memory_screenshots WHERE screenshot_id=?", (row["id"],)
            ):
                continue
            item = ScreenshotContext.from_row(row)
            try:
                self.path(item).unlink(missing_ok=True)
                self.db.execute("DELETE FROM screenshots WHERE id=? AND is_persistent=0", (item.id,))
                removed += 1
            except (OSError, ValueError):
                continue  # A locked file can be retried after a later user capture.
        return removed
