from datetime import UTC, datetime
from typing import Any, Optional

from app.models.project import Project
from app.repositories.base_repository import BaseRepository


class ProjectRepository(BaseRepository):
    TABLE = "projects"

    def create(
        self,
        name: str,
        description: str = "",
        source: str = "",
        goal: str = "",
        tags: str = "",
        default_prompt: str = "",
    ) -> int:
        now = datetime.now(UTC).isoformat()
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO projects (
                    name,
                    description,
                    source,
                    goal,
                    tags,
                    default_prompt,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (name, description, source, goal, tags, default_prompt, now, now),
            )
            return int(cursor.lastrowid)

    def get_by_id(self, project_id: int) -> Optional[Project]:
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
            if row is None:
                return None
            return self._to_model(row)

    def list_all(self) -> list[Project]:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM projects ORDER BY id DESC").fetchall()
            return [self._to_model(r) for r in rows]

    def update(self, project_id: int, **fields: Any) -> bool:
        if not fields:
            return False

        allowed = {"name", "description", "source", "goal", "tags", "default_prompt"}
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
        values.append(project_id)

        with self.get_connection() as conn:
            cursor = conn.execute(
                f"UPDATE {self.TABLE} SET {', '.join(updates)} WHERE id = ?",
                tuple(values),
            )
            return cursor.rowcount > 0

    def delete(self, project_id: int) -> bool:
        with self.get_connection() as conn:
            cursor = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            return cursor.rowcount > 0

    @staticmethod
    def _to_model(row) -> Project:
        return Project(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            source=row["source"],
            goal=row["goal"],
            tags=row["tags"],
            default_prompt=row["default_prompt"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
