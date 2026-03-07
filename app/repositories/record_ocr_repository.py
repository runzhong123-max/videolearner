from datetime import UTC, datetime
from typing import Optional

from app.models.record_ocr_result import RecordOCRResult
from app.repositories.base_repository import BaseRepository


class RecordOCRRepository(BaseRepository):
    TABLE = "record_ocr_results"

    def get_by_record(self, record_id: int) -> Optional[RecordOCRResult]:
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM record_ocr_results WHERE record_id = ?",
                (record_id,),
            ).fetchone()
            return self._to_model(row) if row else None

    def upsert(
        self,
        record_id: int,
        ocr_text: str,
        ocr_status: str,
        ocr_error: str = "",
        provider: str = "mock_ocr",
        metadata_json: str = "{}",
        processed_at: datetime | None = None,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        processed = processed_at.isoformat() if processed_at else None

        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO record_ocr_results (
                    record_id,
                    ocr_text,
                    ocr_status,
                    ocr_error,
                    provider,
                    metadata_json,
                    processed_at,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(record_id) DO UPDATE SET
                    ocr_text = excluded.ocr_text,
                    ocr_status = excluded.ocr_status,
                    ocr_error = excluded.ocr_error,
                    provider = excluded.provider,
                    metadata_json = excluded.metadata_json,
                    processed_at = excluded.processed_at,
                    updated_at = excluded.updated_at
                """,
                (
                    record_id,
                    ocr_text,
                    ocr_status,
                    ocr_error,
                    provider,
                    metadata_json,
                    processed,
                    now,
                    now,
                ),
            )

    @staticmethod
    def _to_model(row) -> RecordOCRResult:
        processed_at = datetime.fromisoformat(row["processed_at"]) if row["processed_at"] else None
        return RecordOCRResult(
            id=row["id"],
            record_id=row["record_id"],
            ocr_text=row["ocr_text"],
            ocr_status=row["ocr_status"],
            ocr_error=row["ocr_error"],
            provider=row["provider"],
            metadata_json=row["metadata_json"],
            processed_at=processed_at,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )