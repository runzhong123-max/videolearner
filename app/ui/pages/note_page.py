from PySide6.QtCore import QThread, QSize, Qt, Signal
import re
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.models.note import Note
from app.models.project import Project
from app.models.session import Session
from app.services.errors import ServiceError
from app.services.note_service import NoteService
from app.ui.view_helpers import (
    build_note_session_display,
    build_session_display_numbers,
    iter_note_sections,
    session_display_label,
)
from app.utils.datetime_utils import format_cn_datetime_seconds


class RegenerateNoteWorker(QThread):
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


class NotePage(QWidget):
    def __init__(self, note_service: NoteService, parent=None):
        super().__init__(parent)
        self.note_service = note_service
        self.current_project: Project | None = None
        self.current_session: Session | None = None
        self.current_note: Note | None = None
        self._section_widgets: list[QWidget] = []
        self._last_copy_text = ""
        self._regen_worker: RegenerateNoteWorker | None = None
        self._project_notes: list[Note] = []
        self._sessions_by_id: dict[int, Session] = {}
        self._session_display_numbers: dict[int, int] = {}

        self.title_label = QLabel("笔记")
        self.title_label.setProperty("role", "pageTitle")
        self.subtitle_label = QLabel("集中查看当前项目下的学习笔记，并保留已有重生成功能。")
        self.subtitle_label.setProperty("role", "pageSubtitle")
        self.summary_label = QLabel("0 篇笔记")
        self.summary_label.setProperty("role", "badge")

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索笔记标题、摘要或来源会话...")
        self.search_input.textChanged.connect(self.refresh_view)

        self.note_list = QListWidget()
        self.note_list.setObjectName("CardList")
        self.note_list.currentItemChanged.connect(self._on_note_changed)

        self.empty_card = self._build_empty_card()
        self.message_label = QLabel("请先在学习页选择项目。")
        self.message_label.setWordWrap(True)
        self.message_label.setProperty("role", "muted")

        self.project_label = QLabel("当前项目：未选择")
        self.project_label.setProperty("role", "muted")
        self.session_label = QLabel("来源：未选择")
        self.session_label.setProperty("role", "muted")
        self.note_title_label = QLabel("笔记标题：-")
        self.note_title_label.setProperty("role", "sectionTitle")
        self.note_time_label = QLabel("生成时间：-")
        self.note_time_label.setProperty("role", "muted")
        self.note_model_label = QLabel("模型：-")
        self.note_model_label.setProperty("role", "muted")
        self.version_hint_label = QLabel("版本：-")
        self.version_hint_label.setProperty("role", "sectionHint")

        self.version_combo = QComboBox()
        self.version_combo.currentIndexChanged.connect(self._on_version_changed)

        self.refresh_btn = QPushButton("刷新笔记")
        self.regenerate_btn = QPushButton("重新生成")
        self.copy_btn = QPushButton("复制笔记")
        self.export_placeholder_btn = QPushButton("导出（即将支持）")
        self.export_placeholder_btn.setEnabled(False)
        self.generate_btn = QPushButton("生成笔记")
        self.generate_btn.setProperty("variant", "primary")

        self.refresh_btn.clicked.connect(self.refresh_view)
        self.regenerate_btn.clicked.connect(self._on_regenerate)
        self.copy_btn.clicked.connect(self._on_copy)
        self.generate_btn.clicked.connect(self._on_regenerate)

        self.review_toggle_btn = QPushButton("显示复盘附加区（可选）")
        self.review_toggle_btn.setCheckable(True)
        self.review_toggle_btn.toggled.connect(self._on_toggle_review_panel)

        self.review_panel = QWidget()
        self.review_panel.setObjectName("InsetCard")
        review_layout = QFormLayout(self.review_panel)
        review_layout.setContentsMargins(16, 16, 16, 16)
        review_layout.setHorizontalSpacing(16)
        review_layout.setVerticalSpacing(12)
        self.review_questions_edit = QTextEdit()
        self.review_questions_edit.setPlaceholderText("复习问题（可选）")
        self.review_questions_edit.setMinimumHeight(90)
        self.key_points_edit = QTextEdit()
        self.key_points_edit.setPlaceholderText("重点提炼（可选）")
        self.key_points_edit.setMinimumHeight(90)
        self.follow_up_tasks_edit = QTextEdit()
        self.follow_up_tasks_edit.setPlaceholderText("后续小任务（可选）")
        self.follow_up_tasks_edit.setMinimumHeight(90)

        self.flag_review_list = QCheckBox("加入复习列表")
        self.flag_key_note = QCheckBox("标记重点")
        self.flag_review_later = QCheckBox("稍后复习")
        self.save_review_btn = QPushButton("保存附加整理")
        self.save_review_btn.clicked.connect(self._on_save_review_fields)

        flags_row = QHBoxLayout()
        flags_row.addWidget(self.flag_review_list)
        flags_row.addWidget(self.flag_key_note)
        flags_row.addWidget(self.flag_review_later)
        flags_row.addStretch(1)

        review_layout.addRow("复习问题", self.review_questions_edit)
        review_layout.addRow("重点提炼", self.key_points_edit)
        review_layout.addRow("后续任务", self.follow_up_tasks_edit)
        review_layout.addRow("轻量标记", flags_row)
        review_layout.addRow("", self.save_review_btn)
        self.review_panel.setVisible(False)

        self.sections_container = QWidget()
        self.sections_layout = QVBoxLayout(self.sections_container)
        self.sections_layout.setContentsMargins(0, 0, 0, 0)
        self.sections_layout.setSpacing(12)
        self.sections_layout.addStretch(1)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.sections_container)

        self._build_ui()
        self._set_action_enabled(False)

    def _build_ui(self) -> None:
        header_row = QHBoxLayout()
        header_row.setSpacing(12)
        header_text = QVBoxLayout()
        header_text.setSpacing(4)
        header_text.addWidget(self.title_label)
        header_text.addWidget(self.subtitle_label)
        header_row.addLayout(header_text)
        header_row.addStretch(1)
        header_row.addWidget(self.summary_label)
        header_row.addWidget(self.generate_btn)

        search_row = QHBoxLayout()
        search_row.setSpacing(12)
        search_row.addWidget(self.search_input, 1)

        list_panel = QWidget()
        list_panel.setObjectName("PanelCard")
        list_layout = QVBoxLayout(list_panel)
        list_layout.setContentsMargins(18, 18, 18, 18)
        list_layout.setSpacing(12)
        list_title = QLabel("笔记列表")
        list_title.setProperty("role", "sectionTitle")
        list_hint = QLabel("优先浏览当前项目下的笔记卡片，再查看下方详细内容。")
        list_hint.setProperty("role", "sectionHint")
        list_layout.addWidget(list_title)
        list_layout.addWidget(list_hint)
        list_layout.addWidget(self.note_list, 1)
        list_layout.addWidget(self.empty_card)
        list_layout.addWidget(self.message_label)

        detail_panel = QWidget()
        detail_panel.setObjectName("PanelCard")
        detail_layout = QVBoxLayout(detail_panel)
        detail_layout.setContentsMargins(18, 18, 18, 18)
        detail_layout.setSpacing(12)
        detail_layout.addWidget(self.note_title_label)
        detail_layout.addWidget(self.project_label)
        detail_layout.addWidget(self.session_label)
        detail_layout.addWidget(self.note_time_label)
        detail_layout.addWidget(self.note_model_label)

        version_row = QHBoxLayout()
        version_row.setSpacing(12)
        version_row.addWidget(self.version_hint_label)
        version_row.addStretch(1)
        version_row.addWidget(self.version_combo)
        detail_layout.addLayout(version_row)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)
        button_row.addWidget(self.refresh_btn)
        button_row.addWidget(self.regenerate_btn)
        button_row.addWidget(self.copy_btn)
        button_row.addWidget(self.export_placeholder_btn)
        detail_layout.addLayout(button_row)
        detail_layout.addWidget(self.review_toggle_btn)
        detail_layout.addWidget(self.review_panel)
        detail_layout.addWidget(self.scroll, 1)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(list_panel)
        splitter.addWidget(detail_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 4)
        splitter.setSizes([320, 520])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)
        layout.addLayout(header_row)
        layout.addLayout(search_row)
        layout.addWidget(splitter, 1)

    def _build_empty_card(self) -> QWidget:
        card = QWidget()
        card.setObjectName("PanelCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(8)
        title = QLabel("还没有可展示的笔记")
        title.setProperty("role", "emptyTitle")
        body = QLabel("先在学习页完成一次学习并生成笔记，这里就会出现对应的笔记卡片。")
        body.setProperty("role", "emptyBody")
        body.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(body)
        layout.addStretch(1)
        return card

    def set_current_project(self, project: Project | None) -> None:
        self.current_project = project
        self.refresh_view()

    def set_selected_session(self, session: Session | None) -> None:
        self.current_session = session
        self.refresh_view()

    def refresh_view(self) -> None:
        preferred_note_id = self.current_note.id if self.current_note is not None else None
        if self.current_session is not None:
            latest_note = self.note_service.get_latest_note_for_session(self.current_session.id)
            if latest_note is not None:
                preferred_note_id = latest_note.id

        self._clear_sections()
        self._last_copy_text = ""
        self.current_note = None
        self.note_list.clear()
        self._project_notes = []
        self._sessions_by_id = {}
        self._session_display_numbers = {}

        if self.current_project is None:
            self.project_label.setText("当前项目：未选择")
            self.session_label.setText("来源：未选择")
            self._clear_note_meta()
            self.message_label.setText("未选择项目。")
            self.summary_label.setText("0 篇笔记")
            self.note_list.setVisible(False)
            self.empty_card.setVisible(True)
            self._set_action_enabled(False)
            return

        self.project_label.setText(f"当前项目：{self.current_project.name}")
        sessions = self.note_service.session_repository.list_by_project(self.current_project.id)
        self._sessions_by_id = {session.id: session for session in sessions if session.id is not None}
        self._session_display_numbers = build_session_display_numbers(sessions)
        notes = self.note_service.note_repository.list_by_project(self.current_project.id, limit=100)
        query = self.search_input.text().strip().lower()
        if query:
            notes = [
                note for note in notes
                if query in (note.title or "").lower()
                or query in (note.summary or "").lower()
                or query in (note.content or "").lower()
            ]
        self._project_notes = notes
        self.summary_label.setText(f"{len(notes)} 篇笔记")

        selected_row = -1
        for index, note in enumerate(notes):
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, note.id)
            item.setSizeHint(QSize(0, 132))
            self.note_list.addItem(item)
            self.note_list.setItemWidget(item, self._build_note_card(note))
            if preferred_note_id is not None and note.id == preferred_note_id:
                selected_row = index

        has_notes = bool(notes)
        self.note_list.setVisible(has_notes)
        self.empty_card.setVisible(not has_notes)

        if selected_row >= 0:
            self.note_list.setCurrentRow(selected_row)
        elif has_notes:
            self.note_list.setCurrentRow(0)
        else:
            self._clear_note_meta()
            self.message_label.setText("当前项目还没有学习笔记。")
            self._set_action_enabled(bool(self.current_session))

    def _build_note_card(self, note: Note) -> QWidget:
        card = QWidget()
        card.setObjectName("PanelCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(8)

        session = self._resolve_note_session(note.session_id)
        title_text, source_text = self._build_note_session_display(session)
        preview = (note.summary or note.content or "暂无摘要").strip().replace("\n", " ")
        if len(preview) > 120:
            preview = preview[:117] + "..."

        title_label = QLabel(title_text)
        title_label.setProperty("role", "cardTitle")
        preview_label = QLabel(preview)
        preview_label.setProperty("role", "cardBody")
        preview_label.setWordWrap(True)
        meta_label = QLabel(f"{source_text}  ·  时间：{format_cn_datetime_seconds(note.updated_at)}")
        meta_label.setProperty("role", "cardMeta")

        layout.addWidget(title_label)
        layout.addWidget(preview_label)
        layout.addWidget(meta_label)
        return card

    def _on_note_changed(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if current is None:
            self.current_note = None
            self._clear_note_meta()
            self._set_action_enabled(bool(self.current_session))
            return

        note_id = current.data(Qt.ItemDataRole.UserRole)
        if note_id is None:
            return

        note = self.note_service.get_note_by_id(int(note_id))
        if note is None:
            self.current_note = None
            self.message_label.setText("笔记读取失败。")
            self._clear_note_meta()
            self._set_action_enabled(bool(self.current_session))
            return

        self._set_current_note(note)
        self.message_label.setText("已加载所选笔记。")
        self._set_action_enabled(True)

    def _set_current_note(self, note: Note) -> None:
        self.current_note = note
        session = self._resolve_note_session(note.session_id)
        title_text, source_text = self._build_note_session_display(session)

        self.note_title_label.setText(title_text)
        self.session_label.setText(source_text)
        self.note_time_label.setText(f"生成时间：{format_cn_datetime_seconds(note.updated_at)}")

        model_text = note.ai_provider or "-"
        if note.ai_model:
            model_text += f" / {note.ai_model}"
        self.note_model_label.setText(f"模型：{model_text}")

        versions = self.note_service.list_note_versions_for_session(note.session_id)
        self._reload_version_combo(versions, note.id)
        self._render_note(note)
        self._load_review_fields(note)

    def _resolve_note_session(self, session_id: int) -> Session | None:
        session = self._sessions_by_id.get(session_id)
        if session is None:
            session = self.note_service.session_repository.get_by_id(session_id)
            if session is not None and session.id is not None:
                self._sessions_by_id[session.id] = session

        if session is not None and session.id is not None and session.id not in self._session_display_numbers:
            self._rebuild_session_display_map()
            session = self._sessions_by_id.get(session_id, session)

        return session

    def _rebuild_session_display_map(self) -> None:
        if self.current_project is None:
            return
        sessions = self.note_service.session_repository.list_by_project(self.current_project.id)
        self._sessions_by_id = {item.id: item for item in sessions if item.id is not None}
        self._session_display_numbers = build_session_display_numbers(sessions)

    def _build_note_session_display(self, session: Session | None) -> tuple[str, str]:
        return build_note_session_display(
            self.current_project.name if self.current_project is not None else None,
            session,
            self._session_display_numbers,
        )

    def _reload_version_combo(self, versions: list[Note], selected_note_id: int | None = None) -> None:
        self.version_combo.blockSignals(True)
        self.version_combo.clear()
        for idx, note in enumerate(versions):
            self.version_combo.addItem(self._build_version_label(note, idx, len(versions)), note.id)
        self.version_combo.blockSignals(False)

        if versions:
            target_id = selected_note_id or versions[0].id
            index = self.version_combo.findData(target_id)
            self.version_combo.setCurrentIndex(index if index >= 0 else 0)
            if len(versions) > 1:
                self.version_hint_label.setText(f"当前会话已保留 {len(versions)} 个笔记版本")
            else:
                self.version_hint_label.setText("当前会话仅有 1 个笔记版本")
        else:
            self.version_hint_label.setText("版本：-")

    def _render_note(self, note: Note) -> None:
        self._clear_sections()
        sections = iter_note_sections(note)
        text_blocks: list[str] = []
        if sections:
            for _key, section_title, section_content in sections:
                self._add_section_card(section_title, section_content)
                text_blocks.append(f"[{section_title}]\n{section_content}")
        else:
            self._add_section_card("笔记内容", "暂无可展示内容。")
            text_blocks.append("暂无可展示内容。")
        self._last_copy_text = "\n\n".join(text_blocks)

    def _add_section_card(self, title: str, content: str) -> None:
        card = QWidget()
        card.setObjectName("InsetCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title_label = QLabel(title)
        title_label.setProperty("role", "sectionTitle")
        viewer = QTextEdit()
        viewer.setReadOnly(True)
        viewer.setPlainText(content)
        viewer.setMinimumHeight(120)

        layout.addWidget(title_label)
        layout.addWidget(viewer)
        self.sections_layout.insertWidget(self.sections_layout.count() - 1, card)
        self._section_widgets.append(card)

    def _clear_sections(self) -> None:
        for widget in self._section_widgets:
            self.sections_layout.removeWidget(widget)
            widget.deleteLater()
        self._section_widgets.clear()

    def _on_copy(self) -> None:
        if not self._last_copy_text.strip():
            return
        QApplication.clipboard().setText(self._last_copy_text)
        self.message_label.setText("笔记内容已复制到剪贴板。")

    def _on_version_changed(self, _index: int) -> None:
        note_id = self.version_combo.currentData()
        if note_id is None:
            return
        note = self.note_service.get_note_by_id(int(note_id))
        if note is None:
            self.message_label.setText("所选版本不存在或已删除。")
            return
        self._set_current_note(note)
        self.message_label.setText("已切换笔记版本。")

    def _on_regenerate(self) -> None:
        if self.current_session is None:
            self.message_label.setText("请先在学习页选择一个学习会话。")
            return
        if self._regen_worker is not None and self._regen_worker.isRunning():
            self.message_label.setText("已有生成任务在进行，请稍候。")
            return

        self.regenerate_btn.setEnabled(False)
        self.generate_btn.setEnabled(False)
        self.regenerate_btn.setText("生成中...")
        self.message_label.setText("正在重新生成笔记...")

        worker = RegenerateNoteWorker(self.note_service, self.current_session.id)
        self._regen_worker = worker
        worker.success.connect(self._on_regenerate_success)
        worker.failure.connect(self._on_regenerate_failure)
        worker.finished.connect(self._on_regenerate_finished)
        worker.start()

    def _on_regenerate_success(self, result) -> None:
        self.refresh_view()
        provider_text = result.provider or "-"
        if result.model:
            provider_text += f"/{result.model}"

        if result.previous_versions_count > 0:
            self.message_label.setText(
                f"重新生成成功（provider={provider_text}），已保留旧版 {result.previous_versions_count} 条。"
            )
        else:
            self.message_label.setText(f"生成成功（provider={provider_text}）。")

    def _on_regenerate_failure(self, error_message: str) -> None:
        msg = (error_message or "").strip()
        lower = msg.lower()
        if "api_key" in lower or "configuration" in lower or "配置" in msg:
            msg += "（请先在 AI 设置 中检查 Provider 配置）"
        self.message_label.setText(f"重新生成失败：{msg}")

    def _on_regenerate_finished(self) -> None:
        self.regenerate_btn.setText("重新生成")
        self.regenerate_btn.setEnabled(True)
        self.generate_btn.setEnabled(self.current_session is not None)
        self._regen_worker = None

    def _on_toggle_review_panel(self, checked: bool) -> None:
        self.review_panel.setVisible(checked)
        self.review_toggle_btn.setText("隐藏复盘附加区" if checked else "显示复盘附加区（可选）")

    def _load_review_fields(self, note: Note) -> None:
        self.review_questions_edit.setPlainText(note.review_questions or "")
        self.key_points_edit.setPlainText(note.key_points or "")
        self.follow_up_tasks_edit.setPlainText(note.follow_up_tasks or "")
        self.flag_review_list.setChecked(bool(note.in_review_list))
        self.flag_key_note.setChecked(bool(note.is_key_note))
        self.flag_review_later.setChecked(bool(note.review_later))

    def _on_save_review_fields(self) -> None:
        if self.current_note is None:
            self.message_label.setText("当前无可保存的笔记版本。")
            return
        try:
            updated = self.note_service.update_note_review_fields(
                note_id=self.current_note.id,
                review_questions=self.review_questions_edit.toPlainText(),
                key_points=self.key_points_edit.toPlainText(),
                follow_up_tasks=self.follow_up_tasks_edit.toPlainText(),
                in_review_list=self.flag_review_list.isChecked(),
                is_key_note=self.flag_key_note.isChecked(),
                review_later=self.flag_review_later.isChecked(),
            )
            self.current_note = updated
            self.message_label.setText("复盘附加区已保存。")
        except ServiceError as exc:
            self.message_label.setText(str(exc))

    def _clear_note_meta(self) -> None:
        self.note_title_label.setText("笔记标题：-")
        self.note_time_label.setText("生成时间：-")
        self.note_model_label.setText("模型：-")
        self.version_hint_label.setText("版本：-")
        self.version_combo.blockSignals(True)
        self.version_combo.clear()
        self.version_combo.blockSignals(False)
        self._clear_review_fields()
        self._clear_sections()

    def _clear_review_fields(self) -> None:
        self.review_questions_edit.clear()
        self.key_points_edit.clear()
        self.follow_up_tasks_edit.clear()
        self.flag_review_list.setChecked(False)
        self.flag_key_note.setChecked(False)
        self.flag_review_later.setChecked(False)

    def _set_action_enabled(self, enabled: bool) -> None:
        self.refresh_btn.setEnabled(self.current_project is not None)
        self.regenerate_btn.setEnabled(self.current_session is not None and enabled)
        self.generate_btn.setEnabled(self.current_session is not None)
        self.copy_btn.setEnabled(self.current_note is not None and enabled)
        self.save_review_btn.setEnabled(self.current_note is not None)
        self.review_toggle_btn.setEnabled(self.current_note is not None)

    @staticmethod
    def _build_version_label(note: Note, idx: int, total: int) -> str:
        time_text = format_cn_datetime_seconds(note.created_at)
        model = note.ai_provider or "manual"
        if note.ai_model:
            model += f"/{note.ai_model}"
        tag = "最新" if idx == 0 else f"v{total - idx}"
        return f"{tag} | #{note.id} | {time_text} | {model}"
