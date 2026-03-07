import json
from abc import ABC, abstractmethod
from typing import Any, Callable

import requests

from app.services.ai_errors import (
    AIConfigurationError,
    AINetworkError,
    AIProviderResponseError,
)
from app.services.ai_providers.ai_result import AIGenerationResult


class BaseAIProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str, context: dict[str, Any]) -> AIGenerationResult:
        """Generate content and return provider-agnostic result object."""


class HTTPChatCompletionsProvider(BaseAIProvider):
    provider_name = "http"

    def __init__(
        self,
        api_key: str | None,
        model: str | None,
        api_url: str | None,
        timeout_seconds: int = 60,
        request_sender: Callable[..., requests.Response] | None = None,
    ):
        self.api_key = (api_key or "").strip()
        self.model = (model or "").strip() or None
        self.api_url = (api_url or "").strip()
        self.timeout_seconds = timeout_seconds
        self.request_sender = request_sender or requests.post

    def generate(self, prompt: str, context: dict[str, Any]) -> AIGenerationResult:
        if not self.api_url:
            raise AIConfigurationError(f"{self.provider_name} provider 缺少 api_url 配置。")
        if not self.api_key:
            raise AIConfigurationError(f"{self.provider_name} provider 缺少 api_key 配置。")

        system_prompt = str(context.get("system_prompt", "")).strip()
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        request_body = {
            "model": self.model,
            "messages": messages,
        }

        try:
            response = self.request_sender(
                self.api_url,
                headers=headers,
                json=request_body,
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise AINetworkError(f"{self.provider_name} 网络请求失败：{exc}") from exc

        if response.status_code >= 400:
            detail = response.text.strip()
            if len(detail) > 300:
                detail = f"{detail[:300]}..."
            raise AIProviderResponseError(
                f"{self.provider_name} 接口错误（HTTP {response.status_code}）：{detail}"
            )

        try:
            raw = response.json()
        except ValueError as exc:
            raise AIProviderResponseError(f"{self.provider_name} 返回非 JSON 数据。") from exc

        if not isinstance(raw, dict):
            raise AIProviderResponseError(f"{self.provider_name} 返回结构非法，根节点必须是对象。")

        content = self._extract_content(raw)
        usage = raw.get("usage") if isinstance(raw.get("usage"), dict) else None
        model = raw.get("model") if isinstance(raw.get("model"), str) else self.model

        return AIGenerationResult(
            content=content,
            provider=self.provider_name,
            model=model,
            raw_response=raw,
            usage=usage,
            metadata={"api_url": self.api_url},
        )

    def _extract_content(self, raw: dict[str, Any]) -> str:
        direct = raw.get("content")
        if isinstance(direct, str) and direct.strip():
            return direct.strip()

        choices = raw.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                message = first.get("message")
                if isinstance(message, dict):
                    text = message.get("content")
                    if isinstance(text, str) and text.strip():
                        return text.strip()
                text = first.get("text")
                if isinstance(text, str) and text.strip():
                    return text.strip()

        # Some providers may return structured result directly.
        if "result" in raw and isinstance(raw["result"], dict):
            return json.dumps(raw["result"], ensure_ascii=False)
        if "summary" in raw or "expansion" in raw or "extension" in raw:
            return json.dumps(raw, ensure_ascii=False)

        raise AIProviderResponseError(f"{self.provider_name} 响应中缺少可用 content。")
