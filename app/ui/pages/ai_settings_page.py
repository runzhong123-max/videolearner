from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.services.ai_errors import AIConfigurationError
from app.services.ai_settings_service import (
    AISettingsService,
    ROUTE_RECORD_CHAT_PROVIDER,
    ROUTE_SESSION_NOTE_PROVIDER,
    SUPPORTED_AI_PROVIDERS,
)
from app.services.ocr_providers.provider_factory import OCR_PROVIDER_MOCK, SUPPORTED_OCR_PROVIDERS
from app.services.ocr_settings_service import OCRSettingsService


class AISettingsPage(QWidget):
    def __init__(
        self,
        ai_settings_service: AISettingsService,
        ocr_settings_service: OCRSettingsService | None = None,
        show_ai_group: bool = True,
        show_provider_group: bool = True,
        show_ocr_group: bool = True,
        parent=None,
    ):
        super().__init__(parent)
        self.ai_settings_service = ai_settings_service
        self.ocr_settings_service = ocr_settings_service
        self.show_ai_group = show_ai_group
        self.show_provider_group = show_provider_group
        self.show_ocr_group = show_ocr_group
        self._provider_cache: dict[str, dict] = {}

        self.default_provider_combo = QComboBox()
        self.route_session_note_combo = QComboBox()
        self.route_record_chat_combo = QComboBox()
        self.edit_provider_combo = QComboBox()

        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_url_edit = QLineEdit()
        self.model_edit = QLineEdit()
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(1, 600)
        self.timeout_spin.setValue(60)

        self.ocr_provider_combo = QComboBox()
        self.ocr_tesseract_path_edit = QLineEdit()
        self.ocr_lang_edit = QLineEdit()

        self.route_preview_label = QLabel("功能路由：-")
        self.route_preview_label.setWordWrap(True)
        self.route_preview_label.setProperty("role", "muted")
        self.message_label = QLabel("")
        self.message_label.setWordWrap(True)

        for provider in SUPPORTED_AI_PROVIDERS:
            self.default_provider_combo.addItem(provider, provider)
            self.edit_provider_combo.addItem(provider, provider)

        self.route_session_note_combo.addItem("跟随默认", "")
        self.route_record_chat_combo.addItem("跟随默认", "")
        for provider in SUPPORTED_AI_PROVIDERS:
            self.route_session_note_combo.addItem(provider, provider)
            self.route_record_chat_combo.addItem(provider, provider)

        for provider in SUPPORTED_OCR_PROVIDERS:
            self.ocr_provider_combo.addItem(provider, provider)

        self.edit_provider_combo.currentIndexChanged.connect(self._on_provider_changed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        if self.show_ai_group:
            layout.addWidget(self._build_global_group())
        if self.show_provider_group:
            layout.addWidget(self._build_provider_group())
        if self.show_ocr_group:
            if self.ocr_settings_service is not None:
                layout.addWidget(self._build_ocr_group())
            else:
                disabled = QLabel("OCR 设置服务未启用。")
                disabled.setProperty("role", "muted")
                layout.addWidget(disabled)
        if self.show_ai_group:
            layout.addWidget(self.route_preview_label)
        layout.addWidget(self.message_label)
        layout.addStretch(1)

        self._reload_settings()

    def _build_global_group(self) -> QGroupBox:
        group = QGroupBox("AI 设置")
        form = QFormLayout(group)
        form.addRow("默认服务", self.default_provider_combo)
        form.addRow("笔记路由", self.route_session_note_combo)
        form.addRow("记录问答路由", self.route_record_chat_combo)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("保存路由")
        save_btn.clicked.connect(self._on_save_routing)
        reload_btn = QPushButton("重新加载")
        reload_btn.clicked.connect(self._reload_settings)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(reload_btn)

        wrapper = QWidget()
        wrapper.setLayout(btn_row)
        form.addRow(wrapper)
        return group

    def _build_provider_group(self) -> QGroupBox:
        group = QGroupBox("服务配置")
        form = QFormLayout(group)
        form.addRow("编辑服务", self.edit_provider_combo)
        form.addRow("接口密钥", self.api_key_edit)
        form.addRow("接口地址", self.api_url_edit)
        form.addRow("模型名称", self.model_edit)
        form.addRow("超时（秒）", self.timeout_spin)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("保存当前服务")
        save_btn.clicked.connect(self._on_save_provider)
        test_btn = QPushButton("测试连接")
        test_btn.clicked.connect(self._on_test_provider)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(test_btn)

        wrapper = QWidget()
        wrapper.setLayout(btn_row)
        form.addRow(wrapper)
        return group

    def _build_ocr_group(self) -> QGroupBox:
        group = QGroupBox("OCR 设置")
        form = QFormLayout(group)
        self.ocr_tesseract_path_edit.setPlaceholderText(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
        self.ocr_lang_edit.setPlaceholderText("chi_sim+eng")

        form.addRow("OCR 服务", self.ocr_provider_combo)
        form.addRow("Tesseract 路径", self.ocr_tesseract_path_edit)
        form.addRow("识别语言", self.ocr_lang_edit)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("保存 OCR 设置")
        save_btn.clicked.connect(self._on_save_ocr_settings)
        test_btn = QPushButton("测试 OCR")
        test_btn.clicked.connect(self._on_test_ocr)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(test_btn)

        wrapper = QWidget()
        wrapper.setLayout(btn_row)
        form.addRow(wrapper)
        return group

    def _reload_settings(self) -> None:
        settings = self.ai_settings_service.load_settings()
        self._set_combo_by_value(self.default_provider_combo, settings.default_provider)
        self._set_combo_by_value(self.route_session_note_combo, settings.feature_routes.get(ROUTE_SESSION_NOTE_PROVIDER, ""))
        self._set_combo_by_value(self.route_record_chat_combo, settings.feature_routes.get(ROUTE_RECORD_CHAT_PROVIDER, ""))

        self._provider_cache.clear()
        for name, cfg in settings.provider_configs.items():
            self._provider_cache[name] = {
                "api_key": cfg.api_key,
                "api_url": cfg.api_url,
                "model": cfg.model,
                "timeout_seconds": cfg.timeout_seconds,
            }

        self._on_provider_changed()
        self._refresh_route_preview()
        self._reload_ocr_settings()
        self._set_message("设置已加载。", is_error=False)

    def _reload_ocr_settings(self) -> None:
        if self.ocr_settings_service is None:
            return
        settings = self.ocr_settings_service.load_settings()
        self._set_combo_by_value(self.ocr_provider_combo, settings.provider)
        self.ocr_tesseract_path_edit.setText(settings.tesseract_cmd)
        self.ocr_lang_edit.setText(settings.ocr_lang)

    def _on_provider_changed(self) -> None:
        provider = self.edit_provider_combo.currentData()
        if provider is None:
            return
        current = self._provider_cache.get(provider, {})
        self.api_key_edit.setText(current.get("api_key", ""))
        self.api_url_edit.setText(current.get("api_url", ""))
        self.model_edit.setText(current.get("model", ""))
        self.timeout_spin.setValue(int(current.get("timeout_seconds", 60) or 60))

    def _on_save_provider(self) -> None:
        provider = self.edit_provider_combo.currentData()
        if provider is None:
            self._set_message("未选择服务。", is_error=True)
            return
        try:
            self.ai_settings_service.save_provider_config(
                provider=provider,
                api_key=self.api_key_edit.text(),
                api_url=self.api_url_edit.text(),
                model=self.model_edit.text(),
                timeout_seconds=self.timeout_spin.value(),
            )
            self._provider_cache[provider] = {
                "api_key": self.api_key_edit.text().strip(),
                "api_url": self.api_url_edit.text().strip(),
                "model": self.model_edit.text().strip(),
                "timeout_seconds": self.timeout_spin.value(),
            }
            self._set_message(f"{provider} 配置已保存。", is_error=False)
        except Exception as exc:
            self._set_message(str(exc), is_error=True)

    def _on_save_routing(self) -> None:
        try:
            default_provider = self.default_provider_combo.currentData()
            self.ai_settings_service.save_default_provider(default_provider)
            self.ai_settings_service.save_feature_route(ROUTE_SESSION_NOTE_PROVIDER, self.route_session_note_combo.currentData() or "")
            self.ai_settings_service.save_feature_route(ROUTE_RECORD_CHAT_PROVIDER, self.route_record_chat_combo.currentData() or "")
            self._refresh_route_preview()
            self._set_message("默认服务与功能路由已保存。", is_error=False)
        except Exception as exc:
            self._set_message(str(exc), is_error=True)

    def _on_save_ocr_settings(self) -> None:
        if self.ocr_settings_service is None:
            self._set_message("OCR 设置服务未启用。", is_error=True)
            return
        try:
            state = self.ocr_settings_service.save_settings(
                provider=self.ocr_provider_combo.currentData() or OCR_PROVIDER_MOCK,
                tesseract_cmd=self.ocr_tesseract_path_edit.text(),
                ocr_lang=self.ocr_lang_edit.text(),
            )
            if state.provider == OCR_PROVIDER_MOCK:
                self._set_message("OCR 设置已保存（当前为 mock_ocr 模拟模式）。", is_error=False)
            else:
                self._set_message("OCR 设置已保存。", is_error=False)
        except Exception as exc:
            self._set_message(f"保存 OCR 设置失败：{exc}", is_error=True)

    def _on_test_provider(self) -> None:
        provider = self.edit_provider_combo.currentData()
        if provider is None:
            self._set_message("未选择服务。", is_error=True)
            return
        try:
            self.ai_settings_service.save_provider_config(
                provider=provider,
                api_key=self.api_key_edit.text(),
                api_url=self.api_url_edit.text(),
                model=self.model_edit.text(),
                timeout_seconds=self.timeout_spin.value(),
            )
            result = self.ai_settings_service.test_provider_connection(provider)
            if result.success:
                model = result.model or "-"
                self._set_message(f"测试成功：provider={result.provider}，model={model}。{result.message}", is_error=False)
            else:
                self._set_message(f"测试失败：provider={result.provider}。{result.message}", is_error=True)
        except AIConfigurationError as exc:
            self._set_message(f"配置错误：{exc}", is_error=True)
        except Exception as exc:
            self._set_message(f"测试异常：{exc}", is_error=True)

    def _on_test_ocr(self) -> None:
        if self.ocr_settings_service is None:
            self._set_message("OCR 设置服务未启用。", is_error=True)
            return
        try:
            self.ocr_settings_service.save_settings(
                provider=self.ocr_provider_combo.currentData() or OCR_PROVIDER_MOCK,
                tesseract_cmd=self.ocr_tesseract_path_edit.text(),
                ocr_lang=self.ocr_lang_edit.text(),
            )
            result = self.ocr_settings_service.test_provider_connection()
            if result.success:
                info = result.text.strip() or "OCR 测试成功。"
                self._set_message(f"OCR 测试成功：provider={result.provider}。{info}", is_error=False)
            else:
                self._set_message(f"OCR 测试失败：provider={result.provider}。{result.error or '未知错误'}", is_error=True)
        except Exception as exc:
            self._set_message(f"OCR 测试异常：{exc}", is_error=True)

    def _refresh_route_preview(self) -> None:
        note_provider = self.ai_settings_service.resolve_provider_name(ROUTE_SESSION_NOTE_PROVIDER)
        chat_provider = self.ai_settings_service.resolve_provider_name(ROUTE_RECORD_CHAT_PROVIDER)
        self.route_preview_label.setText(
            "当前生效路由："
            f"笔记生成 -> {note_provider}；"
            f"记录问答 -> {chat_provider}"
        )

    def _set_message(self, text: str, is_error: bool) -> None:
        color = "#d96b6b" if is_error else "#7db48a"
        self.message_label.setStyleSheet(f"color: {color};")
        self.message_label.setText(text)

    @staticmethod
    def _set_combo_by_value(combo: QComboBox, value: str) -> None:
        target = value or ""
        for idx in range(combo.count()):
            if (combo.itemData(idx) or "") == target:
                combo.setCurrentIndex(idx)
                return
        combo.setCurrentIndex(0)
