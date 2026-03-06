from pathlib import Path

from PIL import ImageGrab


class CaptureService:
    def capture_screen(self, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        screenshot = ImageGrab.grab(all_screens=True)
        screenshot.save(output_path)
