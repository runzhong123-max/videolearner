from app.services.errors import ServiceError
from app.services.ocr_providers.base_provider import BaseOCRProvider
from app.services.ocr_providers.local_ocr_provider import DEFAULT_OCR_LANG, LocalOCRProvider
from app.services.ocr_providers.mock_ocr_provider import MockOCRProvider

OCR_PROVIDER_MOCK = "mock_ocr"
OCR_PROVIDER_LOCAL = "local_ocr"
SUPPORTED_OCR_PROVIDERS = (OCR_PROVIDER_MOCK, OCR_PROVIDER_LOCAL)


class OCRProviderFactory:
    @staticmethod
    def create_provider(
        provider_name: str,
        tesseract_cmd: str = "",
        ocr_lang: str = DEFAULT_OCR_LANG,
    ) -> BaseOCRProvider:
        name = (provider_name or "").strip().lower() or OCR_PROVIDER_MOCK

        if name == OCR_PROVIDER_MOCK:
            return MockOCRProvider()
        if name == OCR_PROVIDER_LOCAL:
            return LocalOCRProvider(tesseract_cmd=tesseract_cmd, ocr_lang=ocr_lang)

        raise ServiceError(
            f"不支持的 OCR provider：{provider_name}。可选值：{OCR_PROVIDER_MOCK}/{OCR_PROVIDER_LOCAL}"
        )
