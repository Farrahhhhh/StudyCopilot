from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json


@dataclass(frozen=True)
class ContextPackage:
    task_type: str
    selected_text: str
    project: dict | None = None
    source: dict | None = None
    topic: dict | None = None
    current_app: str | None = None
    window_title: str | None = None
    recent_context: list[str] = field(default_factory=list)
    related_concepts: list[dict] = field(default_factory=list)
    relevant_memories: list[dict] = field(default_factory=list)
    user_preferences: dict = field(default_factory=dict)
    attachments: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    current_screenshot: dict | None = None
    recent_screenshots: list[dict] = field(default_factory=list)
    session: dict | None = None
    question: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
