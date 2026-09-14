from __future__ import annotations

import re

from studycopilot.memory.database import Database, new_id, now


def required_name(value: str) -> str:
    value = value.strip()
    if not value or len(value) > 200:
        raise ValueError("名称不能为空，且不能超过 200 个字符。")
    return value


def suggest_source(window_title: str | None) -> str:
    """A suggestion only: never silently assign a document to a project."""
    title = (window_title or "").strip()
    pdf = re.search(r"^(.+?\.pdf)(?:\s*[-–—|].*)?$", title, re.IGNORECASE)
    if pdf:
        return pdf.group(1)[:200]
    parts = re.split(r"\s+[-–—|]\s+", title)
    if len(parts) > 1 and any(app in parts[-1].lower() for app in
                             ("edge", "foxit", "adobe", "pdfgear", "chrome", "word")):
        return " - ".join(parts[:-1])[:200]
    return ""


class ProjectManager:
    def __init__(self, db: Database):
        self.db = db

    def list_projects(self) -> list[dict]:
        return self.db.all("SELECT * FROM projects ORDER BY created_at,name")

    def create_project(self, name: str, description: str = "") -> dict:
        identifier, timestamp = new_id(), now()
        self.db.execute("INSERT INTO projects VALUES (?,?,?,?,?)",
                        (identifier, required_name(name), description, timestamp, timestamp))
        return self.project(identifier)

    def project(self, identifier: str) -> dict:
        item = self.db.one("SELECT * FROM projects WHERE id=?", (identifier,))
        if not item:
            raise ValueError("项目不存在。")
        return item

    def list_sources(self, project_id: str) -> list[dict]:
        return self.db.all("SELECT * FROM sources WHERE project_id=? ORDER BY title", (project_id,))

    def create_source(self, project_id: str, title: str, source_type: str = "book") -> dict:
        self.project(project_id)
        if source_type not in {"book", "pdf", "paper", "lecture", "web", "manual", "notes", "documentation"}:
            raise ValueError("未知资料类型。")
        identifier, timestamp = new_id(), now()
        self.db.execute("""INSERT INTO sources
            (id,project_id,source_type,title,created_at,updated_at) VALUES (?,?,?,?,?,?)""",
                        (identifier, project_id, source_type, required_name(title), timestamp, timestamp))
        return self.source(identifier, project_id)

    def source(self, source_id: str, project_id: str) -> dict:
        item = self.db.one("SELECT * FROM sources WHERE id=? AND project_id=?", (source_id, project_id))
        if not item:
            raise ValueError("资料不属于当前项目。")
        return item

    def topic(self, project_id: str, source_id: str | None, name: str) -> dict | None:
        if not name.strip():
            return None
        self.project(project_id)
        if source_id:
            self.source(source_id, project_id)
        name = required_name(name)
        item = self.db.one("SELECT * FROM topics WHERE project_id=? AND source_id IS ? AND name=?",
                           (project_id, source_id, name))
        if item:
            return item
        identifier = new_id()
        self.db.execute("INSERT INTO topics(id,project_id,source_id,name,created_at) VALUES(?,?,?,?,?)",
                        (identifier, project_id, source_id, name, now()))
        return self.db.one("SELECT * FROM topics WHERE id=?", (identifier,))
