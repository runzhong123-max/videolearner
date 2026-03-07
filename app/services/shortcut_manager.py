from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal

from app.services.shortcut_settings_service import ShortcutSettingsService


class HotkeyBackendError(Exception):
    pass


class BaseHotkeyBackend:
    def register_hotkey(self, shortcut: str, callback: Callable[[], None]) -> None:
        raise NotImplementedError

    def unregister_all(self) -> None:
        raise NotImplementedError


class KeyboardHotkeyBackend(BaseHotkeyBackend):
    def __init__(self):
        try:
            import keyboard  # type: ignore
        except Exception as exc:
            raise HotkeyBackendError(f"keyboard 妯″潡涓嶅彲鐢? {exc}") from exc
        self._keyboard = keyboard
        self._shortcuts: list[str] = []

    def register_hotkey(self, shortcut: str, callback: Callable[[], None]) -> None:
        try:
            self._keyboard.add_hotkey(shortcut, callback)
        except Exception as exc:
            raise HotkeyBackendError(f"娉ㄥ唽蹇嵎閿け璐?{shortcut}: {exc}") from exc
        self._shortcuts.append(shortcut)

    def unregister_all(self) -> None:
        for shortcut in self._shortcuts:
            try:
                self._keyboard.remove_hotkey(shortcut)
            except Exception:
                pass
        self._shortcuts.clear()


class NullHotkeyBackend(BaseHotkeyBackend):
    def __init__(self, reason: str | None = None):
        self.reason = reason

    def register_hotkey(self, shortcut: str, callback: Callable[[], None]) -> None:
        _ = (shortcut, callback)

    def unregister_all(self) -> None:
        return


def build_default_hotkey_backend() -> BaseHotkeyBackend:
    try:
        return KeyboardHotkeyBackend()
    except HotkeyBackendError as exc:
        return NullHotkeyBackend(reason=str(exc))


@dataclass
class HotkeyApplyResult:
    success: bool
    registered_actions: list[str]
    failed_actions: list[str]


class ShortcutManager(QObject):
    action_triggered = Signal(str)
    registration_failed = Signal(str)

    def __init__(
        self,
        shortcut_settings_service: ShortcutSettingsService,
        backend: BaseHotkeyBackend | None = None,
    ):
        super().__init__()
        self.shortcut_settings_service = shortcut_settings_service
        self.backend = backend or build_default_hotkey_backend()
        self.current_bindings: dict[str, str] = {}

    def reload_from_settings(self) -> HotkeyApplyResult:
        bindings = self.shortcut_settings_service.load_bindings()
        return self.apply_bindings(bindings)

    def apply_bindings(self, bindings: dict[str, str]) -> HotkeyApplyResult:
        normalized = self.shortcut_settings_service.validate_bindings(bindings)

        self.backend.unregister_all()
        self.current_bindings = dict(normalized)

        if isinstance(self.backend, NullHotkeyBackend) and self.backend.reason:
            failed_actions = list(normalized.keys())
            self.registration_failed.emit(
                f"鍏ㄥ眬蹇嵎閿悗绔笉鍙敤: {self.backend.reason}"
            )
            return HotkeyApplyResult(
                success=False,
                registered_actions=[],
                failed_actions=failed_actions,
            )

        registered_actions: list[str] = []
        failed_actions: list[str] = []

        for action, shortcut in normalized.items():
            try:
                self.backend.register_hotkey(
                    shortcut,
                    self._build_action_callback(action),
                )
                registered_actions.append(action)
            except Exception as exc:
                failed_actions.append(action)
                self.registration_failed.emit(f"{action} -> {shortcut} 娉ㄥ唽澶辫触: {exc}")

        return HotkeyApplyResult(
            success=len(failed_actions) == 0,
            registered_actions=registered_actions,
            failed_actions=failed_actions,
        )

    def save_and_apply(self, bindings: dict[str, str]) -> HotkeyApplyResult:
        normalized = self.shortcut_settings_service.save_bindings(bindings)
        return self.apply_bindings(normalized)

    def stop(self) -> None:
        self.backend.unregister_all()

    def _build_action_callback(self, action: str) -> Callable[[], None]:
        def _callback() -> None:
            self.action_triggered.emit(action)

        return _callback
