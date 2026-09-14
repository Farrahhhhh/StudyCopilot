from __future__ import annotations

import re

from studycopilot.memory.database import Database, new_id, now
from studycopilot.projects.manager import required_name


class ConceptStore:
    def __init__(self, db: Database):
        self.db = db

    def create(self, canonical_name: str, english_name: str = "", chinese_name: str = "",
               description: str = "", aliases: tuple[str, ...] = ()) -> dict:
        identifier, timestamp = new_id(), now()
        with self.db.connection:
            self.db.connection.execute("INSERT INTO concepts VALUES (?,?,?,?,?,?,?)",
                (identifier, required_name(canonical_name), english_name, chinese_name,
                 description, timestamp, timestamp))
            normalized = {required_name(a).casefold() for a in
                          (canonical_name, english_name, chinese_name, *aliases) if a.strip()}
            for alias in normalized:
                self.db.connection.execute("INSERT INTO concept_aliases VALUES (?,?,?,?)",
                    (new_id(), identifier, required_name(alias).casefold(), None))
        return self.get(identifier)

    def list_all(self) -> list[dict]:
        return self.db.all("SELECT * FROM concepts ORDER BY canonical_name")

    def find_name(self, name: str) -> dict | None:
        return self.db.one("SELECT * FROM concepts WHERE canonical_name=? COLLATE NOCASE", (name,))

    def aliases(self, concept_id: str) -> list[str]:
        return [row["alias"] for row in self.db.all(
            "SELECT alias FROM concept_aliases WHERE concept_id=? ORDER BY alias", (concept_id,))]

    def get(self, concept_id: str) -> dict:
        item = self.db.one("SELECT * FROM concepts WHERE id=?", (concept_id,))
        if not item:
            raise ValueError("Concept 不存在。")
        return item

    def add_alias(self, concept_id: str, alias: str, language: str | None = None) -> None:
        self.db.execute("INSERT OR IGNORE INTO concept_aliases VALUES (?,?,?,?)",
                        (new_id(), concept_id, required_name(alias).casefold(), language))

    def add_link(self, source_id: str, target_id: str, relation: str, confidence: float = 1) -> None:
        self.db.execute("INSERT INTO concept_links VALUES (?,?,?,?,?,?) ON CONFLICT(source_concept_id,target_concept_id,relation_type) DO NOTHING",
                        (new_id(), source_id, target_id, relation, confidence, now()))

    def attach_source(self, source_id: str, concept_id: str) -> None:
        self.db.execute("INSERT OR IGNORE INTO source_concepts VALUES (?,?,?,?,?)",
                        (new_id(), source_id, concept_id, 1, now()))

    def match(self, text: str, limit: int = 5) -> list[dict]:
        folded = text.casefold()
        matched: dict[str, int] = {}
        for row in self.db.all("SELECT concept_id,alias FROM concept_aliases"):
            alias = row["alias"]
            # ASCII word boundaries avoid 'ro' matching 'process' or 'output' matching 'outputs'.
            pattern = r"(?<![\w])" + re.escape(alias) + r"(?![\w])"
            found = alias in folded if re.search(r"[\u3400-\u9fff]", alias) else re.search(pattern, folded)
            if found:
                matched[row["concept_id"]] = max(len(alias), matched.get(row["concept_id"], 0))
        return [self.get(cid) for cid in sorted(matched, key=lambda cid: (-matched[cid], cid))[:limit]]

    def seed_terminology(self) -> None:
        terms = [
            ("transconductance", "跨导", ("gm", "g_m")),
            ("small-signal model", "小信号模型", ("small signal model",)),
            ("source degeneration", "源极退化", ()),
            ("common-source amplifier", "共源放大器", ("common source amplifier",)),
            ("channel-length modulation", "沟道长度调制", ("channel length modulation",)),
            ("MOSFET output resistance", "MOSFET 输出电阻", ("r_o", "ro")),
            ("Q-point", "静态工作点", ("bias point",)),
            ("negative feedback", "负反馈", ()),
        ]
        for english, chinese, aliases in terms:
            if not self.db.one("SELECT id FROM concepts WHERE canonical_name=?", (english,)):
                self.create(english, english, chinese, aliases=aliases)
