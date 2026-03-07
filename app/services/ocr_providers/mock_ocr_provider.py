from pathlib import Path

from app.services.ocr_providers.base_provider import BaseOCRProvider
from app.services.ocr_providers.ocr_result import OCRResult


class MockOCRProvider(BaseOCRProvider):
    name = "mock_ocr"

    def extract_text(self, image_path: Path) -> OCRResult:
        file_name = image_path.name
        text = (
            "[Mock OCR 提取结果]\n"
            f"图片文件：{file_name}\n"
            "识别文本：这是一段用于离线测试的 OCR 示例文本。"
        )
        return OCRResult(
            text=text,
            provider=self.name,
            success=True,
            error=None,
            metadata={
                "image_path": str(image_path),
                "mode": "mock",
            },
        )
