import ctypes
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PIL import ImageGrab

from app.services.errors import ServiceError

CAPTURE_MODE_FULL_SCREEN = "full_screen"
CAPTURE_MODE_ACTIVE_WINDOW = "active_window"
CAPTURE_MODE_REGION = "region"
SUPPORTED_CAPTURE_MODES = {
    CAPTURE_MODE_FULL_SCREEN,
    CAPTURE_MODE_ACTIVE_WINDOW,
    CAPTURE_MODE_REGION,
}

Region = tuple[int, int, int, int]


@dataclass
class CaptureResult:
    requested_mode: str
    actual_mode: str
    fallback_reason: str
    region: Region | None


class CaptureService:
    def __init__(
        self,
        grabber: Callable[..., object] | None = None,
        active_window_detector: Callable[[], Region | None] | None = None,
    ):
        self.grabber = grabber or ImageGrab.grab
        self.active_window_detector = active_window_detector or self._detect_active_window_region

    def capture(
        self,
        output_path: Path,
        mode: str = CAPTURE_MODE_ACTIVE_WINDOW,
        region: Region | None = None,
    ) -> CaptureResult:
        requested_mode = (mode or CAPTURE_MODE_FULL_SCREEN).strip().lower()
        if requested_mode not in SUPPORTED_CAPTURE_MODES:
            raise ServiceError(f"不支持的截图模式：{mode}")

        actual_mode = requested_mode
        fallback_reason = ""
        resolved_region = region

        if requested_mode == CAPTURE_MODE_ACTIVE_WINDOW:
            resolved_region = self.active_window_detector()
            if resolved_region is None:
                actual_mode = CAPTURE_MODE_FULL_SCREEN
                fallback_reason = "active_window_unavailable"

        if actual_mode == CAPTURE_MODE_REGION:
            if resolved_region is None:
                raise ServiceError("region 模式缺少截图区域。")
            if len(resolved_region) != 4:
                raise ServiceError("region 模式区域格式非法，应为 (left, top, right, bottom)。")
            screenshot = self.grabber(bbox=resolved_region)
        elif actual_mode == CAPTURE_MODE_FULL_SCREEN:
            screenshot = self._grab_full_screen()
        else:
            # actual active-window capture uses bbox from window detector
            if resolved_region is None:
                raise ServiceError("active_window 模式未获取到窗口区域。")
            screenshot = self.grabber(bbox=resolved_region)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        screenshot.save(output_path)

        return CaptureResult(
            requested_mode=requested_mode,
            actual_mode=actual_mode,
            fallback_reason=fallback_reason,
            region=resolved_region,
        )

    def capture_screen(self, output_path: Path) -> None:
        self.capture(output_path=output_path, mode=CAPTURE_MODE_FULL_SCREEN)

    def capture_active_window(self, output_path: Path) -> CaptureResult:
        return self.capture(output_path=output_path, mode=CAPTURE_MODE_ACTIVE_WINDOW)

    def capture_region(self, output_path: Path, region: Region) -> CaptureResult:
        return self.capture(output_path=output_path, mode=CAPTURE_MODE_REGION, region=region)

    def _grab_full_screen(self):
        try:
            return self.grabber(all_screens=True)
        except TypeError:
            # Older/limited grabbers may not support all_screens kwarg.
            return self.grabber()

    @staticmethod
    def _detect_active_window_region() -> Region | None:
        if sys.platform != "win32":
            return None

        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", ctypes.c_long),
                ("top", ctypes.c_long),
                ("right", ctypes.c_long),
                ("bottom", ctypes.c_long),
            ]

        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if hwnd == 0:
            return None

        rect = RECT()
        ok = user32.GetWindowRect(hwnd, ctypes.byref(rect))
        if ok == 0:
            return None

        left, top, right, bottom = rect.left, rect.top, rect.right, rect.bottom
        if right - left <= 1 or bottom - top <= 1:
            return None
        return (left, top, right, bottom)
