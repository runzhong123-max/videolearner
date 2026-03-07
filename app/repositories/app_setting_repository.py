from datetime import UTC, datetime

from app.repositories.base_repository import BaseRepository


class AppSettingRepository(BaseRepository):
    TABLE = "app_settings"

    def get(self, key: str) -> str | None:
        with self.get_connection() as conn:
            row = conn.execute(
                f"SELECT value FROM {self.TABLE} WHERE key = ?",
                (key,),
            ).fetchone()
            if row is None:
                return None
            return str(row["value"])

    def set(self, key: str, value: str) -> None:
        with self.get_connection() as conn:
            now = datetime.now(UTC).isoformat()
            conn.execute(
                f"""
                INSERT INTO {self.TABLE} (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key)
                DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (key, value, now),
            )
