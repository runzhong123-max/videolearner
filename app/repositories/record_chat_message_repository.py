from datetime import UTC, datetime
from typing import Optional

from app.models.record_chat_message import RecordChatMessage
from app.repositories.base_repository import BaseRepository


class RecordChatMessageRepository(BaseRepository):
    TABLE = "record_chat_messages"

    def create(
        self,
        conversation_id: int,
        role: str,
        content: str,
        response_id: str = "",
        metadata_json: str = "{}",
        image_path: str = "",
    ) -> int:
        now = datetime.now(UTC).isoformat()
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO record_chat_messages (
                    conversation_id,
                    role,
                    content,
                    created_at,
                    response_id,
                    metadata_json,
                    image_path
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (conversation_id, role, content, now, response_id, metadata_json, image_path),
            )
            return int(cursor.lastrowid)

    def get_by_id(self, message_id: int) -> Optional[RecordChatMessage]:
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM record_chat_messages WHERE id = ?",
                (message_id,),
            ).fetchone()
            return self._to_model(row) if row else None

    def list_by_conversation(self, conversation_id: int, limit: int = 100) -> list[RecordChatMessage]:
        with self.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM record_chat_messages
                WHERE conversation_id = ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (conversation_id, limit),
            ).fetchall()
            return [self._to_model(row) for row in rows]

    def list_recent_by_conversation(self, conversation_id: int, limit: int = 8) -> list[RecordChatMessage]:
        with self.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM record_chat_messages
                WHERE conversation_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (conversation_id, limit),
            ).fetchall()
        items = [self._to_model(row) for row in rows]
        items.reverse()
        return items

    def delete(self, message_id: int) -> bool:
        with self.get_connection() as conn:
            cursor = conn.execute("DELETE FROM record_chat_messages WHERE id = ?", (message_id,))
            return cursor.rowcount > 0

    @staticmethod
    def _to_model(row) -> RecordChatMessage:
        return RecordChatMessage(
            id=row["id"],
            conversation_id=row["conversation_id"],
            role=row["role"],
            content=row["content"],
            created_at=datetime.fromisoformat(row["created_at"]),
            response_id=row["response_id"],
            metadata_json=row["metadata_json"],
            image_path=row["image_path"],
        )
