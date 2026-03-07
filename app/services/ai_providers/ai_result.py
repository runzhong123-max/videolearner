from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AIGenerationResult:
    content: str
    provider: str
    model: str | None
    raw_response: dict[str, Any] | None
    usage: dict[str, Any] | None
    metadata: dict[str, Any] | None
