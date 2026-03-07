import json
from dataclasses import dataclass

from app.models.record_chat_message import RecordChatMessage
from app.models.record_conversation import RecordConversation
from app.repositories.record_chat_message_repository import RecordChatMessageRepository
from app.repositories.record_conversation_repository import RecordConversationRepository
from app.repositories.record_repository import RecordRepository
from app.repositories.session_repository import SessionRepository
from app.services.ai_service import AIChatRequest, AIService
from app.services.errors import ServiceError
from app.services.record_chat_context_builder import RecordChatContextBuilder

RECORD_CHAT_ROLE_USER = "user"
RECORD_CHAT_ROLE_ASSISTANT = "assistant"
RECORD_CHAT_ROLE_SYSTEM = "system"

IMAGE_CHAT_STUB_REPLY = "图片智能问答将在后续阶段支持。当前仅保存文本对话占位回复。"


@dataclass
class RecordChatSendResult:
    conversation: RecordConversation
    user_message: RecordChatMessage
    assistant_message: RecordChatMessage
    is_stub: bool


class RecordChatService:
    def __init__(
        self,
        conversation_repository: RecordConversationRepository,
        message_repository: RecordChatMessageRepository,
        record_repository: RecordRepository,
        session_repository: SessionRepository,
        context_builder: RecordChatContextBuilder,
        ai_service: AIService,
    ):
        self.conversation_repository = conversation_repository
        self.message_repository = message_repository
        self.record_repository = record_repository
        self.session_repository = session_repository
        self.context_builder = context_builder
        self.ai_service = ai_service

    def get_or_create_conversation(self, record_id: int) -> RecordConversation:
        record = self.record_repository.get_by_id(record_id)
        if record is None:
            raise ServiceError("Record 不存在，无法创建对话。")

        existing = self.conversation_repository.get_by_record(record_id)
        if existing is not None:
            return existing

        session = self.session_repository.get_by_id(record.session_id)
        if session is None:
            raise ServiceError("Record 所属 Session 不存在，无法创建对话。")

        title = f"Record #{record.id} 对话"
        conversation_id = self.conversation_repository.create(
            record_id=record.id,
            session_id=session.id,
            project_id=session.project_id,
            title=title,
        )
        conversation = self.conversation_repository.get_by_id(conversation_id)
        if conversation is None:
            raise ServiceError("对话创建后读取失败。")
        return conversation

    def list_messages_by_record(self, record_id: int, limit: int = 100) -> list[RecordChatMessage]:
        conversation = self.conversation_repository.get_by_record(record_id)
        if conversation is None:
            return []
        return self.message_repository.list_by_conversation(conversation.id, limit)

    def send_user_message(self, record_id: int, user_content: str) -> RecordChatSendResult:
        content = user_content.strip()
        if not content:
            raise ServiceError("提问内容不能为空。")

        record = self.record_repository.get_by_id(record_id)
        if record is None:
            raise ServiceError("Record 不存在，无法发起对话。")

        conversation = self.get_or_create_conversation(record_id)
        user_message = self._create_message(
            conversation_id=conversation.id,
            role=RECORD_CHAT_ROLE_USER,
            content=content,
        )

        if record.record_type == "image":
            assistant_message = self._create_message(
                conversation_id=conversation.id,
                role=RECORD_CHAT_ROLE_ASSISTANT,
                content=IMAGE_CHAT_STUB_REPLY,
                metadata={"mode": "image_stub"},
                image_path=record.file_path,
            )
            self.conversation_repository.update(
                conversation.id,
                provider="stub",
                model_name="image-placeholder",
            )
            refreshed = self.conversation_repository.get_by_id(conversation.id)
            if refreshed is None:
                raise ServiceError("图片对话保存后读取失败。")
            return RecordChatSendResult(
                conversation=refreshed,
                user_message=user_message,
                assistant_message=assistant_message,
                is_stub=True,
            )

        context = self.context_builder.build_for_record(
            record_id=record_id,
            user_question=content,
            conversation_id=conversation.id,
        )

        result = self.ai_service.generate_chat_reply(
            AIChatRequest(
                system_prompt=context.system_prompt,
                user_prompt=context.user_prompt,
                context_text=context.context_text,
            ),
            feature_name="record_chat_provider",
        )

        reply_text = (result.content or "").strip()
        if not reply_text:
            raise ServiceError("AI 未返回有效回复内容。")

        assistant_message = self._create_message(
            conversation_id=conversation.id,
            role=RECORD_CHAT_ROLE_ASSISTANT,
            content=reply_text,
            metadata={
                "provider": result.provider,
                "model": result.model,
                "usage": result.usage,
                "metadata": result.metadata,
            },
        )
        self.conversation_repository.update(
            conversation.id,
            provider=result.provider,
            model_name=result.model or "",
        )

        refreshed = self.conversation_repository.get_by_id(conversation.id)
        if refreshed is None:
            raise ServiceError("对话更新后读取失败。")

        return RecordChatSendResult(
            conversation=refreshed,
            user_message=user_message,
            assistant_message=assistant_message,
            is_stub=False,
        )

    def _create_message(
        self,
        conversation_id: int,
        role: str,
        content: str,
        metadata: dict | None = None,
        image_path: str = "",
    ) -> RecordChatMessage:
        message_id = self.message_repository.create(
            conversation_id=conversation_id,
            role=role,
            content=content,
            metadata_json=json.dumps(metadata or {}, ensure_ascii=False),
            image_path=image_path,
        )
        message = self.message_repository.get_by_id(message_id)
        if message is None:
            raise ServiceError("消息保存后读取失败。")
        return message
