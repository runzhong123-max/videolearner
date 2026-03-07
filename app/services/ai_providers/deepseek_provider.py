from app.services.ai_providers.base_provider import HTTPChatCompletionsProvider

DEFAULT_DEEPSEEK_MODEL = "deepseek-chat"
DEFAULT_DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"


class DeepSeekProvider(HTTPChatCompletionsProvider):
    provider_name = "deepseek"

    def __init__(
        self,
        api_key: str | None,
        model: str | None = None,
        api_url: str | None = None,
        timeout_seconds: int = 60,
        request_sender=None,
    ):
        super().__init__(
            api_key=api_key,
            model=model or DEFAULT_DEEPSEEK_MODEL,
            api_url=api_url or DEFAULT_DEEPSEEK_API_URL,
            timeout_seconds=timeout_seconds,
            request_sender=request_sender,
        )
