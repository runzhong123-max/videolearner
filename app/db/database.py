import sqlite3
from contextlib import closing
from pathlib import Path

from app.config import DB_DIR, DB_PATH
from app.db.migrations import run_migrations


class Database:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path

    def initialize(self) -> None:
        DB_DIR.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            run_migrations(conn)
            conn.commit()

    def as_path(self) -> str:
        return str(self.db_path)
