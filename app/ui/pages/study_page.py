import subprocess
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QThread, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QGuiApplication, QIcon, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.models.project import Project
from app.models.record import Record
from app.models.session import Session
from app.services.errors import ServiceError
from app.services.note_service import NoteService
from app.services.ocr_service import (
    OCRService,
    OCR_STATUS_COMPLETED,
    OCR_STATUS_FAILED,
    OCR_STATUS_NOT_PROCESSED,
)
from app.services.record_chat_service import RecordChatService
from app.services.record_service import RECORD_TYPE_IMAGE, RecordService
from app.services.session_service import (
    SESSION_FINISHED,
    SESSION_IN_PROGRESS,
    SESSION_PAUSED,
    SessionService,
)
from app.ui.view_helpers import (
    build_note_preview_text,
    build_record_item_text,
    build_session_item_text,
    record_display_name,
    record_display_type,
    record_preview_text,
)
from app.ui.widgets import ImagePreviewLabel, ImageViewerDialog
from app.utils.datetime_utils import format_cn_datetime, format_cn_datetime_seconds
from app.utils.path_utils import resolve_record_file_path


class GenerateNoteWorker(QThread):
    success = Signal(object)
    failure = Signal(str)

    def __init__(self, note_service: NoteService, session_id: int):
        super().__init__()
        self.note_service = note_service
        self.session_id = session_id

    def run(self) -> None:
        try:
            result = self.note_service.generate_note_for_session(self.session_id)
            self.success.emit(result)
        except Exception as exc:
            self.failure.emit(str(exc))


class RecordChatWorker(QThread):
    success = Signal(object)
    failure = Signal(str)

    def __init__(self, record_chat_service: RecordChatService, record_id: int, user_content: str):
        super().__init__()
        self.record_chat_service = record_chat_service
        self.record_id = record_id
        self.user_content = user_content

    def run(self) -> None:
        try:
            result = self.record_chat_service.send_user_message(self.record_id, self.user_content)
            self.success.emit(result)
        except Exception as exc:
            self.failure.emit(str(exc))


