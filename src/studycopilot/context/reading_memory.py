"""Deterministic project-only selection and exact, bounded wire snapshots."""
from dataclasses import dataclass, field
import json
import re

from studycopilot.knowledge.concepts import ConceptStore
from studycopilot.memory.store import MemoryStore
from studycopilot.memory.retrieval import search_tokens

MAX_MEMORIES = 5
MAX_MEMORY_CHARS = 6000
GENERIC = set("why how what when where which explain understand question explanation understanding information relation difference behavior previous help please does do can could would should still not gain meaning 为什么 怎么 如何 什么 理解 这个 那个 问题 请问 可以".split())


def reliable_words(text):
    tokens = {t for t in search_tokens(text) if len(t) >= 3 and t not in GENERIC}
    # Chinese bigrams are too weak by themselves. Require a shared run of 3+ characters.
    for run in re.findall(r"[\u3400-\u9fff]+", text):
        tokens.update(run[i:i+3] for i in range(len(run)-2) if run[i:i+3] not in GENERIC)
    return tokens


def select_project_memories(db, retriever, project_id, query="", manual_ids=()):
    if not project_id:
        return []
    store = MemoryStore(db)
    concepts = ConceptStore(db).match(query, limit=20)
    concept_ids = {c["id"] for c in concepts}
    # Reuse the existing FTS index and concept bridge; add a strict relevance gate.
    candidates = retriever.search(query, project_id, list(concept_ids), limit=20,
                                  project_only=True, pending_only=True)
    manual = {}
    for identifier in dict.fromkeys(manual_ids):
        try:
            item = store.get_project(identifier, project_id)
        except ValueError:
            continue
        if item["status"] == "pending":
            manual[identifier] = item
    words = reliable_words(query)
    selected = dict(manual)
    for item in candidates:
        overlap = words & reliable_words(item["content"])
        content_match = len(overlap) >= 2 or any(
            re.search(r"[㐀-鿿]", word) or len(word) >= 10 for word in overlap)
        if (item["scope"] == "project" and item["project_id"] == project_id
                and item["status"] == "pending"
                and (item["concept_id"] in concept_ids or content_match)):
            selected.setdefault(item["id"], item)
    result = []
    for item in selected.values():
        concept = db.one("SELECT canonical_name FROM concepts WHERE id=?", (item["concept_id"],))
        snapshot = {"id": item["id"], "scope": "project", "content": item["content"],
                    "concept_id": item["concept_id"], "concept": (concept or {}).get("canonical_name", "")[:200],
                    "status": item["status"], "source": store.source(item)}
        proposed = result + [snapshot]
        if len(json.dumps(proposed, ensure_ascii=False, separators=(",", ":"))) <= MAX_MEMORY_CHARS:
            result = proposed
        if len(result) == MAX_MEMORIES:
            break
    return result


@dataclass(frozen=True)
class ReadingContextSnapshot:
    request_id: str
    project: dict | None
    source: dict | None
    session: dict | None
    memories: list[dict] = field(default_factory=list)

    @classmethod
    def from_package(cls, request_id, package):
        # Detached from both mutable UI state and subsequent database edits.
        return cls(request_id, *json.loads(json.dumps(
            [package.project, package.source, package.session, package.relevant_memories],
            ensure_ascii=False)))

    def to_json(self):
        from dataclasses import asdict
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, value):
        return cls(**json.loads(value)) if value else None
