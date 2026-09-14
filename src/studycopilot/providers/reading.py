from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from PySide6.QtCore import QObject, Signal


@dataclass(frozen=True)
class ReadingRequest:
    id: str
    prompt: str
    image_path: Path | None
    task_type: str
    model: str = ""


class ReadingProvider(QObject):
    """Event-based provider contract. No network work occurs at construction."""
    request_progress = Signal(str, str)
    connection_changed = Signal(str, str)
    models_changed = Signal(list)
    text_changed = Signal(str, str)  # request id, current visible answer (not raw reasoning)
    completed = Signal(str, str, str)  # request id, final answer, actual model
    failed = Signal(str, str, str)  # request id, stable code, safe user-facing message
    login_url = Signal(str)

    def login(self) -> None:
        raise NotImplementedError

    def connect_service(self) -> None:
        raise NotImplementedError

    def submit(self, request: ReadingRequest) -> None:
        raise NotImplementedError

    def cancel(self) -> None:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError
