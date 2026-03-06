from app.db.database import Database
from app.repositories.note_repository import NoteRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.prompt_template_repository import PromptTemplateRepository
from app.repositories.record_repository import RecordRepository
from app.repositories.session_repository import SessionRepository


class RepositoryFactory:
    def __init__(self, db: Database):
        db_path = db.as_path()
        self.projects = ProjectRepository(db_path)
        self.sessions = SessionRepository(db_path)
        self.records = RecordRepository(db_path)
        self.notes = NoteRepository(db_path)
        self.prompts = PromptTemplateRepository(db_path)
