from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Session:
    id: Optional[int]
    project_id: int
    title: str
    status: str
    started_at: datetime
    ended_at: Optional[datetime]
    summary: str
    created_at: datetime
    updated_at: datetime
