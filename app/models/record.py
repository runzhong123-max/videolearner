from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Record:
    id: Optional[int]
    session_id: int
    record_type: str
    content: str
    file_path: str
    created_at: datetime
    timestamp_offset: int
    metadata_json: str
    is_inspiration: bool
