from datetime import UTC, datetime
from typing import Any, Optional

from app.models.record_conversation import RecordConversation
from app.repositories.base_repository import BaseRepository


class RecordConversationRepository(BaseRepository):
    TABLE = "record_conversations"

    def create(
        self,
        record_id: int,
        session_id: int,
        project_id: int,
        title: str,
        provider: str = "",
        model_name: str = "",
    ) -> int:
        now = datetime.now(UTC).isoformat()
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO record_conversations (
                    record_id,
                    session_id,
                    project_id,
                    title,
                    provider,
                    model_name,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (record_id, session_id, project_id, title, provider, model_name, now, now),
            )
            return int(cursor.lastrowid)

    def get_by_id(self, conversation_id: int) -> Optional[RecordConversation]:
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM record_conversations WHERE id = ?",
                (conversation_id,),
            ).fetchone()
            return self._to_model(row) if row else None

    def get_by_record(self, record_id: int) -> Optional[RecordConversation]:
        with self.get_connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM record_conversations
                WHERE record_id = ?
                ORDER BY updated_at DESC, id DESC
                LIMIT 1
                """,
                (record_id,),
            ).fetchone()
            return self._to_model(row) if row else None

    def update(self, conversation_id: int, **fields: Any) -> bool:
        if not fields:
            return False

        allowed = {
            "title",
            "provider",
            "model_name",
        }

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
        values.append(conversation_id)

        with self.get_connection() as conn:
            cursor = conn.execute(
                f"UPDATE {self.TABLE} SET {', '.join(updates)} WHERE id = ?",
                tuple(values),
            )
            return cursor.rowcount > 0

    def delete(self, conversation_id: int) -> bool:
        with self.get_connection() as conn:
            cursor = conn.execute("DELETE FROM record_conversations WHERE id = ?", (conversation_id,))
            return cursor.rowcount > 0

    @staticmethod
    def _to_model(row) -> RecordConversation:
        return RecordConversation(
            id=row["id"],
            record_id=row["record_id"],
            session_id=row["session_id"],
            project_id=row["project_id"],
            title=row["title"],
            provider=row["provider"],
            model_name=row["model_name"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
