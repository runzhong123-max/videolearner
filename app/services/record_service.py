import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from app.config import BASE_DIR, PROJECTS_DATA_DIR
from app.models.record import Record
from app.models.session import Session
from app.repositories.record_repository import RecordRepository
from app.repositories.session_repository import SessionRepository
from app.services.capture_service import (
    CAPTURE_MODE_ACTIVE_WINDOW,
    CAPTURE_MODE_FULL_SCREEN,
    CaptureService,
)
from app.services.errors import ServiceError
from app.services.session_service import SESSION_IN_PROGRESS
from app.utils.path_utils import build_session_asset_dir, resolve_record_file_path

RECORD_TYPE_IMAGE = "image"
RECORD_TYPE_TEXT = "text"
SUPPORTED_RECORD_TYPES = {RECORD_TYPE_IMAGE, RECORD_TYPE_TEXT}


@dataclass
class RecordDeleteResult:
    record_id: int
    warnings: list[str] = field(default_factory=list)


class RecordService:
    def __init__(
        self,
        record_repository: RecordRepository,
        session_repository: SessionRepository,
        capture_service: CaptureService,
        projects_root: Path = PROJECTS_DATA_DIR,
        app_root: Path = BASE_DIR,
    ):
        self.record_repository = record_repository
        self.session_repository = session_repository
        self.capture_service = capture_service
        self.projects_root = projects_root
        self.app_root = app_root

    def list_records_by_session(self, session_id: int) -> list[Record]:
        return self.record_repository.list_by_session(session_id)

    def create_text_record(self, session_id: int, text_content: str) -> Record:
        content = text_content.strip()
        if not content:
            raise ServiceError("灵感文本不能为空。")

        session = self._ensure_writable_session(session_id)
        now = datetime.now(UTC)
        offset = self._timestamp_offset_seconds(session, now)

        metadata_json = json.dumps(
            {
                "record_type": RECORD_TYPE_TEXT,
                "text_content": content,
                "timestamp_offset": offset,
            },
            ensure_ascii=False,
        )

        record_id = self.record_repository.create(
            session_id=session.id,
            record_type=RECORD_TYPE_TEXT,
            content=content,
            timestamp_offset=offset,
            metadata_json=metadata_json,
            is_inspiration=True,
        )
        return self._read_created_record(record_id)

    def create_image_record(
        self,
        session_id: int,
        project_id: int,
        capture_mode: str = CAPTURE_MODE_ACTIVE_WINDOW,
    ) -> Record:
        return self.create_image_record_with_options(
            session_id=session_id,
            project_id=project_id,
            is_inspiration=False,
            linked_text_record_id=None,
            capture_mode=capture_mode,
        )

    def create_image_record_with_options(
        self,
        session_id: int,
        project_id: int,
        is_inspiration: bool = False,
        linked_text_record_id: int | None = None,
        capture_mode: str = CAPTURE_MODE_ACTIVE_WINDOW,
    ) -> Record:
        session = self._ensure_writable_session(session_id, project_id=project_id)
        now = datetime.now(UTC)
        offset = self._timestamp_offset_seconds(session, now)

        output_path = self._build_next_shot_path(project_id=project_id, session_id=session_id)

        try:
            capture_meta = self._capture_with_mode(output_path=output_path, capture_mode=capture_mode)
        except Exception as exc:
            raise ServiceError(f"截图失败：{exc}") from exc

        metadata_json = json.dumps(
            {
                "record_type": RECORD_TYPE_IMAGE,
                "timestamp_offset": offset,
                "is_inspiration": bool(is_inspiration),
                "linked_text_record_id": linked_text_record_id,
                "capture_mode": capture_meta["requested_mode"],
                "capture_actual_mode": capture_meta["actual_mode"],
                "capture_fallback_reason": capture_meta["fallback_reason"],
                "capture_region": capture_meta["region"],
            },
            ensure_ascii=False,
        )

        db_file_path = self._to_db_path(output_path)
        try:
            record_id = self.record_repository.create(
                session_id=session.id,
                record_type=RECORD_TYPE_IMAGE,
                file_path=db_file_path,
                timestamp_offset=offset,
                metadata_json=metadata_json,
                is_inspiration=bool(is_inspiration),
            )
        except Exception as exc:
            if output_path.exists():
                output_path.unlink()
            raise ServiceError(f"截图记录写入数据库失败：{exc}") from exc

        return self._read_created_record(record_id)

    def update_insight_text_record(self, record_id: int, text_content: str) -> Record:
        content = text_content.strip()
        if not content:
            raise ServiceError("灵感内容不能为空。")

        existing = self.record_repository.get_by_id(record_id)
        if existing is None:
            raise ServiceError("Record 不存在，无法编辑。")
        if existing.record_type != RECORD_TYPE_TEXT:
            raise ServiceError("仅 text 类型记录支持编辑灵感文本。")
        if not existing.is_inspiration:
            raise ServiceError("仅 insight 记录支持编辑。")

        metadata = self._load_metadata(existing.metadata_json)
        metadata["text_content"] = content

        updated = self.record_repository.update(
            record_id,
            content=content,
            metadata_json=json.dumps(metadata, ensure_ascii=False),
        )
        if not updated:
            raise ServiceError("更新灵感记录失败，请重试。")

        refreshed = self.record_repository.get_by_id(record_id)
        if refreshed is None:
            raise ServiceError("更新后读取记录失败。")
        return refreshed

    def link_image_to_text_record(self, image_record_id: int, text_record_id: int) -> Record:
        image_record = self.record_repository.get_by_id(image_record_id)
        if image_record is None:
            raise ServiceError("图片记录不存在，无法关联灵感。")
        if image_record.record_type != RECORD_TYPE_IMAGE:
            raise ServiceError("仅 image 记录支持关联灵感文本。")

        text_record = self.record_repository.get_by_id(text_record_id)
        if text_record is None:
            raise ServiceError("灵感文本记录不存在，无法关联图片。")
        if text_record.record_type != RECORD_TYPE_TEXT:
            raise ServiceError("仅 text 记录可作为灵感文本关联。")
        if image_record.session_id != text_record.session_id:
            raise ServiceError("图片与灵感文本不属于同一 Session，无法关联。")

        metadata = self._load_metadata(image_record.metadata_json)
        metadata["linked_text_record_id"] = text_record_id
        metadata["is_inspiration"] = True

        updated = self.record_repository.update(
            image_record_id,
            metadata_json=json.dumps(metadata, ensure_ascii=False),
            is_inspiration=True,
        )
        if not updated:
            raise ServiceError("更新图片关联信息失败，请重试。")

        refreshed = self.record_repository.get_by_id(image_record_id)
        if refreshed is None:
            raise ServiceError("更新后读取图片记录失败。")
        return refreshed

    def _capture_with_mode(self, output_path: Path, capture_mode: str) -> dict:
        requested_mode = (capture_mode or CAPTURE_MODE_FULL_SCREEN).strip().lower()

        # Backward compatibility for fake capture services in tests.
        if not hasattr(self.capture_service, "capture"):
            self.capture_service.capture_screen(output_path)
            return {
                "requested_mode": requested_mode,
                "actual_mode": CAPTURE_MODE_FULL_SCREEN,
                "fallback_reason": "legacy_capture_service",
                "region": None,
            }

        result = self.capture_service.capture(output_path=output_path, mode=requested_mode)
        return {
            "requested_mode": result.requested_mode,
            "actual_mode": result.actual_mode,
            "fallback_reason": result.fallback_reason,
            "region": list(result.region) if result.region else None,
        }

    def _build_next_shot_path(self, project_id: int, session_id: int) -> Path:
        asset_dir = build_session_asset_dir(
            project_id=project_id,
            session_id=session_id,
            projects_root=self.projects_root,
        )
        records = self.record_repository.list_by_session(session_id)
        shot_no = sum(1 for item in records if item.record_type == RECORD_TYPE_IMAGE) + 1
        output_path = asset_dir / f"session_{session_id}_shot_{shot_no:03d}.png"

        while output_path.exists():
            shot_no += 1
            output_path = asset_dir / f"session_{session_id}_shot_{shot_no:03d}.png"

        return output_path

    def delete_record(self, record_id: int) -> RecordDeleteResult:
        record = self.record_repository.get_by_id(record_id)
        if record is None:
            raise ServiceError("Record 不存在，无法删除。")

        warnings: list[str] = []
        if record.record_type == RECORD_TYPE_IMAGE and record.file_path:
            file_path = resolve_record_file_path(record.file_path, app_root=self.app_root)
            if file_path is not None:
                try:
                    if file_path.exists():
                        file_path.unlink()
                    else:
                        warnings.append(f"图片文件不存在：{file_path}")
                except Exception as exc:
                    warnings.append(f"删除图片文件失败：{file_path} ({exc})")

        deleted = self.record_repository.delete(record_id)
        if not deleted:
            raise ServiceError("删除 Record 失败，请重试。")

        return RecordDeleteResult(record_id=record_id, warnings=warnings)

    def _ensure_writable_session(self, session_id: int, project_id: int | None = None) -> Session:
        session = self.session_repository.get_by_id(session_id)
        if session is None:
            raise ServiceError("会话不存在，无法写入记录。")
        if project_id is not None and session.project_id != project_id:
            raise ServiceError("会话与当前项目不匹配，无法写入记录。")
        if session.status != SESSION_IN_PROGRESS:
            raise ServiceError("当前会话已结束，不能继续记录。")
        return session

    @staticmethod
    def _timestamp_offset_seconds(session: Session, now: datetime) -> int:
        return max(0, int((now - session.started_at).total_seconds()))

    def _to_db_path(self, output_path: Path) -> str:
        try:
            return output_path.resolve().relative_to(self.app_root.resolve()).as_posix()
        except ValueError:
            return output_path.resolve().as_posix()

    def _read_created_record(self, record_id: int) -> Record:
        record = self.record_repository.get_by_id(record_id)
        if record is None:
            raise ServiceError("记录写入后读取失败。")
        if record.record_type not in SUPPORTED_RECORD_TYPES:
            raise ServiceError(f"不支持的记录类型：{record.record_type}")
        return record

    @staticmethod
    def _load_metadata(metadata_json: str) -> dict:
        raw = (metadata_json or "").strip()
        if not raw:
            return {}
        try:
            loaded = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return loaded if isinstance(loaded, dict) else {}