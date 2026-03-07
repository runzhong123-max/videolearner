from dataclasses import dataclass
from datetime import datetime


@dataclass
class AIProviderConfig:
    provider: str
    api_key: str
    api_url: str
    model: str
    timeout_seconds: int
    updated_at: datetime
