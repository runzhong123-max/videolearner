from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Project:
    id: Optional[int]
    name: str
    description: str
    source: str
    goal: str
    tags: str
    default_prompt: str
    created_at: datetime
    updated_at: datetime
