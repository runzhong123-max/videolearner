import sys
import tempfile
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db.database import Database
from app.repositories.output_profile_repository import OutputProfileRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.prompt_template_repository import PromptTemplateRepository
from app.repositories.record_repository import RecordRepository
from app.repositories.session_repository import SessionRepository
from app.services.output_profile_service import OutputProfileService
from app.services.project_service import ProjectService
from app.services.prompt_service import PromptService, SCOPE_GLOBAL, SCOPE_PROJECT, SCOPE_SESSION


class Phase3PromptOutputTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "phase3.db"
        self.db = Database(self.db_path)
        self.db.initialize()

        db_path = str(self.db_path)
        self.project_repo = ProjectRepository(db_path)
        self.session_repo = SessionRepository(db_path)
        self.record_repo = RecordRepository(db_path)
        self.prompt_repo = PromptTemplateRepository(db_path)
        self.output_repo = OutputProfileRepository(db_path)

        self.project_service = ProjectService(self.project_repo)
        self.prompt_service = PromptService(self.prompt_repo, self.session_repo)
        self.output_service = OutputProfileService(self.output_repo, self.session_repo, self.record_repo)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_prompt_priority_resolution(self) -> None:
        project = self.project_service.create_project(name="P3")
        session = self.session_repo.create(project_id=project.id, title="s1", status="finished")

        self.prompt_service.save_template(
            scope=SCOPE_GLOBAL,
            name="global",
            system_prompt="global-system",
            user_prompt="global-user",
        )
        self.prompt_service.save_template(
            scope=SCOPE_PROJECT,
            project_id=project.id,
            name="project",
            system_prompt="project-system",
            user_prompt="project-user",
        )
        self.prompt_service.save_template(
            scope=SCOPE_SESSION,
            session_id=session,
            name="session",
            system_prompt="session-system",
            user_prompt="session-user",
        )

        resolved_session = self.prompt_service.resolve_effective_prompt(project_id=project.id, session_id=session)
        self.assertEqual(resolved_session.scope, SCOPE_SESSION)
        self.assertEqual(resolved_session.system_prompt, "session-system")

        session2 = self.session_repo.create(project_id=project.id, title="s2", status="finished")
        resolved_project = self.prompt_service.resolve_effective_prompt(project_id=project.id, session_id=session2)
        self.assertEqual(resolved_project.scope, SCOPE_PROJECT)
        self.assertEqual(resolved_project.system_prompt, "project-system")

        project2 = self.project_service.create_project(name="P3-2")
        resolved_global = self.prompt_service.resolve_effective_prompt(project_id=project2.id)
        self.assertEqual(resolved_global.scope, SCOPE_GLOBAL)
        self.assertEqual(resolved_global.system_prompt, "global-system")

    def test_output_profile_rules_and_persistence(self) -> None:
        project = self.project_service.create_project(name="P3-Output")
        session = self.session_repo.create(project_id=project.id, title="for-output", status="in_progress")

        self.record_repo.create(
            session_id=session,
            record_type="text",
            content="idea",
            is_inspiration=True,
            timestamp_offset=10,
        )

        saved_global = self.output_service.save_profile(
            name="global-output",
            scope=SCOPE_GLOBAL,
            context_session_id=session,
            selections={
                "summary": False,
                "extension": False,
                "insight": False,
                "history_link": True,
                "gap_analysis": False,
                "review_questions": False,
                "homework": False,
                "expression_notes": False,
                "evaluation": False,
            },
        )
        self.assertTrue(saved_global.summary)
        self.assertTrue(saved_global.extension)
        self.assertTrue(saved_global.insight)

        saved_session = self.output_service.save_profile(
            name="session-output",
            scope=SCOPE_SESSION,
            session_id=session,
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
        self.assertTrue(saved_session.summary)
        self.assertTrue(saved_session.extension)
        self.assertTrue(saved_session.insight)

        resolved = self.output_service.resolve_effective_profile(project_id=project.id, session_id=session)
        self.assertTrue(resolved.summary)
        self.assertTrue(resolved.extension)
        self.assertTrue(resolved.insight)

        self.prompt_service.save_template(
            scope=SCOPE_GLOBAL,
            name="persist-global",
            system_prompt="persist-system",
            user_prompt="persist-user",
        )

        reopened_prompt = PromptService(
            PromptTemplateRepository(str(self.db_path)),
            SessionRepository(str(self.db_path)),
        )
        reopened_output = OutputProfileService(
            OutputProfileRepository(str(self.db_path)),
            SessionRepository(str(self.db_path)),
            RecordRepository(str(self.db_path)),
        )

        persisted_prompt = reopened_prompt.resolve_effective_prompt()
        self.assertEqual(persisted_prompt.system_prompt, "persist-system")

        persisted_output = reopened_output.resolve_effective_profile(project_id=project.id, session_id=session)
        self.assertTrue(persisted_output.summary)
        self.assertTrue(persisted_output.extension)
        self.assertTrue(persisted_output.insight)


if __name__ == "__main__":
    unittest.main(verbosity=2)
