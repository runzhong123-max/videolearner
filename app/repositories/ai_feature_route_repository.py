from datetime import UTC, datetime

from app.models.ai_feature_route import AIFeatureRoute
from app.repositories.base_repository import BaseRepository


class AIFeatureRouteRepository(BaseRepository):
    TABLE = "ai_feature_routes"

    def upsert(self, feature_name: str, provider: str) -> None:
        with self.get_connection() as conn:
            now = datetime.now(UTC).isoformat()
            conn.execute(
                f"""
                INSERT INTO {self.TABLE} (feature_name, provider, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(feature_name)
                DO UPDATE SET
                    provider = excluded.provider,
                    updated_at = excluded.updated_at
                """,
                (feature_name, provider, now),
            )

    def get_by_feature(self, feature_name: str) -> AIFeatureRoute | None:
        with self.get_connection() as conn:
            row = conn.execute(
                f"SELECT * FROM {self.TABLE} WHERE feature_name = ?",
                (feature_name,),
            ).fetchone()
            return self._to_model(row) if row else None

    def list_all(self) -> list[AIFeatureRoute]:
        with self.get_connection() as conn:
            rows = conn.execute(f"SELECT * FROM {self.TABLE} ORDER BY feature_name ASC").fetchall()
            return [self._to_model(row) for row in rows]

    @staticmethod
    def _to_model(row) -> AIFeatureRoute:
        return AIFeatureRoute(
            feature_name=row["feature_name"],
            provider=row["provider"],
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
