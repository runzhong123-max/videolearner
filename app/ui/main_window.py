from PySide6.QtWidgets import (
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QWidget,
)

from app.models.project import Project
from app.services.output_profile_service import OutputProfileService
from app.services.project_service import ProjectService
from app.services.prompt_service import PromptService
from app.services.record_service import RecordService
from app.services.session_service import SessionService
from app.ui.pages.homework_page import HomeworkPage
from app.ui.pages.note_page import NotePage
from app.ui.pages.project_page import ProjectPage
from app.ui.pages.prompt_page import PromptPage
from app.ui.pages.study_page import StudyPage


class MainWindow(QMainWindow):
    def __init__(
        self,
        project_service: ProjectService,
        session_service: SessionService,
        record_service: RecordService,
        prompt_service: PromptService,
        output_profile_service: OutputProfileService,
    ):
        super().__init__()
        self.project_service = project_service
        self.session_service = session_service
        self.record_service = record_service
        self.prompt_service = prompt_service
        self.output_profile_service = output_profile_service
        self.current_project: Project | None = None

        self.setWindowTitle("VideoLearner")
        self.resize(1200, 760)

        self.nav = QListWidget()
        self.nav.setFixedWidth(180)

        self.project_page = ProjectPage(self.project_service)
        self.study_page = StudyPage(self.session_service, self.record_service)
        self.prompt_page = PromptPage(
            prompt_service=self.prompt_service,
            output_profile_service=self.output_profile_service,
            session_service=self.session_service,
        )
        self.project_page.project_selected.connect(self._on_project_selected)

        self.stack = QStackedWidget()
        self.pages = [
            ("Study", self.study_page),
            ("Project", self.project_page),
            ("Prompt", self.prompt_page),
            ("Note", NotePage()),
            ("Homework", HomeworkPage()),
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

    def _on_nav_changed(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        current_widget = self.stack.widget(index)
        if current_widget is self.prompt_page:
            self.prompt_page.set_current_project(self.current_project)

    def _on_project_selected(self, project: Project | None) -> None:
        self.current_project = project
        self.study_page.set_current_project(project)
        self.project_page.set_current_project(project)
        self.prompt_page.set_current_project(project)

        if project is None:
            self.statusBar().showMessage("当前项目已清空。")
            return
        self.statusBar().showMessage(f"当前项目：{project.name} (ID={project.id})")
