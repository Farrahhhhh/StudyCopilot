from typing import Protocol


class ScreenshotCapture(Protocol):
    """Reserved interface only. V0.1 never takes screen captures."""

    def capture_on_user_request(self) -> bytes: ...
