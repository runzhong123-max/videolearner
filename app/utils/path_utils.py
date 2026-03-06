from pathlib import Path

from app.config import PROJECTS_DATA_DIR


def build_session_asset_dir(
    project_id: int,
    session_id: int,
    projects_root: Path = PROJECTS_DATA_DIR,
) -> Path:
    return projects_root / f"project_{project_id}" / "assets" / f"session_{session_id}"
