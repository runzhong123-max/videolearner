from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class RecordChatMessage:
    id: Optional[int]
    conversation_id: int
    role: str
    content: str
    created_at: datetime
    response_id: str
    metadata_json: str
    image_path: str
