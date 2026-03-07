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
from app.repositories.note_repository import NoteRepository
from app.repositories.output_profile_repository import OutputProfileRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.prompt_template_repository import PromptTemplateRepository
from app.repositories.record_chat_message_repository import RecordChatMessageRepository
from app.repositories.record_conversation_repository import RecordConversationRepository
from app.repositories.record_ocr_repository import RecordOCRRepository
from app.repositories.record_repository import RecordRepository
from app.repositories.session_repository import SessionRepository
from app.services.capture_service import CAPTURE_MODE_FULL_SCREEN
from app.services.context_builder import ContextBuilder
from app.services.ocr_providers.base_provider import BaseOCRProvider
from app.services.ocr_providers.ocr_result import OCRResult
from app.services.ocr_providers.provider_factory import (
    OCR_PROVIDER_LOCAL,
    OCR_PROVIDER_MOCK,
    OCRProviderFactory,
)
from app.services.ocr_service import OCR_STATUS_COMPLETED, OCRService
from app.services.ocr_settings_service import OCRSettingsService
from app.services.output_profile_service import OutputProfileService
from app.services.project_service import ProjectService
from app.services.prompt_service import PromptService
from app.services.record_chat_context_builder import RecordChatContextBuilder
from app.services.record_service import RecordService


