import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db.database import Database
from app.repositories.note_repository import NoteRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.record_repository import RecordRepository
from app.repositories.session_repository import SessionRepository
from app.services.errors import ServiceError
from app.services.project_service import ProjectService
from app.services.record_service import RecordService
from app.services.session_service import SessionService
from app.utils.datetime_utils import format_cn_datetime, format_cn_time
from app.utils.path_utils import build_session_asset_dir


class FakeCaptureService:
    def capture_screen(self, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake-image")


class Phase35HistoryManagementTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_root = Path(self.tmp_dir.name)
        self.db_path = self.tmp_root / "phase35.db"
        db = Database(self.db_path)
        db.initialize()

        db_path = str(self.db_path)
        self.project_repo = ProjectRepository(db_path)
        self.session_repo = SessionRepository(db_path)
        self.record_repo = RecordRepository(db_path)
        self.note_repo = NoteRepository(db_path)

        self.project_service = ProjectService(self.project_repo)
        self.session_service = SessionService(
            self.session_repo,
            self.project_repo,
            self.record_repo,
            app_root=self.tmp_root,
            projects_root=self.tmp_root / "data" / "projects",
        )
        self.record_service = RecordService(
            self.record_repo,
            self.session_repo,
            FakeCaptureService(),
            projects_root=self.tmp_root / "data" / "projects",
            app_root=self.tmp_root,
        )

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_can_read_multiple_history_sessions(self) -> None:
        project = self.project_service.create_project(name="P35-History")

        first = self.session_service.start_session(project.id)
        self.session_service.finish_session(first.id)

        second = self.session_service.start_session(project.id)
        self.session_service.finish_session(second.id)

        sessions = self.session_service.list_sessions_by_project(project.id)
        self.assertEqual(len(sessions), 2)
        self.assertSetEqual({sessions[0].id, sessions[1].id}, {first.id, second.id})

    def test_delete_finished_session_success_with_cascade_cleanup(self) -> None:
        project = self.project_service.create_project(name="P35-Delete")
        session = self.session_service.start_session(project.id)

        self.record_service.create_text_record(session.id, "idea")
        image_record = self.record_service.create_image_record(session.id, project.id)
        self.note_repo.create(session.id, summary="s", suggestions="x")

        self.session_service.finish_session(session.id)
        result = self.session_service.delete_finished_session(session.id, project.id)

        self.assertEqual(result.session_id, session.id)
        self.assertIsNone(self.session_repo.get_by_id(session.id))
        self.assertEqual(self.record_repo.list_by_session(session.id), [])
        self.assertIsNone(self.note_repo.get_by_session(session.id))

        image_abs_path = self.tmp_root / image_record.file_path
        self.assertFalse(image_abs_path.exists())

        session_asset_dir = build_session_asset_dir(
            project_id=project.id,
            session_id=session.id,
            projects_root=self.tmp_root / "data" / "projects",
        )
        self.assertFalse(session_asset_dir.exists())

    def test_delete_in_progress_session_blocked(self) -> None:
        project = self.project_service.create_project(name="P35-Block")
        session = self.session_service.start_session(project.id)

        with self.assertRaises(ServiceError):
            self.session_service.delete_finished_session(session.id, project.id)

    def test_delete_finished_session_when_image_missing_still_succeeds(self) -> None:
        project = self.project_service.create_project(name="P35-Session-Missing")
        session = self.session_service.start_session(project.id)
        image_record = self.record_service.create_image_record(session.id, project.id)
        image_abs_path = self.tmp_root / image_record.file_path
        image_abs_path.unlink()
        self.session_service.finish_session(session.id)

        result = self.session_service.delete_finished_session(session.id, project.id)
        self.assertEqual(result.session_id, session.id)
        self.assertGreater(len(result.warnings), 0)
        self.assertIsNone(self.session_repo.get_by_id(session.id))

    def test_delete_image_record_removes_file(self) -> None:
        project = self.project_service.create_project(name="P35-Record")
        session = self.session_service.start_session(project.id)

        image_record = self.record_service.create_image_record(session.id, project.id)
        image_abs_path = self.tmp_root / image_record.file_path
        self.assertTrue(image_abs_path.exists())

        result = self.record_service.delete_record(image_record.id)
        self.assertEqual(result.record_id, image_record.id)
        self.assertEqual(result.warnings, [])
        self.assertFalse(image_abs_path.exists())
        self.assertIsNone(self.record_repo.get_by_id(image_record.id))

    def test_delete_image_record_when_file_missing_still_succeeds(self) -> None:
        project = self.project_service.create_project(name="P35-Missing")
        session = self.session_service.start_session(project.id)

        image_record = self.record_service.create_image_record(session.id, project.id)
        image_abs_path = self.tmp_root / image_record.file_path
        image_abs_path.unlink()

        result = self.record_service.delete_record(image_record.id)
        self.assertEqual(result.record_id, image_record.id)
        self.assertGreater(len(result.warnings), 0)
        self.assertIsNone(self.record_repo.get_by_id(image_record.id))

    def test_datetime_utils_format_beijing_cn(self) -> None:
        utc_dt = datetime(2026, 3, 6, 11, 9, 10, tzinfo=UTC)
        self.assertEqual(format_cn_datetime(utc_dt), "2026年3月6日 19:09")
        self.assertEqual(format_cn_time(utc_dt), "19:09:10")


if __name__ == "__main__":
    unittest.main(verbosity=2)
