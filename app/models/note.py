from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Note:
    id: Optional[int]
    project_id: Optional[int]
    session_id: int
    note_type: str
    title: str
    content: str
    summary: str
    suggestions: str
    inspiration_refinement: str
    guidance: str
    created_at: datetime
    updated_at: datetime
    ai_provider: str = ""
    ai_model: str = ""
    review_questions: str = ""
    key_points: str = ""
    follow_up_tasks: str = ""
    in_review_list: bool = False
    is_key_note: bool = False
    review_later: bool = False
