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
        project_id: int | None = None,
        note_type: str = "session_summary",
        title: str = "",
        content: str = "",
        ai_provider: str = "",
        ai_model: str = "",
        review_questions: str = "",
        key_points: str = "",
        follow_up_tasks: str = "",
        in_review_list: bool = False,
        is_key_note: bool = False,
        review_later: bool = False,
    ) -> int:
        now = datetime.now(UTC).isoformat()
        with self.get_connection() as conn:
            resolved_project_id = project_id
            if resolved_project_id is None:
                resolved_project_id = self._resolve_project_id_for_session(conn, session_id)

            cursor = conn.execute(
                """
                INSERT INTO notes (
                    project_id,
                    session_id,
                    note_type,
                    title,
                    content,
                    summary,
                    suggestions,
                    inspiration_refinement,
                    guidance,
                    ai_provider,
                    ai_model,
                    review_questions,
                    key_points,
                    follow_up_tasks,
                    in_review_list,
                    is_key_note,
                    review_later,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    resolved_project_id,
                    session_id,
                    note_type,
                    title,
                    content,
                    summary,
                    suggestions,
                    inspiration_refinement,
                    guidance,
                    ai_provider,
                    ai_model,
                    review_questions,
                    key_points,
                    follow_up_tasks,
                    int(in_review_list),
                    int(is_key_note),
                    int(review_later),
                    now,
                    now,
                ),
            )
            return int(cursor.lastrowid)

    def create_generated(
        self,
        project_id: int,
        session_id: int,
        note_type: str,
        title: str,
        content: str,
        summary: str,
        suggestions: str,
        inspiration_refinement: str = "",
        guidance: str = "",
        ai_provider: str = "",
        ai_model: str = "",
        review_questions: str = "",
        key_points: str = "",
        follow_up_tasks: str = "",
    ) -> int:
        return self.create(
            session_id=session_id,
            summary=summary,
            suggestions=suggestions,
            inspiration_refinement=inspiration_refinement,
            guidance=guidance,
            project_id=project_id,
            note_type=note_type,
            title=title,
            content=content,
            ai_provider=ai_provider,
            ai_model=ai_model,
            review_questions=review_questions,
            key_points=key_points,
            follow_up_tasks=follow_up_tasks,
        )

    def get_by_id(self, note_id: int) -> Optional[Note]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
            return self._to_model(row) if row else None

    def get_by_session(self, session_id: int, note_type: str | None = None) -> Optional[Note]:
        sql = "SELECT * FROM notes WHERE session_id = ?"
        params: list[Any] = [session_id]
        if note_type is not None:
            sql += " AND note_type = ?"
            params.append(note_type)
        sql += " ORDER BY id DESC LIMIT 1"

        with self.get_connection() as conn:
            row = conn.execute(sql, tuple(params)).fetchone()
            return self._to_model(row) if row else None

    def list_by_session(self, session_id: int, note_type: str | None = None, limit: int = 30) -> list[Note]:
        sql = "SELECT * FROM notes WHERE session_id = ?"
        params: list[Any] = [session_id]
        if note_type is not None:
            sql += " AND note_type = ?"
            params.append(note_type)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        with self.get_connection() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
            return [self._to_model(r) for r in rows]

    def count_by_session(self, session_id: int, note_type: str | None = None) -> int:
        sql = "SELECT COUNT(*) AS c FROM notes WHERE session_id = ?"
        params: list[Any] = [session_id]
        if note_type is not None:
            sql += " AND note_type = ?"
            params.append(note_type)

        with self.get_connection() as conn:
            row = conn.execute(sql, tuple(params)).fetchone()
            return int(row["c"] if row else 0)

    def list_by_project(self, project_id: int, limit: int = 50) -> list[Note]:
        with self.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM notes
                WHERE project_id = ?
                ORDER BY updated_at DESC, id DESC
                LIMIT ?
                """,
                (project_id, limit),
            ).fetchall()
            return [self._to_model(r) for r in rows]

    def list_latest_session_notes(
        self,
        project_id: int,
        exclude_session_id: int | None = None,
        limit: int = 3,
    ) -> list[Note]:
        with self.get_connection() as conn:
            if exclude_session_id is None:
                rows = conn.execute(
                    """
                    SELECT n.*
                    FROM notes n
                    INNER JOIN (
                        SELECT session_id, MAX(id) AS max_id
                        FROM notes
                        WHERE project_id = ?
                        GROUP BY session_id
                    ) latest ON n.id = latest.max_id
                    ORDER BY n.updated_at DESC, n.id DESC
                    LIMIT ?
                    """,
                    (project_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT n.*
                    FROM notes n
                    INNER JOIN (
                        SELECT session_id, MAX(id) AS max_id
                        FROM notes
                        WHERE project_id = ? AND session_id != ?
                        GROUP BY session_id
                    ) latest ON n.id = latest.max_id
                    ORDER BY n.updated_at DESC, n.id DESC
                    LIMIT ?
                    """,
                    (project_id, exclude_session_id, limit),
                ).fetchall()
            return [self._to_model(r) for r in rows]

    def get_latest_project_summary(self, project_id: int) -> Optional[Note]:
        with self.get_connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM notes
                WHERE project_id = ? AND note_type = 'project_summary'
                ORDER BY updated_at DESC, id DESC
                LIMIT 1
                """,
                (project_id,),
            ).fetchone()
            return self._to_model(row) if row else None

    def update(self, note_id: int, **fields: Any) -> bool:
        if not fields:
            return False

        allowed = {
            "project_id",
            "session_id",
            "note_type",
            "title",
            "content",
            "summary",
            "suggestions",
            "inspiration_refinement",
            "guidance",
            "ai_provider",
            "ai_model",
            "review_questions",
            "key_points",
            "follow_up_tasks",
            "in_review_list",
            "is_key_note",
            "review_later",
        }
        bool_fields = {
            "in_review_list",
            "is_key_note",
            "review_later",
        }
        updates = []
        values = []
        for key, value in fields.items():
            if key in allowed:
                updates.append(f"{key} = ?")
                values.append(int(value) if key in bool_fields else value)

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
    def _resolve_project_id_for_session(conn, session_id: int) -> int | None:
        row = conn.execute(
            "SELECT project_id FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        if row is None:
            return None
        return row["project_id"]

    @staticmethod
    def _to_model(row) -> Note:
        keys = set(row.keys())
        return Note(
            id=row["id"],
            project_id=row["project_id"] if "project_id" in keys else None,
            session_id=row["session_id"],
            note_type=row["note_type"] if "note_type" in keys else "session_summary",
            title=row["title"] if "title" in keys else "",
            content=row["content"] if "content" in keys else "",
            summary=row["summary"],
            suggestions=row["suggestions"],
            inspiration_refinement=row["inspiration_refinement"],
            guidance=row["guidance"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            ai_provider=row["ai_provider"] if "ai_provider" in keys else "",
            ai_model=row["ai_model"] if "ai_model" in keys else "",
            review_questions=row["review_questions"] if "review_questions" in keys else "",
            key_points=row["key_points"] if "key_points" in keys else "",
            follow_up_tasks=row["follow_up_tasks"] if "follow_up_tasks" in keys else "",
            in_review_list=bool(row["in_review_list"]) if "in_review_list" in keys else False,
            is_key_note=bool(row["is_key_note"]) if "is_key_note" in keys else False,
            review_later=bool(row["review_later"]) if "review_later" in keys else False,
        )
