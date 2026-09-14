from __future__ import annotations

import re
from typing import Protocol

from .database import Database

STOP_WORDS = set("the a an of in on to for and or is are be with this that it as at by from user".split())


def search_tokens(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9_]+", text.casefold())
    for run in re.findall(r"[\u3400-\u9fff]+", text):
        tokens.extend(run[i:i + 2] for i in range(max(1, len(run) - 1)))
    return list(dict.fromkeys(t for t in tokens if t not in STOP_WORDS))


def index_text(text: str) -> str:
    return " ".join(search_tokens(text))


class MemoryRetriever(Protocol):
    def search(self, query: str, project_id: str | None = None,
               concept_ids: list[str] | None = None, limit: int = 5,
               source_id: str | None = None, *, project_only: bool = False,
               pending_only: bool = False) -> list[dict]: ...


class FTSMemoryRetriever:
    """Project > global. Other projects are excluded even for matching concepts."""

    def __init__(self, db: Database):
        self.db = db

    def search(self, query: str, project_id: str | None = None,
               concept_ids: list[str] | None = None, limit: int = 5,
               source_id: str | None = None, *, project_only: bool = False,
               pending_only: bool = False) -> list[dict]:
        if limit <= 0:
            return []
        tokens = search_tokens(query)[:48]
        scores: dict[str, float] = {}
        if tokens:
            expression = " OR ".join('"' + token + '"' for token in tokens)
            rows = self.db.all("""SELECT m.id, bm25(memories_fts) AS rank
                FROM memories_fts JOIN memories m ON m.rowid=memories_fts.rowid
                WHERE memories_fts MATCH ? AND
                ((m.scope='project' AND m.project_id=?) OR m.scope='global')""",
                (expression, project_id))
            scores = {row["id"]: row["rank"] for row in rows}
        candidates = self.db.all("""SELECT * FROM memories WHERE
            (scope='project' AND project_id=?) OR scope='global'""", (project_id,))
        concepts = set(concept_ids or [])
        candidates = [m for m in candidates
                      if (not project_only or (m["scope"] == "project" and m["project_id"] == project_id))
                      and (not pending_only or m["status"] == "pending")
                      and (m["id"] in scores or m["concept_id"] in concepts)]
        candidates.sort(key=lambda m: (
            0 if m["scope"] == "project" else 1,
            0 if source_id and m["source_id"] == source_id else 1,
            0 if m["concept_id"] in concepts else 1,
            scores.get(m["id"], 0), -m["importance"], m["id"],
        ))
        return [{k: v for k, v in memory.items() if k != "search_text"} for memory in candidates[:min(limit, 20)]]
