from app.services.ai_providers.base_provider import BaseAIProvider
from app.services.ai_settings_service import (
    AISettingsService,
    ROUTE_RECORD_CHAT_PROVIDER,
    ROUTE_SESSION_NOTE_PROVIDER,
)


class AIProviderResolver:
    def __init__(self, ai_settings_service: AISettingsService):
        self.ai_settings_service = ai_settings_service

    def resolve_provider_name(self, feature_name: str) -> str:
        route_key = self._normalize_feature_name(feature_name)
        return self.ai_settings_service.resolve_provider_name(route_key)

    def resolve_provider(self, feature_name: str) -> BaseAIProvider:
        provider_name = self.resolve_provider_name(feature_name)
        return self.ai_settings_service.build_provider(provider_name)

    @staticmethod
    def _normalize_feature_name(feature_name: str) -> str:
        name = (feature_name or "").strip().lower()
        if name in {"session_note", "generate_session_note", ROUTE_SESSION_NOTE_PROVIDER}:
            return ROUTE_SESSION_NOTE_PROVIDER
        if name in {"record_chat", ROUTE_RECORD_CHAT_PROVIDER}:
            return ROUTE_RECORD_CHAT_PROVIDER
        return name
