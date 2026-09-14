"""Upgrade an existing closed app database, verifying every pre-existing table is unchanged."""
import hashlib
import json
from pathlib import Path
import sqlite3

from studycopilot.memory.database import Database

root = Path(__file__).resolve().parents[1]
path = root / "data" / "study.db"

def snapshot(connection, names):
    result = {}
    for name in names:
        quoted = '"' + name.replace('"', '""') + '"'
        rows = connection.execute("SELECT * FROM " + quoted).fetchall()
        encoded = sorted(json.dumps(list(row), ensure_ascii=False, default=str) for row in rows)
        result[name] = {"rows": len(rows), "sha256": hashlib.sha256(
            "\n".join(encoded).encode("utf-8")).hexdigest()}
    return result

with sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True) as connection:
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    names = [r[0] for r in connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    before = snapshot(connection, names)
db = Database(path)
try:
    after = snapshot(db.connection, names)
    assert before == after, "Pre-existing database content changed unexpectedly"
    assert db.connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert not db.connection.execute("PRAGMA foreign_key_check").fetchall()
    report = {"before_version": version,
              "after_version": db.connection.execute("PRAGMA user_version").fetchone()[0],
              "existing_tables_unchanged": True, "integrity_check": "ok",
              "foreign_key_check": "ok", "tables": before}
    (root / "test-results" / f"v{version:02}-to-v{db.connection.execute('PRAGMA user_version').fetchone()[0]:02}-data-migration.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "tables"}))
finally:
    db.close()
