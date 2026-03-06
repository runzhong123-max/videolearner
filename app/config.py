from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_DIR = BASE_DIR / "data"
DB_PATH = DB_DIR / "videolearner.db"
EXPORT_DIR = BASE_DIR / "exports"
ASSET_DIR = BASE_DIR / "assets"
