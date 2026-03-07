from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class RecordConversation:
    id: Optional[int]
    record_id: int
    session_id: int
    project_id: int
    title: str
    provider: str
    model_name: str
    created_at: datetime
    updated_at: datetime
