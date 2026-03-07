import json
from typing import Any

from app.services.ai_providers.ai_result import AIGenerationResult
from app.services.ai_providers.base_provider import BaseAIProvider


DEFAULT_MOCK_SECTIONS = {
    "summary": "Mock summary for development",
    "expansion": "Mock expansion for development",
    "inspirations": "Mock inspirations:\n- 关键概念：先建立定义再做对比\n- 可行动作：用 3 句话复述本段内容",
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
        _ = prompt
        if self.error is not None:
            raise self.error

        mode = (context or {}).get("mode", "")
        if mode == "record_chat":
            content = self.content if self.content is not None else self._build_chat_reply(context)
            return AIGenerationResult(
                content=content,
                provider=self.provider_name,
                model=self.model,
                raw_response={"message": content},
                usage=None,
                metadata=self.metadata,
            )

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

    @staticmethod
    def _build_chat_reply(context: dict[str, Any]) -> str:
        context_text = str((context or {}).get("context_text", ""))
        user_prompt = str((context or {}).get("user_prompt", "")).strip()

        is_image = "record_type=image" in context_text
        has_ocr = "ocr_status=completed" in context_text and "ocr_text=" in context_text

        if is_image and has_ocr:
            return (
                "这是针对图片记录的模拟回答。已结合 OCR 文本给出解释，"
                "你可以继续追问具体术语或公式。"
            )
        if is_image:
            return "这是针对图片记录的模拟回答。当前 OCR 文本不足，可先执行 OCR 再提问。"

        if user_prompt:
            return f"这是针对该记录的模拟回答：{user_prompt[:80]}"
        return "这是针对该记录的模拟回答。"