import json
from typing import Any

from app.services.ai_providers.ai_result import AIGenerationResult
from app.services.ai_providers.base_provider import BaseAIProvider


DEFAULT_MOCK_SECTIONS = {
    "summary": "Mock summary for development",
    "expansion": "Mock expansion for development",
    "inspirations": "",
    "guidance": "Mock guidance",
}


class MockProvider(BaseAIProvider):
    def __init__(
        self,
        sections: dict[str, Any] | None = None,
        content: str | None = None,
        error: Exception | None = None,
        provider_name: str = "mock",
        model: str | None = "mock-model",
        metadata: dict[str, Any] | None = None,
    ):
        self.sections = sections or dict(DEFAULT_MOCK_SECTIONS)
        self.content = content
        self.error = error
        self.provider_name = provider_name
        self.model = model
        self.metadata = metadata or {"mode": "offline"}

    def generate(self, prompt: str, context: dict[str, Any]) -> AIGenerationResult:
        _ = (prompt, context)
        if self.error is not None:
            raise self.error

        if self.content is None:
            content = json.dumps(self.sections, ensure_ascii=False)
            raw = dict(self.sections)
        else:
            content = self.content
            raw = None

        return AIGenerationResult(
            content=content,
            provider=self.provider_name,
            model=self.model,
            raw_response=raw,
            usage=None,
            metadata=self.metadata,
        )
