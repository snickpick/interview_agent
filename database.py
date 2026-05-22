import json
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
            topic TEXT NOT NULL,
            questions TEXT NOT NULL,
            question_idx INTEGER DEFAULT 0,
            total_score INTEGER DEFAULT 0,
            summary TEXT,
            strengths TEXT,
            weaknesses TEXT,
            fit_result TEXT,
            memory_state TEXT,
            num_questions INTEGER DEFAULT 10,
            created_at TEXT NOT NULL,
            completed_at TEXT
        );
        CREATE TABLE IF NOT EXISTS answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            score INTEGER NOT NULL,
            feedback TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        );
    """)
    for col, col_type in [("memory_state", "TEXT"), ("num_questions", "INTEGER DEFAULT 10")]:
        try:
            conn.execute(f"ALTER TABLE sessions ADD COLUMN {col} {col_type}")
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()


def create_session(name, topic, questions, num_questions=None):
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    conn.execute(
        "INSERT INTO sessions (id, name, topic, questions, question_idx, total_score, num_questions, created_at) VALUES (?, ?, ?, ?, 0, 0, ?, ?)",
        (session_id, name, topic, json.dumps(questions), num_questions or len(questions), now),
    )
    conn.commit()
    conn.close()
    return session_id


def get_session(session_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM sessions WHERE id = ?", (session_id,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["questions"] = json.loads(d["questions"])
    for field in ("strengths", "weaknesses"):
        if d.get(field):
            d[field] = json.loads(d[field])
    return d


def update_session(session_id, **kwargs):
    conn = get_connection()
    fields = []
    values = []
    for k, v in kwargs.items():
        fields.append(f"{k} = ?")
        if isinstance(v, (list, dict)):
            v = json.dumps(v)
        values.append(v)
    values.append(session_id)
    conn.execute(
        f"UPDATE sessions SET {', '.join(fields)} WHERE id = ?", values
    )
    conn.commit()
    conn.close()


def save_answer(session_id, question, answer, score, feedback):
    now = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    conn.execute(
        "INSERT INTO answers (session_id, question, answer, score, feedback, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (session_id, question, answer, score, feedback, now),
    )
    conn.commit()
    conn.close()


def get_answers(session_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM answers WHERE session_id = ? ORDER BY id",
        (session_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_memory_state(session_id, memory_dict):
    conn = get_connection()
    conn.execute(
        "UPDATE sessions SET memory_state = ? WHERE id = ?",
        (json.dumps(memory_dict), session_id),
    )
    conn.commit()
    conn.close()


def get_memory_state(session_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT memory_state FROM sessions WHERE id = ?", (session_id,)
    ).fetchone()
    conn.close()
    if not row or not row["memory_state"]:
        return None
    return json.loads(row["memory_state"])
