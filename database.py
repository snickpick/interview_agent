import sqlite3
import uuid
from datetime import datetime, timezone

DB_PATH = "interviews.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            block_idx INTEGER DEFAULT 0,
            question_idx INTEGER DEFAULT 0,
            history TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            completed_at TEXT
        );
        CREATE TABLE IF NOT EXISTS answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            block_name TEXT NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            feedback TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        );
    """)
    conn.commit()
    conn.close()


def create_session(name):
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    conn.execute(
        "INSERT INTO sessions (id, name, block_idx, question_idx, history, created_at) VALUES (?, ?, 0, 0, '', ?)",
        (session_id, name, now),
    )
    conn.commit()
    conn.close()
    return session_id


def get_session(session_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_session(session_id, block_idx=None, question_idx=None, history=None, completed_at=None):
    conn = get_connection()
    fields = []
    values = []
    if block_idx is not None:
        fields.append("block_idx = ?")
        values.append(block_idx)
    if question_idx is not None:
        fields.append("question_idx = ?")
        values.append(question_idx)
    if history is not None:
        fields.append("history = ?")
        values.append(history)
    if completed_at is not None:
        fields.append("completed_at = ?")
        values.append(completed_at)
    values.append(session_id)
    conn.execute(f"UPDATE sessions SET {', '.join(fields)} WHERE id = ?", values)
    conn.commit()
    conn.close()


def save_answer(session_id, block_name, question, answer, feedback):
    now = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    conn.execute(
        "INSERT INTO answers (session_id, block_name, question, answer, feedback, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (session_id, block_name, question, answer, feedback, now),
    )
    conn.commit()
    conn.close()
