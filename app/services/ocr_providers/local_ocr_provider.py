import time
from pathlib import Path

from app.services.ocr_providers.base_provider import BaseOCRProvider
from app.services.ocr_providers.ocr_result import OCRResult

DEFAULT_TESSERACT_PATHS = [
    Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
    Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
]
DEFAULT_OCR_LANG = "chi_sim+eng"


class LocalOCRProvider(BaseOCRProvider):
    name = "local_ocr"

    def __init__(self, tesseract_cmd: str = "", ocr_lang: str = DEFAULT_OCR_LANG):
        self.tesseract_cmd = (tesseract_cmd or "").strip()
        self.ocr_lang = (ocr_lang or DEFAULT_OCR_LANG).strip() or DEFAULT_OCR_LANG

    def extract_text(self, image_path: Path) -> OCRResult:
        start = time.perf_counter()
        cmd, error = self._resolve_tesseract_cmd()
        if error is not None:
            return OCRResult(
                text="",
                provider=self.name,
                success=False,
                error=error,
                metadata={
                    "image_path": str(image_path),
                    "lang": self.ocr_lang,
                    "tesseract_cmd": cmd or self.tesseract_cmd,
                },
            )

        try:
            import pytesseract
            from PIL import Image
        except Exception as exc:
            return OCRResult(
                text="",
                provider=self.name,
                success=False,
                error=f"未安装 OCR 依赖，请先安装 pytesseract/Pillow：{exc}",
                metadata={
                    "image_path": str(image_path),
                    "lang": self.ocr_lang,
                    "tesseract_cmd": cmd,
                },
            )

        try:
            pytesseract.pytesseract.tesseract_cmd = cmd
            with Image.open(image_path) as image:
                raw = pytesseract.image_to_string(image, lang=self.ocr_lang)
            text = (raw or "").strip()
        except Exception as exc:
            return OCRResult(
                text="",
                provider=self.name,
                success=False,
                error=f"Tesseract OCR 执行失败：{exc}",
                metadata={
                    "image_path": str(image_path),
                    "lang": self.ocr_lang,
                    "tesseract_cmd": cmd,
                    "elapsed_ms": int((time.perf_counter() - start) * 1000),
                },
            )

        if not text:
            return OCRResult(
                text="",
                provider=self.name,
                success=False,
                error="OCR 未识别到文本。",
                metadata={
                    "image_path": str(image_path),
                    "lang": self.ocr_lang,
                    "tesseract_cmd": cmd,
                    "elapsed_ms": int((time.perf_counter() - start) * 1000),
                },
            )

        return OCRResult(
            text=text,
            provider=self.name,
            success=True,
            error=None,
            metadata={
                "image_path": str(image_path),
                "lang": self.ocr_lang,
                "tesseract_cmd": cmd,
                "elapsed_ms": int((time.perf_counter() - start) * 1000),
            },
        )

    def _resolve_tesseract_cmd(self) -> tuple[str, str | None]:
        if self.tesseract_cmd:
            path = Path(self.tesseract_cmd)
            if not path.exists():
                return "", f"Tesseract 路径不存在：{self.tesseract_cmd}"
            return str(path), None

        for candidate in DEFAULT_TESSERACT_PATHS:
            if candidate.exists():
                return str(candidate), None

        try:
            import pytesseract

            # Probe if tesseract can be found in PATH.
            _ = pytesseract.get_tesseract_version()
            return "tesseract", None
        except Exception:
            return "", (
                "未找到 Tesseract 可执行文件。请在 OCR 设置中填写 tesseract.exe 路径，"
                "例如 C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
            )

