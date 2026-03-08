from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.services.ai_settings_service import AISettingsService
from app.services.ocr_settings_service import OCRSettingsService
from app.services.shortcut_manager import ShortcutManager
from app.services.shortcut_settings_service import ACTION_CAPTURE_IMAGE_RECORD, ShortcutSettingsService
from app.ui.pages.ai_settings_page import AISettingsPage
from app.ui.pages.shortcut_settings_page import ShortcutSettingsPage


class SettingsPage(QWidget):
    def __init__(
        self,
        ai_settings_service: AISettingsService | None = None,
        ocr_settings_service: OCRSettingsService | None = None,
        shortcut_settings_service: ShortcutSettingsService | None = None,
        shortcut_manager: ShortcutManager | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.ai_settings_service = ai_settings_service
        self.ocr_settings_service = ocr_settings_service
        self.shortcut_settings_service = shortcut_settings_service
        self.shortcut_manager = shortcut_manager

        self.title_label = QLabel("设置")
        self.title_label.setProperty("role", "pageTitle")
        self.subtitle_label = QLabel("统一整理当前阶段的应用配置，保持分组清晰、文案一致。")
        self.subtitle_label.setProperty("role", "pageSubtitle")

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(28, 24, 28, 24)
        content_layout.setSpacing(22)
        content_layout.addWidget(self.title_label)
        content_layout.addWidget(self.subtitle_label)
        content_layout.addWidget(self._build_general_section())
        content_layout.addWidget(self._build_ai_section())
        content_layout.addWidget(self._build_ocr_section())
        content_layout.addWidget(self._build_capture_section())
        content_layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll)

    def _build_general_section(self) -> QWidget:
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(self._build_section_header("通用", "保持设置页为单一入口，优先保证信息层级清晰。"))

        language_combo = QComboBox()
        language_combo.addItems(["简体中文", "English", "繁體中文"])
        language_combo.setCurrentIndex(0)
        language_combo.setEnabled(False)
        layout.addWidget(self._build_setting_row("语言", "选择界面语言。", language_combo))
        layout.addWidget(self._build_setting_row("产品定位", "当前产品定位为学习记录工具，不是视频播放器。", QLabel("学习记录工具")))
        layout.addWidget(self._build_setting_row("当前阶段", "当前仍停留在 P1，只收口桌面端 UI 壳与页面结构。", QLabel("P1 UI 收口")))
        return section

    def _build_ai_section(self) -> QWidget:
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(self._build_section_header("AI 设置", "统一管理默认服务、功能路由与 AI 服务配置。"))

        if self.ai_settings_service is not None:
            settings = self.ai_settings_service.load_settings()
            route_text = (
                f"笔记生成：{self.ai_settings_service.resolve_provider_name('session_note_provider')}  ·  "
                f"记录问答：{self.ai_settings_service.resolve_provider_name('record_chat_provider')}"
            )
            provider_text = settings.default_provider or "未配置"
            layout.addWidget(self._build_setting_row("默认服务", "当前用于 AI 功能的默认服务。", QLabel(provider_text)))
            layout.addWidget(self._build_setting_row("功能路由", "当前生效的 AI 路由。", QLabel(route_text)))
            layout.addWidget(self._wrap_detail_card(
                AISettingsPage(
                    ai_settings_service=self.ai_settings_service,
                    ocr_settings_service=self.ocr_settings_service,
                    show_ai_group=True,
                    show_provider_group=True,
                    show_ocr_group=False,
                )
            ))
        else:
            layout.addWidget(self._build_setting_row("AI 设置", "AI 设置服务未启用。", QLabel("不可用")))
        return section

    def _build_ocr_section(self) -> QWidget:
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(self._build_section_header("OCR 设置", "控制截图识别能力与识别语言。"))

        if self.ocr_settings_service is not None and self.ai_settings_service is not None:
            settings = self.ocr_settings_service.load_settings()
            layout.addWidget(self._build_setting_row("OCR 服务", "当前用于图片文字识别的服务。", QLabel(settings.provider or "未配置")))
            layout.addWidget(self._build_setting_row("识别语言", "文本提取的主要语言。", QLabel(settings.ocr_lang or "未设置")))
            layout.addWidget(self._wrap_detail_card(
                AISettingsPage(
                    ai_settings_service=self.ai_settings_service,
                    ocr_settings_service=self.ocr_settings_service,
                    show_ai_group=False,
                    show_provider_group=False,
                    show_ocr_group=True,
                )
            ))
        else:
            layout.addWidget(self._build_setting_row("OCR 设置", "OCR 设置服务未启用。", QLabel("不可用")))
        return section

    def _build_capture_section(self) -> QWidget:
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(self._build_section_header("截图设置", "保留当前快捷键文本编辑，不提前进入快捷键录制态。"))

        format_combo = QComboBox()
        format_combo.addItems(["PNG（当前）", "JPG（临时占位）"])
        format_combo.setCurrentIndex(0)
        format_combo.setEnabled(False)
        layout.addWidget(self._build_setting_row("截图格式", "当前阶段只保留界面占位，下一阶段再接入真实配置。", format_combo))

        shortcut_value = "未启用"
        if self.shortcut_settings_service is not None:
            bindings = self.shortcut_settings_service.load_bindings()
            shortcut_value = bindings.get(ACTION_CAPTURE_IMAGE_RECORD, "未配置") or "未配置"
        layout.addWidget(self._build_setting_row("截图快捷键", "当前保留文本编辑交互与恢复默认能力。", QLabel(shortcut_value)))

        if self.shortcut_settings_service is not None and self.shortcut_manager is not None:
            layout.addWidget(self._wrap_detail_card(
                ShortcutSettingsPage(
                    shortcut_settings_service=self.shortcut_settings_service,
                    shortcut_manager=self.shortcut_manager,
                )
            ))
        else:
            layout.addWidget(self._build_setting_row("快捷键配置", "快捷键服务未启用，当前无法编辑截图快捷键。", QLabel("不可用")))
        return section

    def _build_section_header(self, title: str, hint: str) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        title_label = QLabel(title)
        title_label.setProperty("role", "sectionTitle")
        hint_label = QLabel(hint)
        hint_label.setProperty("role", "sectionHint")
        hint_label.setWordWrap(True)
        layout.addWidget(title_label)
        layout.addWidget(hint_label)
        return wrapper

    def _build_setting_row(self, title: str, description: str, control: QWidget) -> QWidget:
        row = QWidget()
        row.setObjectName("SettingRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(4)
        title_label = QLabel(title)
        title_label.setProperty("role", "cardTitle")
        desc_label = QLabel(description)
        desc_label.setProperty("role", "sectionHint")
        desc_label.setWordWrap(True)
        text_col.addWidget(title_label)
        text_col.addWidget(desc_label)

        layout.addLayout(text_col, 1)
        layout.addWidget(control)
        return row

    def _wrap_detail_card(self, child: QWidget) -> QWidget:
        card = QWidget()
        card.setObjectName("PanelCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        layout.addWidget(child)
        return card
