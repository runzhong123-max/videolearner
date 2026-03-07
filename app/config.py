from pathlib import Path
from dataclasses import dataclass
import os

BASE_DIR = Path(__file__).resolve().parent.parent
DB_DIR = BASE_DIR / "data"
DB_PATH = DB_DIR / "videolearner.db"
PROJECTS_DATA_DIR = DB_DIR / "projects"
EXPORT_DIR = BASE_DIR / "exports"
ASSET_DIR = BASE_DIR / "assets"


@dataclass(frozen=True)
class AIProviderSettings:
    provider: str
    provider_from_env: str | None
    openai_api_key: str | None
    openai_api_url: str | None
    openai_model: str | None
    deepseek_api_key: str | None
    deepseek_api_url: str | None
    deepseek_model: str | None
    glm_api_key: str | None
    glm_api_url: str | None
    glm_model: str | None
    legacy_api_key: str | None
    legacy_api_url: str | None
    legacy_model: str | None


def _clean_env(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


def load_ai_provider_settings() -> AIProviderSettings:
    provider_from_env = _clean_env("AI_PROVIDER")
    provider = (provider_from_env or "mock").lower()
    return AIProviderSettings(
        provider=provider,
        provider_from_env=provider_from_env.lower() if provider_from_env else None,
        openai_api_key=_clean_env("OPENAI_API_KEY"),
        openai_api_url=_clean_env("OPENAI_API_URL"),
        openai_model=_clean_env("OPENAI_MODEL"),
        deepseek_api_key=_clean_env("DEEPSEEK_API_KEY"),
        deepseek_api_url=_clean_env("DEEPSEEK_API_URL"),
        deepseek_model=_clean_env("DEEPSEEK_MODEL"),
        glm_api_key=_clean_env("GLM_API_KEY"),
        glm_api_url=_clean_env("GLM_API_URL"),
        glm_model=_clean_env("GLM_MODEL"),
        legacy_api_key=_clean_env("VIDEOLEARNER_AI_API_KEY"),
        legacy_api_url=_clean_env("VIDEOLEARNER_AI_API_URL"),
        legacy_model=_clean_env("VIDEOLEARNER_AI_MODEL"),
    )
