from __future__ import annotations

from dataclasses import asdict, dataclass
import json


@dataclass(frozen=True)
class ScreenshotContext:
    id: str
    file_path: str
    width: int
    height: int
    screen_region: tuple[int, int, int, int]
    created_at: str
    project_id: str | None = None
    source_id: str | None = None
    topic_id: str | None = None
    session_id: str | None = None
    capture_type: str = "region"
    task_type: str = "translate"
    is_persistent: bool = False

    def __post_init__(self):
        if self.width <= 0 or self.height <= 0:
            raise ValueError("截图尺寸无效。")
        if self.task_type not in {"translate", "explain"}:
            raise ValueError("未知截图任务。")
        if len(self.screen_region) != 4 or min(self.screen_region[2:]) <= 0:
            raise ValueError("截图区域无效。")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_row(cls, row: dict) -> ScreenshotContext:
        values = dict(row)
        values["screen_region"] = tuple(json.loads(values["screen_region"]))
        values["is_persistent"] = bool(values["is_persistent"])
        return cls(**values)
