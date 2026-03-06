from datetime import UTC, datetime

from app.models.session import Session
from app.repositories.project_repository import ProjectRepository
from app.repositories.session_repository import SessionRepository
from app.services.errors import ServiceError


SESSION_NOT_STARTED = "not_started"
SESSION_IN_PROGRESS = "in_progress"
SESSION_FINISHED = "finished"


class SessionService:
    def __init__(
        self,
        session_repository: SessionRepository,
        project_repository: ProjectRepository,
    ):
        self.session_repository = session_repository
        self.project_repository = project_repository

    def get_in_progress_session(self) -> Session | None:
        return self.session_repository.get_in_progress_session()

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
