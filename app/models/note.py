from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Note:
    id: Optional[int]
    session_id: int
    summary: str
    suggestions: str
    inspiration_refinement: str
    guidance: str
    created_at: datetime
    updated_at: datetime
