from datetime import UTC, datetime
from typing import Any, Optional

from app.models.record import Record
from app.repositories.base_repository import BaseRepository


class RecordRepository(BaseRepository):
    TABLE = "records"

    def create(
        self,
        session_id: int,
        record_type: str,
        content: str = "",
        file_path: str = "",
        metadata_json: str = "{}",
        is_inspiration: bool = False,
    ) -> int:
        now = datetime.now(UTC).isoformat()
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO records (session_id, record_type, content, file_path, created_at, metadata_json, is_inspiration)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, record_type, content, file_path, now, metadata_json, int(is_inspiration)),
            )
            return int(cursor.lastrowid)

    def get_by_id(self, record_id: int) -> Optional[Record]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM records WHERE id = ?", (record_id,)).fetchone()
            return self._to_model(row) if row else None

    def list_by_session(self, session_id: int) -> list[Record]:
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM records WHERE session_id = ? ORDER BY id ASC",
                (session_id,),
            ).fetchall()
            return [self._to_model(r) for r in rows]

    def update(self, record_id: int, **fields: Any) -> bool:
        if not fields:
            return False

        allowed = {"record_type", "content", "file_path", "metadata_json", "is_inspiration"}
        updates = []
        values = []
        for key, value in fields.items():
            if key in allowed:
                updates.append(f"{key} = ?")
                values.append(int(value) if key == "is_inspiration" else value)

        if not updates:
            return False

        values.append(record_id)
        with self.get_connection() as conn:
            cursor = conn.execute(
                f"UPDATE {self.TABLE} SET {', '.join(updates)} WHERE id = ?",
                tuple(values),
            )
            return cursor.rowcount > 0

    def delete(self, record_id: int) -> bool:
        with self.get_connection() as conn:
            cursor = conn.execute("DELETE FROM records WHERE id = ?", (record_id,))
            return cursor.rowcount > 0

    @staticmethod
    def _to_model(row) -> Record:
        return Record(
            id=row["id"],
            session_id=row["session_id"],
            record_type=row["record_type"],
            content=row["content"],
            file_path=row["file_path"],
            created_at=datetime.fromisoformat(row["created_at"]),
            metadata_json=row["metadata_json"],
            is_inspiration=bool(row["is_inspiration"]),
        )

