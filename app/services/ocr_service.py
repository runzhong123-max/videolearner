import json
from datetime import UTC, datetime
from pathlib import Path

from app.config import BASE_DIR
from app.models.record_ocr_result import RecordOCRResult
from app.repositories.record_ocr_repository import RecordOCRRepository
from app.repositories.record_repository import RecordRepository
from app.services.errors import ServiceError
from app.services.ocr_providers.base_provider import BaseOCRProvider
from app.services.ocr_providers.mock_provider import MockOCRProvider
from app.utils.path_utils import resolve_record_file_path

OCR_STATUS_NOT_PROCESSED = "not_processed"
OCR_STATUS_COMPLETED = "completed"
OCR_STATUS_FAILED = "failed"


class OCRService:
    def __init__(
        self,
        record_repository: RecordRepository,
        record_ocr_repository: RecordOCRRepository,
        provider: BaseOCRProvider | None = None,
        app_root: Path = BASE_DIR,
    ):
        self.record_repository = record_repository
        self.record_ocr_repository = record_ocr_repository
        self.provider = provider or MockOCRProvider()
        self.app_root = app_root

    def get_result_by_record(self, record_id: int) -> RecordOCRResult | None:
        return self.record_ocr_repository.get_by_record(record_id)

    def get_or_default_result(self, record_id: int) -> RecordOCRResult:
        existing = self.record_ocr_repository.get_by_record(record_id)
        if existing is not None:
            return existing

        now = datetime.now(UTC)
        return RecordOCRResult(
            id=None,
            record_id=record_id,
            ocr_text="",
            ocr_status=OCR_STATUS_NOT_PROCESSED,
            ocr_error="",
            provider=getattr(self.provider, "name", "mock_ocr"),
            metadata_json="{}",
            processed_at=None,
            created_at=now,
            updated_at=now,
        )

    def run_ocr_for_record(self, record_id: int) -> RecordOCRResult:
        record = self.record_repository.get_by_id(record_id)
        if record is None:
            raise ServiceError("Record 不存在，无法执行 OCR。")
        if record.record_type != "image":
            raise ServiceError("仅 image Record 支持 OCR。")

        provider_name = getattr(self.provider, "name", "mock_ocr")
        processed_at = datetime.now(UTC)

        file_path = resolve_record_file_path(record.file_path, app_root=self.app_root)
        if file_path is None or not file_path.exists():
            error = "图片文件不存在，无法执行 OCR。"
            self.record_ocr_repository.upsert(
                record_id=record.id,
                ocr_text="",
                ocr_status=OCR_STATUS_FAILED,
                ocr_error=error,
                provider=provider_name,
                metadata_json=json.dumps({"file_path": record.file_path}, ensure_ascii=False),
                processed_at=processed_at,
            )
            raise ServiceError(error)

        try:
            text = (self.provider.extract_text(file_path) or "").strip()
        except Exception as exc:
            error = f"OCR 执行失败：{exc}"
            self.record_ocr_repository.upsert(
                record_id=record.id,
                ocr_text="",
                ocr_status=OCR_STATUS_FAILED,
                ocr_error=error,
                provider=provider_name,
                metadata_json=json.dumps({"file_path": record.file_path}, ensure_ascii=False),
                processed_at=processed_at,
            )
            raise ServiceError(error) from exc

        if not text:
            error = "OCR 未识别到文本。"
            self.record_ocr_repository.upsert(
                record_id=record.id,
                ocr_text="",
                ocr_status=OCR_STATUS_FAILED,
                ocr_error=error,
                provider=provider_name,
                metadata_json=json.dumps({"file_path": record.file_path}, ensure_ascii=False),
                processed_at=processed_at,
            )
            raise ServiceError(error)

        metadata = {
            "file_path": record.file_path,
            "file_size": file_path.stat().st_size,
        }
        self.record_ocr_repository.upsert(
            record_id=record.id,
            ocr_text=text,
            ocr_status=OCR_STATUS_COMPLETED,
            ocr_error="",
            provider=provider_name,
            metadata_json=json.dumps(metadata, ensure_ascii=False),
            processed_at=processed_at,
        )

        refreshed = self.record_ocr_repository.get_by_record(record.id)
        if refreshed is None:
            raise ServiceError("OCR 结果保存后读取失败。")
        return refreshed
