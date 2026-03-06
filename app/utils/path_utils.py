from pathlib import Path

from app.config import BASE_DIR, PROJECTS_DATA_DIR


def build_session_asset_dir(
    project_id: int,
    session_id: int,
    projects_root: Path = PROJECTS_DATA_DIR,
) -> Path:
    return projects_root / f"project_{project_id}" / "assets" / f"session_{session_id}"


def resolve_record_file_path(file_path: str, app_root: Path = BASE_DIR) -> Path | None:
    if not file_path:
        return None

    path = Path(file_path)
    if path.is_absolute():
        return path
    return (app_root / path).resolve()
