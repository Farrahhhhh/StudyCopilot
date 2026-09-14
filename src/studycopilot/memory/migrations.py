import sqlite3

from .schema import SCHEMA_V1

from .schema_v2 import SCHEMA_V2

from .schema_v3 import SCHEMA_V3

MIGRATIONS = {1: SCHEMA_V1, 2: SCHEMA_V2, 3: SCHEMA_V3}
SCHEMA_VERSION = max(MIGRATIONS)


def migrate(connection: sqlite3.Connection) -> None:
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if version > SCHEMA_VERSION:
        raise RuntimeError("数据库来自更新版本，请升级 StudyCopilot；原数据未修改。")
    for target in range(version + 1, SCHEMA_VERSION + 1):
        try:
            connection.executescript(
                f"BEGIN IMMEDIATE;\n{MIGRATIONS[target]}\nPRAGMA user_version={target};\nCOMMIT;"
            )
        except Exception:
            if connection.in_transaction:
                connection.rollback()
            raise
