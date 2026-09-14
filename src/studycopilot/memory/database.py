from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .migrations import migrate, SCHEMA_VERSION


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id() -> str:
    return str(uuid4())


class Database:
    def __init__(self, path: Path | str):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(path), timeout=5)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        try:
            version = self.connection.execute("PRAGMA user_version").fetchone()[0]
            if 0 < version < SCHEMA_VERSION and str(path) != ":memory:":
                backup_dir = Path(path).parent / "backups"
                backup_dir.mkdir(exist_ok=True)
                backup_path = backup_dir / f"study-v{version}-{new_id()}.db"
                backup = sqlite3.connect(str(backup_path))
                try:
                    self.connection.backup(backup)
                finally:
                    backup.close()
            migrate(self.connection)
            self.connection.execute("PRAGMA journal_mode=WAL")
        except Exception:
            self.connection.close()
            raise

    def all(self, sql: str, parameters: tuple = ()) -> list[dict]:
        return [dict(row) for row in self.connection.execute(sql, parameters)]

    def one(self, sql: str, parameters: tuple = ()) -> dict | None:
        row = self.connection.execute(sql, parameters).fetchone()
        return dict(row) if row else None

    def execute(self, sql: str, parameters: tuple = ()) -> None:
        with self.connection:
            self.connection.execute(sql, parameters)

    def close(self) -> None:
        self.connection.close()
