"""Future optional API boundary. No SDK, keys or network access in V0.1."""

from typing import Protocol

from studycopilot.context.package import ContextPackage


class AIProvider(Protocol):
    def complete(self, package: ContextPackage) -> str: ...
