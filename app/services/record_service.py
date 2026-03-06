import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from app.config import BASE_DIR, PROJECTS_DATA_DIR
from app.models.record import Record
from app.models.session import Session
from app.repositories.record_repository import RecordRepository
from app.repositories.session_repository import SessionRepository
from app.services.capture_service import CaptureService
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

    def create_image_record(self, session_id: int, project_id: int) -> Record:
        session = self._ensure_writable_session(session_id, project_id=project_id)
        now = datetime.now(UTC)
        offset = self._timestamp_offset_seconds(session, now)

        output_path = self._build_next_shot_path(project_id=project_id, session_id=session_id)

        try:
            self.capture_service.capture_screen(output_path)
        except Exception as exc:
            raise ServiceError(f"截图失败：{exc}") from exc

        metadata_json = json.dumps(
            {
                "record_type": RECORD_TYPE_IMAGE,
                "timestamp_offset": offset,
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
                is_inspiration=False,
            )
        except Exception as exc:
            if output_path.exists():
                output_path.unlink()
            raise ServiceError(f"截图记录写入数据库失败：{exc}") from exc

        return self._read_created_record(record_id)

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
