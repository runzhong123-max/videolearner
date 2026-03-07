import unittest

import requests

from app.config import AIProviderSettings
from app.services.ai_errors import (
    AIConfigurationError,
    AIContractError,
    AINetworkError,
)
from app.services.ai_providers.ai_result import AIGenerationResult
from app.services.ai_providers.base_provider import BaseAIProvider
from app.services.ai_providers.mock_provider import MockProvider
from app.services.ai_providers.openai_provider import OpenAIProvider
from app.services.ai_providers.provider_factory import AIProviderFactory
from app.services.ai_service import AIGenerationRequest, AIService


class DummyProvider(BaseAIProvider):
    def __init__(self, content: str):
        self.content = content

    def generate(self, prompt: str, context: dict) -> AIGenerationResult:
        _ = (prompt, context)
        return AIGenerationResult(
            content=self.content,
            provider="dummy",
            model="dummy-model",
            raw_response=None,
            usage=None,
            metadata=None,
        )


def build_settings(provider: str) -> AIProviderSettings:
    return AIProviderSettings(
        provider=provider,
        provider_from_env=provider,
        openai_api_key=None,
        openai_api_url=None,
        openai_model=None,
        deepseek_api_key=None,
        deepseek_api_url=None,
        deepseek_model=None,
        glm_api_key=None,
        glm_api_url=None,
        glm_model=None,
        legacy_api_key=None,
        legacy_api_url=None,
        legacy_model=None,
    )


class Phase45AIContractTest(unittest.TestCase):
    def test_mock_provider_returns_unified_result_structure(self) -> None:
        provider = MockProvider()
        result = provider.generate("p", {"system_prompt": "s"})

        self.assertIsInstance(result, AIGenerationResult)
        self.assertEqual(result.provider, "mock")
        self.assertIsNotNone(result.model)
        self.assertIsInstance(result.content, str)

    def test_mock_provider_normal_generation_sections(self) -> None:
        service = AIService(provider=MockProvider())
        sections = service.generate_sections(
            AIGenerationRequest(
                system_prompt="sys",
                user_prompt="user",
                context_text="ctx",
                output_options={"summary": True, "extension": True, "insight": False},
            )
        )

        self.assertTrue(sections["summary"])
        self.assertTrue(sections["expansion"])
        self.assertIn("extension", sections)

    def test_missing_summary_raises_contract_error(self) -> None:
        provider = MockProvider(sections={"expansion": "x", "inspirations": "", "guidance": ""})
        service = AIService(provider=provider)

        with self.assertRaises(AIContractError):
            service.generate_sections(
                AIGenerationRequest(
                    system_prompt="sys",
                    user_prompt="u",
                    context_text="c",
                    output_options={"summary": True, "extension": True, "insight": False},
                )
            )

    def test_missing_expansion_raises_contract_error(self) -> None:
        provider = MockProvider(sections={"summary": "x", "inspirations": "", "guidance": ""})
        service = AIService(provider=provider)

        with self.assertRaises(AIContractError):
            service.generate_sections(
                AIGenerationRequest(
                    system_prompt="sys",
                    user_prompt="u",
                    context_text="c",
                    output_options={"summary": True, "extension": True, "insight": False},
                )
            )

    def test_missing_guidance_is_backfilled(self) -> None:
        provider = MockProvider(sections={"summary": "s", "expansion": "e", "inspirations": ""})
        service = AIService(provider=provider)

        sections = service.generate_sections(
            AIGenerationRequest(
                system_prompt="sys",
                user_prompt="u",
                context_text="c",
                output_options={"summary": True, "extension": True, "insight": False},
            )
        )
        self.assertEqual(sections["guidance"], "")

    def test_missing_inspirations_is_backfilled(self) -> None:
        provider = MockProvider(sections={"summary": "s", "expansion": "e", "guidance": "g"})
        service = AIService(provider=provider)

        sections = service.generate_sections(
            AIGenerationRequest(
                system_prompt="sys",
                user_prompt="u",
                context_text="c",
                output_options={"summary": True, "extension": True, "insight": False},
            )
        )
        self.assertEqual(sections["inspirations"], "")

    def test_invalid_provider_config_raises_configuration_error(self) -> None:
        with self.assertRaises(AIConfigurationError):
            AIProviderFactory.create_provider(build_settings("unknown-provider"))

    def test_network_exception_is_wrapped_as_ai_network_error(self) -> None:
        def failing_sender(*_args, **_kwargs):
            raise requests.Timeout("timeout")

        provider = OpenAIProvider(
            api_key="k",
            api_url="https://api.openai.com/v1/chat/completions",
            model="gpt-4o-mini",
            request_sender=failing_sender,
        )

        with self.assertRaises(AINetworkError):
            provider.generate("hello", {"system_prompt": "sys"})

    def test_ai_service_provider_injection_still_works(self) -> None:
        provider = DummyProvider(
            content='{"summary":"sum","expansion":"exp","inspirations":"","guidance":"g"}'
        )
        service = AIService(provider=provider)
        sections = service.generate_sections(
            AIGenerationRequest(
                system_prompt="sys",
                user_prompt="u",
                context_text="c",
                output_options={"summary": True, "extension": True, "insight": False},
            )
        )

        self.assertEqual(sections["summary"], "sum")
        self.assertEqual(sections["extension"], "exp")


if __name__ == "__main__":
    unittest.main(verbosity=2)
