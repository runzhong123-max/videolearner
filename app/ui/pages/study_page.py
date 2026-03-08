import subprocess
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QThread, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QGuiApplication, QIcon, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
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
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QTabWidget,
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
    build_session_display_numbers,
    build_session_item_text,
    record_display_name,
    record_display_type,
    record_preview_text,
    session_display_label,
    sort_sessions_for_display,
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


class SessionSelectorComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._ensure_valid_fonts()

    def showPopup(self) -> None:
        self._ensure_valid_fonts()
        super().showPopup()

    def _ensure_valid_fonts(self) -> None:
        combo_font = self.font()
        if combo_font.pointSize() <= 0:
            combo_font.setPointSize(11)
        self.setFont(combo_font)

        popup_view = self.view()
        popup_font = popup_view.font()
        if popup_font.pointSize() <= 0:
            popup_font.setPointSize(combo_font.pointSize())
        popup_view.setFont(popup_font)
        popup_view.viewport().setFont(popup_font)


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
        self._session_display_numbers: dict[int, int] = {}
        self._records_by_id: dict[int, Record] = {}
        self._note_worker: GenerateNoteWorker | None = None
        self._chat_worker: RecordChatWorker | None = None
        self._selected_image_path: Path | None = None

        self.page_title_label = QLabel("学习")
        self.page_title_label.setProperty("role", "pageTitle")
        self.page_subtitle_label = QLabel("在学习过程中快速记录截图、灵感与问题，不打断你的学习节奏。")
        self.page_subtitle_label.setProperty("role", "pageSubtitle")

        self.project_badge_label = QLabel("未选择项目")
        self.project_badge_label.setProperty("role", "badge")
        self.record_count_badge = QLabel("0 条记录")
        self.record_count_badge.setProperty("role", "badge")
        self.project_label = QLabel("当前项目：未选择")
        self.project_label.setProperty("role", "muted")
        self.status_label = QLabel("学习状态：尚未开始记录")
        self.status_label.setProperty("role", "muted")
        self.started_label = QLabel("开始时间：-")
        self.started_label.setProperty("role", "muted")
        self.ended_label = QLabel("结束时间：-")
        self.ended_label.setProperty("role", "muted")
        self.note_entry_label = QLabel("学习笔记：-")
        self.note_entry_label.setProperty("role", "muted")
        self.message_label = QLabel("请选择项目并开始记录。")
        self.message_label.setWordWrap(True)
        self.record_type_label = QLabel("-")
        self.record_type_label.setProperty("role", "muted")
        self.record_time_label = QLabel("-")
        self.record_time_label.setProperty("role", "muted")
        self.record_session_label = QLabel("-")
        self.record_session_label.setProperty("role", "muted")

        self.session_list = QListWidget()
        self.session_list.setObjectName("EmbeddedList")
        self.session_list.setMaximumHeight(220)
        self.session_list.currentItemChanged.connect(self._on_session_selected)
        self.timeline_list = QListWidget()
        self.timeline_list.setObjectName("TimelineList")
        self.timeline_list.currentItemChanged.connect(self._on_record_selected)

        self.session_filter_label = QLabel("当前会话")
        self.session_filter_label.setProperty("role", "sectionHint")
        self.session_combo = SessionSelectorComboBox()
        self.session_combo.setObjectName("SessionSelector")
        self.session_combo.setMinimumHeight(38)
        self.session_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.session_combo.setMaxVisibleItems(8)
        self.session_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.session_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.session_combo.setToolTip("点击切换当前项目下的学习会话")
        self.session_combo.view().setObjectName("SessionSelectorPopup")
        self.session_combo.view().setCursor(Qt.CursorShape.PointingHandCursor)
        self.session_combo.currentIndexChanged.connect(self._on_session_combo_changed)

        self.left_toggle_btn = QPushButton("«")
        self.left_toggle_btn.setProperty("variant", "panelToggle")
        self.left_toggle_btn.clicked.connect(self._toggle_left_panel)
        self.right_toggle_btn = QPushButton("»")
        self.right_toggle_btn.setProperty("variant", "panelToggle")
        self.right_toggle_btn.clicked.connect(self._toggle_right_panel)
        self.left_restore_btn = QPushButton("显示记录")
        self.left_restore_btn.setProperty("variant", "ghost")
        self.left_restore_btn.clicked.connect(self._toggle_left_panel)
        self.left_restore_btn.hide()
        self.right_restore_btn = QPushButton("显示上下文")
        self.right_restore_btn.setProperty("variant", "ghost")
        self.right_restore_btn.clicked.connect(self._toggle_right_panel)
        self.right_restore_btn.hide()
        self._left_panel_collapsed = False
        self._right_panel_collapsed = False

        self.detail_title_label = QLabel("预览")
        self.detail_title_label.setProperty("role", "sectionTitle")
        self.detail_meta_label = QLabel("-")
        self.detail_meta_label.setWordWrap(True)
        self.detail_meta_label.setProperty("role", "muted")

        self.detail_stack = QStackedWidget()
        self.placeholder_label = QLabel("当前选中的记录内容将在这里展示。")
        self.placeholder_label.setWordWrap(True)
        self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.placeholder_label.setProperty("role", "muted")

        self.note_preview_edit = QTextEdit()
        self.note_preview_edit.setReadOnly(True)
        self.note_preview_edit.setObjectName("InsetCard")

        self.record_text_edit = QTextEdit()
        self.record_text_edit.setReadOnly(True)
        self.record_text_edit.setObjectName("InsetCard")

        self.image_name_label = QLabel("图片名称：-")
        self.image_name_label.setWordWrap(True)
        self.image_name_label.setProperty("role", "muted")
        self.image_preview_label = ImagePreviewLabel()
        self.image_preview_label.setObjectName("PreviewSurface")
        self.image_preview_label.setText("图片预览区域")
        self.image_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_preview_label.setMinimumHeight(280)
        self.image_preview_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.image_preview_label.open_requested.connect(self._on_open_image_viewer)
        self.image_preview_label.context_menu_requested.connect(self._on_image_context_menu)
        self.ocr_status_label = QLabel("OCR 状态：-")
        self.ocr_status_label.setWordWrap(True)
        self.ocr_status_label.setProperty("role", "muted")
        self.ocr_run_btn = QPushButton("执行 OCR")
        self.ocr_run_btn.clicked.connect(self._on_run_ocr)
        self.ocr_copy_btn = QPushButton("复制 OCR 文本")
        self.ocr_copy_btn.clicked.connect(self._on_copy_ocr_text)
        self.ocr_text_label = QLabel("这里会显示 OCR 识别结果。")
        self.ocr_text_label.setObjectName("InsetCard")
        self.ocr_text_label.setWordWrap(True)
        self.ocr_text_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.ocr_text_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.ocr_scroll_area = QScrollArea()
        self.ocr_scroll_area.setObjectName("OcrScrollArea")
        self.ocr_scroll_area.setWidgetResizable(True)
        self.ocr_scroll_area.setWidget(self.ocr_text_label)

        image_page = QWidget()
        image_layout = QVBoxLayout(image_page)
        image_layout.setContentsMargins(0, 0, 0, 0)
        image_layout.setSpacing(12)
        image_layout.addWidget(self.image_name_label)
        image_layout.addWidget(self.image_preview_label, 1)

        self.detail_stack.addWidget(self.placeholder_label)
        self.detail_stack.addWidget(self.note_preview_edit)
        self.detail_stack.addWidget(self.record_text_edit)
        self.detail_stack.addWidget(image_page)

        self.chat_hint_label = QLabel("选择记录后，可围绕当前内容继续提问。")
        self.chat_hint_label.setWordWrap(True)
        self.chat_hint_label.setProperty("role", "muted")
        self.chat_history_edit = QTextEdit()
        self.chat_history_edit.setReadOnly(True)
        self.chat_history_edit.setObjectName("InsetCard")
        self.chat_history_edit.setMinimumHeight(180)
        self.chat_input_edit = QTextEdit()
        self.chat_input_edit.setObjectName("InsetCard")
        self.chat_input_edit.setPlaceholderText("输入你想继续追问的问题。")
        self.chat_input_edit.setFixedHeight(96)
        self.chat_input_edit.textChanged.connect(self._update_chat_action_state)

        self.ask_ai_btn = QPushButton("开始对话")
        self.ask_ai_btn.clicked.connect(self._on_chat_open)
        self.chat_send_btn = QPushButton("发送")
        self.chat_send_btn.setProperty("variant", "primary")
        self.chat_send_btn.clicked.connect(self._on_chat_send)

        self.start_btn = QPushButton("开始记录")
        self.pause_btn = QPushButton("暂停")
        self.resume_btn = QPushButton("继续")
        self.finish_btn = QPushButton("结束")
        self.session_main_btn = QPushButton("开始学习")
        self.session_main_btn.setProperty("variant", "primary")
        self.session_main_btn.setMinimumWidth(108)
        self.session_aux_btn = QPushButton("暂停")
        self.session_aux_btn.setMinimumWidth(84)
        self.capture_btn = QPushButton("截图")
        self.capture_btn.setProperty("variant", "primary")
        self.text_btn = QPushButton("灵感")
        self.open_ai_btn = QPushButton("AI 提问")
        self.insight_capture_btn = QPushButton("灵感 + 截图")
        self.edit_insight_btn = QPushButton("编辑灵感")
        self.generate_note_btn = QPushButton("生成笔记")
        self.generate_note_btn.setMinimumWidth(96)
        self.delete_session_btn = QPushButton("删除本节")
        self.delete_record_btn = QPushButton("删除当前记录")
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.setProperty("variant", "ghost")
        self.more_btn = QPushButton("更多")
        self.more_btn.setProperty("variant", "ghost")
        self.more_btn.setMinimumWidth(40)
        self.more_menu = QMenu(self)
        self.delete_record_action = self.more_menu.addAction("删除当前记录")
        self.delete_session_action = self.more_menu.addAction("删除本节")

        self.start_btn.clicked.connect(self._on_start)
        self.pause_btn.clicked.connect(self._on_pause)
        self.resume_btn.clicked.connect(self._on_resume)
        self.finish_btn.clicked.connect(self._on_finish)
        self.session_main_btn.clicked.connect(self._on_session_main_action)
        self.session_aux_btn.clicked.connect(self._on_session_aux_action)
        self.capture_btn.clicked.connect(self._on_capture)
        self.text_btn.clicked.connect(self._on_record_text)
        self.open_ai_btn.clicked.connect(self._on_primary_ask_ai)
        self.insight_capture_btn.clicked.connect(self._on_record_text_with_capture)
        self.edit_insight_btn.clicked.connect(self._on_edit_insight)
        self.generate_note_btn.clicked.connect(self._on_generate_note)
        self.delete_session_btn.clicked.connect(self._on_delete_session)
        self.delete_record_btn.clicked.connect(self._on_delete_record)
        self.refresh_btn.clicked.connect(self.refresh_view)
        self.more_btn.clicked.connect(self._show_more_menu)
        self.delete_record_action.triggered.connect(self._on_delete_record)
        self.delete_session_action.triggered.connect(self._on_delete_session)


        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        quick_action_row = QHBoxLayout()
        quick_action_row.setSpacing(8)
        quick_action_row.addWidget(self.capture_btn)
        quick_action_row.addWidget(self.text_btn)
        quick_action_row.addWidget(self.open_ai_btn)

        session_action_row = QHBoxLayout()
        session_action_row.setSpacing(8)
        session_action_row.addWidget(self.session_main_btn)
        session_action_row.addWidget(self.session_aux_btn)
        session_action_row.addWidget(self.generate_note_btn)

        meta_row = QHBoxLayout()
        meta_row.setSpacing(8)
        meta_row.addWidget(self.project_badge_label)
        meta_row.addWidget(self.record_count_badge)
        meta_row.addWidget(self.more_btn)

        action_row.addLayout(quick_action_row)
        action_row.addSpacing(16)
        action_row.addLayout(session_action_row)
        action_row.addStretch(1)
        action_row.addLayout(meta_row)

        header_col = QVBoxLayout()
        header_col.setSpacing(4)
        header_col.addWidget(self.page_title_label)
        header_col.addWidget(self.page_subtitle_label)

        header_row = QHBoxLayout()
        header_row.setSpacing(16)
        header_row.addLayout(header_col)
        header_row.addStretch(1)
        header_row.addLayout(action_row)

        self.context_tabs = QTabWidget()
        self.context_tabs.setDocumentMode(True)
        self.info_tab = self._build_info_tab()
        self.ocr_tab = self._build_ocr_tab()
        self.ai_tab = self._build_ai_tab()
        self.context_tabs.addTab(self.info_tab, "信息")
        self.context_tabs.addTab(self.ocr_tab, "OCR")
        self.context_tabs.addTab(self.ai_tab, "AI")
        self.left_panel = self._build_timeline_panel()
        self.preview_panel = self._build_preview_panel()
        self.right_panel = self._build_context_panel()

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.addWidget(self.left_panel)
        self.splitter.addWidget(self.preview_panel)
        self.splitter.addWidget(self.right_panel)
        self.splitter.setStretchFactor(0, 2)
        self.splitter.setStretchFactor(1, 8)
        self.splitter.setStretchFactor(2, 2)
        self.splitter.setSizes([260, 900, 300])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        layout.addLayout(header_row)
        layout.addWidget(self.splitter, 1)

        self.refresh_view()

    def _build_timeline_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("PanelCard")
        panel.setMinimumWidth(260)
        panel.setMaximumWidth(320)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        title_col = QVBoxLayout()
        title_col.setSpacing(4)
        timeline_label = QLabel("学习记录")
        timeline_label.setProperty("role", "sectionTitle")
        timeline_hint = QLabel("记录时间线")
        timeline_hint.setProperty("role", "sectionHint")
        title_col.addWidget(timeline_label)
        title_col.addWidget(timeline_hint)

        header_row = QHBoxLayout()
        header_row.setSpacing(8)
        header_row.addLayout(title_col, 1)
        header_row.addWidget(self.left_toggle_btn, 0, Qt.AlignmentFlag.AlignTop)

        layout.addLayout(header_row)
        layout.addWidget(self.session_filter_label)
        layout.addWidget(self.session_combo)
        layout.addWidget(self.timeline_list, 1)
        return panel

    def _build_preview_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("PreviewPanel")
        panel.setMinimumWidth(520)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        title_col = QVBoxLayout()
        title_col.setSpacing(4)
        title_col.addWidget(self.detail_title_label)
        title_col.addWidget(self.detail_meta_label)
        preview_hint = QLabel("当前选中的记录内容将在这里展示。")
        preview_hint.setProperty("role", "sectionHint")
        title_col.addWidget(preview_hint)

        restore_row = QHBoxLayout()
        restore_row.setSpacing(8)
        restore_row.addWidget(self.left_restore_btn)
        restore_row.addWidget(self.right_restore_btn)

        header_row = QHBoxLayout()
        header_row.setSpacing(12)
        header_row.addLayout(title_col, 1)
        header_row.addLayout(restore_row)

        layout.addLayout(header_row)
        layout.addWidget(self.detail_stack, 1)
        return panel

    def _build_context_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("PanelCard")
        panel.setMinimumWidth(300)
        panel.setMaximumWidth(320)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        title_col = QVBoxLayout()
        title_col.setSpacing(4)
        context_title = QLabel("上下文")
        context_title.setProperty("role", "sectionTitle")
        context_hint = QLabel("围绕当前记录查看信息、OCR结果和AI分析。")
        context_hint.setProperty("role", "sectionHint")
        title_col.addWidget(context_title)
        title_col.addWidget(context_hint)

        header_row = QHBoxLayout()
        header_row.setSpacing(8)
        header_row.addLayout(title_col, 1)
        header_row.addWidget(self.right_toggle_btn, 0, Qt.AlignmentFlag.AlignTop)

        layout.addLayout(header_row)
        layout.addWidget(self.context_tabs, 1)
        return panel





    def _build_info_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(16)

        record_title = QLabel("当前记录")
        record_title.setProperty("role", "sectionHint")
        layout.addWidget(record_title)

        record_form = QFormLayout()
        record_form.addRow("记录类型", self.record_type_label)
        record_form.addRow("时间", self.record_time_label)
        record_form.addRow("所属会话", self.record_session_label)
        layout.addLayout(record_form)

        session_title = QLabel("当前会话")
        session_title.setProperty("role", "sectionHint")
        layout.addWidget(session_title)

        form = QFormLayout()
        form.addRow("项目", self.project_label)
        form.addRow("状态", self.status_label)
        form.addRow("开始", self.started_label)
        form.addRow("结束", self.ended_label)
        form.addRow("笔记", self.note_entry_label)
        layout.addLayout(form)
        layout.addWidget(self.message_label)
        layout.addStretch(1)
        return panel

    def _build_ocr_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(16)
        layout.addWidget(self.ocr_status_label)

        button_row = QHBoxLayout()
        button_row.addWidget(self.ocr_run_btn)
        button_row.addWidget(self.ocr_copy_btn)
        layout.addLayout(button_row)
        layout.addWidget(self.ocr_scroll_area, 1)
        return panel

    def _build_ai_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(16)
        layout.addWidget(self.chat_hint_label)
        layout.addWidget(self.chat_history_edit, 1)
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
        self.session_combo.blockSignals(True)
        self.session_list.clear()
        self.timeline_list.clear()
        self.session_combo.clear()

        self._sessions_by_id.clear()
        self._session_display_numbers.clear()
        self._records_by_id.clear()
        self.current_session = None
        self.selected_record_id = None

        if self.current_project is None:
            self.project_label.setText("当前项目：未选择")
            self.project_badge_label.setText("未选择项目")
            self._set_session_labels("not_started", None, None)
            self.note_entry_label.setText("学习笔记：-")
            self.session_filter_label.setText("当前会话")
            self.session_combo.setEnabled(False)
            self.session_combo.setCursor(Qt.CursorShape.ArrowCursor)
            self.session_combo.setToolTip("请先选择项目")
            self.session_combo.setCurrentIndex(-1)
            self._set_message("未选择项目，无法开始记录。", is_error=True)
            self._set_detail_placeholder("未选择项目。")
            self._set_action_state(in_progress=None)
            self.session_list.blockSignals(False)
            self.timeline_list.blockSignals(False)
            self.session_combo.blockSignals(False)
            self.session_selected.emit(None)
            return

        self.project_label.setText(f"当前项目：{self.current_project.name} (ID={self.current_project.id})")
        self.project_badge_label.setText(self.current_project.name)

        sessions = sort_sessions_for_display(
            self.session_service.list_sessions_by_project(self.current_project.id)
        )
        in_progress = self.session_service.get_in_progress_session()
        session_count = len(sessions)
        self.session_filter_label.setText("当前会话 · 仅 1 个会话" if session_count == 1 else "当前会话")
        self.session_combo.setEnabled(session_count > 1)
        self.session_combo.setCursor(Qt.CursorShape.PointingHandCursor if session_count > 1 else Qt.CursorShape.ArrowCursor)
        if session_count <= 0:
            self.session_combo.setToolTip("当前项目暂无会话")
        elif session_count == 1:
            self.session_combo.setToolTip("当前项目仅有 1 个会话")
        else:
            self.session_combo.setToolTip("点击切换当前项目下的学习会话")

        self._session_display_numbers = build_session_display_numbers(sessions)

        selected_row = -1
        for idx, session in enumerate(sessions):
            self._sessions_by_id[session.id] = session
            record_count = len(self.record_service.list_records_by_session(session.id))
            has_note = bool(self.note_service and self.note_service.get_latest_note_for_session(session.id))

            item = QListWidgetItem(build_session_item_text(session, record_count, has_note))
            item.setData(Qt.ItemDataRole.UserRole, session.id)
            item.setToolTip(
                f"学习会话 #{session.id}\n状态：{session.status}\n记录数量：{record_count}\n学习笔记：{'有' if has_note else '无'}"
            )
            self._apply_session_item_style(item, session)
            self.session_list.addItem(item)
            self.session_combo.addItem(self._format_session_option_text(session), session.id)

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
            self.session_combo.setCurrentIndex(selected_row)
            self.session_list.setCurrentRow(selected_row)
            selected_item = self.session_list.currentItem()
            selected_id = selected_item.data(Qt.ItemDataRole.UserRole)
            self.selected_session_id = int(selected_id)
            selected_session = self._sessions_by_id[self.selected_session_id]
            self._apply_selected_session(selected_session, in_progress, preferred_record_id)
        else:
            self.selected_session_id = None
            self.session_combo.setCurrentIndex(-1)
            self._set_session_labels("not_started", None, None)
            self.note_entry_label.setText("学习笔记：-")
            self.timeline_list.addItem("暂无记录")
            self._set_detail_placeholder("当前项目还没有学习记录。")
            self.session_selected.emit(None)

        self.session_list.blockSignals(False)
        self.timeline_list.blockSignals(False)
        self.session_combo.blockSignals(False)
        self._set_action_state(in_progress)

        if in_progress is not None and in_progress.project_id != self.current_project.id:
            self._set_message(
                f"已有其他项目会话进行中（项目ID={in_progress.project_id}, 会话ID={in_progress.id}）。",
                is_error=True,
            )
        elif in_progress is not None and in_progress.project_id == self.current_project.id:
            self._set_message("当前项目正在记录中。", is_error=False)
        elif sessions:
            self._set_message("可浏览当前项目的学习记录，并查看预览与上下文。", is_error=False)
        else:
            self._set_message("还没有学习记录，点击“开始记录”即可开始。", is_error=False)

    def _on_session_combo_changed(self, index: int) -> None:
        if index < 0 or index >= self.session_list.count():
            return
        self.session_list.setCurrentRow(index)

    def _format_session_option_text(self, session: Session) -> str:
        status_map = {
            SESSION_IN_PROGRESS: "进行中",
            SESSION_PAUSED: "已暂停",
            SESSION_FINISHED: "已完成",
        }
        status_text = status_map.get(session.status, session.status)
        display_prefix = self._format_session_display_label(session)
        display_time = session.started_at or session.created_at
        if display_time is None:
            started_text = "-"
        else:
            started_text = f"{display_time.month}月{display_time.day}日 {display_time:%H:%M}"
        return f"{display_prefix} · {status_text} · {started_text}"

    def _format_session_display_label(self, session: Session | None) -> str:
        if session is None:
            return "当前会话"
        display_number = self._session_display_numbers.get(session.id)
        if display_number is None:
            return "当前会话"
        return f"第{display_number}节"

    def _apply_session_item_style(self, item: QListWidgetItem, session: Session) -> None:
        if session.status == SESSION_IN_PROGRESS:
            item.setBackground(QColor("#16243a"))
            item.setForeground(QColor("#eaf1fb"))
        elif session.status == SESSION_PAUSED:
            item.setBackground(QColor("#1b202a"))
            item.setForeground(QColor("#d9e0eb"))

    def _on_session_selected(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if current is None:
            self.selected_session_id = None
            self.current_session = None
            self.session_combo.blockSignals(True)
            self.session_combo.setCurrentIndex(-1)
            self.session_combo.blockSignals(False)
            self._set_session_labels("not_started", None, None)
            self.note_entry_label.setText("学习笔记：-")
            self.timeline_list.clear()
            self.timeline_list.addItem("暂无记录")
            self._set_detail_placeholder("当前还没有可预览的记录内容。")
            self._set_action_state(self.session_service.get_in_progress_session())
            self.session_selected.emit(None)
            return

        session_id = current.data(Qt.ItemDataRole.UserRole)
        if session_id is None:
            return

        session = self._sessions_by_id.get(int(session_id))
        if session is None:
            return

        combo_index = self.session_list.row(current)
        self.session_combo.blockSignals(True)
        self.session_combo.setCurrentIndex(combo_index)
        self.session_combo.blockSignals(False)

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
        self.note_entry_label.setText(f"学习笔记：{'已生成' if note_exists else '未生成'}")

        self._refresh_timeline(session.id, preferred_record_id)
        self.session_selected.emit(session)

        if in_progress is not None and session.id == in_progress.id:
            self._set_message("当前查看：正在记录中的内容。", is_error=False)
        elif session.status == SESSION_PAUSED:
            self._set_message("当前查看：已暂停的记录。", is_error=False)
        elif session.status == SESSION_FINISHED:
            self._set_message("当前查看：已结束的记录。", is_error=False)
        else:
            self._set_message("当前查看：历史记录。", is_error=False)

    def _on_start(self) -> None:
        if self.current_project is None:
            self._set_message("请先在项目页选择当前项目。", is_error=True)
            return

        try:
            session = self.session_service.start_session(self.current_project.id)
            self.selected_session_id = session.id
            self._set_message("开始记录成功。", is_error=False)
            self.refresh_view()
        except ServiceError as exc:
            self._set_message(str(exc), is_error=True)

    def _on_pause(self) -> None:
        session = self._get_selected_session()
        if session is None:
            self._set_message("当前没有可暂停的记录。", is_error=True)
            return
        if session.status != SESSION_IN_PROGRESS:
            self._set_message("只有记录中的内容可以暂停。", is_error=True)
            return

        try:
            paused = self.session_service.pause_session(session.id)
            self.selected_session_id = paused.id
            self._set_message("已暂停记录，可稍后继续。", is_error=False)
            self.refresh_view()
        except ServiceError as exc:
            self._set_message(str(exc), is_error=True)

    def _on_resume(self) -> None:
        session = self._get_selected_session()
        if session is None:
            self._set_message("当前没有可继续的记录。", is_error=True)
            return
        if session.status != SESSION_PAUSED:
            self._set_message("只有已暂停的记录可以继续。", is_error=True)
            return

        try:
            resumed = self.session_service.resume_session(session.id)
            self.selected_session_id = resumed.id
            self._set_message("已继续记录。", is_error=False)
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
                self._set_message("结束记录失败：状态未正确更新。", is_error=True)
                return

            self.selected_session_id = finished.id
            self._set_message("结束记录成功。", is_error=False)
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
            self._set_message("请先选择要生成笔记的记录会话。", is_error=True)
            return

        if self._note_worker is not None and self._note_worker.isRunning():
            self._set_message("已有笔记生成任务正在执行，请稍候。", is_error=True)
            return

        self.generate_note_btn.setEnabled(False)
        self.generate_note_btn.setText("生成中...")
        self._set_message(f"正在为记录会话 #{session.id} 生成笔记...", is_error=False)

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
        self._set_message(f"记录会话 #{result.session_id} 的笔记已生成并保存{provider_text}。", is_error=False)
        self.note_generated.emit(result)
        self._show_note_overview(result.session_id)

    def _on_note_generate_failed(self, error_message: str) -> None:
        self._set_message(f"生成笔记失败：{self._friendly_ai_error(error_message)}", is_error=True)

    def _on_note_generate_finished(self) -> None:
        self.generate_note_btn.setText("生成笔记")
        self._set_action_state(self.session_service.get_in_progress_session())
        self._note_worker = None

    def _on_primary_ask_ai(self) -> None:
        self.context_tabs.setCurrentIndex(2)
        self._on_chat_open()

    def _on_chat_open(self) -> None:
        record = self._get_selected_record()
        if record is None:
            self._set_message("请先选择一条记录。", is_error=True)
            return
        if self.record_chat_service is None:
            self._set_message("当前未启用记录对话服务。", is_error=True)
            return

        try:
            self.record_chat_service.get_or_create_conversation(record.id)
            self._refresh_chat_panel(record)
            self._set_message("AI 对话已就绪，可继续提问。", is_error=False)
        except ServiceError as exc:
            self._set_message(str(exc), is_error=True)

    def _on_chat_send(self) -> None:
        record = self._get_selected_record()
        if record is None:
            self._set_message("请先选择一条记录。", is_error=True)
            return
        if self.record_chat_service is None:
            self._set_message("当前未启用记录对话服务。", is_error=True)
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
        self._set_message("正在请求 AI 分析...", is_error=False)

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
            self._set_message("当前图片分析仍为占位回复，后续阶段再接入真实问答。", is_error=False)
        else:
            provider = result.conversation.provider or "-"
            model = result.conversation.model_name or "-"
            self._set_message(f"AI 回复成功（provider={provider}, model={model}）。", is_error=False)

    def _on_chat_send_failure(self, error_message: str) -> None:
        self._set_message(f"AI 对话失败：{self._friendly_ai_error(error_message)}", is_error=True)

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
            self._set_message("请先选择要删除的本节内容。", is_error=True)
            return

        if session.status != SESSION_FINISHED:
            self._set_message("仅允许删除已结束的本节内容。", is_error=True)
            return

        should_delete = QMessageBox.question(
            self,
            "确认删除本节",
            f"确认删除{self._format_session_display_label(session)}吗？\n本节中的所有记录将一并删除，且无法恢复。",
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
                self._set_message(f"本节已删除，存在提示：{warning_text}", is_error=False)
            else:
                self._set_message("本节删除成功。", is_error=False)
            self.refresh_view()
        except ServiceError as exc:
            self._set_message(str(exc), is_error=True)

    def _on_delete_record(self) -> None:
        session = self._get_selected_session()
        if session is None:
            self._set_message("请先选择记录会话。", is_error=True)
            return

        if self.selected_record_id is None:
            self._set_message("请先选择要删除的记录。", is_error=True)
            return

        record = self._records_by_id.get(self.selected_record_id)
        if record is None:
            self._set_message("记录不存在或已被删除。", is_error=True)
            return

        should_delete = QMessageBox.question(
            self,
            "确认删除记录",
            "确认删除当前记录吗？\n删除后将无法恢复。",
        )
        if should_delete != QMessageBox.StandardButton.Yes:
            return

        try:
            result = self.record_service.delete_record(record.id)
            self.selected_record_id = None
            self.refresh_view()
            if result.warnings:
                warning_text = "；".join(result.warnings)
                self._set_message(f"记录已删除，存在提示：{warning_text}", is_error=False)
            else:
                self._set_message("记录删除成功。", is_error=False)
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
        text = self.ocr_text_label.text().strip()
        if not text:
            self._set_message("当前没有可复制的 OCR 文本。", is_error=True)
            return

        QGuiApplication.clipboard().setText(text)
        self._set_message("OCR 文本已复制。", is_error=False)

    def _on_run_ocr(self) -> None:
        record = self._get_selected_record()
        if record is None:
            self._set_message("请先选择图片记录。", is_error=True)
            return
        if record.record_type != RECORD_TYPE_IMAGE:
            self._set_message("只有图片记录支持 OCR。", is_error=True)
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
            self.ocr_text_label.setText("")
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
            self.ocr_text_label.setText(f"OCR 失败：{result.ocr_error}")
        else:
            self.ocr_text_label.setText(result.ocr_text or "")

        selected = self._get_selected_record()
        can_run = selected is not None and selected.record_type == RECORD_TYPE_IMAGE
        self.ocr_run_btn.setEnabled(can_run)
        self.ocr_run_btn.setText("重新执行 OCR" if result.ocr_status == OCR_STATUS_COMPLETED else "执行 OCR")
        self.ocr_copy_btn.setEnabled(bool((result.ocr_text or "").strip()))
    def _reset_ocr_panel(self) -> None:
        self.ocr_status_label.setText("OCR 状态：-")
        self.ocr_text_label.setText("")
        self.ocr_run_btn.setText("执行 OCR")
        self.ocr_run_btn.setEnabled(False)
        self.ocr_copy_btn.setEnabled(False)

    def _toggle_left_panel(self) -> None:
        self._left_panel_collapsed = not self._left_panel_collapsed
        if self._left_panel_collapsed:
            self.left_panel.setMinimumWidth(0)
            self.left_panel.setMaximumWidth(0)
            self.left_restore_btn.show()
        else:
            self.left_panel.setMinimumWidth(260)
            self.left_panel.setMaximumWidth(320)
            self.left_restore_btn.hide()
        self._sync_splitter_sizes()

    def _toggle_right_panel(self) -> None:
        self._right_panel_collapsed = not self._right_panel_collapsed
        if self._right_panel_collapsed:
            self.right_panel.setMinimumWidth(0)
            self.right_panel.setMaximumWidth(0)
            self.right_restore_btn.show()
        else:
            self.right_panel.setMinimumWidth(300)
            self.right_panel.setMaximumWidth(320)
            self.right_restore_btn.hide()
        self._sync_splitter_sizes()

    def _sync_splitter_sizes(self) -> None:
        left_size = 0 if self._left_panel_collapsed else 260
        right_size = 0 if self._right_panel_collapsed else 300
        center_size = max(900, self.width() - left_size - right_size - 64)
        self.splitter.setSizes([left_size, center_size, right_size])

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
        self.record_count_badge.setText(f"{len(records)} 条记录")
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
            item = QListWidgetItem(self._format_record_item_text(record))
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
        self.detail_title_label.setText("预览")
        self.detail_meta_label.setText(
            f"记录 #{record.id} | 会话 #{record.session_id} | 类型：{self._format_record_type_label(record)} | "
            f"时间：{format_cn_datetime_seconds(record.created_at)}"
        )
        self.record_type_label.setText(self._format_record_type_label(record))
        self.record_time_label.setText(format_cn_datetime_seconds(record.created_at))
        self.record_session_label.setText(f"Session #{record.session_id}")


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
                    self.image_preview_label.setText("")
                    self.image_preview_label.setPixmap(pixmap)
            self._refresh_ocr_panel(record)
            self.context_tabs.setCurrentIndex(1)
            self.detail_stack.setCurrentIndex(3)
            self._refresh_chat_panel(record)
            return

        self._selected_image_path = None
        self.image_preview_label.set_image_file_path(None)
        self._reset_ocr_panel()
        full_text = (record.content or "").strip() or record_preview_text(record, max_len=500)
        self.record_text_edit.setPlainText(full_text)
        self.context_tabs.setCurrentIndex(2)
        self.detail_stack.setCurrentIndex(2)
        self._refresh_chat_panel(record)

    def _show_note_overview(self, session_id: int | None) -> None:
        if session_id is None:
            self._set_detail_placeholder("当前还没有可预览的记录内容。")
            return

        if self.note_service is None:
            self._set_detail_placeholder("当前未启用笔记服务。")
            return

        note = self.note_service.get_latest_note_for_session(session_id)
        if note is None:
            self._set_detail_placeholder("当前会话还没有学习笔记，选择记录后可查看详情。")
            return

        self.detail_title_label.setText("预览")
        self.detail_meta_label.setText(
            f"学习笔记 | 会话 #{session_id} | 更新时间：{format_cn_datetime_seconds(note.updated_at)}"
        )
        self.record_type_label.setText("学习笔记")
        self.record_time_label.setText(format_cn_datetime_seconds(note.updated_at))
        self.record_session_label.setText(f"Session #{session_id}")
        self.note_preview_edit.setPlainText(build_note_preview_text(note))
        self._selected_image_path = None
        self.image_preview_label.set_image_file_path(None)
        self.image_preview_label.setPixmap(QPixmap())
        self.image_preview_label.setText("图片预览区域")
        self._reset_ocr_panel()
        self.detail_stack.setCurrentIndex(1)
        self._reset_chat_panel("请选择记录后发起智能对话。")

    def _set_detail_placeholder(self, text: str) -> None:
        self.detail_title_label.setText("预览")
        self.detail_meta_label.setText("-")
        self.placeholder_label.setText(text)
        self.record_count_badge.setText(self.record_count_badge.text())
        self._selected_image_path = None
        self.record_type_label.setText("-")
        self.record_time_label.setText("-")
        self.record_session_label.setText("-")
        self.image_preview_label.set_image_file_path(None)
        self.image_preview_label.setPixmap(QPixmap())
        self.image_preview_label.setText("图片预览区域")
        self._reset_ocr_panel()
        self.detail_stack.setCurrentIndex(0)
        self._reset_chat_panel("请选择记录后发起智能对话。")

    def _refresh_chat_panel(self, record: Record) -> None:
        if self.record_chat_service is None:
            self._reset_chat_panel("当前未启用记录 AI 对话服务。")
            return

        messages = self.record_chat_service.list_messages_by_record(record.id)
        if not messages:
            if record.record_type == RECORD_TYPE_IMAGE:
                self.chat_hint_label.setText("可围绕该图片记录提问，若先执行 OCR，回答通常更准确。")
            else:
                self.chat_hint_label.setText("可围绕该文本记录提问，开始多轮对话。")
            self.chat_history_edit.setPlainText("暂无对话历史。")
        else:
            self.chat_hint_label.setText("已加载当前记录的历史对话，可继续追问。")
            role_map = {
                "user": "你",
                "assistant": "AI",
                "system": "系统",
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

    def _on_session_main_action(self) -> None:
        if self.session_main_btn.text() == "结束学习":
            self._on_finish_current_session()
            return
        self._on_start()

    def _on_session_aux_action(self) -> None:
        if self.session_aux_btn.text() == "继续":
            self._on_resume()
            return
        self._on_pause()

    def _on_finish_current_session(self) -> None:
        session = self._get_selected_session()
        if session is None:
            self._set_message("当前没有可结束的学习会话。", is_error=True)
            return

        try:
            if session.status == SESSION_PAUSED:
                resumed = self.session_service.resume_session(session.id)
                finished = self.session_service.finish_session(resumed.id)
            else:
                finished = self.session_service.finish_session(session.id)

            if finished.status != SESSION_FINISHED:
                self._set_message("结束学习失败：状态未正确更新。", is_error=True)
                return

            self.selected_session_id = finished.id
            self._set_message("已结束学习。", is_error=False)
            self.refresh_view()
        except ServiceError as exc:
            self._set_message(str(exc), is_error=True)

    def _show_more_menu(self) -> None:
        self.delete_record_action.setEnabled(self.delete_record_btn.isEnabled())
        self.delete_session_action.setEnabled(self.delete_session_btn.isEnabled())
        menu_pos = self.more_btn.mapToGlobal(self.more_btn.rect().bottomRight())
        self.more_menu.exec(menu_pos)

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
        can_start = has_project and in_progress is None
        can_resume_selected = selected_is_paused and in_progress is None

        self.start_btn.setEnabled(can_start)
        self.pause_btn.setEnabled(bool(selected_is_active))
        self.resume_btn.setEnabled(bool(can_resume_selected))
        self.finish_btn.setEnabled(bool(selected_is_active))

        session_can_end = bool(selected_is_active or selected_is_paused)
        self.session_main_btn.setText("结束学习" if session_can_end else "开始学习")
        self.session_main_btn.setEnabled(session_can_end or can_start)
        self.session_aux_btn.setText("继续" if selected_is_paused else "暂停")
        self.session_aux_btn.setEnabled(bool(selected_is_active) or bool(can_resume_selected))
        self.capture_btn.setEnabled(bool(selected_is_active))
        self.text_btn.setEnabled(bool(selected_is_active))
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
        self.open_ai_btn.setEnabled(selected_record is not None)
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
        color = "#ff7a7a" if is_error else "#9bb4d1"
        self.message_label.setStyleSheet(f"color: {color};")
        self.message_label.setText(text)

    def _set_session_labels(
        self,
        status: str,
        started_at: datetime | None,
        ended_at: datetime | None,
    ) -> None:
        self.status_label.setText(f"学习状态：{self._format_session_status(status)}")
        self.started_label.setText(f"开始时间：{self._format_dt(started_at)}")
        self.ended_label.setText(f"结束时间：{self._format_dt(ended_at)}")

    @staticmethod
    def _format_session_status(status: str) -> str:
        mapping = {
            "not_started": "尚未开始记录",
            SESSION_IN_PROGRESS: "记录中",
            SESSION_PAUSED: "已暂停",
            SESSION_FINISHED: "已结束",
        }
        return mapping.get(status, status)

    @staticmethod
    def _format_record_type_label(record: Record) -> str:
        if record.record_type == RECORD_TYPE_IMAGE and record.is_inspiration:
            return "灵感配图"
        if record.record_type == RECORD_TYPE_IMAGE:
            return "截图"
        if record.record_type == "text" and record.is_inspiration:
            return "灵感"
        if record.record_type == "text":
            return "文本"
        return record.record_type

    def _format_record_item_text(self, record: Record) -> str:
        created = format_cn_datetime_seconds(record.created_at)
        preview = record_preview_text(record, max_len=48)
        if record.record_type == RECORD_TYPE_IMAGE:
            return f"{created}\n{self._format_record_type_label(record)} · {record_display_name(record)}"
        return f"{created}\n{self._format_record_type_label(record)} · {preview}"

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
            f"类型：{StudyPage._format_record_type_label(record)}\n"
            f"名称：{record_name}\n"
            f"时间：{format_cn_datetime_seconds(record.created_at)}\n"
            f"内容：{preview}"
        )






































