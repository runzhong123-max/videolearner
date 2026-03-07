from dataclasses import dataclass

from app.models.project import Project
from app.models.record import Record
from app.models.record_chat_message import RecordChatMessage
from app.models.session import Session
from app.repositories.project_repository import ProjectRepository
from app.repositories.record_chat_message_repository import RecordChatMessageRepository
from app.repositories.record_conversation_repository import RecordConversationRepository
from app.repositories.record_ocr_repository import RecordOCRRepository
from app.repositories.record_repository import RecordRepository
from app.repositories.session_repository import SessionRepository
from app.services.errors import ServiceError
from app.services.prompt_service import PromptService

MAX_RECORD_CHARS = 400
MAX_MESSAGE_CHARS = 500
MAX_OCR_CHARS = 800


@dataclass
class RecordChatContextBundle:
    project: Project
    session: Session
    record: Record
    system_prompt: str
    user_prompt: str
    context_text: str


class RecordChatContextBuilder:
    def __init__(
        self,
        project_repository: ProjectRepository,
        session_repository: SessionRepository,
        record_repository: RecordRepository,
        conversation_repository: RecordConversationRepository,
        message_repository: RecordChatMessageRepository,
        prompt_service: PromptService,
        record_ocr_repository: RecordOCRRepository | None = None,
    ):
        self.project_repository = project_repository
        self.session_repository = session_repository
        self.record_repository = record_repository
        self.conversation_repository = conversation_repository
        self.message_repository = message_repository
        self.prompt_service = prompt_service
        self.record_ocr_repository = record_ocr_repository

    def build_for_record(
        self,
        record_id: int,
        user_question: str,
        conversation_id: int | None = None,
        history_limit: int = 6,
    ) -> RecordChatContextBundle:
        record = self.record_repository.get_by_id(record_id)
        if record is None:
            raise ServiceError("Record 不存在，无法构造对话上下文。")

        session = self.session_repository.get_by_id(record.session_id)
        if session is None:
            raise ServiceError("Record 所属 Session 不存在，无法构造对话上下文。")

        project = self.project_repository.get_by_id(session.project_id)
        if project is None:
            raise ServiceError("Record 所属 Project 不存在，无法构造对话上下文。")

        effective_prompt = self.prompt_service.resolve_effective_prompt(
            project_id=project.id,
            session_id=session.id,
        )

        resolved_conversation_id = conversation_id
        if resolved_conversation_id is None:
            conversation = self.conversation_repository.get_by_record(record.id)
            resolved_conversation_id = conversation.id if conversation is not None else None

        recent_messages = self._load_recent_messages(resolved_conversation_id, history_limit)
        neighbor_records = self._load_neighbor_records(record)
        ocr_snapshot = self._load_ocr_snapshot(record.id)

        context_text = (
            "[当前记录]\n"
            f"record_id={record.id}\n"
            f"record_type={record.record_type}\n"
            f"created_at={record.created_at.isoformat()}\n"
            f"timestamp_offset={record.timestamp_offset}s\n"
            f"is_inspiration={record.is_inspiration}\n"
            f"record_content={self._record_payload(record, ocr_snapshot)}\n\n"
            "[图像增强信息]\n"
            f"{self._format_image_context(record, ocr_snapshot)}\n\n"
            "[所属 Session]\n"
            f"session_id={session.id}\n"
            f"title={session.title}\n"
            f"status={session.status}\n"
            f"started_at={session.started_at.isoformat()}\n"
            f"ended_at={session.ended_at.isoformat() if session.ended_at else '-'}\n\n"
            "[所属 Project]\n"
            f"project_id={project.id}\n"
            f"name={project.name}\n"
            f"goal={project.goal}\n"
            f"tags={project.tags}\n\n"
            "[邻近记录]\n"
            f"{self._format_neighbor_records(neighbor_records)}\n\n"
            "[最近对话历史]\n"
            f"{self._format_recent_messages(recent_messages)}\n\n"
            "[用户当前问题]\n"
            f"{user_question.strip()}"
        )

        return RecordChatContextBundle(
            project=project,
            session=session,
            record=record,
            system_prompt=effective_prompt.system_prompt,
            user_prompt=effective_prompt.user_prompt,
            context_text=context_text,
        )

    def _load_recent_messages(
        self,
        conversation_id: int | None,
        history_limit: int,
    ) -> list[RecordChatMessage]:
        if conversation_id is None:
            return []
        return self.message_repository.list_recent_by_conversation(conversation_id, history_limit)

    def _load_neighbor_records(self, current_record: Record, radius: int = 2) -> list[Record]:
        records = self.record_repository.list_by_session(current_record.session_id)
        if not records:
            return []

        target_index = -1
        for idx, item in enumerate(records):
            if item.id == current_record.id:
                target_index = idx
                break

        if target_index < 0:
            return []

        start = max(0, target_index - radius)
        end = min(len(records), target_index + radius + 1)
        return [item for item in records[start:end] if item.id != current_record.id]

    def _load_ocr_snapshot(self, record_id: int) -> dict[str, str]:
        if self.record_ocr_repository is None:
            return {
                "status": "not_enabled",
                "text": "",
                "error": "",
                "processed_at": "",
            }

        result = self.record_ocr_repository.get_by_record(record_id)
        if result is None:
            return {
                "status": "not_processed",
                "text": "",
                "error": "",
                "processed_at": "",
            }

        return {
            "status": result.ocr_status,
            "text": self._trim(result.ocr_text, MAX_OCR_CHARS),
            "error": result.ocr_error,
            "processed_at": result.processed_at.isoformat() if result.processed_at else "",
        }

    def _record_payload(self, record: Record, ocr_snapshot: dict[str, str]) -> str:
        if record.record_type == "image":
            ocr_text = ocr_snapshot.get("text", "")
            if ocr_text:
                return (
                    f"image_path={record.file_path}; "
                    f"ocr_text={self._trim(ocr_text, MAX_RECORD_CHARS)}"
                )
            return record.file_path or "(image without path)"
        return self._trim(record.content, MAX_RECORD_CHARS)

    @staticmethod
    def _format_image_context(record: Record, ocr_snapshot: dict[str, str]) -> str:
        if record.record_type != "image":
            return "（非 image 记录）"

        return (
            f"image_path={record.file_path or '-'}\n"
            f"ocr_status={ocr_snapshot.get('status', '-') }\n"
            f"ocr_processed_at={ocr_snapshot.get('processed_at', '-') }\n"
            f"ocr_error={ocr_snapshot.get('error', '-') }\n"
            f"ocr_text={ocr_snapshot.get('text', '')}"
        )

    @staticmethod
    def _format_neighbor_records(records: list[Record]) -> str:
        if not records:
            return "（无）"

        lines: list[str] = []
        for item in records:
            payload = item.file_path if item.record_type == "image" else item.content
            payload = RecordChatContextBuilder._trim(payload, MAX_RECORD_CHARS)
            lines.append(
                f"- record_id={item.id}, type={item.record_type}, offset={item.timestamp_offset}s, content={payload}"
            )
        return "\n".join(lines)

    @staticmethod
    def _format_recent_messages(messages: list[RecordChatMessage]) -> str:
        if not messages:
            return "（无）"

        lines: list[str] = []
        for item in messages:
            role = item.role
            content = RecordChatContextBuilder._trim(item.content, MAX_MESSAGE_CHARS)
            lines.append(f"- {role}: {content}")
        return "\n".join(lines)

    @staticmethod
    def _trim(text: str, limit: int) -> str:
        compact = " ".join((text or "").splitlines()).strip()
        if len(compact) <= limit:
            return compact
        return f"{compact[:limit]}..."