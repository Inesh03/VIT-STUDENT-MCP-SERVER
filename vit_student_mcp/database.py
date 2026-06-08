import sqlite3
import os

BASE_DIR = os.path.expanduser("~/.vit_student_mcp")
os.makedirs(BASE_DIR, exist_ok=True)
DB_PATH = os.path.join(BASE_DIR, "vit_student.db")

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def create_tables():
    conn = get_connection()
    conn.executescript("""

CREATE TABLE IF NOT EXISTS courses (
    id      INTEGER PRIMARY KEY,
    code    TEXT NOT NULL,
    title   TEXT NOT NULL,
    type    TEXT NOT NULL,
    credits INTEGER,
    venue   TEXT,
    faculty TEXT
);

CREATE TABLE IF NOT EXISTS slots (
    id        INTEGER PRIMARY KEY,
    slot      TEXT,
    course_id INTEGER REFERENCES courses(id)
);

CREATE TABLE IF NOT EXISTS timetable (
    id         INTEGER PRIMARY KEY,
    course_id  INTEGER REFERENCES courses(id),
    slot_id    INTEGER REFERENCES slots(id),
    day        TEXT,
    start_time TEXT,
    end_time   TEXT
);

CREATE TABLE IF NOT EXISTS attendance (
    id         INTEGER PRIMARY KEY,
    course_id  INTEGER REFERENCES courses(id),
    attended   INTEGER,
    total      INTEGER,
    percentage INTEGER
);

CREATE TABLE IF NOT EXISTS marks (
    id        INTEGER PRIMARY KEY,
    course_id INTEGER REFERENCES courses(id),
    title     TEXT,
    scored    REAL,
    max       REAL,
    is_read   INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS exams (
    id        INTEGER PRIMARY KEY,
    course_id INTEGER REFERENCES courses(id),
    title     TEXT,
    date      TEXT,
    time      TEXT,
    venue     TEXT,
    seat      TEXT
);

CREATE TABLE IF NOT EXISTS assignments (
    id        INTEGER PRIMARY KEY,
    course_id INTEGER REFERENCES courses(id),
    title     TEXT,
    due_date  TEXT,
    submitted INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS staff (
    id        INTEGER PRIMARY KEY,
    course_id INTEGER REFERENCES courses(id),
    name      TEXT,
    email     TEXT,
    cabin     TEXT
);

CREATE TABLE IF NOT EXISTS profile (
    id             INTEGER PRIMARY KEY,
    name           TEXT,
    cgpa           REAL,
    total_credits  REAL
);

""")
    conn.commit()
    conn.close()
    print(f"✅ Tables created at {DB_PATH}")

if __name__ == "__main__":
    create_tables()
