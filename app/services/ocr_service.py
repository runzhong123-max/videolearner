import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import BASE_DIR
from app.models.record_ocr_result import RecordOCRResult
from app.repositories.record_ocr_repository import RecordOCRRepository
from app.repositories.record_repository import RecordRepository
from app.services.errors import ServiceError
from app.services.ocr_providers.base_provider import BaseOCRProvider
from app.services.ocr_providers.ocr_result import OCRResult
from app.services.ocr_providers.provider_factory import OCR_PROVIDER_MOCK, OCRProviderFactory
from app.services.ocr_settings_service import OCRSettingsService
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
        ocr_settings_service: OCRSettingsService | None = None,
        provider_factory=OCRProviderFactory,
        app_root: Path = BASE_DIR,
    ):
        self.record_repository = record_repository
        self.record_ocr_repository = record_ocr_repository
        self.provider = provider
        self.ocr_settings_service = ocr_settings_service
        self.provider_factory = provider_factory
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
            provider=self._safe_provider_name(),
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

        provider = self._resolve_provider()
        provider_name = getattr(provider, "name", OCR_PROVIDER_MOCK)
        processed_at = datetime.now(UTC)

        file_path = resolve_record_file_path(record.file_path, app_root=self.app_root)
        if file_path is None or not file_path.exists():
            error = "图片文件不存在，无法执行 OCR。"
            self._save_failed(record.id, provider_name, error, processed_at, {"file_path": record.file_path})
            raise ServiceError(error)

        try:
            raw_result = provider.extract_text(file_path)
            result = self._normalize_provider_result(raw_result, provider_name)
        except Exception as exc:
            error = f"OCR 执行失败：{exc}"
            self._save_failed(record.id, provider_name, error, processed_at, {"file_path": record.file_path})
            raise ServiceError(error) from exc

        if not result.success:
            error = (result.error or "OCR 未识别到文本。").strip() or "OCR 未识别到文本。"
            metadata = self._merge_metadata(
                base={"file_path": record.file_path},
                extra=result.metadata,
            )
            self._save_failed(record.id, result.provider or provider_name, error, processed_at, metadata)
            raise ServiceError(error)

        text = (result.text or "").strip()
        if not text:
            error = "OCR 未识别到文本。"
            metadata = self._merge_metadata(
                base={"file_path": record.file_path},
                extra=result.metadata,
            )
            self._save_failed(record.id, result.provider or provider_name, error, processed_at, metadata)
            raise ServiceError(error)

        metadata = self._merge_metadata(
            base={
                "file_path": record.file_path,
                "file_size": file_path.stat().st_size,
            },
            extra=result.metadata,
        )
        self.record_ocr_repository.upsert(
            record_id=record.id,
            ocr_text=text,
            ocr_status=OCR_STATUS_COMPLETED,
            ocr_error="",
            provider=result.provider or provider_name,
            metadata_json=self._safe_dumps(metadata),
            processed_at=processed_at,
        )

        refreshed = self.record_ocr_repository.get_by_record(record.id)
        if refreshed is None:
            raise ServiceError("OCR 结果保存后读取失败。")
        return refreshed

    def _resolve_provider(self) -> BaseOCRProvider:
        if self.provider is not None:
            return self.provider

        if self.ocr_settings_service is not None:
            try:
                return self.ocr_settings_service.build_provider()
            except Exception as exc:
                raise ServiceError(f"OCR provider 配置错误：{exc}") from exc

        return self.provider_factory.create_provider(OCR_PROVIDER_MOCK)

    def _safe_provider_name(self) -> str:
        try:
            provider = self._resolve_provider()
            return getattr(provider, "name", OCR_PROVIDER_MOCK)
        except Exception:
            return OCR_PROVIDER_MOCK

    @staticmethod
    def _normalize_provider_result(raw_result: Any, provider_name: str) -> OCRResult:
        if isinstance(raw_result, OCRResult):
            return raw_result

        if isinstance(raw_result, str):
            text = raw_result.strip()
            return OCRResult(
                text=text,
                provider=provider_name,
                success=bool(text),
                error=None if text else "OCR 未识别到文本。",
                metadata=None,
            )

        if isinstance(raw_result, dict):
            text = str(raw_result.get("text", "")).strip()
            success = bool(raw_result.get("success", bool(text)))
            return OCRResult(
                text=text,
                provider=str(raw_result.get("provider") or provider_name),
                success=success,
                error=raw_result.get("error"),
                metadata=raw_result.get("metadata") if isinstance(raw_result.get("metadata"), dict) else None,
            )

        raise ServiceError("OCR provider 返回结构非法。")

    def _save_failed(
        self,
        record_id: int,
        provider_name: str,
        error: str,
        processed_at: datetime,
        metadata: dict[str, Any],
    ) -> None:
        self.record_ocr_repository.upsert(
            record_id=record_id,
            ocr_text="",
            ocr_status=OCR_STATUS_FAILED,
            ocr_error=error,
            provider=provider_name,
            metadata_json=self._safe_dumps(metadata),
            processed_at=processed_at,
        )

    @staticmethod
    def _merge_metadata(base: dict[str, Any], extra: dict[str, Any] | None) -> dict[str, Any]:
        merged = dict(base)
        if extra:
            merged.update(extra)
        return merged

    @staticmethod
    def _safe_dumps(payload: dict[str, Any]) -> str:
        try:
            return json.dumps(payload, ensure_ascii=False)
        except Exception:
            return "{}"

