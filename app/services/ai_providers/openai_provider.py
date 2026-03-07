from app.services.ai_providers.base_provider import HTTPChatCompletionsProvider

DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"


class OpenAIProvider(HTTPChatCompletionsProvider):
    provider_name = "openai"

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
            model=model or DEFAULT_OPENAI_MODEL,
            api_url=api_url or DEFAULT_OPENAI_API_URL,
            timeout_seconds=timeout_seconds,
            request_sender=request_sender,
        )
