"""SQLite storage and forward-only migration from the original schema."""

from datetime import datetime, timezone
from contextlib import closing, contextmanager
import logging
import sqlite3
from pathlib import Path
from collections.abc import Iterator

logger = logging.getLogger(__name__)


@contextmanager
def connect_db(database_path: str | Path) -> Iterator[sqlite3.Connection]:
    """Open a busy-tolerant SQLite connection and always close it."""
    with closing(sqlite3.connect(str(database_path))) as connection:
        connection.execute("PRAGMA busy_timeout=5000")
        with connection:
            yield connection


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}


def init_db(database_path: str | Path) -> None:
    """Create or migrate the database once during application startup."""
    path = str(database_path)
    with connect_db(path) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute(
            """CREATE TABLE IF NOT EXISTS users (
                user_key TEXT PRIMARY KEY,
                first_seen TEXT,
                last_seen TEXT,
                message_count INTEGER NOT NULL DEFAULT 0,
                first_name TEXT
            )"""
        )
        connection.execute(
            """CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY,
                user_key TEXT NOT NULL,
                timestamp TEXT,
                role TEXT NOT NULL,
                content TEXT NOT NULL
            )"""
        )
        connection.execute(
            """CREATE TABLE IF NOT EXISTS knowledge (
                id INTEGER PRIMARY KEY,
                question TEXT UNIQUE,
                answer TEXT,
                created_at TEXT
            )"""
        )

        user_cols = _columns(connection, "users")
        if "user_id" in user_cols:
            if "user_key" not in user_cols:
                connection.execute("ALTER TABLE users ADD COLUMN user_key TEXT")
            connection.execute(
                "UPDATE users SET user_key = CASE WHEN user_id LIKE '%:%' THEN user_id ELSE 'messenger:' || user_id END WHERE user_key IS NULL"
            )
            connection.execute("UPDATE users SET first_name = COALESCE(first_name, NULL)")
            for private_column in ("profile_pic", "locale", "timezone", "local_photo_path", "last_name"):
                if private_column in user_cols:
                    connection.execute(f"UPDATE users SET {private_column} = NULL")
        elif "user_key" not in user_cols:
            raise RuntimeError("Esquema da tabela users não reconhecido")

        conversation_cols = _columns(connection, "conversations")
        if "user_id" in conversation_cols and "user_key" not in conversation_cols:
            connection.execute("ALTER TABLE conversations ADD COLUMN user_key TEXT")
            connection.execute(
                "UPDATE conversations SET user_key = CASE WHEN user_id LIKE '%:%' THEN user_id ELSE 'messenger:' || user_id END"
            )
        elif "user_key" not in conversation_cols:
            raise RuntimeError("Esquema da tabela conversations não reconhecido")

        connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_user_key ON users(user_key)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_conversations_user_key_id ON conversations(user_key, id)")
    logger.info("Base de dados inicializada e migrada: %s", path)


def save_message(database_path: str | Path, user_key: str, role: str, content: str) -> None:
    """Persist a message and update the minimal user record."""
    now = datetime.now(timezone.utc).isoformat()
    with connect_db(database_path) as connection:
        conversation_columns = _columns(connection, "conversations")
        if "user_id" in conversation_columns:
            connection.execute(
                "INSERT INTO conversations(user_id, user_key, timestamp, role, content) VALUES (?, ?, ?, ?, ?)",
                (user_key.partition(":")[2], user_key, now, role, content),
            )
        else:
            connection.execute(
                "INSERT INTO conversations(user_key, timestamp, role, content) VALUES (?, ?, ?, ?)",
                (user_key, now, role, content),
            )
        if role == "user":
            user_columns = _columns(connection, "users")
            if "user_id" in user_columns:
                connection.execute(
                    """INSERT INTO users(user_id, user_key, first_seen, last_seen, message_count)
                       VALUES (?, ?, ?, ?, 1)
                       ON CONFLICT(user_key) DO UPDATE SET
                         last_seen = excluded.last_seen,
                         message_count = users.message_count + 1""",
                    (user_key.partition(":")[2], user_key, now, now),
                )
            else:
                connection.execute(
                    """INSERT INTO users(user_key, first_seen, last_seen, message_count)
                       VALUES (?, ?, ?, 1)
                       ON CONFLICT(user_key) DO UPDATE SET
                         last_seen = excluded.last_seen,
                         message_count = users.message_count + 1""",
                    (user_key, now, now),
                )


def get_history(database_path: str | Path, user_key: str, limit: int = 10) -> list[dict[str, str]]:
    """Return the latest conversation messages in chronological order."""
    with connect_db(database_path) as connection:
        rows = connection.execute(
            "SELECT role, content FROM conversations WHERE user_key = ? ORDER BY id DESC LIMIT ?",
            (user_key, limit),
        ).fetchall()
    rows.reverse()
    return [{"role": role, "content": content} for role, content in rows]


def search_knowledge(database_path: str | Path, question: str) -> str | None:
    query = question.lower().strip()
    with connect_db(database_path) as connection:
        row = connection.execute(
            "SELECT answer FROM knowledge WHERE LOWER(question) = ? LIMIT 1", (query,)
        ).fetchone()
        if row:
            return str(row[0])
        if len(query) < 4:
            return None
        escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        row = connection.execute(
            "SELECT answer FROM knowledge WHERE LOWER(question) LIKE ? ESCAPE '\\' LIMIT 1",
            (f"%{escaped}%",),
        ).fetchone()
    return str(row[0]) if row else None
