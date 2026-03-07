from dataclasses import dataclass

from app.config import load_ai_provider_settings
from app.repositories.ai_feature_route_repository import AIFeatureRouteRepository
from app.repositories.ai_provider_config_repository import AIProviderConfigRepository
from app.repositories.app_setting_repository import AppSettingRepository
from app.services.ai_errors import AIConfigurationError
from app.services.ai_providers.base_provider import BaseAIProvider
from app.services.ai_providers.provider_factory import AIProviderFactory

SUPPORTED_AI_PROVIDERS = ("mock", "openai", "deepseek", "glm")

ROUTE_SESSION_NOTE_PROVIDER = "session_note_provider"
ROUTE_RECORD_CHAT_PROVIDER = "record_chat_provider"
ROUTE_IMAGE_CHAT_PROVIDER = "image_chat_provider"
ROUTE_OCR_PROVIDER = "ocr_provider"
ROUTE_PLANNING_PROVIDER = "planning_provider"

ROUTE_KEYS = (
    ROUTE_SESSION_NOTE_PROVIDER,
    ROUTE_RECORD_CHAT_PROVIDER,
    ROUTE_IMAGE_CHAT_PROVIDER,
    ROUTE_OCR_PROVIDER,
    ROUTE_PLANNING_PROVIDER,
)

DEFAULT_PROVIDER_SETTING_KEY = "ai.default_provider"


@dataclass
class ProviderConfigState:
    provider: str
    api_key: str
    api_url: str
    model: str
    timeout_seconds: int


@dataclass
class AISettingsState:
    default_provider: str
    provider_configs: dict[str, ProviderConfigState]
    feature_routes: dict[str, str]


@dataclass
class ProviderConnectionTestResult:
    success: bool
    message: str
    provider: str
    model: str | None


