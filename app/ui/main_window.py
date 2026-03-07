from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QWidget,
)

from app.models.project import Project
from app.models.session import Session
from app.services.ai_settings_service import AISettingsService
from app.services.note_service import NoteService
from app.services.ocr_service import OCRService
from app.services.output_profile_service import OutputProfileService
from app.services.project_service import ProjectService
from app.services.prompt_service import PromptService
from app.services.record_chat_service import RecordChatService
from app.services.record_service import RecordService
from app.services.shortcut_manager import ShortcutManager
from app.services.shortcut_settings_service import ShortcutSettingsService
from app.services.session_service import SessionService
from app.ui.pages.ai_settings_page import AISettingsPage
from app.ui.pages.note_page import NotePage
from app.ui.pages.project_page import ProjectPage
from app.ui.pages.prompt_page import PromptPage
from app.ui.pages.shortcut_settings_page import ShortcutSettingsPage
from app.ui.pages.study_page import StudyPage


class MainWindow(QMainWindow):
    def __init__(
        self,
        project_service: ProjectService,
        session_service: SessionService,
        record_service: RecordService,
        prompt_service: PromptService,
        output_profile_service: OutputProfileService,
        note_service: NoteService,
        ai_settings_service: AISettingsService | None = None,
        shortcut_settings_service: ShortcutSettingsService | None = None,
        shortcut_manager: ShortcutManager | None = None,
        record_chat_service: RecordChatService | None = None,
        ocr_service: OCRService | None = None,
    ):
        super().__init__()
        self.project_service = project_service
        self.session_service = session_service
        self.record_service = record_service
        self.prompt_service = prompt_service
        self.output_profile_service = output_profile_service
        self.note_service = note_service
        self.ai_settings_service = ai_settings_service
        self.shortcut_settings_service = shortcut_settings_service
        self.shortcut_manager = shortcut_manager
        self.record_chat_service = record_chat_service
        self.ocr_service = ocr_service
        self.current_project: Project | None = None
        self.current_session: Session | None = None

        self.setWindowTitle("VideoLearner")
        self.resize(1280, 780)

        self.nav = QListWidget()
        self.nav.setFixedWidth(180)

        self.project_page = ProjectPage(self.project_service)
        self.study_page = StudyPage(
            self.session_service,
            self.record_service,
            self.note_service,
            self.record_chat_service,
            ocr_service=self.ocr_service,
        )
        self.prompt_page = PromptPage(
            prompt_service=self.prompt_service,
            output_profile_service=self.output_profile_service,
            session_service=self.session_service,
        )
        self.note_page = NotePage(note_service=self.note_service)

        if self.ai_settings_service is not None:
            self.ai_settings_page: QWidget = AISettingsPage(ai_settings_service=self.ai_settings_service)
        else:
            self.ai_settings_page = QLabel("AI Settings Service 未启用。")

        if self.shortcut_settings_service is not None and self.shortcut_manager is not None:
            self.shortcut_settings_page: QWidget = ShortcutSettingsPage(
                shortcut_settings_service=self.shortcut_settings_service,
                shortcut_manager=self.shortcut_manager,
            )
            self.shortcut_settings_page.shortcuts_saved.connect(self._on_shortcuts_saved)
        else:
            self.shortcut_settings_page = QLabel("Shortcut Service 未启用。")

        self.project_page.project_selected.connect(self._on_project_selected)
        self.study_page.session_selected.connect(self._on_session_selected)
        self.study_page.note_generated.connect(self._on_note_generated)

        self.stack = QStackedWidget()
        self.pages = [
            ("Study", self.study_page),
            ("Project", self.project_page),
            ("Prompt", self.prompt_page),
            ("Note", self.note_page),
            ("AI Settings", self.ai_settings_page),
            ("Shortcuts", self.shortcut_settings_page),
        ]

        for title, page in self.pages:
            QListWidgetItem(title, self.nav)
            self.stack.addWidget(page)

        self.nav.currentRowChanged.connect(self._on_nav_changed)
        self.nav.setCurrentRow(0)

        shell = QWidget()
        layout = QHBoxLayout(shell)
        layout.addWidget(self.nav)
        layout.addWidget(self.stack, 1)

        self.setCentralWidget(shell)
        self.statusBar().showMessage("请选择项目并开始学习。")

        if self.shortcut_manager is not None:
            self.shortcut_manager.action_triggered.connect(self._on_shortcut_action_triggered)
            self.shortcut_manager.registration_failed.connect(self._on_shortcut_registration_failed)
            result = self.shortcut_manager.reload_from_settings()
            if result.failed_actions:
                failed = ", ".join(result.failed_actions)
                self.statusBar().showMessage(f"部分快捷键注册失败：{failed}")

    def _on_nav_changed(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        current_widget = self.stack.widget(index)
        if current_widget is self.prompt_page:
            self.prompt_page.set_current_project(self.current_project)
        elif current_widget is self.note_page:
            self.note_page.set_current_project(self.current_project)
            self.note_page.set_selected_session(self.current_session)

    def _on_project_selected(self, project: Project | None) -> None:
        self.current_project = project
        self.current_session = None

        self.study_page.set_current_project(project)
        self.project_page.set_current_project(project)
        self.prompt_page.set_current_project(project)
        self.note_page.set_current_project(project)
        self.note_page.set_selected_session(None)

        if project is None:
            self.statusBar().showMessage("当前项目已清空。")
            return
        self.statusBar().showMessage(f"当前项目：{project.name} (ID={project.id})")

    def _on_session_selected(self, session: Session | None) -> None:
        self.current_session = session
        self.note_page.set_selected_session(session)

    def _on_note_generated(self, result) -> None:
        provider_text = ""
        if getattr(result, "provider", None):
            provider_text = f" | provider={result.provider}"
            if getattr(result, "model", None):
                provider_text += f"/{result.model}"
        self.statusBar().showMessage(
            f"Session #{result.session_id} 笔记已生成并保存{provider_text}。"
        )
        self.note_page.refresh_view()

    def _on_shortcut_action_triggered(self, action: str) -> None:
        message = self.study_page.trigger_shortcut_action(action)
        if message:
            self.statusBar().showMessage(f"[快捷键] {message}")

    def _on_shortcut_registration_failed(self, message: str) -> None:
        self.statusBar().showMessage(message)

    def _on_shortcuts_saved(self, _bindings: dict) -> None:
        self.statusBar().showMessage("快捷键配置已更新。")

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.shortcut_manager is not None:
            self.shortcut_manager.stop()
        super().closeEvent(event)