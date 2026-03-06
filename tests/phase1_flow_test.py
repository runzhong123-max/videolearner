import sys
import tempfile
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db.database import Database
from app.repositories.project_repository import ProjectRepository
from app.repositories.session_repository import SessionRepository
from app.services.errors import ServiceError
from app.services.project_service import ProjectService
from app.services.session_service import SESSION_FINISHED, SESSION_IN_PROGRESS, SessionService


class Phase1FlowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "phase1.db"
        db = Database(self.db_path)
        db.initialize()

        projects = ProjectRepository(str(self.db_path))
        sessions = SessionRepository(str(self.db_path))
        self.project_service = ProjectService(projects)
        self.session_service = SessionService(sessions, projects)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_phase1_minimum_closed_loop(self) -> None:
        p1 = self.project_service.create_project(
            name="Python 学习",
            description="desc",
            source="video",
            goal="finish course",
            tags="python,oop",
        )
        self.assertIsNotNone(p1.id)

        p1_updated = self.project_service.update_project(
            project_id=p1.id,
            name="Python 学习 V2",
            description="desc2",
            source="video2",
            goal="finish v2",
            tags="python,oop,phase1",
        )
        self.assertEqual(p1_updated.name, "Python 学习 V2")
        self.assertEqual(p1_updated.goal, "finish v2")

        p2 = self.project_service.create_project(name="To Delete")
        self.project_service.delete_project(p2.id)
        self.assertIsNone(self.project_service.get_project(p2.id))

        selected = self.project_service.get_project(p1.id)
        self.assertIsNotNone(selected)
        self.assertEqual(selected.id, p1.id)

        started = self.session_service.start_session(p1.id)
        self.assertEqual(started.status, SESSION_IN_PROGRESS)
        self.assertIsNone(started.ended_at)

        with self.assertRaises(ServiceError):
            self.session_service.start_session(p1.id)

        finished = self.session_service.finish_session(started.id)
        self.assertEqual(finished.status, SESSION_FINISHED)
        self.assertIsNotNone(finished.ended_at)

        reopened_projects = ProjectService(ProjectRepository(str(self.db_path)))
        reopened_sessions = SessionService(
            SessionRepository(str(self.db_path)),
            ProjectRepository(str(self.db_path)),
        )

        persisted_project = reopened_projects.get_project(p1.id)
        self.assertIsNotNone(persisted_project)
        self.assertEqual(persisted_project.name, "Python 学习 V2")

        persisted_sessions = reopened_sessions.list_sessions_by_project(p1.id)
        self.assertEqual(len(persisted_sessions), 1)
        self.assertEqual(persisted_sessions[0].status, SESSION_FINISHED)


if __name__ == "__main__":
    unittest.main(verbosity=2)
