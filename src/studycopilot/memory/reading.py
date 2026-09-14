from studycopilot.memory.database import now
from studycopilot.memory.screenshots import ScreenshotStore


class ReadingStore:
    """Only completed responses, bounded separately from explicitly saved Memory."""
    def __init__(self, db):
        self.db = db

    def save(self, request_id, package, answer, model):
        shot = package.current_screenshot
        project_id = package.project["id"] if package.project else None
        source_id = package.source["id"] if package.source else None
        session_id = package.session["id"] if package.session else None
        topic_id = package.topic["id"] if package.topic else None
        ScreenshotStore(self.db).validate_owner(project_id, source_id, topic_id, session_id)
        if shot:
            item = ScreenshotStore(self.db).get(shot["id"])
            if (item.project_id, item.source_id, item.session_id) != (project_id, source_id, session_id):
                raise ValueError("截图归属已改变，未保存旧回答。")
        if not answer.strip() or len(answer) > 100000:
            raise ValueError("回答为空或过长。")
        with self.db.connection:
            self.db.connection.execute(
                "INSERT INTO reading_results VALUES (?,?,?,?,?,?,?,?,?,?)",
                (request_id, shot["id"] if shot else None, project_id, source_id, session_id,
                 package.task_type, package.question, answer, model, now()))
            self.db.connection.execute("""DELETE FROM reading_results WHERE id NOT IN
                (SELECT id FROM reading_results ORDER BY rowid DESC LIMIT 60)""")

    def latest(self, screenshot_id, project_id, source_id, session_id):
        if not screenshot_id:
            return None
        return self.db.one("""SELECT * FROM reading_results WHERE screenshot_id=?
            AND project_id IS ? AND source_id IS ? AND session_id IS ? ORDER BY rowid DESC LIMIT 1""",
            (screenshot_id, project_id, source_id, session_id))
