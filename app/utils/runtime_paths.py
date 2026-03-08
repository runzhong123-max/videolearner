import os
import sys
from pathlib import Path

APP_NAME = "VideoLearner"
ICON_RELATIVE_PATH = Path("assets") / "icons" / "videolearner.ico"
PROMPTS_RELATIVE_PATH = Path("app") / "prompts"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def source_root() -> Path:
    return Path(__file__).resolve().parents[2]


def bundle_root() -> Path:
    if not is_frozen():
        return source_root()

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return Path(sys.executable).resolve().parent


def writable_root() -> Path:
    env_root = os.getenv("VIDEOLEARNER_HOME", "").strip()
    if env_root:
        return Path(env_root).expanduser().resolve()

    if is_frozen():
        local_appdata = os.getenv("LOCALAPPDATA", "").strip()
        if local_appdata:
            return (Path(local_appdata) / APP_NAME).resolve()
        return (Path.home() / APP_NAME).resolve()

    return source_root()


def resource_path(*parts: str) -> Path:
    return bundle_root().joinpath(*parts)


def prompts_dir() -> Path:
    candidate = resource_path(*PROMPTS_RELATIVE_PATH.parts)
    if candidate.exists():
        return candidate
    return source_root() / PROMPTS_RELATIVE_PATH


def icon_path() -> Path:
    candidate = resource_path(*ICON_RELATIVE_PATH.parts)
    if candidate.exists():
        return candidate
    return source_root() / ICON_RELATIVE_PATH
