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

        title = f"{context.project.name} - Session #{context.session.id} 学习笔记"
        content = self._compose_note_content(sections)
        guidance = self._compose_guidance(sections)

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
        )

        # Persist session-level summary for future context building.
        self.session_repository.update(context.session.id, summary=summary)

        created = self.note_repository.get_by_id(note_id)
        if created is None:
            raise ServiceError("笔记保存后读取失败。")

        ai_result = self.ai_service.get_last_result()
        return NoteGenerationResult(
            note=created,
            session_id=context.session.id,
            project_id=context.project.id,
            provider=ai_result.provider if ai_result else None,
            model=ai_result.model if ai_result else None,
        )

    def get_latest_note_for_session(self, session_id: int) -> Note | None:
        return self.note_repository.get_by_session(session_id)

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
            "history_link",
            "gap_analysis",
            "review_questions",
            "homework",
            "expression_notes",
            "evaluation",
        ]
        titles = {
            "summary": "Summary",
            "extension": "Extension",
            "insight": "Insight",
            "history_link": "History Link",
            "gap_analysis": "Gap Analysis",
            "review_questions": "Review Questions",
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
        keys = ["review_questions", "homework", "evaluation"]
        lines: list[str] = []
        for key in keys:
            text = sections.get(key, "").strip()
            if text:
                lines.append(text)
        return "\n".join(lines)
