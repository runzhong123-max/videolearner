from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class PromptTemplate:
    id: Optional[int]
    scope: str
    project_id: Optional[int]
    session_id: Optional[int]
    name: str
    content: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
