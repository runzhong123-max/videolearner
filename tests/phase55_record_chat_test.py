import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db.database import Database
from app.repositories.project_repository import ProjectRepository
from app.repositories.prompt_template_repository import PromptTemplateRepository
from app.repositories.record_chat_message_repository import RecordChatMessageRepository
from app.repositories.record_conversation_repository import RecordConversationRepository
from app.repositories.record_repository import RecordRepository
from app.repositories.session_repository import SessionRepository
from app.services.ai_providers.ai_result import AIGenerationResult
from app.services.ai_providers.base_provider import BaseAIProvider
from app.services.ai_service import AIService
from app.services.project_service import ProjectService
from app.services.prompt_service import PromptService
from app.services.record_chat_context_builder import RecordChatContextBuilder
from app.services.record_chat_service import RecordChatService
from app.services.record_service import RecordService


class FakeCaptureService:
    def capture_screen(self, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake-image")


class DummyChatProvider(BaseAIProvider):
    def __init__(self):
        self.calls: list[dict] = []

    def generate(self, prompt: str, context: dict) -> AIGenerationResult:
        self.calls.append({"prompt": prompt, "context": context})
        return AIGenerationResult(
            content="这是针对该记录的模拟回答",
            provider="dummy",
            model="dummy-model",
            raw_response=None,
            usage=None,
            metadata=None,
        )


class Phase55RecordChatTest(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["AI_PROVIDER"] = "mock"

        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_root = Path(self.tmp_dir.name)
        self.db_path = self.tmp_root / "phase55.db"
        db = Database(self.db_path)
        db.initialize()

        db_path = str(self.db_path)
        self.project_repo = ProjectRepository(db_path)
        self.session_repo = SessionRepository(db_path)
        self.record_repo = RecordRepository(db_path)
        self.prompt_repo = PromptTemplateRepository(db_path)
        self.conversation_repo = RecordConversationRepository(db_path)
        self.message_repo = RecordChatMessageRepository(db_path)

        self.project_service = ProjectService(self.project_repo)
        self.prompt_service = PromptService(self.prompt_repo, self.session_repo)
        self.record_service = RecordService(
            self.record_repo,
            self.session_repo,
            FakeCaptureService(),
            projects_root=self.tmp_root / "data" / "projects",
            app_root=self.tmp_root,
        )

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def _build_chat_service(self, ai_service: AIService | None = None) -> RecordChatService:
        context_builder = RecordChatContextBuilder(
            project_repository=self.project_repo,
            session_repository=self.session_repo,
            record_repository=self.record_repo,
            conversation_repository=self.conversation_repo,
            message_repository=self.message_repo,
            prompt_service=self.prompt_service,
        )
        return RecordChatService(
            conversation_repository=self.conversation_repo,
            message_repository=self.message_repo,
            record_repository=self.record_repo,
            session_repository=self.session_repo,
            context_builder=context_builder,
            ai_service=ai_service or AIService(provider=DummyChatProvider()),
        )

    def _create_text_record(self, project_name: str = "P55", session_title: str = "S") -> tuple[int, int, int]:
        project = self.project_service.create_project(name=project_name)
        session_id = self.session_repo.create(project.id, title=session_title, status="finished")
        record_id = self.record_repo.create(
            session_id=session_id,
            record_type="text",
            content="record content",
            is_inspiration=True,
            timestamp_offset=3,
        )
        return project.id, session_id, record_id

    def test_create_or_get_conversation_by_record_id(self) -> None:
        project_id, session_id, record_id = self._create_text_record()
        service = self._build_chat_service()

        conversation = service.get_or_create_conversation(record_id)
        self.assertEqual(conversation.record_id, record_id)
        self.assertEqual(conversation.session_id, session_id)
        self.assertEqual(conversation.project_id, project_id)

        reused = service.get_or_create_conversation(record_id)
        self.assertEqual(reused.id, conversation.id)

    def test_text_or_insight_record_can_send_question_and_get_reply(self) -> None:
        _project_id, _session_id, record_id = self._create_text_record()
        service = self._build_chat_service()

        result = service.send_user_message(record_id, "帮我解释这条灵感")
        self.assertFalse(result.is_stub)
        self.assertEqual(result.user_message.role, "user")
        self.assertEqual(result.assistant_message.role, "assistant")
        self.assertIn("模拟回答", result.assistant_message.content)

    def test_chat_messages_persist_and_can_be_reloaded(self) -> None:
        _project_id, _session_id, record_id = self._create_text_record()
        service = self._build_chat_service()

        service.send_user_message(record_id, "问题1")
        service.send_user_message(record_id, "问题2")

        messages = service.list_messages_by_record(record_id)
        self.assertEqual(len(messages), 4)
        self.assertEqual([m.role for m in messages], ["user", "assistant", "user", "assistant"])

    def test_conversations_are_isolated_between_records(self) -> None:
        project = self.project_service.create_project(name="P55-Isolate")
        session_id = self.session_repo.create(project.id, title="s", status="finished")
        r1 = self.record_repo.create(session_id=session_id, record_type="text", content="r1")
        r2 = self.record_repo.create(session_id=session_id, record_type="text", content="r2")

        service = self._build_chat_service()
        service.send_user_message(r1, "q1")
        service.send_user_message(r2, "q2")

        m1 = service.list_messages_by_record(r1)
        m2 = service.list_messages_by_record(r2)
        self.assertEqual(len(m1), 2)
        self.assertEqual(len(m2), 2)
        self.assertNotEqual(
            self.conversation_repo.get_by_record(r1).id,
            self.conversation_repo.get_by_record(r2).id,
        )

    def test_parallel_projects_and_sessions_do_not_mix_chat_data(self) -> None:
        p1 = self.project_service.create_project(name="P55-A")
        s1 = self.session_repo.create(p1.id, title="s1", status="finished")
        r1 = self.record_repo.create(session_id=s1, record_type="text", content="A")

        p2 = self.project_service.create_project(name="P55-B")
        s2 = self.session_repo.create(p2.id, title="s2", status="finished")
        r2 = self.record_repo.create(session_id=s2, record_type="text", content="B")

        service = self._build_chat_service()
        service.send_user_message(r1, "A问题")
        service.send_user_message(r2, "B问题")

        c1 = self.conversation_repo.get_by_record(r1)
        c2 = self.conversation_repo.get_by_record(r2)
        self.assertEqual(c1.project_id, p1.id)
        self.assertEqual(c2.project_id, p2.id)
        self.assertEqual(c1.session_id, s1)
        self.assertEqual(c2.session_id, s2)

    def test_mock_provider_works_without_network(self) -> None:
        _project_id, _session_id, record_id = self._create_text_record()
        service = self._build_chat_service(ai_service=AIService())

        result = service.send_user_message(record_id, "mock 环境提问")
        self.assertFalse(result.is_stub)
        self.assertTrue(result.assistant_message.content)
        self.assertEqual(result.conversation.provider, "mock")

    def test_image_record_chat_works_in_minimum_multimodal_path(self) -> None:
        project = self.project_service.create_project(name="P55-Image")
        session_id = self.session_repo.create(project.id, title="image", status="finished")
        record_id = self.record_repo.create(
            session_id=session_id,
            record_type="image",
            file_path="data/projects/p/assets/s.png",
        )

        service = self._build_chat_service()
        result = service.send_user_message(record_id, "这张图是什么意思")

        self.assertFalse(result.is_stub)
        self.assertIn("模拟回答", result.assistant_message.content)
        self.assertEqual(result.assistant_message.role, "assistant")
        self.assertEqual(result.user_message.image_path, "data/projects/p/assets/s.png")

    def test_delete_record_cascades_conversation_and_messages(self) -> None:
        _project_id, _session_id, record_id = self._create_text_record()
        service = self._build_chat_service()

        result = service.send_user_message(record_id, "要删除前提问")
        conversation_id = result.conversation.id
        self.assertIsNotNone(self.conversation_repo.get_by_id(conversation_id))
        self.assertEqual(len(self.message_repo.list_by_conversation(conversation_id)), 2)

        self.record_service.delete_record(record_id)

        self.assertIsNone(self.conversation_repo.get_by_record(record_id))
        self.assertEqual(self.message_repo.list_by_conversation(conversation_id), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
