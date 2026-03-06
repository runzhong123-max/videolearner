from datetime import UTC, datetime
from typing import Any, Optional

from app.models.session import Session
from app.repositories.base_repository import BaseRepository


class SessionRepository(BaseRepository):
    TABLE = "sessions"

    def create(self, project_id: int, title: str = "", status: str = "in_progress") -> int:
        now = datetime.now(UTC).isoformat()
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO sessions (project_id, title, status, started_at, ended_at, summary, created_at, updated_at)
                VALUES (?, ?, ?, ?, NULL, '', ?, ?)
                """,
                (project_id, title, status, now, now, now),
            )
            return int(cursor.lastrowid)

    def get_by_id(self, session_id: int) -> Optional[Session]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
            return self._to_model(row) if row else None

    def get_in_progress_session(self) -> Optional[Session]:
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE status = 'in_progress' ORDER BY id DESC LIMIT 1"
            ).fetchone()
            return self._to_model(row) if row else None

    def list_by_project(self, project_id: int) -> list[Session]:
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM sessions WHERE project_id = ? ORDER BY id DESC",
                (project_id,),
            ).fetchall()
            return [self._to_model(r) for r in rows]

    def update(self, session_id: int, **fields: Any) -> bool:
        if not fields:
            return False

        allowed = {"title", "status", "started_at", "ended_at", "summary"}
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
        values.append(session_id)

        with self.get_connection() as conn:
            cursor = conn.execute(
                f"UPDATE {self.TABLE} SET {', '.join(updates)} WHERE id = ?",
                tuple(values),
            )
            return cursor.rowcount > 0

    def delete(self, session_id: int) -> bool:
        with self.get_connection() as conn:
            cursor = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            return cursor.rowcount > 0

    @staticmethod
    def _to_model(row) -> Session:
        ended_at = datetime.fromisoformat(row["ended_at"]) if row["ended_at"] else None
        return Session(
            id=row["id"],
            project_id=row["project_id"],
            title=row["title"],
            status=row["status"],
            started_at=datetime.fromisoformat(row["started_at"]),
            ended_at=ended_at,
            summary=row["summary"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
