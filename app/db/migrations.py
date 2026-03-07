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
    (
        5,
        [
            "ALTER TABLE prompt_templates ADD COLUMN system_prompt TEXT NOT NULL DEFAULT '';",
            "ALTER TABLE prompt_templates ADD COLUMN user_prompt TEXT NOT NULL DEFAULT '';",
            "UPDATE prompt_templates SET system_prompt = content WHERE system_prompt = '' AND content != '';",
        ],
    ),
    (
        6,
        [
            """
            CREATE TABLE IF NOT EXISTS output_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                scope TEXT NOT NULL,
                project_id INTEGER,
                session_id INTEGER,
                summary INTEGER NOT NULL DEFAULT 1,
                extension INTEGER NOT NULL DEFAULT 1,
                insight INTEGER NOT NULL DEFAULT 0,
                history_link INTEGER NOT NULL DEFAULT 0,
                gap_analysis INTEGER NOT NULL DEFAULT 0,
                review_questions INTEGER NOT NULL DEFAULT 0,
                homework INTEGER NOT NULL DEFAULT 0,
                expression_notes INTEGER NOT NULL DEFAULT 0,
                evaluation INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );
            """,
            "CREATE INDEX IF NOT EXISTS idx_output_profile_scope ON output_profiles(scope);",
            "CREATE INDEX IF NOT EXISTS idx_output_profile_project_id ON output_profiles(project_id);",
            "CREATE INDEX IF NOT EXISTS idx_output_profile_session_id ON output_profiles(session_id);",
        ],
    ),
    (
        7,
        [
            "ALTER TABLE notes ADD COLUMN project_id INTEGER;",
            "UPDATE notes SET project_id = (SELECT sessions.project_id FROM sessions WHERE sessions.id = notes.session_id) WHERE project_id IS NULL;",
            "ALTER TABLE notes ADD COLUMN note_type TEXT NOT NULL DEFAULT 'session_summary';",
            "ALTER TABLE notes ADD COLUMN title TEXT NOT NULL DEFAULT '';",
            "ALTER TABLE notes ADD COLUMN content TEXT NOT NULL DEFAULT '';",
            "CREATE INDEX IF NOT EXISTS idx_notes_project_id ON notes(project_id);",
            "CREATE INDEX IF NOT EXISTS idx_notes_type ON notes(note_type);",
        ],
    ),
    (
        8,
        [
            """
            CREATE TABLE IF NOT EXISTS record_conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                record_id INTEGER NOT NULL,
                session_id INTEGER NOT NULL,
                project_id INTEGER NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                provider TEXT NOT NULL DEFAULT '',
                model_name TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (record_id) REFERENCES records(id) ON DELETE CASCADE,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS record_chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                response_id TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                image_path TEXT NOT NULL DEFAULT '',
                FOREIGN KEY (conversation_id) REFERENCES record_conversations(id) ON DELETE CASCADE
            );
            """,
            "CREATE INDEX IF NOT EXISTS idx_record_conversations_record_id ON record_conversations(record_id);",
            "CREATE INDEX IF NOT EXISTS idx_record_conversations_session_id ON record_conversations(session_id);",
            "CREATE INDEX IF NOT EXISTS idx_record_chat_messages_conversation_id ON record_chat_messages(conversation_id);",
        ],
    ),
    (
        9,
        [
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS ai_provider_configs (
                provider TEXT PRIMARY KEY,
                api_key TEXT NOT NULL DEFAULT '',
                api_url TEXT NOT NULL DEFAULT '',
                model TEXT NOT NULL DEFAULT '',
                timeout_seconds INTEGER NOT NULL DEFAULT 60,
                updated_at TEXT NOT NULL
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS ai_feature_routes (
                feature_name TEXT PRIMARY KEY,
                provider TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL
            );
            """,
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

