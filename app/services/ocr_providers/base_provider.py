from abc import ABC, abstractmethod
from pathlib import Path


class BaseOCRProvider(ABC):
    name: str = "base_ocr"

    @abstractmethod
    def extract_text(self, image_path: Path) -> str:
        raise NotImplementedError