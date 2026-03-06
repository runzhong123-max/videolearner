from datetime import datetime

from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.models.project import Project
from app.models.session import Session
from app.services.errors import ServiceError
from app.services.session_service import SESSION_FINISHED, SESSION_IN_PROGRESS, SessionService


class StudyPage(QWidget):
    def __init__(self, session_service: SessionService, parent=None):
        super().__init__(parent)
        self.session_service = session_service
        self.current_project: Project | None = None
        self.current_session: Session | None = None

        self.project_label = QLabel("当前项目：未选择")
        self.status_label = QLabel("会话状态：not_started")
        self.started_label = QLabel("开始时间：-")
        self.ended_label = QLabel("结束时间：-")
        self.message_label = QLabel("请选择项目后开始学习。")
        self.message_label.setWordWrap(True)

        self.session_list = QListWidget()

        self.start_btn = QPushButton("开始学习")
        self.finish_btn = QPushButton("结束学习")
        self.refresh_btn = QPushButton("刷新")

        self.start_btn.clicked.connect(self._on_start)
        self.finish_btn.clicked.connect(self._on_finish)
        self.refresh_btn.clicked.connect(self.refresh_view)

        form = QFormLayout()
        form.addRow("项目", self.project_label)
        form.addRow("状态", self.status_label)
        form.addRow("开始", self.started_label)
        form.addRow("结束", self.ended_label)

        action_row = QHBoxLayout()
        action_row.addWidget(self.start_btn)
        action_row.addWidget(self.finish_btn)
        action_row.addWidget(self.refresh_btn)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(action_row)
        layout.addWidget(self.message_label)
        layout.addWidget(QLabel("Session 列表（当前项目）"))
        layout.addWidget(self.session_list)

        self.refresh_view()

    def set_current_project(self, project: Project | None) -> None:
        self.current_project = project
        self.refresh_view()

    def refresh_view(self) -> None:
        self.session_list.clear()
        self.current_session = None

        if self.current_project is None:
            self.project_label.setText("当前项目：未选择")
            self._set_session_labels("not_started", None, None)
            self._set_message("未选择项目，无法开始学习。", is_error=True)
            self.start_btn.setEnabled(False)
            self.finish_btn.setEnabled(False)
            return

        self.project_label.setText(f"当前项目：{self.current_project.name} (ID={self.current_project.id})")

        sessions = self.session_service.list_sessions_by_project(self.current_project.id)
        for session in sessions:
            self.session_list.addItem(self._format_session(session))

        in_progress = self.session_service.get_in_progress_session()
        if in_progress is not None and in_progress.project_id == self.current_project.id:
            self.current_session = in_progress
            self._set_session_labels(in_progress.status, in_progress.started_at, in_progress.ended_at)
            self._set_message("当前项目存在进行中的学习会话。", is_error=False)
            self.start_btn.setEnabled(True)
            self.finish_btn.setEnabled(True)
            return

        if sessions:
            latest = sessions[0]
            self.current_session = latest if latest.status == SESSION_IN_PROGRESS else None
            self._set_session_labels(latest.status, latest.started_at, latest.ended_at)
            self.finish_btn.setEnabled(latest.status == SESSION_IN_PROGRESS)
            if in_progress is not None and in_progress.project_id != self.current_project.id:
                self._set_message(
                    f"已有其他项目会话进行中（项目ID={in_progress.project_id}, 会话ID={in_progress.id}）。",
                    is_error=True,
                )
            else:
                self._set_message("可开始新的学习会话。", is_error=False)
        else:
            self._set_session_labels("not_started", None, None)
            self.finish_btn.setEnabled(False)
            if in_progress is not None and in_progress.project_id != self.current_project.id:
                self._set_message(
                    f"已有其他项目会话进行中（项目ID={in_progress.project_id}, 会话ID={in_progress.id}）。",
                    is_error=True,
                )
            else:
                self._set_message("还没有学习会话，点击“开始学习”创建。", is_error=False)

        self.start_btn.setEnabled(True)

    def _on_start(self) -> None:
        if self.current_project is None:
            self._set_message("请先在 Project 页面选择当前项目。", is_error=True)
            return

        try:
            session = self.session_service.start_session(self.current_project.id)
            self.current_session = session
            self._set_message("开始学习成功。", is_error=False)
            self.refresh_view()
        except ServiceError as exc:
            self._set_message(str(exc), is_error=True)

    def _on_finish(self) -> None:
        if self.current_session is None or self.current_session.status != SESSION_IN_PROGRESS:
            self._set_message("当前没有可结束的进行中会话。", is_error=True)
            return

        try:
            finished = self.session_service.finish_session(self.current_session.id)
            if finished.status != SESSION_FINISHED:
                self._set_message("结束学习失败：状态未切换到 finished。", is_error=True)
                return

            self.current_session = finished
            self._set_message("结束学习成功。", is_error=False)
            self.refresh_view()
        except ServiceError as exc:
            self._set_message(str(exc), is_error=True)

    def _set_message(self, text: str, is_error: bool) -> None:
        color = "#b00020" if is_error else "#2e7d32"
        self.message_label.setStyleSheet(f"color: {color};")
        self.message_label.setText(text)

    def _set_session_labels(
        self,
        status: str,
        started_at: datetime | None,
        ended_at: datetime | None,
    ) -> None:
        self.status_label.setText(f"会话状态：{status}")
        self.started_label.setText(f"开始时间：{self._format_dt(started_at)}")
        self.ended_label.setText(f"结束时间：{self._format_dt(ended_at)}")

    @staticmethod
    def _format_dt(value: datetime | None) -> str:
        if value is None:
            return "-"
        return value.isoformat(timespec="seconds")

    @staticmethod
    def _format_session(session: Session) -> str:
        started = session.started_at.isoformat(timespec="seconds")
        ended = session.ended_at.isoformat(timespec="seconds") if session.ended_at else "-"
        return f"#{session.id} | {session.status} | start={started} | end={ended}"
