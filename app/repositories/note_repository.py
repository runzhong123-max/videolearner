from datetime import UTC, datetime
from typing import Any, Optional

from app.models.note import Note
from app.repositories.base_repository import BaseRepository


class NoteRepository(BaseRepository):
    TABLE = "notes"

    def create(
        self,
        session_id: int,
        summary: str,
        suggestions: str,
        inspiration_refinement: str = "",
        guidance: str = "",
    ) -> int:
        now = datetime.now(UTC).isoformat()
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO notes (
                    session_id,
                    summary,
                    suggestions,
                    inspiration_refinement,
                    guidance,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, summary, suggestions, inspiration_refinement, guidance, now, now),
            )
            return int(cursor.lastrowid)

    def get_by_id(self, note_id: int) -> Optional[Note]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
            return self._to_model(row) if row else None

    def get_by_session(self, session_id: int) -> Optional[Note]:
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM notes WHERE session_id = ? ORDER BY id DESC LIMIT 1",
                (session_id,),
            ).fetchone()
            return self._to_model(row) if row else None

    def update(self, note_id: int, **fields: Any) -> bool:
        if not fields:
            return False

        allowed = {"summary", "suggestions", "inspiration_refinement", "guidance"}
        updates = []
        values = []
        for key, value in fields.items():
            if key in allowed:
                updates.append(f"{key} = ?")
                values.append(value)

        if not updates:
            return False

        updates.append("updated_at = ?")
        values.append(datetime.now(UTC).isoformat())
        values.append(note_id)

        with self.get_connection() as conn:
            cursor = conn.execute(
                f"UPDATE {self.TABLE} SET {', '.join(updates)} WHERE id = ?",
                tuple(values),
            )
            return cursor.rowcount > 0

    def delete(self, note_id: int) -> bool:
        with self.get_connection() as conn:
            cursor = conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
            return cursor.rowcount > 0

    @staticmethod
    def _to_model(row) -> Note:
        return Note(
            id=row["id"],
            session_id=row["session_id"],
            summary=row["summary"],
            suggestions=row["suggestions"],
            inspiration_refinement=row["inspiration_refinement"],
            guidance=row["guidance"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

