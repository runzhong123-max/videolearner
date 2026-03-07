from PySide6.QtWidgets import (
    QApplication,
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

from app.models.project import Project
from app.models.session import Session
from app.services.note_service import NoteService
from app.ui.view_helpers import iter_note_sections
from app.utils.datetime_utils import format_cn_datetime_seconds


class NotePage(QWidget):
    def __init__(self, note_service: NoteService, parent=None):
        super().__init__(parent)
        self.note_service = note_service
        self.current_project: Project | None = None
        self.current_session: Session | None = None
        self._section_widgets: list[QWidget] = []
        self._last_copy_text = ""

        self.project_label = QLabel("当前项目：未选择")
        self.session_label = QLabel("当前 Session：未选择")
        self.note_title_label = QLabel("笔记标题：-")
        self.note_time_label = QLabel("生成时间：-")
        self.message_label = QLabel("请先在 Study 页面选中一个 Session。")
        self.message_label.setWordWrap(True)

        self.refresh_btn = QPushButton("刷新笔记")
        self.copy_btn = QPushButton("复制笔记")
        self.export_placeholder_btn = QPushButton("导出（即将支持）")
        self.export_placeholder_btn.setEnabled(False)

        self.refresh_btn.clicked.connect(self.refresh_view)
        self.copy_btn.clicked.connect(self._on_copy)

        form = QFormLayout()
        form.addRow("项目", self.project_label)
        form.addRow("Session", self.session_label)
        form.addRow("标题", self.note_title_label)
        form.addRow("时间", self.note_time_label)

        button_row = QHBoxLayout()
        button_row.addWidget(self.refresh_btn)
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
        layout.addWidget(self.message_label)
        layout.addWidget(self.scroll, 1)

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

        if self.current_project is None:
            self.project_label.setText("当前项目：未选择")
            self.session_label.setText("当前 Session：未选择")
            self.note_title_label.setText("笔记标题：-")
            self.note_time_label.setText("生成时间：-")
            self.message_label.setText("未选择项目。")
            return

        self.project_label.setText(f"{self.current_project.name} (ID={self.current_project.id})")

        if self.current_session is None or self.current_session.project_id != self.current_project.id:
            self.session_label.setText("当前 Session：未选择")
            self.note_title_label.setText("笔记标题：-")
            self.note_time_label.setText("生成时间：-")
            self.message_label.setText("请在 Study 页面选中一个 Session 后查看笔记。")
            return

        self.session_label.setText(f"#{self.current_session.id} | {self.current_session.status}")
        note = self.note_service.get_latest_note_for_session(self.current_session.id)
        if note is None:
            self.note_title_label.setText("笔记标题：-")
            self.note_time_label.setText("生成时间：-")
            self.message_label.setText("该 Session 还没有生成笔记。")
            return

        title = note.title or f"Session #{note.session_id} 笔记"
        self.note_title_label.setText(title)
        self.note_time_label.setText(format_cn_datetime_seconds(note.updated_at))
        self.message_label.setText("已加载该 Session 最新笔记。")

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
