from dataclasses import dataclass

from app.services.ai_errors import AIContractError
from app.services.ai_prompt_builder import AIPromptBuildInput, PromptBuilder
from app.services.ai_provider_resolver import AIProviderResolver
from app.services.ai_providers.ai_result import AIGenerationResult
from app.services.ai_providers.base_provider import BaseAIProvider
from app.services.ai_providers.provider_factory import AIProviderFactory
from app.services.ai_response_normalizer import AIResponseNormalizer


@dataclass
class AIGenerationRequest:
    system_prompt: str
    user_prompt: str
    context_text: str
    output_options: dict[str, bool]


@dataclass
class AIChatRequest:
    system_prompt: str
    user_prompt: str
    context_text: str


class AIService:
    """Coordinates prompt building, provider call and response normalization."""

    def __init__(
        self,
        provider: BaseAIProvider | None = None,
        prompt_builder: PromptBuilder | None = None,
        response_normalizer: AIResponseNormalizer | None = None,
        provider_resolver: AIProviderResolver | None = None,
    ):
        self.provider = provider
        self.provider_resolver = provider_resolver
        self.default_provider = None if provider or provider_resolver else AIProviderFactory.create_provider()
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.response_normalizer = response_normalizer or AIResponseNormalizer()
        self._last_result: AIGenerationResult | None = None

    def generate_sections(
        self,
        request: AIGenerationRequest,
        feature_name: str = "session_note_provider",
    ) -> dict[str, str]:
        prompt = self.prompt_builder.build(
            AIPromptBuildInput(
                system_prompt=request.system_prompt,
                user_prompt=request.user_prompt,
                context_text=request.context_text,
                output_options=request.output_options,
            )
        )

        provider = self._resolve_provider(feature_name)
        result = provider.generate(
            prompt=prompt,
            context={
                "system_prompt": request.system_prompt.strip(),
                "user_prompt": request.user_prompt.strip(),
                "context_text": request.context_text,
                "output_options": dict(request.output_options),
                "feature": feature_name,
            },
        )
        self._last_result = result
        return self.response_normalizer.normalize(result, request.output_options)

    def generate_chat_reply(
        self,
        request: AIChatRequest,
        feature_name: str = "record_chat_provider",
    ) -> AIGenerationResult:
        prompt = self._build_chat_prompt(request)
        provider = self._resolve_provider(feature_name)
        result = provider.generate(
            prompt=prompt,
            context={
                "system_prompt": request.system_prompt.strip(),
                "user_prompt": request.user_prompt.strip(),
                "context_text": request.context_text,
                "mode": "record_chat",
                "feature": feature_name,
            },
        )
        self._last_result = result
        if not (result.content or "").strip():
            raise AIContractError("AI 对话返回为空。")
        return result

    def get_last_result(self) -> AIGenerationResult | None:
        return self._last_result

    def _resolve_provider(self, feature_name: str) -> BaseAIProvider:
        if self.provider is not None:
            return self.provider

        if self.provider_resolver is not None:
            return self.provider_resolver.resolve_provider(feature_name)

        if self.default_provider is None:
            self.default_provider = AIProviderFactory.create_provider()
        return self.default_provider

    @staticmethod
    def _build_chat_prompt(request: AIChatRequest) -> str:
        return (
            f"{request.user_prompt.strip()}\n\n"
            "请围绕当前记录进行回答，优先引用记录内容与对话历史。"
            "回答应简洁、可执行。\n\n"
            "以下是上下文：\n"
            f"{request.context_text}"
        )
