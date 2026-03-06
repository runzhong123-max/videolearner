from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
import shutil

from app.config import BASE_DIR, PROJECTS_DATA_DIR
from app.models.session import Session
from app.repositories.project_repository import ProjectRepository
from app.repositories.record_repository import RecordRepository
from app.repositories.session_repository import SessionRepository
from app.services.errors import ServiceError
from app.utils.path_utils import build_session_asset_dir, resolve_record_file_path


SESSION_NOT_STARTED = "not_started"
SESSION_IN_PROGRESS = "in_progress"
SESSION_PAUSED = "paused"
SESSION_FINISHED = "finished"


@dataclass
class SessionDeleteResult:
    session_id: int
    warnings: list[str] = field(default_factory=list)


class SessionService:
    def __init__(
        self,
        session_repository: SessionRepository,
        project_repository: ProjectRepository,
        record_repository: RecordRepository | None = None,
        app_root: Path = BASE_DIR,
        projects_root: Path = PROJECTS_DATA_DIR,
    ):
        self.session_repository = session_repository
        self.project_repository = project_repository
        self.record_repository = record_repository
        self.app_root = app_root
        self.projects_root = projects_root

    def get_session(self, session_id: int) -> Session | None:
        return self.session_repository.get_by_id(session_id)

    def get_in_progress_session(self) -> Session | None:
        return self.session_repository.get_in_progress_session()

    def get_paused_session(self) -> Session | None:
        return self.session_repository.get_paused_session()

    def list_sessions_by_project(self, project_id: int) -> list[Session]:
        return self.session_repository.list_by_project(project_id)

    def start_session(self, project_id: int) -> Session:
        project = self.project_repository.get_by_id(project_id)
        if project is None:
            raise ServiceError("无法开始学习：项目不存在。")

        in_progress = self.session_repository.get_in_progress_session()
        if in_progress is not None:
            raise ServiceError(
                f"已有进行中的学习会话（项目ID={in_progress.project_id}, 会话ID={in_progress.id}），请先结束后再开始新会话。"
            )

        session_id = self.session_repository.create(
            project_id=project_id,
            title=f"{project.name} 学习会话",
            status=SESSION_IN_PROGRESS,
        )
        session = self.session_repository.get_by_id(session_id)
        if session is None:
            raise ServiceError("开始学习失败，请重试。")
        return session

    def pause_session(self, session_id: int) -> Session:
        session = self.session_repository.get_by_id(session_id)
        if session is None:
            raise ServiceError("会话不存在，无法暂停。")

        if session.status != SESSION_IN_PROGRESS:
            raise ServiceError(f"当前会话状态为 {session.status}，仅 in_progress 可暂停。")

        updated = self.session_repository.update(session_id, status=SESSION_PAUSED)
        if not updated:
            raise ServiceError("暂停学习失败，请重试。")

        paused = self.session_repository.get_by_id(session_id)
        if paused is None:
            raise ServiceError("暂停后会话读取失败。")
        return paused

    def resume_session(self, session_id: int) -> Session:
        session = self.session_repository.get_by_id(session_id)
        if session is None:
            raise ServiceError("会话不存在，无法继续。")

        if session.status != SESSION_PAUSED:
            raise ServiceError(f"当前会话状态为 {session.status}，仅 paused 可继续。")

        in_progress = self.session_repository.get_in_progress_session()
        if in_progress is not None and in_progress.id != session_id:
            raise ServiceError(
                f"已有其他进行中的会话（项目ID={in_progress.project_id}, 会话ID={in_progress.id}），无法继续当前会话。"
            )

        updated = self.session_repository.update(session_id, status=SESSION_IN_PROGRESS)
        if not updated:
            raise ServiceError("继续学习失败，请重试。")

        resumed = self.session_repository.get_by_id(session_id)
        if resumed is None:
            raise ServiceError("继续后会话读取失败。")
        return resumed

    def finish_session(self, session_id: int) -> Session:
        session = self.session_repository.get_by_id(session_id)
        if session is None:
            raise ServiceError("会话不存在，无法结束。")

        if session.status != SESSION_IN_PROGRESS:
            raise ServiceError(
                f"当前会话状态为 {session.status}，只允许从 in_progress 结束到 finished。"
            )

        ended_at = datetime.now(UTC).isoformat()
        updated = self.session_repository.update(
            session_id,
            status=SESSION_FINISHED,
            ended_at=ended_at,
        )
        if not updated:
            raise ServiceError("结束学习失败，请重试。")

        finished = self.session_repository.get_by_id(session_id)
        if finished is None:
            raise ServiceError("结束后会话读取失败。")
        return finished

    def delete_finished_session(
        self,
        session_id: int,
        project_id: int | None = None,
    ) -> SessionDeleteResult:
        session = self.session_repository.get_by_id(session_id)
        if session is None:
            raise ServiceError("会话不存在，无法删除。")

        if project_id is not None and session.project_id != project_id:
            raise ServiceError("会话不属于当前项目，无法删除。")

        if session.status == SESSION_IN_PROGRESS:
            raise ServiceError("进行中的 Session 不允许删除。")

        if session.status != SESSION_FINISHED:
            raise ServiceError(f"仅允许删除 finished Session，当前状态为 {session.status}。")

        warnings: list[str] = []

        if self.record_repository is not None:
            records = self.record_repository.list_by_session(session_id)
            for record in records:
                if record.record_type != "image" or not record.file_path:
                    continue
                file_path = resolve_record_file_path(record.file_path, app_root=self.app_root)
                if file_path is None:
                    continue
                try:
                    if file_path.exists():
                        file_path.unlink()
                    else:
                        warnings.append(f"图片文件不存在：{file_path}")
                except Exception as exc:
                    warnings.append(f"删除图片文件失败：{file_path} ({exc})")

        session_asset_dir = build_session_asset_dir(
            project_id=session.project_id,
            session_id=session.id,
            projects_root=self.projects_root,
        )
        try:
            if session_asset_dir.exists():
                shutil.rmtree(session_asset_dir)
        except Exception as exc:
            warnings.append(f"删除 Session 资源目录失败：{session_asset_dir} ({exc})")

        deleted = self.session_repository.delete(session_id)
        if not deleted:
            raise ServiceError("删除 Session 失败，请重试。")

        return SessionDeleteResult(session_id=session_id, warnings=warnings)
