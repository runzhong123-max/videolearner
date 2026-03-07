from pathlib import Path

from app.services.ocr_providers.base_provider import BaseOCRProvider


class MockOCRProvider(BaseOCRProvider):
    name = "mock_ocr"

    def extract_text(self, image_path: Path) -> str:
        file_name = image_path.name
        return (
            "[Mock OCR 提取结果]\n"
            f"图片文件：{file_name}\n"
            "识别文本：这是一段用于离线测试的 OCR 示例文本。"
        )