from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.models.note import Note
from app.models.project import Project
from app.models.session import Session
from app.services.errors import ServiceError
from app.services.note_service import NoteService
from app.ui.view_helpers import iter_note_sections
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

        self.project_label = QLabel("当前项目：未选择")
        self.session_label = QLabel("当前 Session：未选择")
        self.note_title_label = QLabel("笔记标题：-")
        self.note_time_label = QLabel("生成时间：-")
        self.note_model_label = QLabel("模型：-")
        self.version_hint_label = QLabel("版本：-")
        self.message_label = QLabel("请先在 Study 页面选中一个 Session。")
        self.message_label.setWordWrap(True)

        self.version_combo = QComboBox()
        self.version_combo.currentIndexChanged.connect(self._on_version_changed)

        self.refresh_btn = QPushButton("刷新笔记")
        self.regenerate_btn = QPushButton("重新生成")
        self.copy_btn = QPushButton("复制笔记")
        self.export_placeholder_btn = QPushButton("导出（即将支持）")
        self.export_placeholder_btn.setEnabled(False)

        self.refresh_btn.clicked.connect(self.refresh_view)
        self.regenerate_btn.clicked.connect(self._on_regenerate)
        self.copy_btn.clicked.connect(self._on_copy)

        self.review_toggle_btn = QPushButton("显示复盘附加区（可选）")
        self.review_toggle_btn.setCheckable(True)
        self.review_toggle_btn.toggled.connect(self._on_toggle_review_panel)

        self.review_panel = QWidget()
        review_layout = QFormLayout(self.review_panel)
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

        review_layout.addRow("复习问题", self.review_questions_edit)
        review_layout.addRow("重点提炼", self.key_points_edit)
        review_layout.addRow("后续任务", self.follow_up_tasks_edit)
        review_layout.addRow("轻量标记", flags_row)
        review_layout.addRow("", self.save_review_btn)

        self.review_panel.setVisible(False)

        form = QFormLayout()
        form.addRow("项目", self.project_label)
        form.addRow("Session", self.session_label)
        form.addRow("标题", self.note_title_label)
        form.addRow("时间", self.note_time_label)
        form.addRow("模型", self.note_model_label)
        form.addRow("版本", self.version_combo)

        button_row = QHBoxLayout()
        button_row.addWidget(self.refresh_btn)
        button_row.addWidget(self.regenerate_btn)
        button_row.addWidget(self.copy_btn)
        button_row.addWidget(self.export_placeholder_btn)

        self.sections_container = QWidget()
        self.sections_layout = QVBoxLayout(self.sections_container)
        self.sections_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.sections_container)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(button_row)
        layout.addWidget(self.version_hint_label)
        layout.addWidget(self.message_label)
        layout.addWidget(self.review_toggle_btn)
        layout.addWidget(self.review_panel)
        layout.addWidget(self.scroll, 1)

        self._set_action_enabled(False)

    def set_current_project(self, project: Project | None) -> None:
        self.current_project = project
        if project is None:
            self.project_label.setText("当前项目：未选择")
        else:
            self.project_label.setText(f"{project.name} (ID={project.id})")
        self.refresh_view()

    def set_selected_session(self, session: Session | None) -> None:
        self.current_session = session
        self.refresh_view()

    def refresh_view(self) -> None:
        self._clear_sections()
        self._last_copy_text = ""
        self.current_note = None

        if self.current_project is None:
            self.project_label.setText("当前项目：未选择")
            self.session_label.setText("当前 Session：未选择")
            self._clear_note_meta()
            self.message_label.setText("未选择项目。")
            self._set_action_enabled(False)
            return

        self.project_label.setText(f"{self.current_project.name} (ID={self.current_project.id})")

        if self.current_session is None or self.current_session.project_id != self.current_project.id:
            self.session_label.setText("当前 Session：未选择")
            self._clear_note_meta()
            self.message_label.setText("请在 Study 页面选中一个 Session 后查看笔记。")
            self._set_action_enabled(False)
            return

        self.session_label.setText(f"#{self.current_session.id} | {self.current_session.status}")
        versions = self.note_service.list_note_versions_for_session(self.current_session.id)
        self._reload_version_combo(versions)

        if not versions:
            self._clear_note_meta()
            self.message_label.setText("该 Session 还没有生成笔记。")
            self._set_action_enabled(True)
            return

        latest = versions[0]
        self._set_current_note(latest)
        self.message_label.setText("已加载该 Session 最新笔记。")
        self._set_action_enabled(True)

    def _reload_version_combo(self, versions: list[Note]) -> None:
        self.version_combo.blockSignals(True)
        self.version_combo.clear()
        for idx, note in enumerate(versions):
            label = self._build_version_label(note, idx, len(versions))
            self.version_combo.addItem(label, note.id)
        self.version_combo.blockSignals(False)

        if versions:
            self.version_combo.setCurrentIndex(0)
            if len(versions) > 1:
                self.version_hint_label.setText(f"当前 Session 已保留 {len(versions)} 个版本（最新在最上方）。")
            else:
                self.version_hint_label.setText("当前 Session 仅有 1 个版本。")
        else:
            self.version_hint_label.setText("版本：-")

    def _set_current_note(self, note: Note) -> None:
        self.current_note = note
        title = note.title or f"Session #{note.session_id} 笔记"
        self.note_title_label.setText(title)
        self.note_time_label.setText(format_cn_datetime_seconds(note.updated_at))

        model_text = "-"
        if note.ai_provider:
            model_text = note.ai_provider
            if note.ai_model:
                model_text += f" / {note.ai_model}"
        self.note_model_label.setText(model_text)

        self._render_note(note)
        self._load_review_fields(note)

    def _render_note(self, note: Note) -> None:
        self._clear_sections()
        sections = iter_note_sections(note)
        text_blocks: list[str] = []
        for _key, section_title, section_content in sections:
            self._add_section_card(section_title, section_content)
            text_blocks.append(f"[{section_title}]\n{section_content}")

        if not sections:
            self._add_section_card("内容", "暂无可展示内容。")
            text_blocks.append("暂无可展示内容。")

        self._last_copy_text = "\n\n".join(text_blocks)

    def _add_section_card(self, title: str, content: str) -> None:
        box = QGroupBox(title)
        inner = QVBoxLayout(box)

        viewer = QTextEdit()
        viewer.setReadOnly(True)
        viewer.setPlainText(content)
        viewer.setMinimumHeight(120)

        inner.addWidget(viewer)
        self.sections_layout.addWidget(box)
        self._section_widgets.append(box)

    def _clear_sections(self) -> None:
        for widget in self._section_widgets:
            self.sections_layout.removeWidget(widget)
            widget.deleteLater()
        self._section_widgets.clear()

    def _on_copy(self) -> None:
        if not self._last_copy_text.strip():
            return
        clipboard = QApplication.clipboard()
        clipboard.setText(self._last_copy_text)
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
            self.message_label.setText("请先选择 Session。")
            return
        if self._regen_worker is not None and self._regen_worker.isRunning():
            self.message_label.setText("已有生成任务在进行，请稍候。")
            return

        self.regenerate_btn.setEnabled(False)
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
        if self.current_note is not None:
            idx = self.version_combo.findData(self.current_note.id)
            if idx >= 0:
                self.version_combo.setCurrentIndex(idx)

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
            msg += "（请先在 AI Settings 中检查 Provider 配置）"
        self.message_label.setText(f"重新生成失败：{msg}")

    def _on_regenerate_finished(self) -> None:
        self.regenerate_btn.setText("重新生成")
        self.regenerate_btn.setEnabled(True)
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

    def _clear_review_fields(self) -> None:
        self.review_questions_edit.clear()
        self.key_points_edit.clear()
        self.follow_up_tasks_edit.clear()
        self.flag_review_list.setChecked(False)
        self.flag_key_note.setChecked(False)
        self.flag_review_later.setChecked(False)

    def _set_action_enabled(self, enabled: bool) -> None:
        self.refresh_btn.setEnabled(enabled)
        self.regenerate_btn.setEnabled(enabled)
        self.copy_btn.setEnabled(enabled)
        has_note = self.current_note is not None
        self.save_review_btn.setEnabled(has_note)
        self.review_toggle_btn.setEnabled(enabled)

    @staticmethod
    def _build_version_label(note: Note, idx: int, total: int) -> str:
        time_text = format_cn_datetime_seconds(note.created_at)
        model = note.ai_provider or "manual"
        if note.ai_model:
            model += f"/{note.ai_model}"
        tag = "最新" if idx == 0 else f"v{total - idx}"
        return f"{tag} | #{note.id} | {time_text} | {model}"
