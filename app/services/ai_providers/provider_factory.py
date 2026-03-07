from app.config import AIProviderSettings, load_ai_provider_settings
from app.services.ai_errors import AIConfigurationError
from app.services.ai_providers.base_provider import BaseAIProvider
from app.services.ai_providers.deepseek_provider import DeepSeekProvider
from app.services.ai_providers.glm_provider import GLMProvider
from app.services.ai_providers.mock_provider import MockProvider
from app.services.ai_providers.openai_provider import OpenAIProvider


class AIProviderFactory:
    @staticmethod
    def create_provider(settings: AIProviderSettings | None = None) -> BaseAIProvider:
        settings = settings or load_ai_provider_settings()

        provider_name = settings.provider.strip().lower()
        legacy_present = bool(settings.legacy_api_key or settings.legacy_api_url)
        if settings.provider_from_env is None and provider_name == "mock" and legacy_present:
            provider_name = "openai"

        if provider_name == "openai":
            return AIProviderFactory.create_provider_by_name(
                provider_name=provider_name,
                api_key=settings.openai_api_key or settings.legacy_api_key,
                api_url=settings.openai_api_url or settings.legacy_api_url,
                model=settings.openai_model or settings.legacy_model,
            )

        if provider_name == "deepseek":
            return AIProviderFactory.create_provider_by_name(
                provider_name=provider_name,
                api_key=settings.deepseek_api_key,
                api_url=settings.deepseek_api_url,
                model=settings.deepseek_model,
            )

        if provider_name == "glm":
            return AIProviderFactory.create_provider_by_name(
                provider_name=provider_name,
                api_key=settings.glm_api_key,
                api_url=settings.glm_api_url,
                model=settings.glm_model,
            )

        return AIProviderFactory.create_provider_by_name(provider_name=provider_name)

    @staticmethod
    def create_provider_by_name(
        provider_name: str,
        api_key: str | None = None,
        api_url: str | None = None,
        model: str | None = None,
        timeout_seconds: int = 60,
    ) -> BaseAIProvider:
        name = (provider_name or "").strip().lower()

        if name == "mock":
            return MockProvider()

        if name == "openai":
            return OpenAIProvider(
                api_key=api_key,
                api_url=api_url,
                model=model,
                timeout_seconds=timeout_seconds,
            )

        if name == "deepseek":
            return DeepSeekProvider(
                api_key=api_key,
                api_url=api_url,
                model=model,
                timeout_seconds=timeout_seconds,
            )

        if name == "glm":
            return GLMProvider(
                api_key=api_key,
                api_url=api_url,
                model=model,
                timeout_seconds=timeout_seconds,
            )

        raise AIConfigurationError(
            f"不支持的 AI_PROVIDER={name}。可选值：mock/openai/deepseek/glm"
        )
