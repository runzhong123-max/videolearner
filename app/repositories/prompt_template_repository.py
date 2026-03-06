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
        content: str = "",
        project_id: Optional[int] = None,
        session_id: Optional[int] = None,
        system_prompt: str = "",
        user_prompt: str = "",
        is_active: bool = True,
    ) -> int:
        now = datetime.now(UTC).isoformat()
        resolved_system_prompt = system_prompt if system_prompt else content
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO prompt_templates (
                    scope,
                    project_id,
                    session_id,
                    name,
                    content,
                    system_prompt,
                    user_prompt,
                    is_active,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    scope,
                    project_id,
                    session_id,
                    name,
                    content,
                    resolved_system_prompt,
                    user_prompt,
                    int(is_active),
                    now,
                    now,
                ),
            )
            return int(cursor.lastrowid)

    def get_by_id(self, template_id: int) -> Optional[PromptTemplate]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM prompt_templates WHERE id = ?", (template_id,)).fetchone()
            return self._to_model(row) if row else None

    def get_by_scope_target(
        self,
        scope: str,
        project_id: Optional[int] = None,
        session_id: Optional[int] = None,
    ) -> Optional[PromptTemplate]:
        sql = "SELECT * FROM prompt_templates WHERE scope = ?"
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

        allowed = {
            "name",
            "content",
            "system_prompt",
            "user_prompt",
            "is_active",
            "project_id",
            "session_id",
            "scope",
        }
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

    def upsert_scope_target(
        self,
        scope: str,
        name: str,
        system_prompt: str,
        user_prompt: str,
        project_id: Optional[int] = None,
        session_id: Optional[int] = None,
    ) -> PromptTemplate:
        existing = self.get_by_scope_target(scope=scope, project_id=project_id, session_id=session_id)
        if existing is None:
            template_id = self.create(
                scope=scope,
                name=name,
                content=system_prompt,
                project_id=project_id,
                session_id=session_id,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                is_active=True,
            )
            created = self.get_by_id(template_id)
            if created is None:
                raise RuntimeError("Failed to load created prompt template")
            return created

        updated = self.update(
            existing.id,
            name=name,
            content=system_prompt,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            scope=scope,
            project_id=project_id,
            session_id=session_id,
            is_active=True,
        )
        if not updated:
            raise RuntimeError("Failed to update prompt template")

        refreshed = self.get_by_id(existing.id)
        if refreshed is None:
            raise RuntimeError("Failed to load updated prompt template")
        return refreshed

    def delete(self, template_id: int) -> bool:
        with self.get_connection() as conn:
            cursor = conn.execute("DELETE FROM prompt_templates WHERE id = ?", (template_id,))
            return cursor.rowcount > 0

    @staticmethod
    def _to_model(row) -> PromptTemplate:
        system_prompt = row["system_prompt"] if "system_prompt" in row.keys() else row["content"]
        user_prompt = row["user_prompt"] if "user_prompt" in row.keys() else ""
        return PromptTemplate(
            id=row["id"],
            scope=row["scope"],
            project_id=row["project_id"],
            session_id=row["session_id"],
            name=row["name"],
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