class FakeCaptureService:
    def capture_screen(self, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake-image")


class DummySuccessOCRProvider(BaseOCRProvider):
    name = OCR_PROVIDER_LOCAL

    def extract_text(self, image_path: Path) -> OCRResult:
        return OCRResult(
            text=f"OCR_OK:{image_path.name}",
            provider=self.name,
            success=True,
            error=None,
            metadata={"source": "dummy"},
        )


class Phase8LocalOCRIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["AI_PROVIDER"] = "mock"

        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_root = Path(self.tmp_dir.name)
        self.db_path = self.tmp_root / "phase8_local_ocr.db"
        db = Database(self.db_path)
        db.initialize()

        db_path = str(self.db_path)
        self.project_repo = ProjectRepository(db_path)
        self.session_repo = SessionRepository(db_path)
        self.record_repo = RecordRepository(db_path)
        self.record_ocr_repo = RecordOCRRepository(db_path)
        self.record_conversation_repo = RecordConversationRepository(db_path)
        self.record_chat_message_repo = RecordChatMessageRepository(db_path)
        self.note_repo = NoteRepository(db_path)
        self.prompt_repo = PromptTemplateRepository(db_path)
        self.output_profile_repo = OutputProfileRepository(db_path)
        self.app_settings_repo = AppSettingRepository(db_path)

        self.project_service = ProjectService(self.project_repo)
        self.record_service = RecordService(
            self.record_repo,
            self.session_repo,
            FakeCaptureService(),
            projects_root=self.tmp_root / "data" / "projects",
            app_root=self.tmp_root,
        )
        self.ocr_settings_service = OCRSettingsService(self.app_settings_repo)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def _create_active_image_record(self) -> int:
        project = self.project_service.create_project(name="P8-LocalOCR")
        session_id = self.session_repo.create(project.id, title="S", status="in_progress")
        image = self.record_service.create_image_record(
            session_id=session_id,
            project_id=project.id,
            capture_mode=CAPTURE_MODE_FULL_SCREEN,
        )
        return image.id

    def test_ocr_settings_can_save_and_load(self) -> None:
        self.ocr_settings_service.save_settings(
            provider=OCR_PROVIDER_LOCAL,
            tesseract_cmd=r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            ocr_lang="chi_sim+eng",
        )

        loaded = self.ocr_settings_service.load_settings()
        self.assertEqual(loaded.provider, OCR_PROVIDER_LOCAL)
        self.assertIn("Tesseract-OCR", loaded.tesseract_cmd)
        self.assertEqual(loaded.ocr_lang, "chi_sim+eng")

    def test_ocr_provider_factory_supports_mock_and_local(self) -> None:
        mock_provider = OCRProviderFactory.create_provider(OCR_PROVIDER_MOCK)
        local_provider = OCRProviderFactory.create_provider(
            OCR_PROVIDER_LOCAL,
            tesseract_cmd=r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            ocr_lang="eng",
        )

        self.assertEqual(getattr(mock_provider, "name", ""), OCR_PROVIDER_MOCK)
        self.assertEqual(getattr(local_provider, "name", ""), OCR_PROVIDER_LOCAL)

    def test_ocr_service_not_hardcoded_mock_when_settings_local(self) -> None:
        self.ocr_settings_service.save_settings(
            provider=OCR_PROVIDER_LOCAL,
            tesseract_cmd="",
            ocr_lang="chi_sim+eng",
        )

        service = OCRService(
            record_repository=self.record_repo,
            record_ocr_repository=self.record_ocr_repo,
            ocr_settings_service=self.ocr_settings_service,
            app_root=self.tmp_root,
        )
        default_result = service.get_or_default_result(record_id=9999)
        self.assertEqual(default_result.provider, OCR_PROVIDER_LOCAL)

    def test_mock_ocr_still_available_for_offline(self) -> None:
        self.ocr_settings_service.save_settings(
            provider=OCR_PROVIDER_MOCK,
            tesseract_cmd="",
            ocr_lang="chi_sim+eng",
        )
        record_id = self._create_active_image_record()

        service = OCRService(
            record_repository=self.record_repo,
            record_ocr_repository=self.record_ocr_repo,
            ocr_settings_service=self.ocr_settings_service,
            app_root=self.tmp_root,
        )

        result = service.run_ocr_for_record(record_id)
        self.assertEqual(result.ocr_status, OCR_STATUS_COMPLETED)
        self.assertIn("Mock OCR", result.ocr_text)
        self.assertEqual(result.provider, OCR_PROVIDER_MOCK)

    def test_injected_provider_can_persist_ocr_result_without_tesseract(self) -> None:
        record_id = self._create_active_image_record()
        service = OCRService(
            record_repository=self.record_repo,
            record_ocr_repository=self.record_ocr_repo,
            provider=DummySuccessOCRProvider(),
            app_root=self.tmp_root,
        )

        result = service.run_ocr_for_record(record_id)
        self.assertEqual(result.ocr_status, OCR_STATUS_COMPLETED)
        self.assertEqual(result.provider, OCR_PROVIDER_LOCAL)
        self.assertIn("OCR_OK", result.ocr_text)

        loaded = self.record_ocr_repo.get_by_record(record_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.ocr_status, OCR_STATUS_COMPLETED)
        self.assertIn("OCR_OK", loaded.ocr_text)

    def test_note_context_builder_includes_ocr_text(self) -> None:
        project = self.project_service.create_project(name="P8-Context")
        session_id = self.session_repo.create(project.id, title="S", status="finished")
        record_id = self.record_repo.create(
            session_id=session_id,
            record_type="image",
            file_path="data/projects/project_1/assets/session_1/example.png",
            timestamp_offset=3,
        )
        self.record_ocr_repo.upsert(
            record_id=record_id,
            ocr_text="this is ocr text",
            ocr_status=OCR_STATUS_COMPLETED,
            provider=OCR_PROVIDER_LOCAL,
        )

        prompt_service = PromptService(self.prompt_repo, self.session_repo)
        output_profile_service = OutputProfileService(
            self.output_profile_repo,
            self.session_repo,
            self.record_repo,
        )
        context_builder = ContextBuilder(
            project_repository=self.project_repo,
            session_repository=self.session_repo,
            record_repository=self.record_repo,
            record_ocr_repository=self.record_ocr_repo,
            note_repository=self.note_repo,
            prompt_service=prompt_service,
            output_profile_service=output_profile_service,
        )

        bundle = context_builder.build_for_session(session_id)
        self.assertIn("ocr_status=completed", bundle.context_text)
        self.assertIn("ocr_text=this is ocr text", bundle.context_text)

    def test_image_chat_context_builder_includes_ocr_text(self) -> None:
        project = self.project_service.create_project(name="P8-Chat")
        session_id = self.session_repo.create(project.id, title="S", status="in_progress")
        record_id = self.record_repo.create(
            session_id=session_id,
            record_type="image",
            file_path="data/projects/project_1/assets/session_1/chat.png",
            timestamp_offset=8,
        )
        self.record_ocr_repo.upsert(
            record_id=record_id,
            ocr_text="chat ocr text",
            ocr_status=OCR_STATUS_COMPLETED,
            provider=OCR_PROVIDER_LOCAL,
        )

        prompt_service = PromptService(self.prompt_repo, self.session_repo)
        context_builder = RecordChatContextBuilder(
            project_repository=self.project_repo,
            session_repository=self.session_repo,
            record_repository=self.record_repo,
            conversation_repository=self.record_conversation_repo,
            message_repository=self.record_chat_message_repo,
            prompt_service=prompt_service,
            record_ocr_repository=self.record_ocr_repo,
        )

        bundle = context_builder.build_for_record(record_id=record_id, user_question="这张图讲了什么？")
        self.assertIn("ocr_status=completed", bundle.context_text)
        self.assertIn("ocr_text=chat ocr text", bundle.context_text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
