import tempfile
from dataclasses import dataclass
from pathlib import Path

from app.repositories.app_setting_repository import AppSettingRepository
from app.services.errors import ServiceError
from app.services.ocr_providers.local_ocr_provider import DEFAULT_OCR_LANG
from app.services.ocr_providers.ocr_result import OCRResult
from app.services.ocr_providers.provider_factory import (
    OCR_PROVIDER_LOCAL,
    OCR_PROVIDER_MOCK,
    SUPPORTED_OCR_PROVIDERS,
    OCRProviderFactory,
)

OCR_PROVIDER_SETTING_KEY = "ocr.provider"
OCR_TESSERACT_CMD_SETTING_KEY = "ocr.tesseract_cmd"
OCR_LANG_SETTING_KEY = "ocr.lang"


@dataclass
class OCRSettingsState:
    provider: str
    tesseract_cmd: str
    ocr_lang: str


class OCRSettingsService:
    def __init__(self, app_setting_repository: AppSettingRepository):
        self.app_setting_repository = app_setting_repository

    def load_settings(self) -> OCRSettingsState:
        provider = (self.app_setting_repository.get(OCR_PROVIDER_SETTING_KEY) or OCR_PROVIDER_MOCK).strip().lower()
        if provider not in SUPPORTED_OCR_PROVIDERS:
            provider = OCR_PROVIDER_MOCK

        tesseract_cmd = (self.app_setting_repository.get(OCR_TESSERACT_CMD_SETTING_KEY) or "").strip()
        ocr_lang = (self.app_setting_repository.get(OCR_LANG_SETTING_KEY) or DEFAULT_OCR_LANG).strip() or DEFAULT_OCR_LANG

        return OCRSettingsState(
            provider=provider,
            tesseract_cmd=tesseract_cmd,
            ocr_lang=ocr_lang,
        )

    def save_settings(self, provider: str, tesseract_cmd: str, ocr_lang: str) -> OCRSettingsState:
        normalized_provider = (provider or "").strip().lower()
        if normalized_provider not in SUPPORTED_OCR_PROVIDERS:
            raise ServiceError(f"不支持的 OCR provider：{provider}")

        normalized_cmd = (tesseract_cmd or "").strip()
        normalized_lang = (ocr_lang or DEFAULT_OCR_LANG).strip() or DEFAULT_OCR_LANG

        self.app_setting_repository.set(OCR_PROVIDER_SETTING_KEY, normalized_provider)
        self.app_setting_repository.set(OCR_TESSERACT_CMD_SETTING_KEY, normalized_cmd)
        self.app_setting_repository.set(OCR_LANG_SETTING_KEY, normalized_lang)

        return OCRSettingsState(
            provider=normalized_provider,
            tesseract_cmd=normalized_cmd,
            ocr_lang=normalized_lang,
        )

    def build_provider(self):
        settings = self.load_settings()
        return OCRProviderFactory.create_provider(
            provider_name=settings.provider,
            tesseract_cmd=settings.tesseract_cmd,
            ocr_lang=settings.ocr_lang,
        )

    def test_provider_connection(self) -> OCRResult:
        settings = self.load_settings()
        provider = OCRProviderFactory.create_provider(
            provider_name=settings.provider,
            tesseract_cmd=settings.tesseract_cmd,
            ocr_lang=settings.ocr_lang,
        )

        if settings.provider == OCR_PROVIDER_MOCK:
            return OCRResult(
                text="Mock OCR 可用（离线模拟）。",
                provider=OCR_PROVIDER_MOCK,
                success=True,
                error=None,
                metadata={"mode": "mock"},
            )

        try:
            from PIL import Image, ImageDraw
        except Exception as exc:
            return OCRResult(
                text="",
                provider=settings.provider,
                success=False,
                error=f"缺少 Pillow，无法执行 OCR 测试：{exc}",
                metadata=None,
            )

        with tempfile.TemporaryDirectory() as tmp:
            img_path = Path(tmp) / "ocr_test.png"
            img = Image.new("RGB", (360, 90), color=(255, 255, 255))
            drawer = ImageDraw.Draw(img)
            drawer.text((10, 30), "OCR TEST 123", fill=(0, 0, 0))
            img.save(img_path)
            return provider.extract_text(img_path)


def is_mock_ocr_provider(provider_name: str) -> bool:
    return (provider_name or "").strip().lower() == OCR_PROVIDER_MOCK
