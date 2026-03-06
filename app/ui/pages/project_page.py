from PySide6.QtCore import Qt, Signal
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
from app.services.project_service import ProjectService


class ProjectPage(QWidget):
    project_selected = Signal(object)

    def __init__(self, project_service: ProjectService, parent=None):
        super().__init__(parent)
        self.project_service = project_service
        self.current_project_id: int | None = None
        self.active_project_id: int | None = None

        self.project_list = QListWidget()
        self.project_list.currentItemChanged.connect(self._on_item_changed)

        self.name_edit = QLineEdit()
        self.description_edit = QTextEdit()
        self.source_edit = QLineEdit()
        self.goal_edit = QLineEdit()
        self.tags_edit = QLineEdit()

        self.message_label = QLabel("")
        self.message_label.setWordWrap(True)

        create_btn = QPushButton("新建")
        save_btn = QPushButton("保存")
        delete_btn = QPushButton("删除")
        select_btn = QPushButton("设为当前项目")
        reload_btn = QPushButton("刷新")

        create_btn.clicked.connect(self._on_new)
        save_btn.clicked.connect(self._on_save)
        delete_btn.clicked.connect(self._on_delete)
        select_btn.clicked.connect(self._on_select)
        reload_btn.clicked.connect(self.reload_projects)

        form = QFormLayout()
        form.addRow("名称*", self.name_edit)
        form.addRow("描述", self.description_edit)
        form.addRow("来源", self.source_edit)
        form.addRow("目标", self.goal_edit)
        form.addRow("标签", self.tags_edit)

        btn_row = QHBoxLayout()
        btn_row.addWidget(create_btn)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(delete_btn)
        btn_row.addWidget(select_btn)
        btn_row.addWidget(reload_btn)

        right = QVBoxLayout()
        right.addLayout(form)
        right.addLayout(btn_row)
        right.addWidget(self.message_label)
        right.addStretch(1)

        root = QHBoxLayout(self)
        root.addWidget(self.project_list, 2)
        root.addLayout(right, 3)

        self.reload_projects()

    def set_current_project(self, project: Project | None) -> None:
        self.active_project_id = project.id if project else None
        self.reload_projects(select_project_id=self.current_project_id)

    def reload_projects(self, select_project_id: int | None = None) -> None:
        projects = self.project_service.list_projects()
        self.project_list.clear()

        selected_row = -1
        for idx, project in enumerate(projects):
            title = project.name
            if self.active_project_id == project.id:
                title = f"{title} [当前]"

            item = QListWidgetItem(title)
            item.setData(Qt.ItemDataRole.UserRole, project.id)
            self.project_list.addItem(item)

            if select_project_id is not None and project.id == select_project_id:
                selected_row = idx

        if selected_row >= 0:
            self.project_list.setCurrentRow(selected_row)
        elif self.project_list.count() > 0:
            self.project_list.setCurrentRow(0)
        else:
            self.current_project_id = None
            self._clear_form()
            self._set_message("暂无项目，请先创建。", is_error=False)

    def _on_item_changed(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if current is None:
            self.current_project_id = None
            self._clear_form()
            return

        project_id = current.data(Qt.ItemDataRole.UserRole)
        project = self.project_service.get_project(project_id)
        if project is None:
            self.current_project_id = None
            self._clear_form()
            self._set_message("项目读取失败。", is_error=True)
            return

        self.current_project_id = project.id
        self._fill_form(project)

    def _on_new(self) -> None:
        self.current_project_id = None
        self.project_list.clearSelection()
        self._clear_form()
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
            "确定删除该项目吗？该项目下的 Session 会一起删除。",
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
        color = "#b00020" if is_error else "#2e7d32"
        self.message_label.setStyleSheet(f"color: {color};")
        self.message_label.setText(text)
