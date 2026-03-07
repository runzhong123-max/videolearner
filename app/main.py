import sys

from PySide6.QtWidgets import QApplication

from app.db.database import Database
from app.services.ai_provider_resolver import AIProviderResolver
from app.services.ai_service import AIService
from app.services.ai_settings_service import AISettingsService
from app.services.capture_service import CaptureService
from app.services.context_builder import ContextBuilder
from app.services.note_service import NoteService
from app.services.ocr_service import OCRService
from app.services.output_profile_service import OutputProfileService
from app.services.project_service import ProjectService
from app.services.prompt_service import PromptService
from app.services.record_chat_context_builder import RecordChatContextBuilder
from app.services.record_chat_service import RecordChatService
from app.services.record_service import RecordService
from app.services.repository_factory import RepositoryFactory
from app.services.shortcut_manager import ShortcutManager
from app.services.shortcut_settings_service import ShortcutSettingsService
from app.services.session_service import SessionService
from app.ui.main_window import MainWindow


def main() -> int:
    db = Database()
    db.initialize()

    repositories = RepositoryFactory(db)
    project_service = ProjectService(repositories.projects)
    session_service = SessionService(
        repositories.sessions,
        repositories.projects,
        repositories.records,
    )
    capture_service = CaptureService()
    record_service = RecordService(repositories.records, repositories.sessions, capture_service)
    ocr_service = OCRService(
        record_repository=repositories.records,
        record_ocr_repository=repositories.record_ocr_results,
    )
    prompt_service = PromptService(repositories.prompts, repositories.sessions)
    output_profile_service = OutputProfileService(
        repositories.output_profiles,
        repositories.sessions,
        repositories.records,
    )

    ai_settings_service = AISettingsService(
        app_setting_repository=repositories.app_settings,
        provider_config_repository=repositories.ai_provider_configs,
        feature_route_repository=repositories.ai_feature_routes,
    )
    shortcut_settings_service = ShortcutSettingsService(repositories.app_settings)
    shortcut_manager = ShortcutManager(shortcut_settings_service)
    ai_provider_resolver = AIProviderResolver(ai_settings_service)

    context_builder = ContextBuilder(
        project_repository=repositories.projects,
        session_repository=repositories.sessions,
        record_repository=repositories.records,
        note_repository=repositories.notes,
        prompt_service=prompt_service,
        output_profile_service=output_profile_service,
    )
    ai_service = AIService(provider_resolver=ai_provider_resolver)
    note_service = NoteService(
        note_repository=repositories.notes,
        session_repository=repositories.sessions,
        context_builder=context_builder,
        ai_service=ai_service,
    )

    record_chat_context_builder = RecordChatContextBuilder(
        project_repository=repositories.projects,
        session_repository=repositories.sessions,
        record_repository=repositories.records,
        conversation_repository=repositories.record_conversations,
        message_repository=repositories.record_chat_messages,
        prompt_service=prompt_service,
        record_ocr_repository=repositories.record_ocr_results,
    )
    record_chat_service = RecordChatService(
        conversation_repository=repositories.record_conversations,
        message_repository=repositories.record_chat_messages,
        record_repository=repositories.records,
        session_repository=repositories.sessions,
        context_builder=record_chat_context_builder,
        ai_service=ai_service,
    )

    app = QApplication(sys.argv)
    window = MainWindow(
        project_service=project_service,
        session_service=session_service,
        record_service=record_service,
        prompt_service=prompt_service,
        output_profile_service=output_profile_service,
        note_service=note_service,
        ai_settings_service=ai_settings_service,
        shortcut_settings_service=shortcut_settings_service,
        shortcut_manager=shortcut_manager,
        record_chat_service=record_chat_service,
        ocr_service=ocr_service,
    )
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())