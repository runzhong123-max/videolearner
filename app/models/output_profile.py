from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class OutputProfile:
    id: Optional[int]
    name: str
    scope: str
    project_id: Optional[int]
    session_id: Optional[int]
    summary: bool
    extension: bool
    insight: bool
    history_link: bool
    gap_analysis: bool
    review_questions: bool
    homework: bool
    expression_notes: bool
    evaluation: bool
    created_at: datetime
    updated_at: datetime
