from typing import Protocol

from studycopilot.context.package import ContextPackage


class Integration(Protocol):
    def format(self, package: ContextPackage) -> str: ...
