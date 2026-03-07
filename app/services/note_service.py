from dataclasses import dataclass

from app.models.note import Note
from app.repositories.note_repository import NoteRepository
from app.repositories.session_repository import SessionRepository
from app.services.ai_service import AIGenerationRequest, AIService
from app.services.context_builder import ContextBuilder
from app.services.errors import ServiceError

NOTE_TYPE_SESSION_SUMMARY = "session_summary"


@dataclass
class NoteGenerationResult:
    note: Note
    session_id: int
    project_id: int
    provider: str | None = None
    model: str | None = None
    previous_versions_count: int = 0


class NoteService:
    def __init__(
        self,
        note_repository: NoteRepository,
        session_repository: SessionRepository,
        context_builder: ContextBuilder,
        ai_service: AIService,
    ):
        self.note_repository = note_repository
        self.session_repository = session_repository
        self.context_builder = context_builder
        self.ai_service = ai_service

    def generate_note_for_session(self, session_id: int) -> NoteGenerationResult:
        context = self.context_builder.build_for_session(session_id)
        previous_count = self.note_repository.count_by_session(session_id=session_id, note_type=NOTE_TYPE_SESSION_SUMMARY)

        sections = self.ai_service.generate_sections(
            AIGenerationRequest(
                system_prompt=context.effective_prompt.system_prompt,
                user_prompt=context.effective_prompt.user_prompt,
                context_text=context.context_text,
                output_options=context.output_options,
            ),
            feature_name="session_note_provider",
        )

        self._validate_output_sections(sections, context.output_options)

        summary = sections["summary"]
        extension = sections["extension"]
        insight = sections.get("insight", "")
        review_questions = sections.get("review_questions", "")
        key_points = sections.get("key_points", "")
        follow_up_tasks = sections.get("follow_up_tasks", "") or sections.get("homework", "")

        title = f"{context.project.name} - Session #{context.session.id} 学习笔记"
        content = self._compose_note_content(sections)
        guidance = self._compose_guidance(sections)

        ai_result = self.ai_service.get_last_result()
        note_id = self.note_repository.create_generated(
            project_id=context.project.id,
            session_id=context.session.id,
            note_type=NOTE_TYPE_SESSION_SUMMARY,
            title=title,
            content=content,
            summary=summary,
            suggestions=extension,
            inspiration_refinement=insight,
            guidance=guidance,
            ai_provider=ai_result.provider if ai_result else "",
            ai_model=(ai_result.model or "") if ai_result else "",
            review_questions=review_questions,
            key_points=key_points,
            follow_up_tasks=follow_up_tasks,
        )

        # Persist session-level summary for future context building.
        self.session_repository.update(context.session.id, summary=summary)

        created = self.note_repository.get_by_id(note_id)
        if created is None:
            raise ServiceError("笔记保存后读取失败。")

        return NoteGenerationResult(
            note=created,
            session_id=context.session.id,
            project_id=context.project.id,
            provider=created.ai_provider or None,
            model=created.ai_model or None,
            previous_versions_count=previous_count,
        )

    def get_latest_note_for_session(self, session_id: int) -> Note | None:
        return self.note_repository.get_by_session(session_id)

    def list_note_versions_for_session(self, session_id: int, limit: int = 30) -> list[Note]:
        return self.note_repository.list_by_session(
            session_id=session_id,
            note_type=NOTE_TYPE_SESSION_SUMMARY,
            limit=limit,
        )

    def get_note_by_id(self, note_id: int) -> Note | None:
        return self.note_repository.get_by_id(note_id)

    def update_note_review_fields(
        self,
        note_id: int,
        review_questions: str,
        key_points: str,
        follow_up_tasks: str,
        in_review_list: bool,
        is_key_note: bool,
        review_later: bool,
    ) -> Note:
        existing = self.note_repository.get_by_id(note_id)
        if existing is None:
            raise ServiceError("笔记不存在，无法保存附加整理信息。")

        updated = self.note_repository.update(
            note_id,
            review_questions=review_questions.strip(),
            key_points=key_points.strip(),
            follow_up_tasks=follow_up_tasks.strip(),
            in_review_list=in_review_list,
            is_key_note=is_key_note,
            review_later=review_later,
        )
        if not updated:
            raise ServiceError("附加整理信息保存失败。")

        refreshed = self.note_repository.get_by_id(note_id)
        if refreshed is None:
            raise ServiceError("保存后读取笔记失败。")
        return refreshed

    @staticmethod
    def _validate_output_sections(sections: dict[str, str], output_options: dict[str, bool]) -> None:
        if not sections.get("summary", "").strip():
            raise ServiceError("模型输出缺少 summary。")
        if not sections.get("extension", "").strip():
            raise ServiceError("模型输出缺少 extension。")

        if output_options.get("insight", False) and not sections.get("insight", "").strip():
            raise ServiceError("当前 Session 需要 insight，但模型未返回 insight。")

    @staticmethod
    def _compose_note_content(sections: dict[str, str]) -> str:
        order = [
            "summary",
            "extension",
            "insight",
            "review_questions",
            "key_points",
            "follow_up_tasks",
            "history_link",
            "gap_analysis",
            "homework",
            "expression_notes",
            "evaluation",
        ]
        titles = {
            "summary": "Summary",
            "extension": "Extension",
            "insight": "Insight",
            "review_questions": "Review Questions",
            "key_points": "Key Points",
            "follow_up_tasks": "Follow-up Tasks",
            "history_link": "History Link",
            "gap_analysis": "Gap Analysis",
            "homework": "Homework",
            "expression_notes": "Expression Notes",
            "evaluation": "Evaluation",
        }

        chunks: list[str] = []
        for key in order:
            value = sections.get(key, "").strip()
            if not value:
                continue
            chunks.append(f"## {titles[key]}\n\n{value}")

        return "\n\n".join(chunks)

    @staticmethod
    def _compose_guidance(sections: dict[str, str]) -> str:
        keys = ["review_questions", "follow_up_tasks", "homework", "evaluation"]
        lines: list[str] = []
        for key in keys:
            text = sections.get(key, "").strip()
            if text:
                lines.append(text)
        return "\n".join(lines)

