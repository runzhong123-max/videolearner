from datetime import UTC, datetime
from typing import Any, Optional

from app.models.prompt_template import PromptTemplate
from app.repositories.base_repository import BaseRepository


class PromptTemplateRepository(BaseRepository):
    TABLE = "prompt_templates"

    def create(
        self,
        scope: str,
        name: str,
        content: str,
        project_id: Optional[int] = None,
        session_id: Optional[int] = None,
        is_active: bool = True,
    ) -> int:
        now = datetime.now(UTC).isoformat()
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO prompt_templates (
                    scope,
                    project_id,
                    session_id,
                    name,
                    content,
                    is_active,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (scope, project_id, session_id, name, content, int(is_active), now, now),
            )
            return int(cursor.lastrowid)

    def get_by_id(self, template_id: int) -> Optional[PromptTemplate]:
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM prompt_templates WHERE id = ?",
                (template_id,),
            ).fetchone()
            return self._to_model(row) if row else None

    def list_by_scope(self, scope: str) -> list[PromptTemplate]:
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM prompt_templates WHERE scope = ? ORDER BY id DESC",
                (scope,),
            ).fetchall()
            return [self._to_model(r) for r in rows]

    def update(self, template_id: int, **fields: Any) -> bool:
        if not fields:
            return False

        allowed = {"name", "content", "is_active", "project_id", "session_id", "scope"}
        updates = []
        values = []
        for key, value in fields.items():
            if key in allowed:
                updates.append(f"{key} = ?")
                values.append(int(value) if key == "is_active" else value)

        if not updates:
            return False

        updates.append("updated_at = ?")
        values.append(datetime.now(UTC).isoformat())
        values.append(template_id)

        with self.get_connection() as conn:
            cursor = conn.execute(
                f"UPDATE {self.TABLE} SET {', '.join(updates)} WHERE id = ?",
                tuple(values),
            )
            return cursor.rowcount > 0

    def delete(self, template_id: int) -> bool:
        with self.get_connection() as conn:
            cursor = conn.execute("DELETE FROM prompt_templates WHERE id = ?", (template_id,))
            return cursor.rowcount > 0

    @staticmethod
    def _to_model(row) -> PromptTemplate:
        return PromptTemplate(
            id=row["id"],
            scope=row["scope"],
            project_id=row["project_id"],
            session_id=row["session_id"],
            name=row["name"],
            content=row["content"],
            is_active=bool(row["is_active"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

