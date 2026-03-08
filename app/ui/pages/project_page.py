from datetime import datetime

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.models.project import Project
from app.services.errors import ServiceError
from app.services.note_service import NoteService
from app.services.project_service import ProjectService
from app.services.session_service import SessionService
from app.utils.datetime_utils import format_cn_datetime


class ProjectPage(QWidget):
    project_selected = Signal(object)

    def __init__(
        self,
        project_service: ProjectService,
        session_service: SessionService,
        note_service: NoteService,
        parent=None,
    ):
        super().__init__(parent)
        self.project_service = project_service
        self.session_service = session_service
        self.note_service = note_service
        self.current_project_id: int | None = None
        self.active_project_id: int | None = None

        self.title_label = QLabel("项目")
        self.title_label.setProperty("role", "pageTitle")
        self.subtitle_label = QLabel("管理长期学习主题，按项目查看 Session 与笔记沉淀。")
        self.subtitle_label.setProperty("role", "pageSubtitle")
        self.summary_label = QLabel("0 个项目")
        self.summary_label.setProperty("role", "badge")

        self.project_list = QListWidget()
        self.project_list.setObjectName("CardList")
        self.project_list.currentItemChanged.connect(self._on_item_changed)

        self.empty_card = self._build_empty_card()
        self.message_label = QLabel("")
        self.message_label.setWordWrap(True)
        self.message_label.setProperty("role", "muted")

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("输入项目名称")
        self.description_edit = QTextEdit()
        self.description_edit.setPlaceholderText("补充项目简介、学习范围或背景。")
        self.description_edit.setMinimumHeight(110)
        self.source_edit = QLineEdit()
        self.source_edit.setPlaceholderText("例如：课程、书籍、训练营")
        self.goal_edit = QLineEdit()
        self.goal_edit.setPlaceholderText("例如：掌握基础理论并完成复习")
        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("例如：机器学习, 数学基础")

        self.detail_title_label = QLabel("项目详情")
        self.detail_title_label.setProperty("role", "sectionTitle")
        self.detail_hint_label = QLabel("选中项目后可查看信息并继续沿用现有创建、保存与删除流程。")
        self.detail_hint_label.setProperty("role", "sectionHint")
        self.detail_meta_label = QLabel("未选择项目")
        self.detail_meta_label.setProperty("role", "muted")
        self.detail_meta_label.setWordWrap(True)

        self.new_btn = QPushButton("新建项目")
        self.new_btn.setProperty("variant", "primary")
        self.save_btn = QPushButton("保存修改")
        self.select_btn = QPushButton("设为当前项目")
        self.delete_btn = QPushButton("删除项目")
        self.refresh_btn = QPushButton("刷新列表")
        self.refresh_btn.setProperty("variant", "ghost")

        self.new_btn.clicked.connect(self._on_new)
        self.save_btn.clicked.connect(self._on_save)
        self.delete_btn.clicked.connect(self._on_delete)
        self.select_btn.clicked.connect(self._on_select)
        self.refresh_btn.clicked.connect(self.reload_projects)

        self._build_ui()
        self.reload_projects()

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
        header_row.addWidget(self.new_btn)

        list_panel = QWidget()
        list_panel.setObjectName("PanelCard")
        list_layout = QVBoxLayout(list_panel)
        list_layout.setContentsMargins(18, 18, 18, 18)
        list_layout.setSpacing(12)
        list_title = QLabel("项目列表")
        list_title.setProperty("role", "sectionTitle")
        list_hint = QLabel("优先浏览项目卡片，再在右侧做轻量维护。")
        list_hint.setProperty("role", "sectionHint")
        list_layout.addWidget(list_title)
        list_layout.addWidget(list_hint)
        list_layout.addWidget(self.project_list, 1)
        list_layout.addWidget(self.empty_card)
        list_layout.addWidget(self.message_label)

        detail_panel = QWidget()
        detail_panel.setObjectName("PanelCard")
        detail_layout = QVBoxLayout(detail_panel)
        detail_layout.setContentsMargins(18, 18, 18, 18)
        detail_layout.setSpacing(12)
        detail_layout.addWidget(self.detail_title_label)
        detail_layout.addWidget(self.detail_hint_label)
        detail_layout.addWidget(self.detail_meta_label)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)
        form.addRow("项目名称", self.name_edit)
        form.addRow("项目简介", self.description_edit)
        form.addRow("学习来源", self.source_edit)
        form.addRow("学习目标", self.goal_edit)
        form.addRow("标签", self.tags_edit)
        detail_layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(self.select_btn)
        btn_row.addWidget(self.delete_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(self.refresh_btn)
        detail_layout.addLayout(btn_row)
        detail_layout.addStretch(1)

        content_row = QHBoxLayout()
        content_row.setSpacing(16)
        content_row.addWidget(list_panel, 5)
        content_row.addWidget(detail_panel, 4)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)
        layout.addLayout(header_row)
        layout.addLayout(content_row, 1)

    def _build_empty_card(self) -> QWidget:
        card = QWidget()
        card.setObjectName("PanelCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(8)
        title = QLabel("还没有项目")
        title.setProperty("role", "emptyTitle")
        body = QLabel("先创建一个长期学习主题，后续的学习会话和笔记都会围绕它沉淀。")
        body.setProperty("role", "emptyBody")
        body.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(body)
        layout.addStretch(1)
        return card

    def set_current_project(self, project: Project | None) -> None:
        self.active_project_id = project.id if project else None
        self.reload_projects(select_project_id=self.current_project_id)

    def reload_projects(self, select_project_id: int | None = None) -> None:
        projects = self.project_service.list_projects()
        self.project_list.clear()
        self.summary_label.setText(f"{len(projects)} 个项目")

        selected_row = -1
        for index, project in enumerate(projects):
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, project.id)
            item.setSizeHint(QSize(0, 128))
            self.project_list.addItem(item)
            self.project_list.setItemWidget(item, self._build_card_widget(project))
            if select_project_id is not None and project.id == select_project_id:
                selected_row = index

        has_projects = bool(projects)
        self.project_list.setVisible(has_projects)
        self.empty_card.setVisible(not has_projects)

        if selected_row >= 0:
            self.project_list.setCurrentRow(selected_row)
        elif has_projects:
            self.project_list.setCurrentRow(0)
        else:
            self.current_project_id = None
            self._clear_form()
            self.detail_meta_label.setText("未选择项目")
            self._set_message("暂无项目，请先创建。", is_error=False)

    def _build_card_widget(self, project: Project) -> QWidget:
        sessions = self.session_service.list_sessions_by_project(project.id)
        notes = self.note_service.note_repository.list_by_project(project.id, limit=200)
        session_count = len(sessions)
        note_count = len(notes)
        updated_text = format_cn_datetime(project.updated_at)

        card = QWidget()
        card.setObjectName("PanelCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(8)

        top_row = QHBoxLayout()
        top_row.setSpacing(10)
        title_label = QLabel(project.name)
        title_label.setProperty("role", "cardTitle")
        top_row.addWidget(title_label)
        top_row.addStretch(1)
        if self.active_project_id == project.id:
            badge = QLabel("当前项目")
            badge.setProperty("role", "badge")
            top_row.addWidget(badge)

        meta_label = QLabel(f"最近更新：{updated_text}")
        meta_label.setProperty("role", "cardMeta")

        stats_row = QHBoxLayout()
        stats_row.setSpacing(14)
        for text in [
            f"Session 数量：{session_count}",
            f"笔记数量：{note_count}",
        ]:
            label = QLabel(text)
            label.setProperty("role", "cardMeta")
            stats_row.addWidget(label)
        stats_row.addStretch(1)

        preview_text = project.description.strip() or project.goal.strip() or project.source.strip() or "还没有补充项目简介。"
        preview_label = QLabel(preview_text)
        preview_label.setProperty("role", "cardBody")
        preview_label.setWordWrap(True)

        layout.addLayout(top_row)
        layout.addWidget(meta_label)
        layout.addLayout(stats_row)
        layout.addWidget(preview_label)
        return card

    def _on_item_changed(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if current is None:
            self.current_project_id = None
            self._clear_form()
            self.detail_meta_label.setText("未选择项目")
            return

        project_id = current.data(Qt.ItemDataRole.UserRole)
        project = self.project_service.get_project(project_id)
        if project is None:
            self.current_project_id = None
            self._clear_form()
            self.detail_meta_label.setText("项目读取失败")
            self._set_message("项目读取失败。", is_error=True)
            return

        self.current_project_id = project.id
        self._fill_form(project)

    def _on_new(self) -> None:
        self.current_project_id = None
        self.project_list.clearSelection()
        self._clear_form()
        self.detail_meta_label.setText("新建项目")
        self._set_message("已切换到新建模式。", is_error=False)

    def _on_save(self) -> None:
        name = self.name_edit.text()
        description = self.description_edit.toPlainText()
        source = self.source_edit.text()
        goal = self.goal_edit.text()
        tags = self.tags_edit.text()

        try:
            if self.current_project_id is None:
                project = self.project_service.create_project(
                    name=name,
                    description=description,
                    source=source,
                    goal=goal,
                    tags=tags,
                )
                self.current_project_id = project.id
                self._set_message("项目创建成功。", is_error=False)
            else:
                project = self.project_service.update_project(
                    project_id=self.current_project_id,
                    name=name,
                    description=description,
                    source=source,
                    goal=goal,
                    tags=tags,
                )
                self._set_message("项目更新成功。", is_error=False)

            self.reload_projects(select_project_id=project.id)
        except ServiceError as exc:
            self._set_message(str(exc), is_error=True)

    def _on_delete(self) -> None:
        if self.current_project_id is None:
            self._set_message("请先选择要删除的项目。", is_error=True)
            return

        should_delete = QMessageBox.question(
            self,
            "确认删除",
            "确定删除该项目吗？该项目下的学习会话会一起删除。",
        )
        if should_delete != QMessageBox.StandardButton.Yes:
            return

        deleting_id = self.current_project_id
        try:
            self.project_service.delete_project(deleting_id)
            self.current_project_id = None
            if self.active_project_id == deleting_id:
                self.active_project_id = None
                self.project_selected.emit(None)
            self.reload_projects()
            self._set_message("项目删除成功。", is_error=False)
        except ServiceError as exc:
            self._set_message(str(exc), is_error=True)

    def _on_select(self) -> None:
        if self.current_project_id is None:
            self._set_message("请先选择项目。", is_error=True)
            return

        project = self.project_service.get_project(self.current_project_id)
        if project is None:
            self._set_message("项目不存在或已被删除。", is_error=True)
            return

        self.active_project_id = project.id
        self.project_selected.emit(project)
        self.reload_projects(select_project_id=project.id)
        self._set_message(f"当前项目已切换为：{project.name}", is_error=False)

    def _fill_form(self, project: Project) -> None:
        sessions = self.session_service.list_sessions_by_project(project.id)
        notes = self.note_service.note_repository.list_by_project(project.id, limit=200)
        self.detail_meta_label.setText(
            f"Session 数量：{len(sessions)}  ·  笔记数量：{len(notes)}  ·  最近更新：{format_cn_datetime(project.updated_at)}"
        )
        self.name_edit.setText(project.name)
        self.description_edit.setPlainText(project.description)
        self.source_edit.setText(project.source)
        self.goal_edit.setText(project.goal)
        self.tags_edit.setText(project.tags)

    def _clear_form(self) -> None:
        self.name_edit.clear()
        self.description_edit.clear()
        self.source_edit.clear()
        self.goal_edit.clear()
        self.tags_edit.clear()

    def _set_message(self, text: str, is_error: bool) -> None:
        color = "#d96b6b" if is_error else "#8f9aae"
        self.message_label.setStyleSheet(f"color: {color};")
        self.message_label.setText(text)
