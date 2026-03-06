from dataclasses import dataclass
from datetime import UTC, datetime

from app.models.prompt_template import PromptTemplate
from app.repositories.prompt_template_repository import PromptTemplateRepository
from app.repositories.session_repository import SessionRepository
from app.services.errors import ServiceError

SCOPE_GLOBAL = "global"
SCOPE_PROJECT = "project"
SCOPE_SESSION = "session"
ALLOWED_SCOPES = {SCOPE_GLOBAL, SCOPE_PROJECT, SCOPE_SESSION}

DEFAULT_SYSTEM_PROMPT = "你是学习助手，请基于上下文输出结构化结果。"
DEFAULT_USER_PROMPT = "请根据当前学习记录生成用户请求的输出内容。"


@dataclass
class EffectivePrompt:
    scope: str
    name: str
    system_prompt: str
    user_prompt: str
    source_template_id: int | None


class PromptService:
    def __init__(
        self,
        prompt_repository: PromptTemplateRepository,
        session_repository: SessionRepository,
    ):
        self.prompt_repository = prompt_repository
        self.session_repository = session_repository

    def get_template(
        self,
        scope: str,
        project_id: int | None = None,
        session_id: int | None = None,
    ) -> PromptTemplate | None:
        self._validate_scope(scope, project_id, session_id)
        return self.prompt_repository.get_by_scope_target(
            scope=scope,
            project_id=project_id,
            session_id=session_id,
        )

    def get_template_or_default(
        self,
        scope: str,
        project_id: int | None = None,
        session_id: int | None = None,
    ) -> PromptTemplate:
        found = self.get_template(scope=scope, project_id=project_id, session_id=session_id)
        if found is not None:
            return found
        return self._build_default_template(scope=scope, project_id=project_id, session_id=session_id)

    def save_template(
        self,
        scope: str,
        name: str,
        system_prompt: str,
        user_prompt: str,
        project_id: int | None = None,
        session_id: int | None = None,
    ) -> PromptTemplate:
        self._validate_scope(scope, project_id, session_id)

        cleaned_name = name.strip()
        if not cleaned_name:
            raise ServiceError("Prompt 名称不能为空。")

        return self.prompt_repository.upsert_scope_target(
            scope=scope,
            name=cleaned_name,
            system_prompt=system_prompt.strip(),
            user_prompt=user_prompt.strip(),
            project_id=project_id,
            session_id=session_id,
        )

    def restore_default(
        self,
        scope: str,
        project_id: int | None = None,
        session_id: int | None = None,
    ) -> PromptTemplate:
        self._validate_scope(scope, project_id, session_id)
        default_name = f"Default {scope.title()} Prompt"
        return self.prompt_repository.upsert_scope_target(
            scope=scope,
            name=default_name,
            system_prompt=DEFAULT_SYSTEM_PROMPT,
            user_prompt=DEFAULT_USER_PROMPT,
            project_id=project_id,
            session_id=session_id,
        )

    def resolve_effective_prompt(
        self,
        project_id: int | None = None,
        session_id: int | None = None,
    ) -> EffectivePrompt:
        resolved_project_id = project_id
        if session_id is not None and resolved_project_id is None:
            session = self.session_repository.get_by_id(session_id)
            if session is None:
                raise ServiceError("会话不存在，无法解析 Prompt。")
            resolved_project_id = session.project_id

        if session_id is not None:
            session_prompt = self.get_template(scope=SCOPE_SESSION, session_id=session_id)
            if session_prompt is not None:
                return EffectivePrompt(
                    scope=SCOPE_SESSION,
                    name=session_prompt.name,
                    system_prompt=session_prompt.system_prompt,
                    user_prompt=session_prompt.user_prompt,
                    source_template_id=session_prompt.id,
                )

        if resolved_project_id is not None:
            project_prompt = self.get_template(scope=SCOPE_PROJECT, project_id=resolved_project_id)
            if project_prompt is not None:
                return EffectivePrompt(
                    scope=SCOPE_PROJECT,
                    name=project_prompt.name,
                    system_prompt=project_prompt.system_prompt,
                    user_prompt=project_prompt.user_prompt,
                    source_template_id=project_prompt.id,
                )

        global_prompt = self.get_template(scope=SCOPE_GLOBAL)
        if global_prompt is not None:
            return EffectivePrompt(
                scope=SCOPE_GLOBAL,
                name=global_prompt.name,
                system_prompt=global_prompt.system_prompt,
                user_prompt=global_prompt.user_prompt,
                source_template_id=global_prompt.id,
            )

        return EffectivePrompt(
            scope=SCOPE_GLOBAL,
            name="Default Global Prompt",
            system_prompt=DEFAULT_SYSTEM_PROMPT,
            user_prompt=DEFAULT_USER_PROMPT,
            source_template_id=None,
        )

    @staticmethod
    def _validate_scope(scope: str, project_id: int | None, session_id: int | None) -> None:
        if scope not in ALLOWED_SCOPES:
            raise ServiceError(f"不支持的 Prompt scope：{scope}")
        if scope == SCOPE_GLOBAL and (project_id is not None or session_id is not None):
            raise ServiceError("Global Prompt 不应绑定 project_id 或 session_id。")
        if scope == SCOPE_PROJECT and project_id is None:
            raise ServiceError("Project Prompt 需要 project_id。")
        if scope == SCOPE_PROJECT and session_id is not None:
            raise ServiceError("Project Prompt 不应绑定 session_id。")
        if scope == SCOPE_SESSION and session_id is None:
            raise ServiceError("Session Prompt 需要 session_id。")

    @staticmethod
    def _build_default_template(
        scope: str,
        project_id: int | None,
        session_id: int | None,
    ) -> PromptTemplate:
        now = datetime.now(UTC)
        return PromptTemplate(
            id=None,
            scope=scope,
            project_id=project_id,
            session_id=session_id,
            name=f"Default {scope.title()} Prompt",
            system_prompt=DEFAULT_SYSTEM_PROMPT,
            user_prompt=DEFAULT_USER_PROMPT,
            created_at=now,
            updated_at=now,
        )
