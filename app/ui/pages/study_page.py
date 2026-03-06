from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.models.project import Project
from app.models.record import Record
from app.models.session import Session
from app.services.errors import ServiceError
from app.services.record_service import RECORD_TYPE_IMAGE, RECORD_TYPE_TEXT, RecordService
from app.services.session_service import (
    SESSION_FINISHED,
    SESSION_IN_PROGRESS,
    SESSION_PAUSED,
    SessionService,
)
from app.utils.datetime_utils import format_cn_datetime, format_cn_time


class StudyPage(QWidget):
    def __init__(self, session_service: SessionService, record_service: RecordService, parent=None):
        super().__init__(parent)
        self.session_service = session_service
        self.record_service = record_service
        self.current_project: Project | None = None
        self.current_session: Session | None = None
        self.selected_session_id: int | None = None
        self.selected_record_id: int | None = None
        self._sessions_by_id: dict[int, Session] = {}
        self._records_by_id: dict[int, Record] = {}

        self.project_label = QLabel("当前项目：未选择")
        self.status_label = QLabel("会话状态：not_started")
        self.started_label = QLabel("开始时间：-")
        self.ended_label = QLabel("结束时间：-")
        self.note_entry_label = QLabel("Note 查看入口：待实现")
        self.message_label = QLabel("请选择项目后开始学习。")
        self.message_label.setWordWrap(True)

        self.session_list = QListWidget()
        self.session_list.currentItemChanged.connect(self._on_session_selected)
        self.timeline_list = QListWidget()
        self.timeline_list.currentItemChanged.connect(self._on_record_selected)

        self.start_btn = QPushButton("开始学习")
        self.pause_btn = QPushButton("暂停学习")
        self.resume_btn = QPushButton("继续学习")
        self.finish_btn = QPushButton("结束学习")
        self.capture_btn = QPushButton("记录截图")
        self.text_btn = QPushButton("记录灵感")
        self.delete_session_btn = QPushButton("删除 Session")
        self.delete_record_btn = QPushButton("删除 Record")
        self.refresh_btn = QPushButton("刷新")

        self.start_btn.clicked.connect(self._on_start)
        self.pause_btn.clicked.connect(self._on_pause)
        self.resume_btn.clicked.connect(self._on_resume)
        self.finish_btn.clicked.connect(self._on_finish)
        self.capture_btn.clicked.connect(self._on_capture)
        self.text_btn.clicked.connect(self._on_record_text)
        self.delete_session_btn.clicked.connect(self._on_delete_session)
        self.delete_record_btn.clicked.connect(self._on_delete_record)
        self.refresh_btn.clicked.connect(self.refresh_view)

        form = QFormLayout()
        form.addRow("项目", self.project_label)
        form.addRow("状态", self.status_label)
        form.addRow("开始", self.started_label)
        form.addRow("结束", self.ended_label)
        form.addRow("Note", self.note_entry_label)

        action_row = QHBoxLayout()
        action_row.addWidget(self.start_btn)
        action_row.addWidget(self.pause_btn)
        action_row.addWidget(self.resume_btn)
        action_row.addWidget(self.finish_btn)
        action_row.addWidget(self.capture_btn)
        action_row.addWidget(self.text_btn)
        action_row.addWidget(self.delete_session_btn)
        action_row.addWidget(self.delete_record_btn)
        action_row.addWidget(self.refresh_btn)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(action_row)
        layout.addWidget(self.message_label)
        layout.addWidget(QLabel("Session 列表（当前项目）"))
        layout.addWidget(self.session_list)
        layout.addWidget(QLabel("Record 时间线（选中 Session）"))
        layout.addWidget(self.timeline_list)

        self.refresh_view()

    def set_current_project(self, project: Project | None) -> None:
        self.current_project = project
        self.selected_session_id = None
        self.selected_record_id = None
        self.refresh_view()

    def refresh_view(self) -> None:
        preferred_session_id = self.selected_session_id
        preferred_record_id = self.selected_record_id

        self.session_list.blockSignals(True)
        self.timeline_list.blockSignals(True)
        self.session_list.clear()
        self.timeline_list.clear()
        self.session_list.blockSignals(False)
        self.timeline_list.blockSignals(False)

        self._sessions_by_id.clear()
        self._records_by_id.clear()
        self.current_session = None
        self.selected_record_id = None

        if self.current_project is None:
            self.project_label.setText("当前项目：未选择")
            self._set_session_labels("not_started", None, None)
            self.note_entry_label.setText("Note 查看入口：待实现")
            self._set_message("未选择项目，无法开始学习和记录。", is_error=True)
            self._set_action_state(in_progress=None)
            return

        self.project_label.setText(f"当前项目：{self.current_project.name} (ID={self.current_project.id})")

        sessions = self.session_service.list_sessions_by_project(self.current_project.id)
        in_progress = self.session_service.get_in_progress_session()

        selected_row = -1
        for idx, session in enumerate(sessions):
            self._sessions_by_id[session.id] = session
            item = QListWidgetItem(self._format_session(session, in_progress))
            item.setData(Qt.ItemDataRole.UserRole, session.id)
            self.session_list.addItem(item)

            if preferred_session_id is not None and preferred_session_id == session.id:
                selected_row = idx

        if selected_row < 0 and in_progress is not None and in_progress.project_id == self.current_project.id:
            for idx, session in enumerate(sessions):
                if session.id == in_progress.id:
                    selected_row = idx
                    break

        if selected_row < 0 and sessions:
            selected_row = 0

        if selected_row >= 0:
            self.session_list.setCurrentRow(selected_row)
            selected_item = self.session_list.currentItem()
            selected_id = selected_item.data(Qt.ItemDataRole.UserRole)
            self.selected_session_id = int(selected_id)
            selected_session = self._sessions_by_id[self.selected_session_id]
            self._apply_selected_session(selected_session, in_progress, preferred_record_id)
        else:
            self.selected_session_id = None
            self._set_session_labels("not_started", None, None)
            self.note_entry_label.setText("Note 查看入口：待实现")
            self.timeline_list.addItem("暂无记录")

        self._set_action_state(in_progress)

        if in_progress is not None and in_progress.project_id != self.current_project.id:
            self._set_message(
                f"已有其他项目会话进行中（项目ID={in_progress.project_id}, 会话ID={in_progress.id}）。",
                is_error=True,
            )
        elif in_progress is not None and in_progress.project_id == self.current_project.id:
            self._set_message("当前项目存在进行中的学习会话。", is_error=False)
        elif sessions:
            self._set_message("可自由查看历史 Session（含已暂停会话）。", is_error=False)
        else:
            self._set_message("还没有学习会话，点击“开始学习”创建。", is_error=False)

    def _on_session_selected(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if current is None:
            self.selected_session_id = None
            self.current_session = None
            self._set_session_labels("not_started", None, None)
            self.note_entry_label.setText("Note 查看入口：待实现")
            self.timeline_list.clear()
            self.timeline_list.addItem("暂无记录")
            self._set_action_state(self.session_service.get_in_progress_session())
            return

        session_id = int(current.data(Qt.ItemDataRole.UserRole))
        session = self._sessions_by_id.get(session_id)
        if session is None:
            return

        self.selected_session_id = session_id
        self.selected_record_id = None
        in_progress = self.session_service.get_in_progress_session()
        self._apply_selected_session(session, in_progress, None)
        self._set_action_state(in_progress)

    def _on_record_selected(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if current is None:
            self.selected_record_id = None
        else:
            data = current.data(Qt.ItemDataRole.UserRole)
            self.selected_record_id = int(data) if data is not None else None
        self.delete_record_btn.setEnabled(self.selected_record_id is not None)

    def _apply_selected_session(
        self,
        session: Session,
        in_progress: Session | None,
        preferred_record_id: int | None,
    ) -> None:
        self.current_session = session
        self._set_session_labels(session.status, session.started_at, session.ended_at)
        self.note_entry_label.setText(f"Note 查看入口：Session #{session.id}（待实现）")
        self._refresh_timeline(session.id, preferred_record_id)

        if in_progress is not None and session.id == in_progress.id:
            self._set_message("当前查看：进行中的 Session。", is_error=False)
        elif session.status == SESSION_PAUSED:
            self._set_message("当前查看：已暂停 Session。", is_error=False)
        elif session.status == SESSION_FINISHED:
            self._set_message("当前查看：历史已完成 Session。", is_error=False)
        else:
            self._set_message("当前查看：历史 Session。", is_error=False)

    def _on_start(self) -> None:
        if self.current_project is None:
            self._set_message("请先在 Project 页面选择当前项目。", is_error=True)
            return

        try:
            session = self.session_service.start_session(self.current_project.id)
            self.selected_session_id = session.id
            self._set_message("开始学习成功。", is_error=False)
            self.refresh_view()
        except ServiceError as exc:
            self._set_message(str(exc), is_error=True)

    def _on_pause(self) -> None:
        session = self._get_selected_session()
        if session is None:
            self._set_message("请先选择要暂停的 Session。", is_error=True)
            return
        if session.status != SESSION_IN_PROGRESS:
            self._set_message("仅进行中的 Session 可以暂停。", is_error=True)
            return

        try:
            paused = self.session_service.pause_session(session.id)
            self.selected_session_id = paused.id
            self._set_message("学习已暂停，可稍后继续。", is_error=False)
            self.refresh_view()
        except ServiceError as exc:
            self._set_message(str(exc), is_error=True)

    def _on_resume(self) -> None:
        session = self._get_selected_session()
        if session is None:
            self._set_message("请先选择要继续的 Session。", is_error=True)
            return
        if session.status != SESSION_PAUSED:
            self._set_message("仅已暂停的 Session 可以继续。", is_error=True)
            return

        try:
            resumed = self.session_service.resume_session(session.id)
            self.selected_session_id = resumed.id
            self._set_message("已继续学习。", is_error=False)
            self.refresh_view()
        except ServiceError as exc:
            self._set_message(str(exc), is_error=True)

    def _on_finish(self) -> None:
        session = self._require_current_in_progress_session()
        if session is None:
            return

        try:
            finished = self.session_service.finish_session(session.id)
            if finished.status != SESSION_FINISHED:
                self._set_message("结束学习失败：状态未切换到 finished。", is_error=True)
                return

            self.selected_session_id = finished.id
            self._set_message("结束学习成功。", is_error=False)
            self.refresh_view()
        except ServiceError as exc:
            self._set_message(str(exc), is_error=True)

    def _on_capture(self) -> None:
        if self.current_project is None:
            self._set_message("请先选择当前项目。", is_error=True)
            return

        session = self._require_current_in_progress_session()
        if session is None:
            return

        try:
            self.record_service.create_image_record(session_id=session.id, project_id=self.current_project.id)
            self.selected_session_id = session.id
            self._set_message("截图记录成功。", is_error=False)
            self.refresh_view()
        except ServiceError as exc:
            self._set_message(str(exc), is_error=True)

    def _on_record_text(self) -> None:
        session = self._require_current_in_progress_session()
        if session is None:
            return

        text, ok = QInputDialog.getMultiLineText(self, "记录灵感", "请输入灵感内容：")
        if not ok:
            return
        if not text.strip():
            self._set_message("灵感内容不能为空。", is_error=True)
            return

        try:
            self.record_service.create_text_record(session_id=session.id, text_content=text)
            self.selected_session_id = session.id
            self._set_message("灵感记录成功。", is_error=False)
            self.refresh_view()
        except ServiceError as exc:
            self._set_message(str(exc), is_error=True)

    def _on_delete_session(self) -> None:
        if self.current_project is None:
            self._set_message("请先选择当前项目。", is_error=True)
            return

        session = self._get_selected_session()
        if session is None:
            self._set_message("请先选择要删除的 Session。", is_error=True)
            return

        if session.status != SESSION_FINISHED:
            self._set_message("仅允许删除 finished Session。", is_error=True)
            return

        should_delete = QMessageBox.question(
            self,
            "确认删除 Session",
            f"确定删除 Session #{session.id} 吗？关联记录会被一并清理。",
        )
        if should_delete != QMessageBox.StandardButton.Yes:
            return

        try:
            result = self.session_service.delete_finished_session(
                session_id=session.id,
                project_id=self.current_project.id,
            )
            self.selected_session_id = None
            self.selected_record_id = None
            if result.warnings:
                warning_text = "；".join(result.warnings)
                self._set_message(f"Session 已删除，存在告警：{warning_text}", is_error=False)
            else:
                self._set_message("Session 删除成功。", is_error=False)
            self.refresh_view()
        except ServiceError as exc:
            self._set_message(str(exc), is_error=True)

    def _on_delete_record(self) -> None:
        session = self._get_selected_session()
        if session is None:
            self._set_message("请先选择 Session。", is_error=True)
            return

        if self.selected_record_id is None:
            self._set_message("请先选择要删除的 Record。", is_error=True)
            return

        record = self._records_by_id.get(self.selected_record_id)
        if record is None:
            self._set_message("Record 不存在或已被删除。", is_error=True)
            return

        should_delete = QMessageBox.question(
            self,
            "确认删除 Record",
            "确定删除以下 Record 吗？\n"
            f"{self._format_record_confirm_text(record)}",
        )
        if should_delete != QMessageBox.StandardButton.Yes:
            return

        try:
            result = self.record_service.delete_record(record.id)
            self.selected_record_id = None
            self.refresh_view()
            if result.warnings:
                warning_text = "；".join(result.warnings)
                self._set_message(f"Record 已删除，存在告警：{warning_text}", is_error=False)
            else:
                self._set_message("Record 删除成功。", is_error=False)
        except ServiceError as exc:
            self._set_message(str(exc), is_error=True)

    def _require_current_in_progress_session(self) -> Session | None:
        if self.current_project is None:
            self._set_message("请先选择当前项目。", is_error=True)
            return None

        in_progress = self.session_service.get_in_progress_session()
        if in_progress is None or in_progress.project_id != self.current_project.id:
            self._set_message("当前没有进行中的会话，无法记录。", is_error=True)
            return None

        self.current_session = in_progress
        return in_progress

    def _refresh_timeline(self, session_id: int, preferred_record_id: int | None) -> None:
        self.timeline_list.blockSignals(True)
        self.timeline_list.clear()
        self._records_by_id.clear()
        self.timeline_list.blockSignals(False)

        records = self.record_service.list_records_by_session(session_id)
        if not records:
            self.timeline_list.addItem("暂无记录")
            self.selected_record_id = None
            self.delete_record_btn.setEnabled(False)
            return

        selected_row = -1
        for idx, record in enumerate(records):
            self._records_by_id[record.id] = record
            item = QListWidgetItem(self._format_record_timeline(record))
            item.setData(Qt.ItemDataRole.UserRole, record.id)
            self.timeline_list.addItem(item)
            if preferred_record_id is not None and preferred_record_id == record.id:
                selected_row = idx

        if selected_row < 0:
            selected_row = 0

        self.timeline_list.setCurrentRow(selected_row)
        selected_item = self.timeline_list.currentItem()
        if selected_item is not None:
            self.selected_record_id = int(selected_item.data(Qt.ItemDataRole.UserRole))
        else:
            self.selected_record_id = None
        self.delete_record_btn.setEnabled(self.selected_record_id is not None)

    def _get_selected_session(self) -> Session | None:
        if self.selected_session_id is None:
            return None
        return self._sessions_by_id.get(self.selected_session_id)

    def _set_action_state(self, in_progress: Session | None) -> None:
        has_project = self.current_project is not None
        self.start_btn.setEnabled(has_project and in_progress is None)

        selected = self._get_selected_session()
        selected_is_active = (
            has_project
            and selected is not None
            and in_progress is not None
            and selected.id == in_progress.id
            and selected.project_id == self.current_project.id
            and selected.status == SESSION_IN_PROGRESS
        )
        selected_is_paused = (
            has_project
            and selected is not None
            and selected.status == SESSION_PAUSED
            and selected.project_id == self.current_project.id
        )
        can_resume_selected = selected_is_paused and in_progress is None

        self.pause_btn.setEnabled(bool(selected_is_active))
        self.resume_btn.setEnabled(bool(can_resume_selected))
        self.finish_btn.setEnabled(bool(selected_is_active))
        self.capture_btn.setEnabled(bool(selected_is_active))
        self.text_btn.setEnabled(bool(selected_is_active))

        self.delete_session_btn.setEnabled(bool(selected is not None and selected.status == SESSION_FINISHED))
        self.delete_record_btn.setEnabled(self.selected_record_id is not None)

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
        return format_cn_datetime(value)

    @staticmethod
    def _format_session(session: Session, in_progress: Session | None) -> str:
        if session.status == SESSION_IN_PROGRESS:
            status_label = "进行中"
        elif session.status == SESSION_PAUSED:
            status_label = "已暂停"
        elif session.status == SESSION_FINISHED:
            status_label = "已完成"
        else:
            status_label = session.status

        if in_progress is not None and in_progress.id == session.id:
            status_label = f"{status_label}（当前进行）"

        started = format_cn_datetime(session.started_at)
        ended = format_cn_datetime(session.ended_at) if session.ended_at else "-"
        return f"#{session.id} | {status_label} | 开始 {started} | 结束 {ended}"

    @staticmethod
    def _format_record_timeline(record: Record) -> str:
        created = format_cn_time(record.created_at)
        if record.record_type == RECORD_TYPE_TEXT:
            payload = record.content
        elif record.record_type == RECORD_TYPE_IMAGE:
            payload = record.file_path
        else:
            payload = "-"
        payload = StudyPage._preview_text(payload)
        return f"#{record.id} [{created}] (+{record.timestamp_offset}s) {record.record_type}: {payload}"

    @staticmethod
    def _preview_text(text: str, max_len: int = 60) -> str:
        one_line = " ".join(text.splitlines()).strip()
        if not one_line:
            return "-"
        if len(one_line) <= max_len:
            return one_line
        return f"{one_line[:max_len]}..."

    @staticmethod
    def _format_record_confirm_text(record: Record) -> str:
        created = format_cn_time(record.created_at)
        if record.record_type == RECORD_TYPE_TEXT:
            payload = record.content
        elif record.record_type == RECORD_TYPE_IMAGE:
            payload = record.file_path
        else:
            payload = "-"
        preview = StudyPage._preview_text(payload, max_len=80)
        return (
            f"Record #{record.id}\n"
            f"时间：{created}\n"
            f"类型：{record.record_type}\n"
            f"内容：{preview}"
        )
