from __future__ import annotations

from typing import Protocol

from labsmith.models import PartRequest


class PromptParser(Protocol):
    def parse(self, prompt: str) -> PartRequest:
        """Convert natural language into a structured lab part request."""
