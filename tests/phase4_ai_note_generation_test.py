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
from app.services.ai_service import AIGenerationRequest, AIService
from app.services.context_builder import ContextBuilder
from app.services.errors import ServiceError
from app.services.note_service import NoteService
from app.services.output_profile_service import OutputProfileService
from app.services.project_service import ProjectService
from app.services.prompt_service import PromptService, SCOPE_GLOBAL, SCOPE_PROJECT, SCOPE_SESSION


class CapturingProvider(BaseAIProvider):
    def __init__(self, sections: dict | None = None, should_fail: bool = False):
        self.sections = sections or {"summary": "s", "expansion": "e", "inspirations": "", "guidance": "g"}
        self.should_fail = should_fail
        self.calls: list[dict] = []

    def generate(self, prompt: str, context: dict) -> AIGenerationResult:
        self.calls.append({"prompt": prompt, "context": context})
        if self.should_fail:
            raise ServiceError("mock api failure")
        return AIGenerationResult(
            content=json.dumps(self.sections, ensure_ascii=False),
            provider="capturing",
            model="capturing-model",
            raw_response=dict(self.sections),
            usage=None,
            metadata=None,
        )


class Phase4AINoteGenerationTest(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["AI_PROVIDER"] = "mock"

        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "phase4.db"
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

    def _build_note_service(self, provider: BaseAIProvider) -> NoteService:
        return NoteService(
            note_repository=self.note_repo,
            session_repository=self.session_repo,
            context_builder=self.context_builder,
            ai_service=AIService(provider=provider),
        )

    def test_context_builder_uses_specified_session_id(self) -> None:
        project = self.project_service.create_project(name="P4")
        target_session_id = self.session_repo.create(project.id, title="target", status="finished")
        other_session_id = self.session_repo.create(project.id, title="other", status="finished")

        self.record_repo.create(
            session_id=target_session_id,
            record_type="text",
            content="target-only-record",
            timestamp_offset=1,
        )
        self.record_repo.create(
            session_id=other_session_id,
            record_type="text",
            content="other-record-should-not-appear",
            timestamp_offset=2,
        )

        bundle = self.context_builder.build_for_session(target_session_id)
        self.assertIn("target-only-record", bundle.context_text)
        self.assertNotIn("other-record-should-not-appear", bundle.context_text)

    def test_prompt_priority_applies_in_generation_chain(self) -> None:
        project = self.project_service.create_project(name="Prompt P4")
        session_id = self.session_repo.create(project.id, title="s", status="finished")

        self.prompt_service.save_template(
            scope=SCOPE_GLOBAL,
            name="g",
            system_prompt="global-system",
            user_prompt="global-user",
        )
        self.prompt_service.save_template(
            scope=SCOPE_PROJECT,
            project_id=project.id,
            name="p",
            system_prompt="project-system",
            user_prompt="project-user",
        )
        self.prompt_service.save_template(
            scope=SCOPE_SESSION,
            session_id=session_id,
            name="s",
            system_prompt="session-system",
            user_prompt="session-user",
        )

        provider = CapturingProvider(sections={"summary": "ok", "expansion": "ok", "inspirations": "", "guidance": ""})
        note_service = self._build_note_service(provider)
        note_service.generate_note_for_session(session_id)

        call = provider.calls[0]
        self.assertEqual(call["context"]["system_prompt"], "session-system")
        self.assertIn("session-user", call["prompt"])

    def test_output_profile_rules_apply_in_generation_chain(self) -> None:
        project = self.project_service.create_project(name="Output P4")
        session_id = self.session_repo.create(project.id, title="s", status="finished")

        self.output_service.save_profile(
            name="global-output",
            scope=SCOPE_GLOBAL,
            selections={
                "summary": False,
                "extension": False,
                "insight": False,
                "history_link": False,
                "gap_analysis": False,
                "review_questions": False,
                "homework": False,
                "expression_notes": False,
                "evaluation": False,
            },
        )

        bundle = self.context_builder.build_for_session(session_id)
        self.assertTrue(bundle.output_options["summary"])
        self.assertTrue(bundle.output_options["extension"])

    def test_insight_forced_when_inspiration_exists(self) -> None:
        project = self.project_service.create_project(name="Insight P4")
        session_id = self.session_repo.create(project.id, title="s", status="finished")

        self.record_repo.create(
            session_id=session_id,
            record_type="text",
            content="idea",
            is_inspiration=True,
            timestamp_offset=3,
        )

        bundle = self.context_builder.build_for_session(session_id)
        self.assertTrue(bundle.has_inspiration_records)
        self.assertTrue(bundle.output_options["insight"])

    def test_generation_saves_note_to_notes_table(self) -> None:
        project = self.project_service.create_project(name="Save P4")
        session_id = self.session_repo.create(project.id, title="s", status="finished")

        provider = CapturingProvider(
            sections={
                "summary": "Summary Text",
                "expansion": "Extension Text",
                "inspirations": "Insight Text",
                "guidance": "Guidance Text",
            }
        )
        note_service = self._build_note_service(provider)

        result = note_service.generate_note_for_session(session_id)
        self.assertEqual(result.note.session_id, session_id)
        self.assertEqual(result.note.project_id, project.id)
        self.assertEqual(result.note.note_type, "session_summary")
        self.assertTrue(result.note.title)
        self.assertIn("Summary", result.note.content)

        persisted = self.note_repo.get_by_session(session_id)
        self.assertIsNotNone(persisted)
        self.assertEqual(persisted.summary, "Summary Text")

    def test_parallel_sessions_do_not_mix_records(self) -> None:
        project = self.project_service.create_project(name="Parallel P4")
        s1 = self.session_repo.create(project.id, title="s1", status="finished")
        s2 = self.session_repo.create(project.id, title="s2", status="finished")

        self.record_repo.create(session_id=s1, record_type="text", content="record-s1", timestamp_offset=1)
        self.record_repo.create(session_id=s2, record_type="text", content="record-s2", timestamp_offset=1)

        provider = CapturingProvider(sections={"summary": "ok", "expansion": "ok", "inspirations": "", "guidance": ""})
        note_service = self._build_note_service(provider)
        note_service.generate_note_for_session(s1)

        user_prompt = provider.calls[0]["prompt"]
        self.assertIn("record-s1", user_prompt)
        self.assertNotIn("record-s2", user_prompt)

    def test_api_failure_returns_error_and_does_not_pollute_notes(self) -> None:
        project = self.project_service.create_project(name="Fail P4")
        session_id = self.session_repo.create(project.id, title="s", status="finished")

        provider = CapturingProvider(should_fail=True)
        note_service = self._build_note_service(provider)

        with self.assertRaises(ServiceError):
            note_service.generate_note_for_session(session_id)

        self.assertIsNone(self.note_repo.get_by_session(session_id))

    def test_mock_provider_can_drive_full_generation(self) -> None:
        project = self.project_service.create_project(name="Mock P4")
        session_id = self.session_repo.create(project.id, title="s", status="finished")

        provider = CapturingProvider(
            sections={
                "summary": "mock summary",
                "expansion": "mock extension",
                "review_questions": "q1",
                "inspirations": "",
                "guidance": "",
            }
        )
        note_service = self._build_note_service(provider)

        result = note_service.generate_note_for_session(session_id)
        self.assertIn("mock summary", result.note.content)
        self.assertIn("mock extension", result.note.content)

    def test_ai_service_default_provider_is_mock(self) -> None:
        ai_service = AIService()
        sections = ai_service.generate_sections(
            AIGenerationRequest(
                system_prompt="sys",
                user_prompt="user",
                context_text="ctx",
                output_options={"summary": True, "extension": True, "insight": False},
            )
        )
        self.assertIn("summary", sections)
        self.assertIn("expansion", sections)
        self.assertIn("extension", sections)


if __name__ == "__main__":
    unittest.main(verbosity=2)
