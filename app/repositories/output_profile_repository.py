from datetime import UTC, datetime
from typing import Any, Optional

from app.models.output_profile import OutputProfile
from app.repositories.base_repository import BaseRepository


class OutputProfileRepository(BaseRepository):
    TABLE = "output_profiles"

    def create(
        self,
        name: str,
        scope: str,
        project_id: Optional[int] = None,
        session_id: Optional[int] = None,
        summary: bool = True,
        extension: bool = True,
        insight: bool = False,
        history_link: bool = False,
        gap_analysis: bool = False,
        review_questions: bool = False,
        homework: bool = False,
        expression_notes: bool = False,
        evaluation: bool = False,
    ) -> int:
        now = datetime.now(UTC).isoformat()
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO output_profiles (
                    name,
                    scope,
                    project_id,
                    session_id,
                    summary,
                    extension,
                    insight,
                    history_link,
                    gap_analysis,
                    review_questions,
                    homework,
                    expression_notes,
                    evaluation,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    scope,
                    project_id,
                    session_id,
                    int(summary),
                    int(extension),
                    int(insight),
                    int(history_link),
                    int(gap_analysis),
                    int(review_questions),
                    int(homework),
                    int(expression_notes),
                    int(evaluation),
                    now,
                    now,
                ),
            )
            return int(cursor.lastrowid)

    def get_by_id(self, profile_id: int) -> Optional[OutputProfile]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM output_profiles WHERE id = ?", (profile_id,)).fetchone()
            return self._to_model(row) if row else None

    def get_by_scope_target(
        self,
        scope: str,
        project_id: Optional[int] = None,
        session_id: Optional[int] = None,
    ) -> Optional[OutputProfile]:
        sql = "SELECT * FROM output_profiles WHERE scope = ?"
        params: list[Any] = [scope]

        if project_id is None:
            sql += " AND project_id IS NULL"
        else:
            sql += " AND project_id = ?"
            params.append(project_id)

        if session_id is None:
            sql += " AND session_id IS NULL"
        else:
            sql += " AND session_id = ?"
            params.append(session_id)

        sql += " ORDER BY id DESC LIMIT 1"

        with self.get_connection() as conn:
            row = conn.execute(sql, tuple(params)).fetchone()
            return self._to_model(row) if row else None

    def update(self, profile_id: int, **fields: Any) -> bool:
        if not fields:
            return False

        allowed = {
            "name",
            "scope",
            "project_id",
            "session_id",
            "summary",
            "extension",
            "insight",
            "history_link",
            "gap_analysis",
            "review_questions",
            "homework",
            "expression_notes",
            "evaluation",
        }
        bool_fields = {
            "summary",
            "extension",
            "insight",
            "history_link",
            "gap_analysis",
            "review_questions",
            "homework",
            "expression_notes",
            "evaluation",
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
        values.append(profile_id)

        with self.get_connection() as conn:
            cursor = conn.execute(
                f"UPDATE {self.TABLE} SET {', '.join(updates)} WHERE id = ?",
                tuple(values),
            )
            return cursor.rowcount > 0

    def upsert_scope_target(
        self,
        name: str,
        scope: str,
        project_id: Optional[int],
        session_id: Optional[int],
        summary: bool,
        extension: bool,
        insight: bool,
        history_link: bool,
        gap_analysis: bool,
        review_questions: bool,
        homework: bool,
        expression_notes: bool,
        evaluation: bool,
    ) -> OutputProfile:
        existing = self.get_by_scope_target(scope=scope, project_id=project_id, session_id=session_id)
        if existing is None:
            profile_id = self.create(
                name=name,
                scope=scope,
                project_id=project_id,
                session_id=session_id,
                summary=summary,
                extension=extension,
                insight=insight,
                history_link=history_link,
                gap_analysis=gap_analysis,
                review_questions=review_questions,
                homework=homework,
                expression_notes=expression_notes,
                evaluation=evaluation,
            )
            created = self.get_by_id(profile_id)
            if created is None:
                raise RuntimeError("Failed to load created output profile")
            return created

        updated = self.update(
            existing.id,
            name=name,
            scope=scope,
            project_id=project_id,
            session_id=session_id,
            summary=summary,
            extension=extension,
            insight=insight,
            history_link=history_link,
            gap_analysis=gap_analysis,
            review_questions=review_questions,
            homework=homework,
            expression_notes=expression_notes,
            evaluation=evaluation,
        )
        if not updated:
            raise RuntimeError("Failed to update output profile")

        refreshed = self.get_by_id(existing.id)
        if refreshed is None:
            raise RuntimeError("Failed to load updated output profile")
        return refreshed

    def delete(self, profile_id: int) -> bool:
        with self.get_connection() as conn:
            cursor = conn.execute("DELETE FROM output_profiles WHERE id = ?", (profile_id,))
            return cursor.rowcount > 0

    @staticmethod
    def _to_model(row) -> OutputProfile:
        return OutputProfile(
            id=row["id"],
            name=row["name"],
            scope=row["scope"],
            project_id=row["project_id"],
            session_id=row["session_id"],
            summary=bool(row["summary"]),
            extension=bool(row["extension"]),
            insight=bool(row["insight"]),
            history_link=bool(row["history_link"]),
            gap_analysis=bool(row["gap_analysis"]),
            review_questions=bool(row["review_questions"]),
            homework=bool(row["homework"]),
            expression_notes=bool(row["expression_notes"]),
            evaluation=bool(row["evaluation"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
