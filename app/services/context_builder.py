from dataclasses import dataclass

from app.models.project import Project
from app.models.session import Session
from app.repositories.note_repository import NoteRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.record_repository import RecordRepository
from app.repositories.session_repository import SessionRepository
from app.services.errors import ServiceError
from app.services.output_profile_service import EffectiveOutputProfile, OutputProfileService
from app.services.prompt_service import EffectivePrompt, PromptService

MAX_PROJECT_SUMMARY_CHARS = 1200
MAX_SESSION_SUMMARY_CHARS = 400
MAX_RECORD_TEXT_CHARS = 300


@dataclass
class ContextBundle:
    project: Project
    session: Session
    effective_prompt: EffectivePrompt
    effective_output: EffectiveOutputProfile
    output_options: dict[str, bool]
    has_inspiration_records: bool
    context_text: str


class ContextBuilder:
    def __init__(
        self,
        project_repository: ProjectRepository,
        session_repository: SessionRepository,
        record_repository: RecordRepository,
        note_repository: NoteRepository,
        prompt_service: PromptService,
        output_profile_service: OutputProfileService,
    ):
        self.project_repository = project_repository
        self.session_repository = session_repository
        self.record_repository = record_repository
        self.note_repository = note_repository
        self.prompt_service = prompt_service
        self.output_profile_service = output_profile_service

    def build_for_session(self, session_id: int) -> ContextBundle:
        session = self.session_repository.get_by_id(session_id)
        if session is None:
            raise ServiceError("会话不存在，无法组装 AI 上下文。")

        project = self.project_repository.get_by_id(session.project_id)
        if project is None:
            raise ServiceError("项目不存在，无法组装 AI 上下文。")

        effective_prompt = self.prompt_service.resolve_effective_prompt(
            project_id=project.id,
            session_id=session.id,
        )
        effective_output = self.output_profile_service.resolve_effective_profile(
            project_id=project.id,
            session_id=session.id,
        )

        output_options = {
            "summary": effective_output.summary,
            "extension": effective_output.extension,
            "insight": effective_output.insight,
            "history_link": effective_output.history_link,
            "gap_analysis": effective_output.gap_analysis,
            "review_questions": effective_output.review_questions,
            "homework": effective_output.homework,
            "expression_notes": effective_output.expression_notes,
            "evaluation": effective_output.evaluation,
        }

        has_inspiration = self.record_repository.has_inspiration_records(session.id)
        project_info = self._build_project_info(project)
        project_summary = self._build_project_summary(project.id)
        recent_summaries = self._build_recent_session_summaries(project.id, session.id)
        current_records = self._build_current_session_records(session.id)

        context_text = (
            "[项目基本信息]\n"
            f"{project_info}\n\n"
            "[项目总笔记摘要]\n"
            f"{project_summary}\n\n"
            "[最近 2~3 次 Session 摘要]\n"
            f"{recent_summaries}\n\n"
            "[当前 Session 全量记录]\n"
            f"{current_records}\n\n"
            "[当前 Prompt]\n"
            f"scope={effective_prompt.scope}\n"
            f"system_prompt={effective_prompt.system_prompt}\n"
            f"user_prompt={effective_prompt.user_prompt}\n\n"
            "[当前输出选项]\n"
            f"{self._format_output_options(output_options)}"
        )

        return ContextBundle(
            project=project,
            session=session,
            effective_prompt=effective_prompt,
            effective_output=effective_output,
            output_options=output_options,
            has_inspiration_records=has_inspiration,
            context_text=context_text,
        )

    @staticmethod
    def _build_project_info(project: Project) -> str:
        return (
            f"project_id={project.id}\n"
            f"name={project.name}\n"
            f"description={project.description}\n"
            f"source={project.source}\n"
            f"goal={project.goal}\n"
            f"tags={project.tags}"
        )

    def _build_project_summary(self, project_id: int) -> str:
        project_summary = self.note_repository.get_latest_project_summary(project_id)
        if project_summary is None:
            return "（无）"

        content = project_summary.content or project_summary.summary
        return self._trim(content, MAX_PROJECT_SUMMARY_CHARS)

    def _build_recent_session_summaries(self, project_id: int, current_session_id: int) -> str:
        latest_notes = self.note_repository.list_latest_session_notes(
            project_id=project_id,
            exclude_session_id=current_session_id,
            limit=3,
        )
        if not latest_notes:
            return "（无）"

        lines: list[str] = []
        for note in latest_notes:
            raw = note.summary or note.title or note.content
            lines.append(
                f"- session_id={note.session_id}: {self._trim(raw, MAX_SESSION_SUMMARY_CHARS)}"
            )
        return "\n".join(lines)

    def _build_current_session_records(self, session_id: int) -> str:
        records = self.record_repository.list_by_session(session_id)
        if not records:
            return "（无记录）"

        lines: list[str] = []
        for record in records:
            if record.record_type == "text":
                payload = self._trim(record.content, MAX_RECORD_TEXT_CHARS)
            elif record.record_type == "image":
                payload = record.file_path
            else:
                payload = self._trim(record.content or record.file_path, MAX_RECORD_TEXT_CHARS)

            lines.append(
                f"- record_id={record.id}, type={record.record_type}, offset={record.timestamp_offset}s, created_at={record.created_at.isoformat()}, payload={payload}"
            )
        return "\n".join(lines)

    @staticmethod
    def _format_output_options(output_options: dict[str, bool]) -> str:
        return "\n".join(f"- {key}: {value}" for key, value in output_options.items())

    @staticmethod
    def _trim(text: str, limit: int) -> str:
        collapsed = " ".join((text or "").splitlines()).strip()
        if len(collapsed) <= limit:
            return collapsed
        return f"{collapsed[:limit]}..."
