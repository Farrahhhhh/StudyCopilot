from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    home: Path
    max_selection_chars: int = 24000
    max_memory_chars: int = 2000
    capture_timeout_ms: int = 2200

    @property
    def database_path(self) -> Path:
        return self.home / "data" / "study.db"

    @property
    def log_path(self) -> Path:
        return self.home / "logs" / "app.log"

    @classmethod
    def load(cls, home: str | None = None) -> Settings:
        override = home or os.environ.get("STUDYCOPILOT_HOME")
        if override:
            return cls(Path(override).expanduser().resolve())
        checkout = Path(__file__).resolve().parents[2]
        if (checkout / "pyproject.toml").exists():
            return cls(checkout)
        return cls(Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "StudyCopilot")
