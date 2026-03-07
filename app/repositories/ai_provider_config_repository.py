from datetime import UTC, datetime

from app.models.ai_provider_config import AIProviderConfig
from app.repositories.base_repository import BaseRepository


class AIProviderConfigRepository(BaseRepository):
    TABLE = "ai_provider_configs"

    def upsert(
        self,
        provider: str,
        api_key: str,
        api_url: str,
        model: str,
        timeout_seconds: int = 60,
    ) -> None:
        with self.get_connection() as conn:
            now = datetime.now(UTC).isoformat()
            conn.execute(
                f"""
                INSERT INTO {self.TABLE} (
                    provider,
                    api_key,
                    api_url,
                    model,
                    timeout_seconds,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(provider)
                DO UPDATE SET
                    api_key = excluded.api_key,
                    api_url = excluded.api_url,
                    model = excluded.model,
                    timeout_seconds = excluded.timeout_seconds,
                    updated_at = excluded.updated_at
                """,
                (
                    provider,
                    api_key,
                    api_url,
                    model,
                    int(timeout_seconds),
                    now,
                ),
            )

    def get_by_provider(self, provider: str) -> AIProviderConfig | None:
        with self.get_connection() as conn:
            row = conn.execute(
                f"SELECT * FROM {self.TABLE} WHERE provider = ?",
                (provider,),
            ).fetchone()
            return self._to_model(row) if row else None

    def list_all(self) -> list[AIProviderConfig]:
        with self.get_connection() as conn:
            rows = conn.execute(f"SELECT * FROM {self.TABLE} ORDER BY provider ASC").fetchall()
            return [self._to_model(row) for row in rows]

    @staticmethod
    def _to_model(row) -> AIProviderConfig:
        return AIProviderConfig(
            provider=row["provider"],
            api_key=row["api_key"],
            api_url=row["api_url"],
            model=row["model"],
            timeout_seconds=int(row["timeout_seconds"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
