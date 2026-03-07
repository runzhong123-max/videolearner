from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.models.project import Project
from app.services.errors import ServiceError
from app.services.output_profile_service import OUTPUT_FIELDS, OutputProfileService
from app.services.prompt_service import SCOPE_GLOBAL, SCOPE_PROJECT, SCOPE_SESSION, PromptService
from app.services.session_service import SessionService


class PromptPage(QWidget):
    def __init__(
        self,
        prompt_service: PromptService,
        output_profile_service: OutputProfileService,
        session_service: SessionService,
        parent=None,
    ):
        super().__init__(parent)
        self.prompt_service = prompt_service
        self.output_profile_service = output_profile_service
        self.session_service = session_service
        self.current_project: Project | None = None

        self.context_label = QLabel("当前上下文：global")

        self.tabs = QTabWidget()

        self.global_name = QLineEdit()
        self.global_system = QTextEdit()
        self.global_user = QTextEdit()

        self.project_name = QLineEdit()
        self.project_system = QTextEdit()
        self.project_user = QTextEdit()

        self.session_selector = QComboBox()
        self.session_selector.currentIndexChanged.connect(self._on_session_changed)
        self.session_name = QLineEdit()
        self.session_system = QTextEdit()
        self.session_user = QTextEdit()

        self.output_scope_selector = QComboBox()
        self.output_scope_selector.addItem("Global", SCOPE_GLOBAL)
        self.output_scope_selector.addItem("Project", SCOPE_PROJECT)
        self.output_scope_selector.addItem("Session", SCOPE_SESSION)
        self.output_scope_selector.currentIndexChanged.connect(self._load_output_profile)

        self.output_name = QLineEdit()
        self.output_checks = {field: QComboBox() for field in OUTPUT_FIELDS}
        for combo in self.output_checks.values():
            combo.addItem("关闭", False)
            combo.addItem("开启", True)

        self.output_checks["summary"].setCurrentIndex(1)
        self.output_checks["summary"].setEnabled(False)
        self.output_checks["extension"].setCurrentIndex(1)
        self.output_checks["extension"].setEnabled(False)

        self.message_label = QLabel("")
        self.message_label.setWordWrap(True)

        self.tabs.addTab(self._build_prompt_tab(SCOPE_GLOBAL), "Global Prompt")
        self.tabs.addTab(self._build_prompt_tab(SCOPE_PROJECT), "Project Prompt")
        self.tabs.addTab(self._build_prompt_tab(SCOPE_SESSION), "Session Prompt")
        self.tabs.addTab(self._build_output_tab(), "Output Profile")

        layout = QVBoxLayout(self)
        layout.addWidget(self.context_label)
        layout.addWidget(self.tabs)
        layout.addWidget(self.message_label)

        self._refresh_context()

    def set_current_project(self, project: Project | None) -> None:
        self.current_project = project
        self._refresh_context()

    def _build_prompt_tab(self, scope: str) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)

        form = QFormLayout()
        if scope == SCOPE_GLOBAL:
            form.addRow("名称", self.global_name)
            form.addRow("System Prompt", self.global_system)
            form.addRow("User Prompt", self.global_user)
        elif scope == SCOPE_PROJECT:
            form.addRow("名称", self.project_name)
            form.addRow("System Prompt", self.project_system)
            form.addRow("User Prompt", self.project_user)
        else:
            form.addRow("Session", self.session_selector)
            form.addRow("名称", self.session_name)
            form.addRow("System Prompt", self.session_system)
            form.addRow("User Prompt", self.session_user)

        btn_row = QHBoxLayout()
        load_btn = QPushButton("加载")
        save_btn = QPushButton("保存")
        reset_btn = QPushButton("Reset to VL Default Prompt")

        load_btn.clicked.connect(lambda: self._load_prompt(scope))
        save_btn.clicked.connect(lambda: self._save_prompt(scope))
        reset_btn.clicked.connect(lambda: self._reset_prompt(scope))

        btn_row.addWidget(load_btn)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(reset_btn)

        layout.addLayout(form)
        layout.addLayout(btn_row)
        layout.addStretch(1)
        return container

    def _build_output_tab(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)

        top_form = QFormLayout()
        top_form.addRow("配置作用域", self.output_scope_selector)
        top_form.addRow("配置名称", self.output_name)

        options_box = QGroupBox("输出项配置")
        options_layout = QGridLayout(options_box)
        options_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        labels = {
            "summary": "summary（必选）",
            "extension": "extension（必选）",
            "insight": "insight（灵感时必选）",
            "history_link": "history_link",
            "gap_analysis": "gap_analysis",
            "review_questions": "review_questions",
            "homework": "homework",
            "expression_notes": "expression_notes",
            "evaluation": "evaluation",
        }

        for row, field in enumerate(OUTPUT_FIELDS):
            options_layout.addWidget(QLabel(labels[field]), row, 0)
            options_layout.addWidget(self.output_checks[field], row, 1)

        btn_row = QHBoxLayout()
        load_btn = QPushButton("加载配置")
        save_btn = QPushButton("保存配置模板")
        load_btn.clicked.connect(self._load_output_profile)
        save_btn.clicked.connect(self._save_output_profile)
        btn_row.addWidget(load_btn)
        btn_row.addWidget(save_btn)

        layout.addLayout(top_form)
        layout.addWidget(options_box)
        layout.addLayout(btn_row)
        layout.addWidget(QLabel("规则：summary/extension 强制开启；若 Session 有灵感记录，insight 强制开启。"))
        layout.addStretch(1)
        return container

    def _refresh_context(self) -> None:
        if self.current_project is None:
            self.context_label.setText("当前上下文：global（未选择项目）")
        else:
            self.context_label.setText(
                f"当前上下文：project={self.current_project.name} (ID={self.current_project.id})"
            )

        self._refresh_session_selector()
        self._load_prompt(SCOPE_GLOBAL)
        self._load_prompt(SCOPE_PROJECT)
        self._load_prompt(SCOPE_SESSION)
        self._load_output_profile()

    def _refresh_session_selector(self) -> None:
        self.session_selector.blockSignals(True)
        self.session_selector.clear()
        self.session_selector.addItem("未选择", None)

        if self.current_project is not None:
            sessions = self.session_service.list_sessions_by_project(self.current_project.id)
            for session in sessions:
                label = f"#{session.id} | {session.status}"
                self.session_selector.addItem(label, session.id)

            in_progress = self.session_service.get_in_progress_session()
            if in_progress is not None and in_progress.project_id == self.current_project.id:
                for idx in range(self.session_selector.count()):
                    if self.session_selector.itemData(idx) == in_progress.id:
                        self.session_selector.setCurrentIndex(idx)
                        break

        self.session_selector.blockSignals(False)

    def _selected_session_id(self) -> int | None:
        return self.session_selector.currentData()

    def _load_prompt(self, scope: str) -> None:
        try:
            project_id = self.current_project.id if self.current_project else None
            session_id = self._selected_session_id()

            if scope == SCOPE_GLOBAL:
                template = self.prompt_service.get_template_or_default(scope=SCOPE_GLOBAL)
                self.global_name.setText(template.name)
                self.global_system.setPlainText(template.system_prompt)
                self.global_user.setPlainText(template.user_prompt)
                return

            if scope == SCOPE_PROJECT:
                if project_id is None:
                    self.project_name.setText("")
                    self.project_system.setPlainText("")
                    self.project_user.setPlainText("")
                    return
                template = self.prompt_service.get_template_or_default(
                    scope=SCOPE_PROJECT,
                    project_id=project_id,
                )
                self.project_name.setText(template.name)
                self.project_system.setPlainText(template.system_prompt)
                self.project_user.setPlainText(template.user_prompt)
                return

            if session_id is None:
                self.session_name.setText("")
                self.session_system.setPlainText("")
                self.session_user.setPlainText("")
                return
            template = self.prompt_service.get_template_or_default(
                scope=SCOPE_SESSION,
                session_id=session_id,
            )
            self.session_name.setText(template.name)
            self.session_system.setPlainText(template.system_prompt)
            self.session_user.setPlainText(template.user_prompt)
        except ServiceError as exc:
            self._set_message(str(exc), True)

    def _save_prompt(self, scope: str) -> None:
        try:
            project_id = self.current_project.id if self.current_project else None
            session_id = self._selected_session_id()

            if scope == SCOPE_GLOBAL:
                self.prompt_service.save_template(
                    scope=SCOPE_GLOBAL,
                    name=self.global_name.text(),
                    system_prompt=self.global_system.toPlainText(),
                    user_prompt=self.global_user.toPlainText(),
                )
            elif scope == SCOPE_PROJECT:
                if project_id is None:
                    raise ServiceError("未选择项目，无法保存 Project Prompt。")
                self.prompt_service.save_template(
                    scope=SCOPE_PROJECT,
                    project_id=project_id,
                    name=self.project_name.text(),
                    system_prompt=self.project_system.toPlainText(),
                    user_prompt=self.project_user.toPlainText(),
                )
            else:
                if session_id is None:
                    raise ServiceError("未选择 Session，无法保存 Session Prompt。")
                self.prompt_service.save_template(
                    scope=SCOPE_SESSION,
                    session_id=session_id,
                    name=self.session_name.text(),
                    system_prompt=self.session_system.toPlainText(),
                    user_prompt=self.session_user.toPlainText(),
                )

            self._set_message(f"{scope} Prompt 保存成功。", False)
            self._load_prompt(scope)
        except ServiceError as exc:
            self._set_message(str(exc), True)

    def _reset_prompt(self, scope: str) -> None:
        try:
            project_id = self.current_project.id if self.current_project else None
            session_id = self._selected_session_id()

            if scope == SCOPE_GLOBAL:
                self.prompt_service.restore_default(scope=SCOPE_GLOBAL)
            elif scope == SCOPE_PROJECT:
                if project_id is None:
                    raise ServiceError("未选择项目，无法恢复 Project Prompt 默认值。")
                self.prompt_service.restore_default(scope=SCOPE_PROJECT, project_id=project_id)
            else:
                if session_id is None:
                    raise ServiceError("未选择 Session，无法恢复 Session Prompt 默认值。")
                self.prompt_service.restore_default(scope=SCOPE_SESSION, session_id=session_id)

            self._set_message(f"{scope} Prompt 已恢复默认。", False)
            self._load_prompt(scope)
        except ServiceError as exc:
            self._set_message(str(exc), True)

    def _on_session_changed(self) -> None:
        self._load_prompt(SCOPE_SESSION)
        self._load_output_profile()

    def _load_output_profile(self) -> None:
        try:
            scope = self.output_scope_selector.currentData()
            project_id = self.current_project.id if self.current_project else None
            session_id = self._selected_session_id()

            if scope == SCOPE_GLOBAL:
                profile = self.output_profile_service.get_profile_or_default(scope=SCOPE_GLOBAL)
            elif scope == SCOPE_PROJECT:
                if project_id is None:
                    self.output_name.setText("")
                    self._set_output_selections({field: False for field in OUTPUT_FIELDS})
                    return
                profile = self.output_profile_service.get_profile_or_default(
                    scope=SCOPE_PROJECT,
                    project_id=project_id,
                )
            else:
                if session_id is None:
                    self.output_name.setText("")
                    self._set_output_selections({field: False for field in OUTPUT_FIELDS})
                    return
                profile = self.output_profile_service.get_profile_or_default(
                    scope=SCOPE_SESSION,
                    session_id=session_id,
                )

            self.output_name.setText(profile.name)
            base_selections = {
                "summary": profile.summary,
                "extension": profile.extension,
                "insight": profile.insight,
                "history_link": profile.history_link,
                "gap_analysis": profile.gap_analysis,
                "review_questions": profile.review_questions,
                "homework": profile.homework,
                "expression_notes": profile.expression_notes,
                "evaluation": profile.evaluation,
            }
            enforced = self.output_profile_service.apply_output_rules(base_selections, session_id=session_id)
            self._set_output_selections(enforced)
        except ServiceError as exc:
            self._set_message(str(exc), True)

    def _save_output_profile(self) -> None:
        try:
            scope = self.output_scope_selector.currentData()
            project_id = self.current_project.id if self.current_project else None
            session_id = self._selected_session_id()

            selections = {field: bool(self.output_checks[field].currentData()) for field in OUTPUT_FIELDS}

            if scope == SCOPE_GLOBAL:
                saved = self.output_profile_service.save_profile(
                    name=self.output_name.text() or "Global Output",
                    scope=SCOPE_GLOBAL,
                    selections=selections,
                    context_session_id=session_id,
                )
            elif scope == SCOPE_PROJECT:
                if project_id is None:
                    raise ServiceError("未选择项目，无法保存 Project 输出配置。")
                saved = self.output_profile_service.save_profile(
                    name=self.output_name.text() or "Project Output",
                    scope=SCOPE_PROJECT,
                    project_id=project_id,
                    selections=selections,
                    context_session_id=session_id,
                )
            else:
                if session_id is None:
                    raise ServiceError("未选择 Session，无法保存 Session 输出配置。")
                saved = self.output_profile_service.save_profile(
                    name=self.output_name.text() or "Session Output",
                    scope=SCOPE_SESSION,
                    session_id=session_id,
                    selections=selections,
                    context_session_id=session_id,
                )

            self.output_name.setText(saved.name)
            base_selections = {
                "summary": saved.summary,
                "extension": saved.extension,
                "insight": saved.insight,
                "history_link": saved.history_link,
                "gap_analysis": saved.gap_analysis,
                "review_questions": saved.review_questions,
                "homework": saved.homework,
                "expression_notes": saved.expression_notes,
                "evaluation": saved.evaluation,
            }
            enforced = self.output_profile_service.apply_output_rules(base_selections, session_id=session_id)
            self._set_output_selections(enforced)
            self._set_message("输出配置已保存（已应用强制规则）。", False)
        except ServiceError as exc:
            self._set_message(str(exc), True)

    def _set_output_selections(self, selections: dict[str, bool]) -> None:
        for field, combo in self.output_checks.items():
            enabled = bool(selections.get(field, False))
            combo.setCurrentIndex(1 if enabled else 0)

        self.output_checks["summary"].setCurrentIndex(1)
        self.output_checks["summary"].setEnabled(False)
        self.output_checks["extension"].setCurrentIndex(1)
        self.output_checks["extension"].setEnabled(False)

    def _set_message(self, text: str, is_error: bool) -> None:
        color = "#b00020" if is_error else "#2e7d32"
        self.message_label.setStyleSheet(f"color: {color};")
        self.message_label.setText(text)