class StudyPage(QWidget):
    session_selected = Signal(object)
    note_generated = Signal(object)

    def __init__(
        self,
        session_service: SessionService,
        record_service: RecordService,
        note_service: NoteService | None = None,
        record_chat_service: RecordChatService | None = None,
        ocr_service: OCRService | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.session_service = session_service
        self.record_service = record_service
        self.note_service = note_service
        self.record_chat_service = record_chat_service
        self.ocr_service = ocr_service
        self.current_project: Project | None = None
        self.current_session: Session | None = None
        self.selected_session_id: int | None = None
        self.selected_record_id: int | None = None
        self._sessions_by_id: dict[int, Session] = {}
        self._records_by_id: dict[int, Record] = {}
        self._note_worker: GenerateNoteWorker | None = None
        self._chat_worker: RecordChatWorker | None = None
        self._selected_image_path: Path | None = None

        self.project_label = QLabel("当前项目：未选择")
        self.status_label = QLabel("会话状态：not_started")
        self.started_label = QLabel("开始时间：-")
        self.ended_label = QLabel("结束时间：-")
        self.note_entry_label = QLabel("Session Note：-")
        self.message_label = QLabel("请选择项目后开始学习。")
        self.message_label.setWordWrap(True)

        self.session_list = QListWidget()
        self.session_list.currentItemChanged.connect(self._on_session_selected)
        self.timeline_list = QListWidget()
        self.timeline_list.currentItemChanged.connect(self._on_record_selected)

        self.detail_title_label = QLabel("详情预览")
        self.detail_meta_label = QLabel("-")
        self.detail_meta_label.setWordWrap(True)

        self.detail_stack = QStackedWidget()
        self.placeholder_label = QLabel("请选择 Session 与 Record 查看详情。")
        self.placeholder_label.setWordWrap(True)
        self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self.note_preview_edit = QTextEdit()
        self.note_preview_edit.setReadOnly(True)

        self.record_text_edit = QTextEdit()
        self.record_text_edit.setReadOnly(True)

        self.image_name_label = QLabel("图片名称：-")
        self.image_name_label.setWordWrap(True)
        self.image_preview_label = ImagePreviewLabel()
        self.image_preview_label.setText("图片预览区域")
        self.image_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_preview_label.setMinimumHeight(260)
        self.image_preview_label.setStyleSheet("border: 1px solid #d0d0d0; background: #fafafa;")
        self.image_preview_label.open_requested.connect(self._on_open_image_viewer)
        self.image_preview_label.context_menu_requested.connect(self._on_image_context_menu)
        self.ocr_status_label = QLabel("OCR 状态：未处理")
        self.ocr_status_label.setWordWrap(True)
        self.ocr_run_btn = QPushButton("执行 OCR")
        self.ocr_run_btn.clicked.connect(self._on_run_ocr)
        self.ocr_copy_btn = QPushButton("复制 OCR 文本")
        self.ocr_copy_btn.clicked.connect(self._on_copy_ocr_text)
        self.ocr_text_edit = QTextEdit()
        self.ocr_text_edit.setReadOnly(True)
        self.ocr_text_edit.setPlaceholderText("OCR 结果将在这里显示。")
        self.ocr_text_edit.setMinimumHeight(120)

        image_page = QWidget()
        image_layout = QVBoxLayout(image_page)
        image_layout.addWidget(self.image_name_label)
        image_layout.addWidget(self.image_preview_label, 1)
        image_layout.addWidget(self.ocr_status_label)
        ocr_btn_row = QHBoxLayout()
        ocr_btn_row.addWidget(self.ocr_run_btn)
        ocr_btn_row.addWidget(self.ocr_copy_btn)
        image_layout.addLayout(ocr_btn_row)
        image_layout.addWidget(QLabel("OCR 文本"))
        image_layout.addWidget(self.ocr_text_edit)

        self.detail_stack.addWidget(self.placeholder_label)
        self.detail_stack.addWidget(self.note_preview_edit)
        self.detail_stack.addWidget(self.record_text_edit)
        self.detail_stack.addWidget(image_page)

        self.chat_hint_label = QLabel("AI 对话：请选择 Record 后开始。")
        self.chat_hint_label.setWordWrap(True)
        self.chat_history_edit = QTextEdit()
        self.chat_history_edit.setReadOnly(True)
        self.chat_history_edit.setMinimumHeight(150)
        self.chat_input_edit = QTextEdit()
        self.chat_input_edit.setPlaceholderText("输入你对当前记录的问题…")
        self.chat_input_edit.setFixedHeight(90)
        self.chat_input_edit.textChanged.connect(self._update_chat_action_state)

        self.ask_ai_btn = QPushButton("开始对话")
        self.ask_ai_btn.clicked.connect(self._on_chat_open)
        self.chat_send_btn = QPushButton("发送")
        self.chat_send_btn.clicked.connect(self._on_chat_send)

        self.start_btn = QPushButton("开始学习")
        self.pause_btn = QPushButton("暂停学习")
        self.resume_btn = QPushButton("继续学习")
        self.finish_btn = QPushButton("结束学习")
        self.capture_btn = QPushButton("记录截图")
        self.text_btn = QPushButton("记录灵感")
        self.insight_capture_btn = QPushButton("灵感+截图")
        self.edit_insight_btn = QPushButton("编辑灵感")
        self.generate_note_btn = QPushButton("生成笔记")
        self.delete_session_btn = QPushButton("删除 Session")
        self.delete_record_btn = QPushButton("删除 Record")
        self.refresh_btn = QPushButton("刷新")

        self.start_btn.clicked.connect(self._on_start)
        self.pause_btn.clicked.connect(self._on_pause)
        self.resume_btn.clicked.connect(self._on_resume)
        self.finish_btn.clicked.connect(self._on_finish)
        self.capture_btn.clicked.connect(self._on_capture)
        self.text_btn.clicked.connect(self._on_record_text)
        self.insight_capture_btn.clicked.connect(self._on_record_text_with_capture)
        self.edit_insight_btn.clicked.connect(self._on_edit_insight)
        self.generate_note_btn.clicked.connect(self._on_generate_note)
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
        action_row.addWidget(self.insight_capture_btn)
        action_row.addWidget(self.edit_insight_btn)
        action_row.addWidget(self.generate_note_btn)
        action_row.addWidget(self.delete_session_btn)
        action_row.addWidget(self.delete_record_btn)
        action_row.addWidget(self.refresh_btn)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_session_panel())
        splitter.addWidget(self._build_timeline_panel())
        splitter.addWidget(self._build_detail_panel())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 4)
        splitter.setStretchFactor(2, 5)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(action_row)
        layout.addWidget(self.message_label)
        layout.addWidget(splitter, 1)

        self.refresh_view()

    def _build_session_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.addWidget(QLabel("Session 浏览区"))
        layout.addWidget(self.session_list, 1)
        return panel

    def _build_timeline_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.addWidget(QLabel("Record 时间线"))
        layout.addWidget(self.timeline_list, 1)
        return panel

    def _build_detail_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.addWidget(QLabel("详情预览区"))
        layout.addWidget(self.detail_title_label)
        layout.addWidget(self.detail_meta_label)
        layout.addWidget(self.detail_stack, 1)
        layout.addWidget(QLabel("Record 智能对话"))
        layout.addWidget(self.chat_hint_label)
        layout.addWidget(self.chat_history_edit)
        layout.addWidget(self.chat_input_edit)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.ask_ai_btn)
        btn_row.addWidget(self.chat_send_btn)
        layout.addLayout(btn_row)
        return panel

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
            self.note_entry_label.setText("Session Note：-")
            self._set_message("未选择项目，无法开始学习和记录。", is_error=True)
            self._set_detail_placeholder("未选择项目。")
            self._set_action_state(in_progress=None)
            self.session_selected.emit(None)
            return

        self.project_label.setText(f"当前项目：{self.current_project.name} (ID={self.current_project.id})")

        sessions = self.session_service.list_sessions_by_project(self.current_project.id)
        in_progress = self.session_service.get_in_progress_session()

        selected_row = -1
        for idx, session in enumerate(sessions):
            self._sessions_by_id[session.id] = session
            record_count = len(self.record_service.list_records_by_session(session.id))
            has_note = bool(self.note_service and self.note_service.get_latest_note_for_session(session.id))

            item = QListWidgetItem(build_session_item_text(session, record_count, has_note))
            item.setData(Qt.ItemDataRole.UserRole, session.id)
            item.setToolTip(
                f"Session #{session.id}\n状态：{session.status}\nRecord：{record_count}\nNote：{'有' if has_note else '无'}"
            )
            self._apply_session_item_style(item, session)
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
            self.note_entry_label.setText("Session Note：-")
            self.timeline_list.addItem("暂无记录")
            self._set_detail_placeholder("当前项目还没有 Session。")
            self.session_selected.emit(None)

        self._set_action_state(in_progress)

        if in_progress is not None and in_progress.project_id != self.current_project.id:
            self._set_message(
                f"已有其他项目会话进行中（项目ID={in_progress.project_id}, 会话ID={in_progress.id}）。",
                is_error=True,
            )
        elif in_progress is not None and in_progress.project_id == self.current_project.id:
            self._set_message("当前项目存在进行中的学习会话。", is_error=False)
        elif sessions:
            self._set_message("可自由浏览历史 Session 并预览记录与笔记。", is_error=False)
        else:
            self._set_message("还没有学习会话，点击“开始学习”创建。", is_error=False)

    def _apply_session_item_style(self, item: QListWidgetItem, session: Session) -> None:
        if session.status == SESSION_IN_PROGRESS:
            item.setBackground(QColor("#e8f5e9"))
        elif session.status == SESSION_PAUSED:
            item.setBackground(QColor("#fff8e1"))

    def _on_session_selected(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if current is None:
            self.selected_session_id = None
            self.current_session = None
            self._set_session_labels("not_started", None, None)
            self.note_entry_label.setText("Session Note：-")
            self.timeline_list.clear()
            self.timeline_list.addItem("暂无记录")
            self._set_detail_placeholder("未选择 Session。")
            self._set_action_state(self.session_service.get_in_progress_session())
            self.session_selected.emit(None)
            return

        session_id = current.data(Qt.ItemDataRole.UserRole)
        if session_id is None:
            return

        session = self._sessions_by_id.get(int(session_id))
        if session is None:
            return

        self.selected_session_id = int(session_id)
        self.selected_record_id = None
        in_progress = self.session_service.get_in_progress_session()
        self._apply_selected_session(session, in_progress, None)
        self._set_action_state(in_progress)

    def _on_record_selected(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if current is None:
            self.selected_record_id = None
            self.delete_record_btn.setEnabled(False)
            self._show_note_overview(self.selected_session_id)
            self._set_action_state(self.session_service.get_in_progress_session())
            return

        record_id = current.data(Qt.ItemDataRole.UserRole)
        if record_id is None:
            self.selected_record_id = None
            self.delete_record_btn.setEnabled(False)
            self._show_note_overview(self.selected_session_id)
            self._set_action_state(self.session_service.get_in_progress_session())
            return

        record = self._records_by_id.get(int(record_id))
        if record is None:
            self.selected_record_id = None
            self.delete_record_btn.setEnabled(False)
            self._show_note_overview(self.selected_session_id)
            self._set_action_state(self.session_service.get_in_progress_session())
            return

        self.selected_record_id = int(record_id)
        self.delete_record_btn.setEnabled(True)
        self._show_record_detail(record)
        self._set_action_state(self.session_service.get_in_progress_session())

    def _apply_selected_session(
        self,
        session: Session,
        in_progress: Session | None,
        preferred_record_id: int | None,
    ) -> None:
        self.current_session = session
        self._set_session_labels(session.status, session.started_at, session.ended_at)

        note_exists = bool(self.note_service and self.note_service.get_latest_note_for_session(session.id))
        self.note_entry_label.setText(f"Session Note：{'已生成' if note_exists else '未生成'}")

        self._refresh_timeline(session.id, preferred_record_id)
        self.session_selected.emit(session)

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

        text, ok = self._prompt_topmost_multiline_text("记录灵感", "请输入灵感内容：")
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

    def _on_record_text_with_capture(self) -> None:
        if self.current_project is None:
            self._set_message("请先选择当前项目。", is_error=True)
            return

        session = self._require_current_in_progress_session()
        if session is None:
            return

        try:
            image_record = self.record_service.create_image_record_with_options(
                session_id=session.id,
                project_id=self.current_project.id,
                is_inspiration=True,
                linked_text_record_id=None,
            )
        except ServiceError as exc:
            self._set_message(str(exc), is_error=True)
            return

        text, ok = self._prompt_topmost_multiline_text("灵感配图", "请输入灵感内容：")
        if not ok:
            self.selected_session_id = session.id
            self.selected_record_id = image_record.id
            self._set_message("配图已记录，未保存灵感文字。", is_error=False)
            self.refresh_view()
            return

        content = text.strip()
        if not content:
            self.selected_session_id = session.id
            self.selected_record_id = image_record.id
            self._set_message("配图已记录，灵感内容为空，未保存文字。", is_error=True)
            self.refresh_view()
            return

        try:
            text_record = self.record_service.create_text_record(session_id=session.id, text_content=content)
            self.record_service.link_image_to_text_record(image_record.id, text_record.id)
            self.selected_session_id = session.id
            self.selected_record_id = text_record.id
            self._set_message("灵感与配图记录成功。", is_error=False)
            self.refresh_view()
        except ServiceError as exc:
            self.selected_session_id = session.id
            self.selected_record_id = image_record.id
            self._set_message(f"配图已记录，但灵感文字保存失败：{exc}", is_error=True)
            self.refresh_view()

    def _on_edit_insight(self) -> None:
        record = self._get_selected_record()
        if record is None:
            self._set_message("请先选择要编辑的 insight 记录。", is_error=True)
            return
        if record.record_type != "text" or not record.is_inspiration:
            self._set_message("仅支持编辑 insight 文本记录。", is_error=True)
            return

        text, ok = self._prompt_topmost_multiline_text(
            "编辑灵感",
            "更新灵感内容：",
            record.content,
        )
        if not ok:
            return
        if not text.strip():
            self._set_message("灵感内容不能为空。", is_error=True)
            return

        try:
            updated = self.record_service.update_insight_text_record(record.id, text)
            self.selected_record_id = updated.id
            self._set_message("灵感已更新。", is_error=False)
            self.refresh_view()
        except ServiceError as exc:
            self._set_message(str(exc), is_error=True)

    def _on_generate_note(self) -> None:
        if self.note_service is None:
            self._set_message("当前未启用 AI 笔记服务。", is_error=True)
            return

        session = self._get_selected_session()
        if session is None:
            self._set_message("请先选择要生成笔记的 Session。", is_error=True)
            return

        if self._note_worker is not None and self._note_worker.isRunning():
            self._set_message("已有笔记生成任务正在执行，请稍候。", is_error=True)
            return

        self.generate_note_btn.setEnabled(False)
        self.generate_note_btn.setText("生成中...")
        self._set_message(f"正在为 Session #{session.id} 生成笔记（路由：session_note_provider）...", is_error=False)

        worker = GenerateNoteWorker(self.note_service, session.id)
        self._note_worker = worker
        worker.success.connect(self._on_note_generated)
        worker.failure.connect(self._on_note_generate_failed)
        worker.finished.connect(self._on_note_generate_finished)
        worker.start()

    def _on_note_generated(self, result) -> None:
        provider = getattr(result, "provider", None)
        model = getattr(result, "model", None)
        provider_text = ""
        if provider:
            provider_text = f"（provider={provider}" + (f"/{model}" if model else "") + ")"
        self._set_message(f"Session #{result.session_id} 笔记生成并保存成功{provider_text}。", is_error=False)
        self.note_generated.emit(result)
        self._show_note_overview(result.session_id)

    def _on_note_generate_failed(self, error_message: str) -> None:
        self._set_message(f"生成笔记失败：{self._friendly_ai_error(error_message)}", is_error=True)

    def _on_note_generate_finished(self) -> None:
        self.generate_note_btn.setText("生成笔记")
        self._set_action_state(self.session_service.get_in_progress_session())
        self._note_worker = None

    def _on_chat_open(self) -> None:
        record = self._get_selected_record()
        if record is None:
            self._set_message("请先选择 Record。", is_error=True)
            return
        if self.record_chat_service is None:
            self._set_message("当前未启用 Record 对话服务。", is_error=True)
            return

        try:
            self.record_chat_service.get_or_create_conversation(record.id)
            self._refresh_chat_panel(record)
            self._set_message("Record 对话已就绪，可继续提问。", is_error=False)
        except ServiceError as exc:
            self._set_message(str(exc), is_error=True)

    def _on_chat_send(self) -> None:
        record = self._get_selected_record()
        if record is None:
            self._set_message("请先选择 Record。", is_error=True)
            return
        if self.record_chat_service is None:
            self._set_message("当前未启用 Record 对话服务。", is_error=True)
            return

        content = self.chat_input_edit.toPlainText().strip()
        if not content:
            self._set_message("请输入问题后再发送。", is_error=True)
            return

        if self._chat_worker is not None and self._chat_worker.isRunning():
            self._set_message("当前有对话请求进行中，请稍候。", is_error=True)
            return

        self._update_chat_action_state()
        self.chat_send_btn.setEnabled(False)
        self.chat_send_btn.setText("发送中...")
        self._set_message("正在请求 AI（路由：record_chat_provider）...", is_error=False)

        worker = RecordChatWorker(self.record_chat_service, record.id, content)
        self._chat_worker = worker
        worker.success.connect(self._on_chat_send_success)
        worker.failure.connect(self._on_chat_send_failure)
        worker.finished.connect(self._on_chat_send_finished)
        worker.start()

    def _on_chat_send_success(self, result) -> None:
        self.chat_input_edit.clear()

        record = self._get_selected_record()
        if record is not None:
            self._refresh_chat_panel(record)

        if getattr(result, "is_stub", False):
            self._set_message("图片 Record 当前使用占位回复，后续阶段将支持真实图片问答。", is_error=False)
        else:
            provider = result.conversation.provider or "-"
            model = result.conversation.model_name or "-"
            self._set_message(f"Record 对话回复成功（provider={provider}, model={model}）。", is_error=False)

    def _on_chat_send_failure(self, error_message: str) -> None:
        self._set_message(f"Record 对话失败：{self._friendly_ai_error(error_message)}", is_error=True)

    def _on_chat_send_finished(self) -> None:
        self.chat_send_btn.setText("发送")
        self._chat_worker = None
        self._update_chat_action_state()

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

    def _on_open_image_viewer(self) -> None:
        image_path = self._selected_image_path
        if image_path is None or not image_path.exists():
            self._set_message("图片文件不存在，无法打开。", is_error=True)
            return

        viewer = ImageViewerDialog(image_path, self)
        viewer.exec()

    def _on_image_context_menu(self, global_pos) -> None:
        record = self._get_selected_record()
        if record is None or record.record_type != RECORD_TYPE_IMAGE:
            return

        menu = QMenu(self)
        action_open = menu.addAction("Open Image")
        action_show = menu.addAction("Show in Explorer")
        action_copy_image = menu.addAction("Copy Image")
        action_copy_path = menu.addAction("Copy Path")
        menu.addSeparator()
        action_delete = menu.addAction("Delete")

        has_image_file = self._selected_image_path is not None and self._selected_image_path.exists()
        action_open.setEnabled(has_image_file)
        action_show.setEnabled(has_image_file)
        action_copy_image.setEnabled(has_image_file)
        action_copy_path.setEnabled(has_image_file)

        picked = menu.exec(global_pos)
        if picked == action_open:
            self._on_open_image_viewer()
        elif picked == action_show:
            self._on_show_image_in_explorer()
        elif picked == action_copy_image:
            self._on_copy_image()
        elif picked == action_copy_path:
            self._on_copy_image_path()
        elif picked == action_delete:
            self._on_delete_record()

    def _on_show_image_in_explorer(self) -> None:
        image_path = self._selected_image_path
        if image_path is None or not image_path.exists():
            self._set_message("图片文件不存在，无法定位。", is_error=True)
            return

        try:
            subprocess.run(["explorer", "/select,", str(image_path)], check=False)
        except Exception:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(image_path.parent)))

    def _on_copy_image(self) -> None:
        image_path = self._selected_image_path
        if image_path is None or not image_path.exists():
            self._set_message("图片文件不存在，无法复制。", is_error=True)
            return

        pixmap = QPixmap(str(image_path))
        if pixmap.isNull():
            self._set_message("图片加载失败，无法复制。", is_error=True)
            return

        QGuiApplication.clipboard().setPixmap(pixmap)
        self._set_message("图片已复制到剪贴板。", is_error=False)

    def _on_copy_image_path(self) -> None:
        image_path = self._selected_image_path
        if image_path is None or not image_path.exists():
            self._set_message("图片文件不存在，无法复制路径。", is_error=True)
            return

        QGuiApplication.clipboard().setText(str(image_path))
        self._set_message("图片路径已复制。", is_error=False)

    def _on_copy_ocr_text(self) -> None:
        text = self.ocr_text_edit.toPlainText().strip()
        if not text:
            self._set_message("当前没有可复制的 OCR 文本。", is_error=True)
            return

        QGuiApplication.clipboard().setText(text)
        self._set_message("OCR 文本已复制。", is_error=False)

    def _on_run_ocr(self) -> None:
        record = self._get_selected_record()
        if record is None:
            self._set_message("请先选择 image Record。", is_error=True)
            return
        if record.record_type != RECORD_TYPE_IMAGE:
            self._set_message("仅 image Record 支持 OCR。", is_error=True)
            return
        if self.ocr_service is None:
            self._set_message("当前未启用 OCR 服务。", is_error=True)
            return

        try:
            result = self.ocr_service.run_ocr_for_record(record.id)
            if (result.provider or "").strip().lower() == "mock_ocr":
                self._set_message("OCR 完成（provider=mock_ocr，当前为模拟 OCR 结果）。", is_error=False)
            else:
                self._set_message(
                    f"OCR 完成（provider={result.provider}）。",
                    is_error=False,
                )
        except ServiceError as exc:
            self._set_message(str(exc), is_error=True)

        self._refresh_ocr_panel(record)

    def _refresh_ocr_panel(self, record: Record) -> None:
        if self.ocr_service is None:
            self.ocr_status_label.setText("OCR 状态：服务未启用")
            self.ocr_text_edit.setPlainText("")
            self.ocr_run_btn.setEnabled(False)
            self.ocr_run_btn.setText("执行 OCR")
            self.ocr_copy_btn.setEnabled(False)
            return

        result = self.ocr_service.get_or_default_result(record.id)
        status_text = self._format_ocr_status_label(result.ocr_status)
        provider_name = (result.provider or "").strip().lower()
        if provider_name == "mock_ocr":
            status_text += "（mock 模拟）"
        self.ocr_status_label.setText(f"OCR 状态：{status_text}")
        if result.ocr_status == OCR_STATUS_FAILED and result.ocr_error:
            self.ocr_text_edit.setPlainText(f"OCR 失败：{result.ocr_error}")
        else:
            self.ocr_text_edit.setPlainText(result.ocr_text or "")

        selected = self._get_selected_record()
        can_run = selected is not None and selected.record_type == RECORD_TYPE_IMAGE
        self.ocr_run_btn.setEnabled(can_run)
        self.ocr_run_btn.setText("重新执行 OCR" if result.ocr_status == OCR_STATUS_COMPLETED else "执行 OCR")
        self.ocr_copy_btn.setEnabled(bool((result.ocr_text or "").strip()))

    def _reset_ocr_panel(self) -> None:
        self.ocr_status_label.setText("OCR 状态：-")
        self.ocr_text_edit.setPlainText("")
        self.ocr_run_btn.setText("执行 OCR")
        self.ocr_run_btn.setEnabled(False)
        self.ocr_copy_btn.setEnabled(False)

    @staticmethod
    def _format_ocr_status_label(status: str) -> str:
        mapping = {
            OCR_STATUS_NOT_PROCESSED: "未处理",
            OCR_STATUS_COMPLETED: "已完成",
            OCR_STATUS_FAILED: "失败",
        }
        return mapping.get(status, status)
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
            no_item = QListWidgetItem("暂无记录")
            no_item.setData(Qt.ItemDataRole.UserRole, None)
            self.timeline_list.addItem(no_item)
            self.selected_record_id = None
            self.delete_record_btn.setEnabled(False)
            self._show_note_overview(session_id)
            return

        selected_row = -1
        for idx, record in enumerate(records):
            self._records_by_id[record.id] = record
            item = QListWidgetItem(build_record_item_text(record))
            item.setData(Qt.ItemDataRole.UserRole, record.id)
            item.setToolTip(self._format_record_confirm_text(record))
            if record.record_type == RECORD_TYPE_IMAGE:
                resolved = resolve_record_file_path(record.file_path)
                if resolved is not None and resolved.exists():
                    thumb = QPixmap(str(resolved))
                    if not thumb.isNull():
                        item.setIcon(QIcon(thumb.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)))
            self.timeline_list.addItem(item)
            if preferred_record_id is not None and preferred_record_id == record.id:
                selected_row = idx

        if selected_row < 0:
            selected_row = 0

        self.timeline_list.setCurrentRow(selected_row)
        selected_item = self.timeline_list.currentItem()
        if selected_item is not None and selected_item.data(Qt.ItemDataRole.UserRole) is not None:
            self.selected_record_id = int(selected_item.data(Qt.ItemDataRole.UserRole))
            record = self._records_by_id.get(self.selected_record_id)
            if record is not None:
                self._show_record_detail(record)
        else:
            self.selected_record_id = None
            self._show_note_overview(session_id)
        self.delete_record_btn.setEnabled(self.selected_record_id is not None)

    def _show_record_detail(self, record: Record) -> None:
        self.detail_title_label.setText(f"Record #{record.id} 详情")
        self.detail_meta_label.setText(
            f"Session #{record.session_id} | 类型：{record_display_type(record)} | "
            f"时间：{format_cn_datetime_seconds(record.created_at)}"
        )

        if record.record_type == RECORD_TYPE_IMAGE:
            self.image_name_label.setText(f"图片名称：{record_display_name(record)}")
            resolved = resolve_record_file_path(record.file_path)
            self._selected_image_path = resolved if resolved is not None and resolved.exists() else None
            self.image_preview_label.set_image_file_path(self._selected_image_path)

            if self._selected_image_path is None:
                self.image_preview_label.setText("图片文件不存在，无法预览。")
                self.image_preview_label.setPixmap(QPixmap())
            else:
                pixmap = QPixmap(str(self._selected_image_path))
                if pixmap.isNull():
                    self.image_preview_label.setText("图片加载失败，无法预览。")
                    self.image_preview_label.setPixmap(QPixmap())
                else:
                    self.image_preview_label.setText("")
                    scaled = pixmap.scaled(
                        760,
                        520,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    self.image_preview_label.setPixmap(scaled)
            self._refresh_ocr_panel(record)
            self.detail_stack.setCurrentIndex(3)
            self._refresh_chat_panel(record)
            return

        self._selected_image_path = None
        self.image_preview_label.set_image_file_path(None)
        self._reset_ocr_panel()
        full_text = (record.content or "").strip() or record_preview_text(record, max_len=500)
        self.record_text_edit.setPlainText(full_text)
        self.detail_stack.setCurrentIndex(2)
        self._refresh_chat_panel(record)

    def _show_note_overview(self, session_id: int | None) -> None:
        if session_id is None:
            self._set_detail_placeholder("请选择 Session。")
            return

        if self.note_service is None:
            self._set_detail_placeholder("当前未启用 Note 服务。")
            return

        note = self.note_service.get_latest_note_for_session(session_id)
        if note is None:
            self._set_detail_placeholder("该 Session 暂无 Note，选择 Record 可查看详情。")
            return

        self.detail_title_label.setText(f"Session #{session_id} Note 概览")
        self.detail_meta_label.setText(
            f"标题：{note.title or '-'} | 更新时间：{format_cn_datetime_seconds(note.updated_at)}"
        )
        self.note_preview_edit.setPlainText(build_note_preview_text(note))
        self._selected_image_path = None
        self.image_preview_label.set_image_file_path(None)
        self.image_preview_label.setPixmap(QPixmap())
        self.image_preview_label.setText("图片预览区域")
        self._reset_ocr_panel()
        self.detail_stack.setCurrentIndex(1)
        self._reset_chat_panel("请选择 Record 后发起智能对话。")

    def _set_detail_placeholder(self, text: str) -> None:
        self.detail_title_label.setText("详情预览")
        self.detail_meta_label.setText("-")
        self.placeholder_label.setText(text)
        self._selected_image_path = None
        self.image_preview_label.set_image_file_path(None)
        self.image_preview_label.setPixmap(QPixmap())
        self.image_preview_label.setText("图片预览区域")
        self._reset_ocr_panel()
        self.detail_stack.setCurrentIndex(0)
        self._reset_chat_panel("请选择 Record 后发起智能对话。")

    def _refresh_chat_panel(self, record: Record) -> None:
        if self.record_chat_service is None:
            self._reset_chat_panel("当前未启用 Record AI 对话服务。")
            return

        messages = self.record_chat_service.list_messages_by_record(record.id)
        if not messages:
            if record.record_type == RECORD_TYPE_IMAGE:
                self.chat_hint_label.setText("可围绕该图片记录提问，若先执行 OCR，回答通常更准确。")
            else:
                self.chat_hint_label.setText("可围绕该文本记录提问，开始多轮对话。")
            self.chat_history_edit.setPlainText("暂无对话历史。")
        else:
            self.chat_hint_label.setText("已加载该 Record 的历史对话，可继续追问。")
            role_map = {
                "user": "你",
                "assistant": "AI",
                "system": "System",
            }
            lines: list[str] = []
            for item in messages:
                role_text = role_map.get(item.role, item.role)
                lines.append(
                    f"[{format_cn_datetime_seconds(item.created_at)}] {role_text}:\n{item.content}"
                )
            self.chat_history_edit.setPlainText("\n\n".join(lines))

        self.ask_ai_btn.setText("继续对话" if messages else "开始对话")
        self._update_chat_action_state()

    def _reset_chat_panel(self, hint_text: str) -> None:
        self.chat_hint_label.setText(hint_text)
        self.chat_history_edit.setPlainText("")
        self.chat_input_edit.clear()
        self.ask_ai_btn.setText("开始对话")
        self._update_chat_action_state()
        self.chat_send_btn.setEnabled(False)

    def _update_chat_action_state(self) -> None:
        has_record = self._get_selected_record() is not None
        has_service = self.record_chat_service is not None
        worker_running = self._chat_worker is not None and self._chat_worker.isRunning()
        can_chat = has_record and has_service and not worker_running

        self.ask_ai_btn.setEnabled(can_chat)
        has_input = bool(self.chat_input_edit.toPlainText().strip())
        self.chat_send_btn.setEnabled(can_chat and has_input)
    def _get_selected_session(self) -> Session | None:
        if self.selected_session_id is None:
            return None
        return self._sessions_by_id.get(self.selected_session_id)

    def _get_selected_record(self) -> Record | None:
        if self.selected_record_id is None:
            return None
        return self._records_by_id.get(self.selected_record_id)

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
        self.insight_capture_btn.setEnabled(bool(selected_is_active))
        can_generate = self.note_service is not None and selected is not None
        if self._note_worker is not None and self._note_worker.isRunning():
            can_generate = False
        self.generate_note_btn.setEnabled(can_generate)

        selected_record = self._get_selected_record()
        self.delete_session_btn.setEnabled(bool(selected is not None and selected.status == SESSION_FINISHED))
        self.delete_record_btn.setEnabled(selected_record is not None)
        self.edit_insight_btn.setEnabled(
            selected_record is not None
            and selected_record.record_type == "text"
            and selected_record.is_inspiration
        )
        self.ocr_run_btn.setEnabled(
            selected_record is not None
            and selected_record.record_type == RECORD_TYPE_IMAGE
            and self.ocr_service is not None
        )
        self._update_chat_action_state()

    def trigger_shortcut_action(self, action: str) -> str:
        handlers = {
            "start_session": self._on_start,
            "pause_session": self._on_pause,
            "resume_session": self._on_resume,
            "finish_session": self._on_finish,
            "capture_image_record": self._on_capture,
            "capture_text_record": self._on_record_text,
        }
        handler = handlers.get(action)
        if handler is None:
            self._set_message(f"不支持的快捷键动作：{action}", is_error=True)
            return self.message_label.text()

        handler()
        return self.message_label.text()

    def _prompt_topmost_multiline_text(
        self,
        title: str,
        label: str,
        initial_text: str = "",
    ) -> tuple[str, bool]:
        # Keep dialog topmost but decouple from main window, so hotkey input does not
        # bring the whole workspace window to front and block video playback.
        dialog = QInputDialog(None)
        dialog.setWindowTitle(title)
        dialog.setLabelText(label)
        dialog.setInputMode(QInputDialog.InputMode.TextInput)
        dialog.setOption(QInputDialog.InputDialogOption.UsePlainTextEditForTextInput, True)
        dialog.setTextValue(initial_text or "")
        dialog.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        dialog.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        dialog.resize(560, 300)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

        editor = dialog.findChild(QTextEdit)
        if editor is not None:
            editor.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
            if initial_text:
                editor.selectAll()
        else:
            line_editor = dialog.findChild(QLineEdit)
            if line_editor is not None:
                line_editor.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
                if initial_text:
                    line_editor.selectAll()

        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        return dialog.textValue(), accepted
    @staticmethod
    def _friendly_ai_error(error_message: str) -> str:
        text = (error_message or "").strip()
        lower = text.lower()
        if "缺少 api_key" in text or "configuration" in lower or "配置错误" in text:
            return text + "（请先到 AI Settings 页面配置 Provider Key/Model）"
        return text

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
    def _format_record_confirm_text(record: Record) -> str:
        record_name = record_display_name(record)
        preview = record_preview_text(record, max_len=120)
        return (
            f"Record #{record.id}\n"
            f"类型：{record_display_type(record)}\n"
            f"名称：{record_name}\n"
            f"时间：{format_cn_datetime_seconds(record.created_at)}\n"
            f"内容：{preview}"
        )


