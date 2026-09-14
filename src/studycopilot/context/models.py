from __future__ import annotations

from dataclasses import dataclass, field

from studycopilot.memory.database import now
from .screenshot import ScreenshotContext


@dataclass(frozen=True)
class StudyContext:
    selected_text: str | None = ""
    project_id: str | None = None
    source_id: str | None = None
    topic_id: str | None = None
    session_id: str | None = None
    current_app: str | None = None
    process_name: str | None = None
    window_title: str | None = None
    recent_context: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=now)
    current_screenshot: ScreenshotContext | None = None
    recent_screenshots: list[ScreenshotContext] = field(default_factory=list)
    question: str = ""
