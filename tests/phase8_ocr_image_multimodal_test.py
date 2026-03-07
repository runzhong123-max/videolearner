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
from app.repositories.record_ocr_repository import RecordOCRRepository
from app.repositories.record_repository import RecordRepository
from app.repositories.session_repository import SessionRepository
from app.services.ai_service import AIService
from app.services.capture_service import (
    CAPTURE_MODE_ACTIVE_WINDOW,
    CAPTURE_MODE_FULL_SCREEN,
    CaptureService,
)
from app.services.errors import ServiceError
from app.services.ocr_providers.base_provider import BaseOCRProvider
from app.services.ocr_service import OCR_STATUS_COMPLETED, OCR_STATUS_FAILED, OCRService
from app.services.project_service import ProjectService
from app.services.prompt_service import PromptService
from app.services.record_chat_context_builder import RecordChatContextBuilder
from app.services.record_chat_service import RecordChatService
from app.services.record_service import RecordService


class FakeCaptureService:
    def capture_screen(self, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake-image")


class SuccessOCRProvider(BaseOCRProvider):
    name = "mock_ocr"

    def extract_text(self, image_path: Path) -> str:
        return f"OCR({image_path.name}) => sample text"


class FailingOCRProvider(BaseOCRProvider):
    name = "mock_ocr"

    def extract_text(self, image_path: Path) -> str:
        _ = image_path
        raise RuntimeError("ocr engine down")


class DummyImage:
    def __init__(self, marker: bytes = b"img"):
        self.marker = marker

    def save(self, output_path: Path) -> None:
        Path(output_path).write_bytes(self.marker)


class CaptureServicePhase8Test(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_root = Path(self.tmp_dir.name)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_capture_mode_dispatch_and_active_window_fallback(self) -> None:
        calls: list[dict] = []

        def grabber(**kwargs):
            calls.append(kwargs)
            return DummyImage()

        service = CaptureService(grabber=grabber, active_window_detector=lambda: None)
        output_path = self.tmp_root / "capture.png"

        result = service.capture(output_path, mode=CAPTURE_MODE_ACTIVE_WINDOW)

        self.assertEqual(result.requested_mode, CAPTURE_MODE_ACTIVE_WINDOW)
        self.assertEqual(result.actual_mode, CAPTURE_MODE_FULL_SCREEN)
        self.assertEqual(result.fallback_reason, "active_window_unavailable")
        self.assertTrue(output_path.exists())
        self.assertEqual(calls[-1], {"all_screens": True})

    def test_capture_active_window_uses_window_bbox_when_available(self) -> None:
        calls: list[dict] = []

        def grabber(**kwargs):
            calls.append(kwargs)
            return DummyImage(b"active")

        bbox = (1, 2, 120, 80)
        service = CaptureService(grabber=grabber, active_window_detector=lambda: bbox)
        output_path = self.tmp_root / "active.png"

        result = service.capture(output_path, mode=CAPTURE_MODE_ACTIVE_WINDOW)

        self.assertEqual(result.actual_mode, CAPTURE_MODE_ACTIVE_WINDOW)
        self.assertEqual(result.region, bbox)
        self.assertEqual(calls[-1], {"bbox": bbox})

    def test_capture_unsupported_mode_raises_service_error(self) -> None:
        service = CaptureService(grabber=lambda **_kwargs: DummyImage())
        with self.assertRaises(ServiceError):
            service.capture(self.tmp_root / "x.png", mode="unsupported_mode")


class Phase8OCRAndImageChatTest(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["AI_PROVIDER"] = "mock"

        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_root = Path(self.tmp_dir.name)
        self.db_path = self.tmp_root / "phase8.db"
        db = Database(self.db_path)
        db.initialize()

        db_path = str(self.db_path)
        self.project_repo = ProjectRepository(db_path)
        self.session_repo = SessionRepository(db_path)
        self.record_repo = RecordRepository(db_path)
        self.record_ocr_repo = RecordOCRRepository(db_path)
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
            record_ocr_repository=self.record_ocr_repo,
        )
        return RecordChatService(
            conversation_repository=self.conversation_repo,
            message_repository=self.message_repo,
            record_repository=self.record_repo,
            session_repository=self.session_repo,
            context_builder=context_builder,
            ai_service=ai_service or AIService(),
        )

    def _create_active_image_record(self) -> tuple[int, int, int]:
        project = self.project_service.create_project(name="P8-Image")
        session_id = self.session_repo.create(project.id, title="S", status="in_progress")
        image = self.record_service.create_image_record(session_id, project.id)
        return project.id, session_id, image.id

    def test_image_record_can_persist_ocr_result_and_reload(self) -> None:
        _project_id, _session_id, record_id = self._create_active_image_record()
        ocr_service = OCRService(self.record_repo, self.record_ocr_repo, provider=SuccessOCRProvider(), app_root=self.tmp_root)

        result = ocr_service.run_ocr_for_record(record_id)
        self.assertEqual(result.ocr_status, OCR_STATUS_COMPLETED)
        self.assertIn("sample text", result.ocr_text)

        loaded = self.record_ocr_repo.get_by_record(record_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.ocr_status, OCR_STATUS_COMPLETED)
        self.assertIn("sample text", loaded.ocr_text)

    def test_ocr_failure_persists_failed_status_and_error(self) -> None:
        _project_id, _session_id, record_id = self._create_active_image_record()
        ocr_service = OCRService(self.record_repo, self.record_ocr_repo, provider=FailingOCRProvider(), app_root=self.tmp_root)

        with self.assertRaises(ServiceError):
            ocr_service.run_ocr_for_record(record_id)

        loaded = self.record_ocr_repo.get_by_record(record_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.ocr_status, OCR_STATUS_FAILED)
        self.assertIn("ocr engine down", loaded.ocr_error)

    def test_image_record_chat_works_in_mock_mode(self) -> None:
        _project_id, _session_id, record_id = self._create_active_image_record()
        ocr_service = OCRService(self.record_repo, self.record_ocr_repo, provider=SuccessOCRProvider(), app_root=self.tmp_root)
        ocr_service.run_ocr_for_record(record_id)

        chat_service = self._build_chat_service(ai_service=AIService())
        result = chat_service.send_user_message(record_id, "这张图在讲什么？")

        self.assertFalse(result.is_stub)
        self.assertTrue(result.assistant_message.content)
        self.assertEqual(result.conversation.provider, "mock")

    def test_text_chat_still_works_when_image_chat_enabled(self) -> None:
        project = self.project_service.create_project(name="P8-Text")
        session_id = self.session_repo.create(project.id, title="S", status="finished")
        text_record_id = self.record_repo.create(
            session_id=session_id,
            record_type="text",
            content="hello text",
            is_inspiration=True,
        )

        chat_service = self._build_chat_service(ai_service=AIService())
        result = chat_service.send_user_message(text_record_id, "解释这条文本")

        self.assertFalse(result.is_stub)
        self.assertTrue(result.assistant_message.content)

    def test_delete_image_record_cascades_ocr_result(self) -> None:
        _project_id, _session_id, record_id = self._create_active_image_record()
        ocr_service = OCRService(self.record_repo, self.record_ocr_repo, provider=SuccessOCRProvider(), app_root=self.tmp_root)
        ocr_service.run_ocr_for_record(record_id)

        self.record_service.delete_record(record_id)
        self.assertIsNone(self.record_ocr_repo.get_by_record(record_id))


if __name__ == "__main__":
    unittest.main(verbosity=2)

