import sys
import tempfile
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db.database import Database
from app.repositories.project_repository import ProjectRepository
from app.repositories.record_repository import RecordRepository
from app.repositories.session_repository import SessionRepository
from app.services.errors import ServiceError
from app.services.project_service import ProjectService
from app.services.record_service import RECORD_TYPE_IMAGE, RECORD_TYPE_TEXT, RecordService
from app.services.session_service import SESSION_FINISHED, SessionService


class FakeCaptureService:
    def capture_screen(self, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake-image")


class Phase2RecordTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_root = Path(self.tmp_dir.name)
        self.db_path = self.tmp_root / "phase2.db"
        db = Database(self.db_path)
        db.initialize()

        self.project_repo = ProjectRepository(str(self.db_path))
        self.session_repo = SessionRepository(str(self.db_path))
        self.record_repo = RecordRepository(str(self.db_path))

        self.project_service = ProjectService(self.project_repo)
        self.session_service = SessionService(self.session_repo, self.project_repo)
        self.record_service = RecordService(
            self.record_repo,
            self.session_repo,
            FakeCaptureService(),
            projects_root=self.tmp_root / "data" / "projects",
            app_root=self.tmp_root,
        )

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_no_in_progress_session_cannot_write_record(self) -> None:
        project = self.project_service.create_project(name="P2")
        session = self.session_service.start_session(project.id)
        finished = self.session_service.finish_session(session.id)
        self.assertEqual(finished.status, SESSION_FINISHED)

        with self.assertRaises(ServiceError):
            self.record_service.create_text_record(session.id, "idea")

        with self.assertRaises(ServiceError):
            self.record_service.create_image_record(session.id, project.id)

    def test_create_text_and_image_record_and_list_timeline_order(self) -> None:
        project = self.project_service.create_project(name="Phase2")
        session = self.session_service.start_session(project.id)

        text1 = self.record_service.create_text_record(session.id, "first idea")
        image1 = self.record_service.create_image_record(session.id, project.id)
        text2 = self.record_service.create_text_record(session.id, "second idea")
        image2 = self.record_service.create_image_record(session.id, project.id)

        self.assertEqual(text1.record_type, RECORD_TYPE_TEXT)
        self.assertEqual(image1.record_type, RECORD_TYPE_IMAGE)
        self.assertEqual(text2.record_type, RECORD_TYPE_TEXT)
        self.assertEqual(image2.record_type, RECORD_TYPE_IMAGE)

        records = self.record_service.list_records_by_session(session.id)
        self.assertEqual(len(records), 4)
        self.assertEqual(
            [r.record_type for r in records],
            [RECORD_TYPE_TEXT, RECORD_TYPE_IMAGE, RECORD_TYPE_TEXT, RECORD_TYPE_IMAGE],
        )

        self.assertGreaterEqual(records[0].timestamp_offset, 0)
        self.assertGreaterEqual(records[1].timestamp_offset, 0)
        self.assertGreaterEqual(records[2].timestamp_offset, 0)
        self.assertGreaterEqual(records[3].timestamp_offset, 0)

        expected_prefix = f"data/projects/project_{project.id}/assets/session_{session.id}/"
        self.assertTrue(image1.file_path.startswith(expected_prefix))
        self.assertTrue(image2.file_path.startswith(expected_prefix))

        self.assertTrue(image1.file_path.endswith(f"session_{session.id}_shot_001.png"))
        self.assertTrue(image2.file_path.endswith(f"session_{session.id}_shot_002.png"))

        image1_abs_path = self.tmp_root / Path(image1.file_path)
        image2_abs_path = self.tmp_root / Path(image2.file_path)
        self.assertTrue(image1_abs_path.exists())
        self.assertTrue(image2_abs_path.exists())

    def test_finished_session_cannot_continue_recording(self) -> None:
        project = self.project_service.create_project(name="Phase2-Finish")
        session = self.session_service.start_session(project.id)
        self.session_service.finish_session(session.id)

        with self.assertRaises(ServiceError):
            self.record_service.create_text_record(session.id, "after finish")

        with self.assertRaises(ServiceError):
            self.record_service.create_image_record(session.id, project.id)


if __name__ == "__main__":
    unittest.main(verbosity=2)
