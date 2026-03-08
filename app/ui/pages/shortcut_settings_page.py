from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.services.errors import ServiceError
from app.services.shortcut_manager import ShortcutManager
from app.services.shortcut_settings_service import (
    ACTION_CAPTURE_IMAGE_RECORD,
    ACTION_CAPTURE_TEXT_RECORD,
    ACTION_FINISH_SESSION,
    ACTION_PAUSE_SESSION,
    ACTION_RESUME_SESSION,
    ACTION_START_SESSION,
    SHORTCUT_ACTIONS,
    ShortcutSettingsService,
)

ACTION_LABELS = {
    ACTION_START_SESSION: "开始学习",
    ACTION_PAUSE_SESSION: "暂停学习",
    ACTION_RESUME_SESSION: "继续学习",
    ACTION_FINISH_SESSION: "结束学习",
    ACTION_CAPTURE_IMAGE_RECORD: "记录截图",
    ACTION_CAPTURE_TEXT_RECORD: "记录灵感",
}

SHORTCUT_KEY_REFERENCE: list[tuple[str, str]] = [
    ("ctrl / control", "控制键，例如 ctrl+alt+s"),
    ("alt", "Alt 键"),
    ("shift", "Shift 键"),
    ("tab", "Tab 键（全局场景冲突较高）"),
    ("enter", "回车键"),
    ("space", "空格键"),
    ("esc / escape", "Esc 键"),
    ("up / down / left / right", "方向键"),
    ("f1 ~ f12", "功能键"),
    ("a ~ z / 0 ~ 9", "字母键或数字键"),
]


class ShortcutSettingsPage(QWidget):
    shortcuts_saved = Signal(dict)

    def __init__(
        self,
        shortcut_settings_service: ShortcutSettingsService,
        shortcut_manager: ShortcutManager,
        parent=None,
    ):
        super().__init__(parent)
        self.shortcut_settings_service = shortcut_settings_service
        self.shortcut_manager = shortcut_manager
        self.editors: dict[str, QLineEdit] = {}

        intro_label = QLabel("当前阶段只保留快捷键文本编辑，不提前进入快捷键录制态。")
        intro_label.setWordWrap(True)
        intro_label.setProperty("role", "sectionHint")

        self.message_label = QLabel("")
        self.message_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.addWidget(intro_label)
        layout.addWidget(self._build_editor_group())
        layout.addWidget(self._build_help_group())
        layout.addWidget(self.message_label)
        layout.addStretch(1)

        self._load_bindings_to_ui(self.shortcut_settings_service.load_bindings())

    def _build_editor_group(self) -> QGroupBox:
        group = QGroupBox("快捷键配置")
        form = QFormLayout(group)

        for action in SHORTCUT_ACTIONS:
            editor = QLineEdit()
            editor.setPlaceholderText("例如 ctrl+alt+s")
            editor.setClearButtonEnabled(True)
            self.editors[action] = editor
            form.addRow(ACTION_LABELS[action], editor)

        row = QHBoxLayout()
        save_btn = QPushButton("保存并生效")
        save_btn.clicked.connect(self._on_save)
        load_btn = QPushButton("重新加载")
        load_btn.clicked.connect(self._on_reload)
        reset_btn = QPushButton("恢复默认")
        reset_btn.clicked.connect(self._on_restore_default)

        row.addWidget(save_btn)
        row.addWidget(load_btn)
        row.addWidget(reset_btn)

        row_wrap = QWidget()
        row_wrap.setLayout(row)
        form.addRow(row_wrap)
        return group

    def _build_help_group(self) -> QGroupBox:
        group = QGroupBox("键位参考")
        layout = QGridLayout(group)

        for index, text in enumerate([
            "1. 快捷键格式示例：ctrl+alt+s、ctrl+shift+a。",
            "2. 保存后会立即重新注册快捷键。",
            "3. 为避免冲突，默认未使用 Tab 作为全局截图热键。",
            "4. 若系统占用导致注册失败，会在消息区提示。",
        ]):
            label = QLabel(text)
            label.setProperty("role", "muted")
            layout.addWidget(label, index, 0)

        key_table = QTableWidget(len(SHORTCUT_KEY_REFERENCE), 2)
        key_table.setHorizontalHeaderLabels(["键位名称", "说明"])
        key_table.verticalHeader().setVisible(False)
        key_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        key_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        key_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        key_table.setAlternatingRowColors(True)

        for row, (key_name, desc) in enumerate(SHORTCUT_KEY_REFERENCE):
            key_table.setItem(row, 0, QTableWidgetItem(key_name))
            key_table.setItem(row, 1, QTableWidgetItem(desc))

        key_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        key_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        key_table.setMinimumHeight(240)
        layout.addWidget(key_table, 4, 0)

        return group

    def _on_save(self) -> None:
        try:
            bindings = self._collect_bindings_from_ui()
            result = self.shortcut_manager.save_and_apply(bindings)
            self.shortcuts_saved.emit(dict(self.shortcut_manager.current_bindings))

            if result.failed_actions:
                failed = ", ".join(result.failed_actions)
                self._set_message(f"已保存，但部分快捷键注册失败：{failed}", is_error=True)
            else:
                self._set_message("快捷键已保存并生效。", is_error=False)
        except ServiceError as exc:
            self._set_message(str(exc), is_error=True)

    def _on_reload(self) -> None:
        bindings = self.shortcut_settings_service.load_bindings()
        self._load_bindings_to_ui(bindings)
        self._set_message("已从本地配置重新加载。", is_error=False)

    def _on_restore_default(self) -> None:
        try:
            defaults = self.shortcut_settings_service.restore_defaults()
            self._load_bindings_to_ui(defaults)
            result = self.shortcut_manager.apply_bindings(defaults)
            self.shortcuts_saved.emit(dict(self.shortcut_manager.current_bindings))
            if result.failed_actions:
                failed = ", ".join(result.failed_actions)
                self._set_message(f"默认值已恢复，但注册失败：{failed}", is_error=True)
            else:
                self._set_message("已恢复默认快捷键并生效。", is_error=False)
        except ServiceError as exc:
            self._set_message(str(exc), is_error=True)

    def _collect_bindings_from_ui(self) -> dict[str, str]:
        return {action: self.editors[action].text().strip() for action in SHORTCUT_ACTIONS}

    def _load_bindings_to_ui(self, bindings: dict[str, str]) -> None:
        for action in SHORTCUT_ACTIONS:
            self.editors[action].setText(bindings.get(action, ""))

    def _set_message(self, text: str, is_error: bool) -> None:
        color = "#d96b6b" if is_error else "#7db48a"
        self.message_label.setStyleSheet(f"color: {color};")
        self.message_label.setText(text)
