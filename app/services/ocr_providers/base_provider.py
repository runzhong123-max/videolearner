from abc import ABC, abstractmethod
from pathlib import Path

from app.services.ocr_providers.ocr_result import OCRResult


class BaseOCRProvider(ABC):
    name: str = "base_ocr"

    @abstractmethod
    def extract_text(self, image_path: Path) -> OCRResult:
        raise NotImplementedError
