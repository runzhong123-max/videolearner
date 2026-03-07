import os
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db.database import Database
from app.models.note import Note
from app.repositories.note_repository import NoteRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.record_repository import RecordRepository
from app.repositories.session_repository import SessionRepository
from app.services.project_service import ProjectService
from app.services.record_service import RECORD_TYPE_IMAGE, RECORD_TYPE_TEXT, RecordService
from app.services.session_service import SessionService
from app.ui.pages.study_page import StudyPage
from app.ui.view_helpers import build_session_item_text, iter_note_sections, parse_note_sections
from app.utils.datetime_utils import (
    format_cn_datetime,
    format_cn_datetime_seconds,
    format_cn_time,
    format_offset_hms,
)


class FakeCaptureService:
    def capture_screen(self, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake")


class StubNoteService:
    def __init__(self, note_repo: NoteRepository):
        self.note_repo = note_repo

    def get_latest_note_for_session(self, session_id: int):
        return self.note_repo.get_by_session(session_id)


class Phase5WorkspaceViewTest(unittest.TestCase):
    def setUp(self) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_root = Path(self.tmp_dir.name)
        self.db_path = self.tmp_root / "phase5.db"

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
        self.note_service = StubNoteService(self.note_repo)

        from PySide6.QtWidgets import QApplication

        self.app = QApplication.instance() or QApplication([])

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def _build_page(self) -> StudyPage:
        page = StudyPage(
            session_service=self.session_service,
            record_service=self.record_service,
            note_service=self.note_service,
        )
        return page

    def _seed_project_with_two_sessions(self):
        project = self.project_service.create_project(name="P5")
        s1 = self.session_repo.create(project.id, title="Session A", status="finished")
        s2 = self.session_repo.create(project.id, title="Session B", status="finished")
        return project, s1, s2

    def test_history_sessions_can_be_read_and_selected(self) -> None:
        project, s1, s2 = self._seed_project_with_two_sessions()
        page = self._build_page()
        page.set_current_project(project)

        self.assertEqual(page.session_list.count(), 2)

        row_for_s1 = None
        row_for_s2 = None
        for idx in range(page.session_list.count()):
            item = page.session_list.item(idx)
            sid = int(item.data(Qt.ItemDataRole.UserRole))
            if sid == s1:
                row_for_s1 = idx
            if sid == s2:
                row_for_s2 = idx

        self.assertIsNotNone(row_for_s1)
        self.assertIsNotNone(row_for_s2)

        page.session_list.setCurrentRow(row_for_s1)
        self.assertEqual(page.selected_session_id, s1)
        page.session_list.setCurrentRow(row_for_s2)
        self.assertEqual(page.selected_session_id, s2)

    def test_session_item_has_record_count_and_note_status(self) -> None:
        project, s1, _s2 = self._seed_project_with_two_sessions()
        self.record_repo.create(session_id=s1, record_type="text", content="idea", is_inspiration=True)
        self.note_repo.create(session_id=s1, summary="s", suggestions="x")

        session = self.session_repo.get_by_id(s1)
        self.assertIsNotNone(session)

        text = build_session_item_text(
            session=session,
            record_count=1,
            has_note=True,
        )
        self.assertIn("Record 1 条", text)
        self.assertIn("有笔记", text)

        page = self._build_page()
        page.set_current_project(project)
        matched = [
            page.session_list.item(i).text()
            for i in range(page.session_list.count())
            if f"#{s1}" in page.session_list.item(i).text()
        ]
        self.assertTrue(matched)
        self.assertIn("Record 1 条", matched[0])
        self.assertIn("有笔记", matched[0])

    def test_select_different_session_switches_timeline(self) -> None:
        project, s1, s2 = self._seed_project_with_two_sessions()
        r1 = self.record_repo.create(session_id=s1, record_type="text", content="a")
        r2 = self.record_repo.create(session_id=s2, record_type="text", content="b")

        page = self._build_page()
        page.set_current_project(project)

        for idx in range(page.session_list.count()):
            item = page.session_list.item(idx)
            sid = int(item.data(Qt.ItemDataRole.UserRole))
            page.session_list.setCurrentRow(idx)
            loaded_ids = set(page._records_by_id.keys())
            if sid == s1:
                self.assertEqual(loaded_ids, {r1})
            elif sid == s2:
                self.assertEqual(loaded_ids, {r2})

    def test_delete_record_refreshes_timeline_and_detail(self) -> None:
        project, s1, _s2 = self._seed_project_with_two_sessions()
        record_id = self.record_repo.create(session_id=s1, record_type="text", content="to delete")

        page = self._build_page()
        page.set_current_project(project)

        target_row = None
        for idx in range(page.session_list.count()):
            sid = int(page.session_list.item(idx).data(Qt.ItemDataRole.UserRole))
            if sid == s1:
                target_row = idx
                break
        self.assertIsNotNone(target_row)

        page.session_list.setCurrentRow(target_row)
        self.assertEqual(set(page._records_by_id.keys()), {record_id})

        timeline_row = None
        for idx in range(page.timeline_list.count()):
            rid = page.timeline_list.item(idx).data(Qt.ItemDataRole.UserRole)
            if rid == record_id:
                timeline_row = idx
                break
        self.assertIsNotNone(timeline_row)

        page.timeline_list.setCurrentRow(timeline_row)

        from PySide6.QtWidgets import QMessageBox

        with patch("app.ui.pages.study_page.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes):
            page._on_delete_record()

        self.assertIsNone(self.record_repo.get_by_id(record_id))
        self.assertEqual(page.selected_record_id, None)
        self.assertIn(page.detail_stack.currentIndex(), {0, 1})

    def test_datetime_utils_formats_beijing(self) -> None:
        utc_dt = datetime(2026, 3, 6, 11, 9, 10, tzinfo=UTC)
        self.assertEqual(format_cn_datetime(utc_dt), "2026年3月6日 19:09")
        self.assertEqual(format_cn_datetime_seconds(utc_dt), "2026年3月6日 19:09:10")
        self.assertEqual(format_cn_time(utc_dt), "19:09:10")
        self.assertEqual(format_offset_hms(3661), "+01:01:01")

    def test_note_section_parser_works_for_typical_input(self) -> None:
        now = datetime.now(UTC)
        note = Note(
            id=1,
            project_id=1,
            session_id=1,
            note_type="session_summary",
            title="N",
            content=(
                "## Summary\n\nA\n\n"
                "## Insight\n\nB\n\n"
                "## Extension\n\nC\n\n"
                "## Guidance\n\nD\n"
            ),
            summary="",
            suggestions="",
            inspiration_refinement="",
            guidance="",
            created_at=now,
            updated_at=now,
        )

        sections = parse_note_sections(note)
        self.assertEqual(sections["summary"], "A")
        self.assertEqual(sections["inspirations"], "B")
        self.assertEqual(sections["expansion"], "C")
        self.assertEqual(sections["guidance"], "D")

        block_titles = [title for _, title, _ in iter_note_sections(note)]
        self.assertIn("Summary", block_titles)
        self.assertIn("Inspirations", block_titles)
        self.assertIn("Expansion", block_titles)
        self.assertIn("Guidance", block_titles)

    def test_record_chat_entry_exists_and_disabled_without_record(self) -> None:
        project, _s1, _s2 = self._seed_project_with_two_sessions()
        page = self._build_page()
        page.set_current_project(project)

        self.assertIn("开始对话", page.ask_ai_btn.text())
        self.assertFalse(page.ask_ai_btn.isEnabled())
        self.assertFalse(page.chat_send_btn.isEnabled())


    def test_finished_session_insight_can_be_edited_in_study(self) -> None:
        project = self.project_service.create_project(name="P5-Insight-Edit")
        active_session = self.session_service.start_session(project.id)
        insight_record = self.record_service.create_text_record(active_session.id, "before finish")
        self.session_service.finish_session(active_session.id)

        page = self._build_page()
        page.set_current_project(project)

        session_row = None
        for idx in range(page.session_list.count()):
            sid = int(page.session_list.item(idx).data(Qt.ItemDataRole.UserRole))
            if sid == active_session.id:
                session_row = idx
                break
        self.assertIsNotNone(session_row)
        page.session_list.setCurrentRow(session_row)

        record_row = None
        for idx in range(page.timeline_list.count()):
            rid = page.timeline_list.item(idx).data(Qt.ItemDataRole.UserRole)
            if rid == insight_record.id:
                record_row = idx
                break
        self.assertIsNotNone(record_row)
        page.timeline_list.setCurrentRow(record_row)

        self.assertTrue(page.edit_insight_btn.isEnabled())

        with patch(
            "app.ui.pages.study_page.StudyPage._prompt_topmost_multiline_text",
            return_value=("edited after finish", True),
        ):
            page._on_edit_insight()

        refreshed = self.record_repo.get_by_id(insight_record.id)
        self.assertIsNotNone(refreshed)
        self.assertEqual(refreshed.content, "edited after finish")

    def test_insight_capture_happens_before_text_dialog(self) -> None:
        project = self.project_service.create_project(name="P5-Insight-Capture-Order")
        session = self.session_service.start_session(project.id)

        page = self._build_page()
        page.set_current_project(project)

        capture_called: list[bool] = []
        original_capture = self.record_service.create_image_record_with_options

        def wrapped_capture(*args, **kwargs):
            capture_called.append(True)
            return original_capture(*args, **kwargs)

        self.record_service.create_image_record_with_options = wrapped_capture  # type: ignore[method-assign]

        def fake_dialog(*_args, **_kwargs):
            self.assertTrue(capture_called)
            return ("ordered insight", True)

        with patch(
            "app.ui.pages.study_page.StudyPage._prompt_topmost_multiline_text",
            side_effect=fake_dialog,
        ):
            page._on_record_text_with_capture()

        records = self.record_repo.list_by_session(session.id)
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0].record_type, RECORD_TYPE_IMAGE)
        self.assertEqual(records[1].record_type, RECORD_TYPE_TEXT)


if __name__ == "__main__":
    unittest.main(verbosity=2)

