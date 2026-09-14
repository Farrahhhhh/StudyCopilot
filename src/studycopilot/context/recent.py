from __future__ import annotations

from studycopilot.memory.database import Database, new_id, now


class RecentContextStore:
    def __init__(self, db: Database):
        self.db = db

    def record(self, context, task_type: str, question: str = "") -> None:
        if task_type not in {"translate", "explain"}:
            raise ValueError("未知任务。")
        from studycopilot.memory.screenshots import ScreenshotStore
        ScreenshotStore(self.db).validate_owner(context.project_id, context.source_id,
                                                context.topic_id, context.session_id)
        shot = context.current_screenshot
        if shot and (shot.project_id, shot.source_id, shot.topic_id, shot.session_id) != (
            context.project_id, context.source_id, context.topic_id, context.session_id
        ):
            raise ValueError("截图与最近上下文的归属不一致。")
        self.db.execute("""INSERT INTO recent_context VALUES (?,?,?,?,?,?,?,?,?)""",
            (new_id(), context.project_id, context.source_id, context.session_id,
             shot.id if shot else None, task_type, (context.selected_text or "")[:1000], question[:1000], now()))
        # This is a bounded recent buffer, not an archive or learning memory.
        if context.session_id:
            self.db.execute("""DELETE FROM recent_context WHERE session_id=? AND id NOT IN
                (SELECT id FROM recent_context WHERE session_id=? ORDER BY rowid DESC LIMIT 20)""",
                (context.session_id, context.session_id))

    def list(self, project_id, source_id, session_id, limit=5) -> list[dict]:
        if not session_id:
            return []
        return self.db.all("""SELECT * FROM recent_context WHERE project_id IS ? AND source_id IS ?
            AND session_id=? ORDER BY rowid DESC LIMIT ?""", (project_id, source_id, session_id, min(limit, 20)))
