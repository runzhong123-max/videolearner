from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class RecordOCRResult:
    id: Optional[int]
    record_id: int
    ocr_text: str
    ocr_status: str
    ocr_error: str
    provider: str
    metadata_json: str
    processed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime