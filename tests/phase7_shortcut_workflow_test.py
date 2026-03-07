import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db.database import Database
from app.repositories.app_setting_repository import AppSettingRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.record_repository import RecordRepository
from app.repositories.session_repository import SessionRepository
from app.services.errors import ServiceError
from app.services.project_service import ProjectService
from app.services.record_service import RecordService
from app.services.session_service import SessionService
from app.services.shortcut_manager import BaseHotkeyBackend, ShortcutManager
from app.services.shortcut_settings_service import (
    ACTION_CAPTURE_IMAGE_RECORD,
    ACTION_START_SESSION,
    ShortcutSettingsService,
)
from app.ui.pages.study_page import StudyPage


class FakeCaptureService:
    def capture_screen(self, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake")


class FakeHotkeyBackend(BaseHotkeyBackend):
    def __init__(self):
        self.callbacks: dict[str, callable] = {}

    def register_hotkey(self, shortcut: str, callback):
        self.callbacks[shortcut] = callback

    def unregister_all(self) -> None:
        self.callbacks.clear()

    def trigger(self, shortcut: str) -> None:
        callback = self.callbacks.get(shortcut)
        if callback is not None:
            callback()


class Phase7ShortcutTest(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["AI_PROVIDER"] = "mock"
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_root = Path(self.tmp_dir.name)
        self.db_path = self.tmp_root / "phase7.db"

        db = Database(self.db_path)
        db.initialize()

        db_path = str(self.db_path)
        self.app_setting_repo = AppSettingRepository(db_path)
        self.settings_service = ShortcutSettingsService(self.app_setting_repo)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_default_shortcut_bindings_can_be_loaded(self) -> None:
        bindings = self.settings_service.load_bindings()
        self.assertIn(ACTION_START_SESSION, bindings)
        self.assertIn(ACTION_CAPTURE_IMAGE_RECORD, bindings)
        self.assertTrue(bindings[ACTION_START_SESSION])

    def test_custom_bindings_can_be_saved_and_reloaded(self) -> None:
        bindings = self.settings_service.load_bindings()
        bindings[ACTION_START_SESSION] = "ctrl+alt+1"
        saved = self.settings_service.save_bindings(bindings)

        reloaded = self.settings_service.load_bindings()
        self.assertEqual(saved[ACTION_START_SESSION], "ctrl+alt+1")
        self.assertEqual(reloaded[ACTION_START_SESSION], "ctrl+alt+1")

    def test_conflict_detection_works(self) -> None:
        bindings = self.settings_service.load_bindings()
        bindings[ACTION_START_SESSION] = "ctrl+alt+z"
        bindings[ACTION_CAPTURE_IMAGE_RECORD] = "ctrl+alt+z"

        with self.assertRaises(ServiceError):
            self.settings_service.save_bindings(bindings)

    def test_shortcut_manager_maps_action_to_signal(self) -> None:
        backend = FakeHotkeyBackend()
        manager = ShortcutManager(self.settings_service, backend=backend)

        bindings = self.settings_service.load_bindings()
        manager.apply_bindings(bindings)

        triggered: list[str] = []
        manager.action_triggered.connect(lambda action: triggered.append(action))

        backend.trigger(bindings[ACTION_START_SESSION])
        self.assertEqual(triggered, [ACTION_START_SESSION])

    def test_settings_can_be_loaded_after_restart(self) -> None:
        bindings = self.settings_service.load_bindings()
        bindings[ACTION_CAPTURE_IMAGE_RECORD] = "ctrl+alt+9"
        self.settings_service.save_bindings(bindings)

        # simulate app restart by creating a new service instance
        restarted_service = ShortcutSettingsService(AppSettingRepository(str(self.db_path)))
        reloaded = restarted_service.load_bindings()
        self.assertEqual(reloaded[ACTION_CAPTURE_IMAGE_RECORD], "ctrl+alt+9")

    def test_shortcut_action_reuses_existing_study_services(self) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        db_path = str(self.db_path)
        project_repo = ProjectRepository(db_path)
        session_repo = SessionRepository(db_path)
        record_repo = RecordRepository(db_path)

        project_service = ProjectService(project_repo)
        session_service = SessionService(session_repo, project_repo, record_repo)
        record_service = RecordService(
            record_repo,
            session_repo,
            FakeCaptureService(),
            projects_root=self.tmp_root / "data" / "projects",
            app_root=self.tmp_root,
        )

        app = QApplication.instance() or QApplication([])
        page = StudyPage(
            session_service=session_service,
            record_service=record_service,
            note_service=None,
            record_chat_service=None,
        )

        project = project_service.create_project(name="Shortcut Project")
        page.set_current_project(project)

        page.trigger_shortcut_action("start_session")
        running = session_service.get_in_progress_session()
        self.assertIsNotNone(running)
        self.assertEqual(running.project_id, project.id)

        page.trigger_shortcut_action("capture_image_record")
        records = record_service.list_records_by_session(running.id)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].record_type, "image")

        page.close()
        app.quit()


if __name__ == "__main__":
    unittest.main(verbosity=2)
