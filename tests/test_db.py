import sqlite3

from eivorak.memory.db import connect_db, get_history, init_db, save_message, search_knowledge


def test_migrates_legacy_data_and_removes_unneeded_profile_fields(tmp_path):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """CREATE TABLE users (user_id TEXT PRIMARY KEY, first_seen TEXT, last_seen TEXT,
            message_count INTEGER DEFAULT 0, first_name TEXT, last_name TEXT, profile_pic TEXT,
            locale TEXT, timezone TEXT, local_photo_path TEXT);
            CREATE TABLE conversations (id INTEGER PRIMARY KEY, user_id TEXT, timestamp TEXT, role TEXT, content TEXT);
            CREATE TABLE knowledge (id INTEGER PRIMARY KEY, question TEXT UNIQUE, answer TEXT, created_at TEXT);
            INSERT INTO users VALUES ('123', 'then', 'now', 2, 'Ana', 'Silva', 'photo', 'pt', '1', 'file.jpg');
            INSERT INTO conversations(user_id, timestamp, role, content) VALUES ('123', 'then', 'user', 'Olá');"""
        )
    init_db(path)
    init_db(path)
    with sqlite3.connect(path) as connection:
        user = connection.execute(
            "SELECT user_key, first_name, last_name, profile_pic, locale, timezone, local_photo_path FROM users"
        ).fetchone()
        message = connection.execute("SELECT user_key, content FROM conversations").fetchone()
    assert user == ("messenger:123", "Ana", None, None, None, None, None)
    assert message == ("messenger:123", "Olá")
    save_message(path, "messenger:123", "user", "Outra")
    assert get_history(path, "messenger:123") == [
        {"role": "user", "content": "Olá"}, {"role": "user", "content": "Outra"}
    ]


def test_new_database_uses_channel_qualified_keys(tmp_path):
    path = tmp_path / "new.db"
    init_db(path)
    save_message(path, "messenger:42", "user", "Olá")
    assert get_history(path, "messenger:42") == [{"role": "user", "content": "Olá"}]


def test_connections_use_busy_timeout_and_escape_like_wildcards(tmp_path):
    path = tmp_path / "knowledge.db"
    init_db(path)
    with connect_db(path) as connection:
        assert connection.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
        connection.executemany(
            "INSERT INTO knowledge(question, answer) VALUES (?, ?)",
            [("contains a%b_ token", "literal"), ("contains axbX token", "wildcard")],
        )
    assert search_knowledge(path, "a%b_") == "literal"
    assert search_knowledge(path, "a_b") is None
