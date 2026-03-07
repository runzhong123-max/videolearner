from dataclasses import dataclass
from typing import Any


@dataclass
class OCRResult:
    text: str
    provider: str
    success: bool
    error: str | None = None
    metadata: dict[str, Any] | None = None
