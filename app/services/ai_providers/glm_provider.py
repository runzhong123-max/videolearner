from app.services.ai_providers.base_provider import HTTPChatCompletionsProvider

DEFAULT_GLM_MODEL = "glm-4-flash"
DEFAULT_GLM_API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"


class GLMProvider(HTTPChatCompletionsProvider):
    provider_name = "glm"

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
            model=model or DEFAULT_GLM_MODEL,
            api_url=api_url or DEFAULT_GLM_API_URL,
            timeout_seconds=timeout_seconds,
            request_sender=request_sender,
        )
