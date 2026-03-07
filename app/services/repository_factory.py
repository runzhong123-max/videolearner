from app.db.database import Database
from app.repositories.ai_feature_route_repository import AIFeatureRouteRepository
from app.repositories.ai_provider_config_repository import AIProviderConfigRepository
from app.repositories.app_setting_repository import AppSettingRepository
from app.repositories.note_repository import NoteRepository
from app.repositories.output_profile_repository import OutputProfileRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.prompt_template_repository import PromptTemplateRepository
from app.repositories.record_chat_message_repository import RecordChatMessageRepository
from app.repositories.record_conversation_repository import RecordConversationRepository
from app.repositories.record_repository import RecordRepository
from app.repositories.session_repository import SessionRepository


class RepositoryFactory:
    def __init__(self, db: Database):
        db_path = db.as_path()
        self.projects = ProjectRepository(db_path)
        self.sessions = SessionRepository(db_path)
        self.records = RecordRepository(db_path)
        self.record_conversations = RecordConversationRepository(db_path)
        self.record_chat_messages = RecordChatMessageRepository(db_path)
        self.notes = NoteRepository(db_path)
        self.prompts = PromptTemplateRepository(db_path)
        self.output_profiles = OutputProfileRepository(db_path)
        self.app_settings = AppSettingRepository(db_path)
        self.ai_provider_configs = AIProviderConfigRepository(db_path)
        self.ai_feature_routes = AIFeatureRouteRepository(db_path)
