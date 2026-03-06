import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db.database import Database
from app.repositories.note_repository import NoteRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.prompt_template_repository import PromptTemplateRepository
from app.repositories.record_repository import RecordRepository
from app.repositories.session_repository import SessionRepository
from app.services.project_service import ProjectService
from app.services.session_service import SessionService
from app.ui.main_window import MainWindow


class DatabaseSmokeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "smoke.db"
        self.db = Database(self.db_path)
        self.db.initialize()

        db_path_str = self.db.as_path()
        self.projects = ProjectRepository(db_path_str)
        self.sessions = SessionRepository(db_path_str)
        self.records = RecordRepository(db_path_str)
        self.notes = NoteRepository(db_path_str)
        self.prompts = PromptTemplateRepository(db_path_str)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_migrations_are_idempotent(self) -> None:
        self.db.initialize()

        with closing(sqlite3.connect(self.db.as_path())) as conn:
            tables = {
                row[0]
                for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            }
            self.assertIn("projects", tables)
            self.assertIn("sessions", tables)
            self.assertIn("records", tables)
            self.assertIn("notes", tables)
            self.assertIn("prompt_templates", tables)
            self.assertIn("schema_migrations", tables)

            versions = conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
            self.assertEqual(versions, 3)

    def test_foreign_keys_enforced(self) -> None:
        with self.assertRaises(sqlite3.IntegrityError):
            self.sessions.create(project_id=999999, title="invalid")

    def test_repository_crud_minimum_flow(self) -> None:
        project_id = self.projects.create(
            name="Demo Project",
            description="desc",
            source="video",
            goal="goal",
            tags="tag1,tag2",
        )
        self.assertIsNotNone(self.projects.get_by_id(project_id))

        self.assertTrue(self.projects.update(project_id, name="Demo Project V2"))
        project = self.projects.get_by_id(project_id)
        self.assertIsNotNone(project)
        self.assertEqual(project.name, "Demo Project V2")

        session_id = self.sessions.create(project_id, "Session 1")
        self.assertIsNotNone(self.sessions.get_by_id(session_id))
        self.assertTrue(self.sessions.update(session_id, status="finished", summary="ok"))

        record_id = self.records.create(
            session_id=session_id,
            record_type="text",
            content="hello",
            is_inspiration=True,
        )
        self.assertIsNotNone(self.records.get_by_id(record_id))
        self.assertTrue(self.records.update(record_id, content="hello2"))

        note_id = self.notes.create(
            session_id=session_id,
            summary="summary",
            suggestions="suggestions",
            guidance="guidance",
        )
        self.assertIsNotNone(self.notes.get_by_id(note_id))
        self.assertTrue(self.notes.update(note_id, summary="summary2"))

        prompt_id = self.prompts.create(
            scope="global",
            name="default",
            content="template",
        )
        self.assertIsNotNone(self.prompts.get_by_id(prompt_id))
        self.assertTrue(self.prompts.update(prompt_id, is_active=False))

        self.assertTrue(self.records.delete(record_id))
        self.assertTrue(self.notes.delete(note_id))
        self.assertTrue(self.prompts.delete(prompt_id))
        self.assertTrue(self.sessions.delete(session_id))
        self.assertTrue(self.projects.delete(project_id))


class UISmokeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "ui_smoke.db"
        self.db = Database(self.db_path)
        self.db.initialize()

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_main_window_navigation(self) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        projects = ProjectRepository(self.db.as_path())
        sessions = SessionRepository(self.db.as_path())
        project_service = ProjectService(projects)
        session_service = SessionService(sessions, projects)

        app = QApplication.instance() or QApplication([])
        window = MainWindow(project_service=project_service, session_service=session_service)

        self.assertEqual(window.nav.count(), 5)
        self.assertEqual(window.stack.count(), 5)

        for idx in range(window.nav.count()):
            window.nav.setCurrentRow(idx)
            self.assertEqual(window.stack.currentIndex(), idx)

        window.close()
        app.quit()


if __name__ == "__main__":
    unittest.main(verbosity=2)
