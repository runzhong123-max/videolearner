from dataclasses import dataclass
from datetime import UTC, datetime

from app.models.output_profile import OutputProfile
from app.repositories.output_profile_repository import OutputProfileRepository
from app.repositories.record_repository import RecordRepository
from app.repositories.session_repository import SessionRepository
from app.services.errors import ServiceError
from app.services.prompt_service import SCOPE_GLOBAL, SCOPE_PROJECT, SCOPE_SESSION

OUTPUT_FIELDS = [
    "summary",
    "extension",
    "insight",
    "history_link",
    "gap_analysis",
    "review_questions",
    "homework",
    "expression_notes",
    "evaluation",
]


@dataclass
class EffectiveOutputProfile:
    scope: str
    name: str
    summary: bool
    extension: bool
    insight: bool
    history_link: bool
    gap_analysis: bool
    review_questions: bool
    homework: bool
    expression_notes: bool
    evaluation: bool
    source_profile_id: int | None


class OutputProfileService:
    def __init__(
        self,
        output_profile_repository: OutputProfileRepository,
        session_repository: SessionRepository,
        record_repository: RecordRepository,
    ):
        self.output_profile_repository = output_profile_repository
        self.session_repository = session_repository
        self.record_repository = record_repository

    def get_profile(
        self,
        scope: str,
        project_id: int | None = None,
        session_id: int | None = None,
    ) -> OutputProfile | None:
        self._validate_scope(scope, project_id, session_id)
        return self.output_profile_repository.get_by_scope_target(
            scope=scope,
            project_id=project_id,
            session_id=session_id,
        )

    def get_profile_or_default(
        self,
        scope: str,
        project_id: int | None = None,
        session_id: int | None = None,
    ) -> OutputProfile:
        profile = self.get_profile(scope=scope, project_id=project_id, session_id=session_id)
        if profile is not None:
            return profile
        return self._build_default_profile(scope=scope, project_id=project_id, session_id=session_id)

    def save_profile(
        self,
        name: str,
        scope: str,
        selections: dict[str, bool],
        project_id: int | None = None,
        session_id: int | None = None,
        context_session_id: int | None = None,
    ) -> OutputProfile:
        self._validate_scope(scope, project_id, session_id)

        cleaned_name = name.strip()
        if not cleaned_name:
            raise ServiceError("输出配置名称不能为空。")

        rule_session_id = session_id if session_id is not None else context_session_id
        normalized = self.apply_output_rules(selections, session_id=rule_session_id)

        return self.output_profile_repository.upsert_scope_target(
            name=cleaned_name,
            scope=scope,
            project_id=project_id,
            session_id=session_id,
            summary=normalized["summary"],
            extension=normalized["extension"],
            insight=normalized["insight"],
            history_link=normalized["history_link"],
            gap_analysis=normalized["gap_analysis"],
            review_questions=normalized["review_questions"],
            homework=normalized["homework"],
            expression_notes=normalized["expression_notes"],
            evaluation=normalized["evaluation"],
        )

    def apply_output_rules(
        self,
        selections: dict[str, bool],
        session_id: int | None = None,
    ) -> dict[str, bool]:
        normalized = self._normalize_selections(selections)
        normalized["summary"] = True
        normalized["extension"] = True
        if session_id is not None and self.record_repository.has_inspiration_records(session_id):
            normalized["insight"] = True
        return normalized

    def resolve_effective_profile(
        self,
        project_id: int | None = None,
        session_id: int | None = None,
    ) -> EffectiveOutputProfile:
        resolved_project_id = project_id
        if session_id is not None and resolved_project_id is None:
            session = self.session_repository.get_by_id(session_id)
            if session is None:
                raise ServiceError("会话不存在，无法解析输出配置。")
            resolved_project_id = session.project_id

        profile: OutputProfile | None = None
        scope = SCOPE_GLOBAL

        if session_id is not None:
            profile = self.get_profile(scope=SCOPE_SESSION, session_id=session_id)
            if profile is not None:
                scope = SCOPE_SESSION

        if profile is None and resolved_project_id is not None:
            profile = self.get_profile(scope=SCOPE_PROJECT, project_id=resolved_project_id)
            if profile is not None:
                scope = SCOPE_PROJECT

        if profile is None:
            profile = self.get_profile(scope=SCOPE_GLOBAL)
            scope = SCOPE_GLOBAL

        if profile is None:
            profile = self._build_default_profile(scope=SCOPE_GLOBAL, project_id=None, session_id=None)

        summary = True
        extension = True
        insight = profile.insight
        if session_id is not None and self.record_repository.has_inspiration_records(session_id):
            insight = True

        return EffectiveOutputProfile(
            scope=scope,
            name=profile.name,
            summary=summary,
            extension=extension,
            insight=insight,
            history_link=profile.history_link,
            gap_analysis=profile.gap_analysis,
            review_questions=profile.review_questions,
            homework=profile.homework,
            expression_notes=profile.expression_notes,
            evaluation=profile.evaluation,
            source_profile_id=profile.id,
        )

    @staticmethod
    def _normalize_selections(selections: dict[str, bool]) -> dict[str, bool]:
        normalized: dict[str, bool] = {}
        for field in OUTPUT_FIELDS:
            normalized[field] = bool(selections.get(field, False))
        return normalized

    @staticmethod
    def _validate_scope(scope: str, project_id: int | None, session_id: int | None) -> None:
        if scope not in {SCOPE_GLOBAL, SCOPE_PROJECT, SCOPE_SESSION}:
            raise ServiceError(f"不支持的输出配置 scope：{scope}")
        if scope == SCOPE_GLOBAL and (project_id is not None or session_id is not None):
            raise ServiceError("Global 输出配置不应绑定 project_id 或 session_id。")
        if scope == SCOPE_PROJECT and project_id is None:
            raise ServiceError("Project 输出配置需要 project_id。")
        if scope == SCOPE_PROJECT and session_id is not None:
            raise ServiceError("Project 输出配置不应绑定 session_id。")
        if scope == SCOPE_SESSION and session_id is None:
            raise ServiceError("Session 输出配置需要 session_id。")

    @staticmethod
    def _build_default_profile(
        scope: str,
        project_id: int | None,
        session_id: int | None,
    ) -> OutputProfile:
        now = datetime.now(UTC)
        return OutputProfile(
            id=None,
            name=f"Default {scope.title()} Output",
            scope=scope,
            project_id=project_id,
            session_id=session_id,
            summary=True,
            extension=True,
            insight=False,
            history_link=False,
            gap_analysis=False,
            review_questions=False,
            homework=False,
            expression_notes=False,
            evaluation=False,
            created_at=now,
            updated_at=now,
        )
