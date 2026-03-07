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
from app.repositories.note_repository import NoteRepository
from app.repositories.output_profile_repository import OutputProfileRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.prompt_template_repository import PromptTemplateRepository
from app.repositories.record_repository import RecordRepository
from app.repositories.session_repository import SessionRepository
from app.services.ai_providers.ai_result import AIGenerationResult
from app.services.ai_providers.base_provider import BaseAIProvider
from app.services.ai_service import AIService
from app.services.context_builder import ContextBuilder
from app.services.note_service import NoteService
from app.services.output_profile_service import OutputProfileService
from app.services.project_service import ProjectService
from app.services.prompt_service import PromptService


class RotatingProvider(BaseAIProvider):
    def __init__(self):
        self.i = 0

    def generate(self, prompt: str, context: dict) -> AIGenerationResult:
        _ = prompt
        _ = context
        self.i += 1
        sections = {
            "summary": f"summary-{self.i}",
            "expansion": f"expansion-{self.i}",
            "inspirations": "",
            "guidance": "guidance",
            "review_questions": f"q-{self.i}",
            "key_points": f"k-{self.i}",
            "follow_up_tasks": f"t-{self.i}",
        }
        return AIGenerationResult(
            content=json.dumps(sections, ensure_ascii=False),
            provider="rotating",
            model="rotating-model",
            raw_response=sections,
            usage=None,
            metadata=None,
        )


class Phase9LightweightNoteTest(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["AI_PROVIDER"] = "mock"

        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "phase9.db"
        db = Database(self.db_path)
        db.initialize()

        db_path = str(self.db_path)
        self.project_repo = ProjectRepository(db_path)
        self.session_repo = SessionRepository(db_path)
        self.record_repo = RecordRepository(db_path)
        self.note_repo = NoteRepository(db_path)
        self.prompt_repo = PromptTemplateRepository(db_path)
        self.output_repo = OutputProfileRepository(db_path)

        self.project_service = ProjectService(self.project_repo)
        self.prompt_service = PromptService(self.prompt_repo, self.session_repo)
        self.output_service = OutputProfileService(self.output_repo, self.session_repo, self.record_repo)

        self.context_builder = ContextBuilder(
            project_repository=self.project_repo,
            session_repository=self.session_repo,
            record_repository=self.record_repo,
            note_repository=self.note_repo,
            prompt_service=self.prompt_service,
            output_profile_service=self.output_service,
        )

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def _build_note_service(self, ai_service: AIService) -> NoteService:
        return NoteService(
            note_repository=self.note_repo,
            session_repository=self.session_repo,
            context_builder=self.context_builder,
            ai_service=ai_service,
        )

    def test_regenerate_keeps_old_versions(self) -> None:
        project = self.project_service.create_project(name="P9")
        session_id = self.session_repo.create(project.id, title="S", status="finished")

        provider = RotatingProvider()
        note_service = self._build_note_service(AIService(provider=provider))

        first = note_service.generate_note_for_session(session_id)
        second = note_service.generate_note_for_session(session_id)

        self.assertNotEqual(first.note.id, second.note.id)
        self.assertEqual(second.previous_versions_count, 1)

        versions = note_service.list_note_versions_for_session(session_id)
        self.assertEqual(len(versions), 2)
        self.assertEqual(versions[0].id, second.note.id)
        self.assertEqual(versions[1].id, first.note.id)

    def test_note_versions_can_be_loaded_with_provider_model(self) -> None:
        project = self.project_service.create_project(name="P9-V")
        session_id = self.session_repo.create(project.id, title="S", status="finished")

        note_service = self._build_note_service(AIService(provider=RotatingProvider()))
        note_service.generate_note_for_session(session_id)

        versions = note_service.list_note_versions_for_session(session_id)
        self.assertTrue(versions)
        self.assertEqual(versions[0].ai_provider, "rotating")
        self.assertEqual(versions[0].ai_model, "rotating-model")
        self.assertTrue(versions[0].content)

    def test_review_fields_and_lightweight_marks_persist(self) -> None:
        project = self.project_service.create_project(name="P9-R")
        session_id = self.session_repo.create(project.id, title="S", status="finished")

        note_service = self._build_note_service(AIService(provider=RotatingProvider()))
        generated = note_service.generate_note_for_session(session_id)

        updated = note_service.update_note_review_fields(
            note_id=generated.note.id,
            review_questions="Q1\nQ2",
            key_points="K1\nK2",
            follow_up_tasks="T1",
            in_review_list=True,
            is_key_note=True,
            review_later=True,
        )

        self.assertEqual(updated.review_questions, "Q1\nQ2")
        self.assertEqual(updated.key_points, "K1\nK2")
        self.assertEqual(updated.follow_up_tasks, "T1")
        self.assertTrue(updated.in_review_list)
        self.assertTrue(updated.is_key_note)
        self.assertTrue(updated.review_later)

        reloaded = note_service.get_note_by_id(updated.id)
        self.assertIsNotNone(reloaded)
        self.assertTrue(reloaded.in_review_list)
        self.assertTrue(reloaded.is_key_note)
        self.assertTrue(reloaded.review_later)

    def test_default_path_uses_mock_without_real_network(self) -> None:
        project = self.project_service.create_project(name="P9-Mock")
        session_id = self.session_repo.create(project.id, title="S", status="finished")

        note_service = self._build_note_service(AIService())
        result = note_service.generate_note_for_session(session_id)

        self.assertIsNotNone(result.note.id)
        self.assertIn("Mock", result.note.content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
