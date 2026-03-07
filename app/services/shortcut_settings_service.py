import json

from app.repositories.app_setting_repository import AppSettingRepository
from app.services.errors import ServiceError

ACTION_START_SESSION = "start_session"
ACTION_PAUSE_SESSION = "pause_session"
ACTION_RESUME_SESSION = "resume_session"
ACTION_FINISH_SESSION = "finish_session"
ACTION_CAPTURE_IMAGE_RECORD = "capture_image_record"
ACTION_CAPTURE_TEXT_RECORD = "capture_text_record"

SHORTCUT_ACTIONS = (
    ACTION_START_SESSION,
    ACTION_PAUSE_SESSION,
    ACTION_RESUME_SESSION,
    ACTION_FINISH_SESSION,
    ACTION_CAPTURE_IMAGE_RECORD,
    ACTION_CAPTURE_TEXT_RECORD,
)

# NOTE: Tab is intentionally not the default for global shortcut because it conflicts heavily
# with system/app focus navigation and input fields. Users can still set it manually.
DEFAULT_SHORTCUT_BINDINGS: dict[str, str] = {
    ACTION_START_SESSION: "ctrl+alt+s",
    ACTION_PAUSE_SESSION: "ctrl+alt+p",
    ACTION_RESUME_SESSION: "ctrl+alt+r",
    ACTION_FINISH_SESSION: "ctrl+alt+e",
    ACTION_CAPTURE_IMAGE_RECORD: "ctrl+alt+c",
    ACTION_CAPTURE_TEXT_RECORD: "ctrl+shift+a",
}

SHORTCUT_BINDINGS_KEY = "shortcuts.bindings.v1"


class ShortcutSettingsService:
    def __init__(self, app_setting_repository: AppSettingRepository):
        self.app_setting_repository = app_setting_repository

    def get_default_bindings(self) -> dict[str, str]:
        return dict(DEFAULT_SHORTCUT_BINDINGS)

    def load_bindings(self) -> dict[str, str]:
        raw = self.app_setting_repository.get(SHORTCUT_BINDINGS_KEY)
        if raw is None or not raw.strip():
            return self.get_default_bindings()

        try:
            loaded = json.loads(raw)
        except json.JSONDecodeError:
            return self.get_default_bindings()

        if not isinstance(loaded, dict):
            return self.get_default_bindings()

        merged = self.get_default_bindings()
        for action in SHORTCUT_ACTIONS:
            value = loaded.get(action)
            if isinstance(value, str) and value.strip():
                merged[action] = self.normalize_shortcut(value)

        self.validate_bindings(merged)
        return merged

    def save_bindings(self, bindings: dict[str, str]) -> dict[str, str]:
        normalized = self.validate_bindings(bindings)
        self.app_setting_repository.set(
            SHORTCUT_BINDINGS_KEY,
            json.dumps(normalized, ensure_ascii=False),
        )
        return normalized

    def restore_defaults(self) -> dict[str, str]:
        defaults = self.get_default_bindings()
        self.save_bindings(defaults)
        return defaults

    def validate_bindings(self, bindings: dict[str, str]) -> dict[str, str]:
        normalized: dict[str, str] = {}
        missing = [action for action in SHORTCUT_ACTIONS if action not in bindings]
        if missing:
            raise ServiceError(f"快捷键配置缺少动作：{', '.join(missing)}")

        for action in SHORTCUT_ACTIONS:
            raw = bindings.get(action, "")
            if not isinstance(raw, str) or not raw.strip():
                raise ServiceError(f"动作 {action} 的快捷键不能为空。")
            normalized[action] = self.normalize_shortcut(raw)

        conflicts = self.detect_conflicts(normalized)
        if conflicts:
            conflict_desc = "; ".join(
                f"{shortcut}: {', '.join(actions)}"
                for shortcut, actions in conflicts.items()
            )
            raise ServiceError(f"快捷键冲突：{conflict_desc}")

        return normalized

    def detect_conflicts(self, bindings: dict[str, str]) -> dict[str, list[str]]:
        grouped: dict[str, list[str]] = {}
        for action, shortcut in bindings.items():
            key = self.normalize_shortcut(shortcut)
            grouped.setdefault(key, []).append(action)

        return {key: actions for key, actions in grouped.items() if len(actions) > 1}

    @staticmethod
    def normalize_shortcut(shortcut: str) -> str:
        text = "".join((shortcut or "").strip().split())
        text = text.replace("+", "+")
        return text.lower()