class AISettingsService:
    def __init__(
        self,
        app_setting_repository: AppSettingRepository,
        provider_config_repository: AIProviderConfigRepository,
        feature_route_repository: AIFeatureRouteRepository,
    ):
        self.app_setting_repository = app_setting_repository
        self.provider_config_repository = provider_config_repository
        self.feature_route_repository = feature_route_repository

    def load_settings(self) -> AISettingsState:
        env = load_ai_provider_settings()

        default_provider = self.app_setting_repository.get(DEFAULT_PROVIDER_SETTING_KEY)
        default_provider = (default_provider or env.provider or "mock").strip().lower()
        try:
            default_provider = self._normalize_provider(default_provider)
        except AIConfigurationError:
            default_provider = "mock"

        provider_configs = {name: self._build_provider_config(name, env) for name in SUPPORTED_AI_PROVIDERS}
        for saved in self.provider_config_repository.list_all():
            if saved.provider not in provider_configs:
                continue
            provider_configs[saved.provider] = ProviderConfigState(
                provider=saved.provider,
                api_key=saved.api_key,
                api_url=saved.api_url,
                model=saved.model,
                timeout_seconds=saved.timeout_seconds,
            )

        routes = {key: "" for key in ROUTE_KEYS}
        for saved_route in self.feature_route_repository.list_all():
            if saved_route.feature_name not in routes:
                continue
            try:
                routes[saved_route.feature_name] = self._normalize_optional_provider(saved_route.provider)
            except AIConfigurationError:
                routes[saved_route.feature_name] = ""

        return AISettingsState(
            default_provider=default_provider,
            provider_configs=provider_configs,
            feature_routes=routes,
        )

    def save_default_provider(self, provider: str) -> None:
        normalized = self._normalize_provider(provider)
        self.app_setting_repository.set(DEFAULT_PROVIDER_SETTING_KEY, normalized)

    def save_provider_config(
        self,
        provider: str,
        api_key: str,
        api_url: str,
        model: str,
        timeout_seconds: int = 60,
    ) -> None:
        normalized_provider = self._normalize_provider(provider)
        self.provider_config_repository.upsert(
            provider=normalized_provider,
            api_key=(api_key or "").strip(),
            api_url=(api_url or "").strip(),
            model=(model or "").strip(),
            timeout_seconds=max(1, int(timeout_seconds)),
        )

    def save_feature_route(self, feature_name: str, provider: str) -> None:
        if feature_name not in ROUTE_KEYS:
            raise AIConfigurationError(f"不支持的功能路由：{feature_name}")
        normalized = self._normalize_optional_provider(provider)
        self.feature_route_repository.upsert(feature_name=feature_name, provider=normalized)

    def resolve_provider_name(self, feature_name: str) -> str:
        settings = self.load_settings()
        route_provider = settings.feature_routes.get(feature_name, "")
        if route_provider:
            return route_provider
        return settings.default_provider

    def build_provider(self, provider_name: str) -> BaseAIProvider:
        settings = self.load_settings()
        normalized = self._normalize_provider(provider_name)
        config = settings.provider_configs[normalized]

        return AIProviderFactory.create_provider_by_name(
            provider_name=normalized,
            api_key=config.api_key,
            api_url=config.api_url,
            model=config.model,
            timeout_seconds=config.timeout_seconds,
        )

    def test_provider_connection(self, provider_name: str) -> ProviderConnectionTestResult:
        normalized = self._normalize_provider(provider_name)
        if normalized == "mock":
            provider = self.build_provider("mock")
            result = provider.generate(
                prompt="ping",
                context={"system_prompt": "connectivity test", "mode": "connectivity_test"},
            )
            return ProviderConnectionTestResult(
                success=True,
                message="Mock provider 可用（离线模式）。",
                provider=result.provider,
                model=result.model,
            )

        try:
            provider = self.build_provider(normalized)
            result = provider.generate(
                prompt="请回复：ok",
                context={"system_prompt": "这是连通性测试，请简短回复。", "mode": "connectivity_test"},
            )
        except AIConfigurationError as exc:
            return ProviderConnectionTestResult(
                success=False,
                message=f"配置错误：{exc}",
                provider=normalized,
                model=None,
            )
        except Exception as exc:
            return ProviderConnectionTestResult(
                success=False,
                message=f"连接失败：{exc}",
                provider=normalized,
                model=None,
            )

        content_ok = bool((result.content or "").strip())
        if not content_ok:
            return ProviderConnectionTestResult(
                success=False,
                message="连接成功但返回内容为空。",
                provider=result.provider,
                model=result.model,
            )

        return ProviderConnectionTestResult(
            success=True,
            message="连接成功。",
            provider=result.provider,
            model=result.model,
        )

    def _build_provider_config(self, provider_name: str, env_settings) -> ProviderConfigState:
        if provider_name == "openai":
            return ProviderConfigState(
                provider="openai",
                api_key=env_settings.openai_api_key or env_settings.legacy_api_key or "",
                api_url=env_settings.openai_api_url or env_settings.legacy_api_url or "",
                model=env_settings.openai_model or env_settings.legacy_model or "",
                timeout_seconds=60,
            )

        if provider_name == "deepseek":
            return ProviderConfigState(
                provider="deepseek",
                api_key=env_settings.deepseek_api_key or "",
                api_url=env_settings.deepseek_api_url or "",
                model=env_settings.deepseek_model or "",
                timeout_seconds=60,
            )

        if provider_name == "glm":
            return ProviderConfigState(
                provider="glm",
                api_key=env_settings.glm_api_key or "",
                api_url=env_settings.glm_api_url or "",
                model=env_settings.glm_model or "",
                timeout_seconds=60,
            )

        return ProviderConfigState(
            provider="mock",
            api_key="",
            api_url="",
            model="",
            timeout_seconds=60,
        )

    @staticmethod
    def _normalize_provider(provider: str) -> str:
        name = (provider or "").strip().lower()
        if name not in SUPPORTED_AI_PROVIDERS:
            raise AIConfigurationError(f"不支持的 provider：{provider}")
        return name

    @staticmethod
    def _normalize_optional_provider(provider: str) -> str:
        name = (provider or "").strip().lower()
        if not name:
            return ""
        if name not in SUPPORTED_AI_PROVIDERS:
            raise AIConfigurationError(f"不支持的 provider：{provider}")
        return name

