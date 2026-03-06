import sqlite3
from typing import Iterable

MIGRATIONS: list[tuple[int, Iterable[str]]] = [
    (
        1,
        [
            """
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                default_prompt TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'not_started',
                started_at TEXT NOT NULL,
                ended_at TEXT,
                summary TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                record_type TEXT NOT NULL,
                content TEXT NOT NULL DEFAULT '',
                file_path TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                is_inspiration INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                summary TEXT NOT NULL,
                suggestions TEXT NOT NULL,
                inspiration_refinement TEXT NOT NULL DEFAULT '',
                guidance TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS prompt_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scope TEXT NOT NULL,
                project_id INTEGER,
                session_id INTEGER,
                name TEXT NOT NULL,
                content TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );
            """,
            "CREATE INDEX IF NOT EXISTS idx_sessions_project_id ON sessions(project_id);",
            "CREATE INDEX IF NOT EXISTS idx_records_session_id ON records(session_id);",
            "CREATE INDEX IF NOT EXISTS idx_notes_session_id ON notes(session_id);",
            "CREATE INDEX IF NOT EXISTS idx_prompt_scope ON prompt_templates(scope);",
        ],
    ),
    (
        2,
        [
            "ALTER TABLE projects ADD COLUMN source TEXT NOT NULL DEFAULT '';",
            "ALTER TABLE projects ADD COLUMN goal TEXT NOT NULL DEFAULT '';",
            "ALTER TABLE projects ADD COLUMN tags TEXT NOT NULL DEFAULT '';",
        ],
    ),
    (
        3,
        [
            "UPDATE sessions SET status = 'in_progress' WHERE status = 'active';",
        ],
    ),
    (
        4,
        [
            "ALTER TABLE records ADD COLUMN timestamp_offset INTEGER NOT NULL DEFAULT 0;",
        ],
    ),
]


def run_migrations(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """
    )

    applied_versions = {
        row["version"]
        for row in conn.execute("SELECT version FROM schema_migrations ORDER BY version ASC").fetchall()
    }

    for version, statements in MIGRATIONS:
        if version in applied_versions:
            continue

        for statement in statements:
            conn.execute(statement)

        conn.execute("INSERT INTO schema_migrations (version) VALUES (?)", (version,))
