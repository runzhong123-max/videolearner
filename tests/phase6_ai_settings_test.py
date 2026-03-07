import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db.database import Database
from app.repositories.ai_feature_route_repository import AIFeatureRouteRepository
from app.repositories.ai_provider_config_repository import AIProviderConfigRepository
from app.repositories.app_setting_repository import AppSettingRepository
from app.services.ai_provider_resolver import AIProviderResolver
from app.services.ai_providers.ai_result import AIGenerationResult
from app.services.ai_providers.base_provider import BaseAIProvider
from app.services.ai_service import AIGenerationRequest, AIService
from app.services.ai_settings_service import (
    AISettingsService,
    ROUTE_RECORD_CHAT_PROVIDER,
    ROUTE_SESSION_NOTE_PROVIDER,
)


class DummyProvider(BaseAIProvider):
    def generate(self, prompt: str, context: dict) -> AIGenerationResult:
        _ = (prompt, context)
        return AIGenerationResult(
            content=json.dumps(
                {
                    "summary": "dummy summary",
                    "expansion": "dummy expansion",
                    "inspirations": "",
                    "guidance": "",
                },
                ensure_ascii=False,
            ),
            provider="dummy",
            model="dummy-model",
            raw_response=None,
            usage=None,
            metadata=None,
        )


class Phase6AISettingsTest(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["AI_PROVIDER"] = "mock"

        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "phase6.db"
        db = Database(self.db_path)
        db.initialize()

        db_path = str(self.db_path)
        self.app_settings_repo = AppSettingRepository(db_path)
        self.provider_repo = AIProviderConfigRepository(db_path)
        self.route_repo = AIFeatureRouteRepository(db_path)

        self.settings_service = AISettingsService(
            app_setting_repository=self.app_settings_repo,
            provider_config_repository=self.provider_repo,
            feature_route_repository=self.route_repo,
        )
        self.resolver = AIProviderResolver(self.settings_service)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_save_and_load_default_provider(self) -> None:
        self.settings_service.save_default_provider("deepseek")
        loaded = self.settings_service.load_settings()
        self.assertEqual(loaded.default_provider, "deepseek")

    def test_save_and_load_provider_config(self) -> None:
        self.settings_service.save_provider_config(
            provider="openai",
            api_key="k-123",
            api_url="https://example.test/v1/chat/completions",
            model="gpt-x",
            timeout_seconds=99,
        )

        loaded = self.settings_service.load_settings()
        config = loaded.provider_configs["openai"]
        self.assertEqual(config.api_key, "k-123")
        self.assertEqual(config.api_url, "https://example.test/v1/chat/completions")
        self.assertEqual(config.model, "gpt-x")
        self.assertEqual(config.timeout_seconds, 99)

    def test_save_and_load_feature_routes(self) -> None:
        self.settings_service.save_feature_route(ROUTE_SESSION_NOTE_PROVIDER, "deepseek")
        self.settings_service.save_feature_route(ROUTE_RECORD_CHAT_PROVIDER, "openai")

        loaded = self.settings_service.load_settings()
        self.assertEqual(loaded.feature_routes[ROUTE_SESSION_NOTE_PROVIDER], "deepseek")
        self.assertEqual(loaded.feature_routes[ROUTE_RECORD_CHAT_PROVIDER], "openai")

    def test_route_fallback_to_default_provider(self) -> None:
        self.settings_service.save_default_provider("glm")
        self.settings_service.save_feature_route(ROUTE_SESSION_NOTE_PROVIDER, "")

        resolved = self.settings_service.resolve_provider_name(ROUTE_SESSION_NOTE_PROVIDER)
        self.assertEqual(resolved, "glm")

    def test_mock_provider_connection_success(self) -> None:
        result = self.settings_service.test_provider_connection("mock")
        self.assertTrue(result.success)
        self.assertEqual(result.provider, "mock")

    def test_provider_resolver_returns_feature_specific_provider(self) -> None:
        self.settings_service.save_default_provider("mock")
        self.settings_service.save_feature_route(ROUTE_SESSION_NOTE_PROVIDER, "deepseek")
        self.settings_service.save_feature_route(ROUTE_RECORD_CHAT_PROVIDER, "openai")

        note_provider = self.resolver.resolve_provider_name("session_note")
        chat_provider = self.resolver.resolve_provider_name("record_chat")
        self.assertEqual(note_provider, "deepseek")
        self.assertEqual(chat_provider, "openai")

    def test_ai_service_provider_injection_still_works(self) -> None:
        service = AIService(provider=DummyProvider())
        sections = service.generate_sections(
            AIGenerationRequest(
                system_prompt="s",
                user_prompt="u",
                context_text="c",
                output_options={"summary": True, "extension": True, "insight": False},
            )
        )
        self.assertEqual(sections["summary"], "dummy summary")
        self.assertEqual(sections["extension"], "dummy expansion")

    def test_default_tests_path_works_without_real_network(self) -> None:
        self.settings_service.save_default_provider("mock")
        self.settings_service.save_feature_route(ROUTE_SESSION_NOTE_PROVIDER, "")

        service = AIService(provider_resolver=self.resolver)
        sections = service.generate_sections(
            AIGenerationRequest(
                system_prompt="sys",
                user_prompt="user",
                context_text="ctx",
                output_options={"summary": True, "extension": True, "insight": False},
            ),
            feature_name=ROUTE_SESSION_NOTE_PROVIDER,
        )
        self.assertTrue(sections["summary"])
        self.assertTrue(sections["extension"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
