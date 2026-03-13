import sqlite3
import os
import threading
from typing import List, Tuple
from datetime import datetime

import numpy as np

from config import (
    DB_FILE,
    DATA_DIR,
    STUDENT_IMAGES_DIR,
    GROUP_PHOTOS_DIR,
    DEFAULT_ADMIN_EMAIL,
    DEFAULT_ADMIN_PASSWORD,
)

# Module-level lock and init flag to prevent concurrent init and database locking
_init_lock = threading.Lock()
_db_initialized = False

def get_db_connection(timeout: float = 30.0):
    """Establishes a connection to the SQLite database with proper timeout handling."""
    conn = sqlite3.connect(DB_FILE, timeout=timeout)
    conn.row_factory = sqlite3.Row
    # Enable foreign keys so CASCADE deletes work (SQLite does not enable them by default)
    conn.execute("PRAGMA foreign_keys = ON")
    # Prevent "database is locked" by waiting up to 30 seconds for locks to clear
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn

def init_db():
    """Initializes the database, creates tables, and seeds default data.
    Uses a lock to ensure only one initialization runs at a time.
    Skips re-initialization if already done in this process.
    """
    global _db_initialized

    with _init_lock:
        if _db_initialized:
            return

        # Ensure data directories exist
        os.makedirs(DATA_DIR, exist_ok=True)
        os.makedirs(STUDENT_IMAGES_DIR, exist_ok=True)
        os.makedirs(GROUP_PHOTOS_DIR, exist_ok=True)

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # Create tables
            cursor.executescript("""
                CREATE TABLE IF NOT EXISTS Admins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS Teachers (
                    teacher_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    branch TEXT,
                    subject TEXT NOT NULL,
                    password TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS Students (
                    student_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    roll TEXT NOT NULL,
                    section TEXT NOT NULL,
                    class TEXT NOT NULL,
                    password TEXT NOT NULL,
                    photo_path TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS Attendance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    date TEXT NOT NULL,
                    status TEXT NOT NULL,
                    marked_by TEXT NOT NULL,
                    UNIQUE(student_id, subject, date),
                    FOREIGN KEY (student_id) REFERENCES Students(student_id) ON DELETE CASCADE,
                    FOREIGN KEY (marked_by) REFERENCES Teachers(teacher_id)
                );
                CREATE TABLE IF NOT EXISTS FaceEmbeddings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT UNIQUE NOT NULL,
                    embedding BLOB NOT NULL,
                    FOREIGN KEY (student_id) REFERENCES Students(student_id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS Meta (
                    key TEXT PRIMARY KEY,
                    value INTEGER NOT NULL
                );
                -- New: classes and mappings
                CREATE TABLE IF NOT EXISTS Classes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    branch TEXT,
                    section TEXT
                );
                CREATE TABLE IF NOT EXISTS TeacherClasses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    teacher_id TEXT NOT NULL,
                    class_name TEXT NOT NULL,
                    FOREIGN KEY (teacher_id) REFERENCES Teachers(teacher_id) ON DELETE CASCADE,
                    FOREIGN KEY (class_name) REFERENCES Classes(name) ON DELETE CASCADE
                );
                -- New: notifications
                CREATE TABLE IF NOT EXISTS Notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    body TEXT NOT NULL,
                    audience TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                -- New: complaints
                CREATE TABLE IF NOT EXISTS Complaints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    message TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    resolved_at TEXT
                );
                -- New: outgoing messages (SMS/email)
                CREATE TABLE IF NOT EXISTS Messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    phone TEXT,
                    body TEXT NOT NULL,
                    provider TEXT,
                    status TEXT,
                    created_at TEXT NOT NULL
                );
                -- New: direct teacher-to-student messages
                CREATE TABLE IF NOT EXISTS DirectMessages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    teacher_id TEXT NOT NULL,
                    student_id TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    is_read INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (teacher_id) REFERENCES Teachers(teacher_id) ON DELETE CASCADE,
                    FOREIGN KEY (student_id) REFERENCES Students(student_id) ON DELETE CASCADE
                );
            """)

            # Seed default admin if not exists
            cursor.execute("SELECT * FROM Admins WHERE email = ?", (DEFAULT_ADMIN_EMAIL,))
            if not cursor.fetchone():
                cursor.execute("INSERT INTO Admins (email, password) VALUES (?, ?)", (DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD))

            # Seed meta counters if not exists
            cursor.execute("INSERT OR IGNORE INTO Meta (key, value) VALUES ('last_teacher_serial', 0);")
            cursor.execute("INSERT OR IGNORE INTO Meta (key, value) VALUES ('last_student_serial', 0);")

            # Seed default classes
            default_classes = [
                "B.Tech AI 1st Year",
                "B.Tech AI 2nd Year",
                "B.Tech AI 3rd Year",
                "B.Tech AI 4th Year",
            ]
            for cname in default_classes:
                cursor.execute(
                    "INSERT OR IGNORE INTO Classes (name) VALUES (?)", (cname,)
                )

            # Add phone columns to Teachers/Students if they don't exist
            try:
                cursor.execute("ALTER TABLE Teachers ADD COLUMN phone TEXT")
            except sqlite3.OperationalError:
                pass
            try:
                cursor.execute("ALTER TABLE Students ADD COLUMN phone TEXT")
            except sqlite3.OperationalError:
                pass

            # Add branch/section columns to Classes if they don't exist (for legacy DBs)
            try:
                cursor.execute("ALTER TABLE Classes ADD COLUMN branch TEXT")
            except sqlite3.OperationalError:
                pass
            try:
                cursor.execute("ALTER TABLE Classes ADD COLUMN section TEXT")
            except sqlite3.OperationalError:
                pass

            # Table to track per-year/branch/section roll serials
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS RollSerials (
                    year INTEGER NOT NULL,
                    branch TEXT NOT NULL,
                    section TEXT NOT NULL,
                    last_serial INTEGER NOT NULL,
                    PRIMARY KEY (year, branch, section)
                );
                """
            )

            conn.commit()
            _db_initialized = True
            print("Database initialized successfully.")
        except sqlite3.OperationalError as e:
            print(f"Database init warning (may retry): {e}")
            raise
        finally:
            conn.close()

# --- Meta Table Functions ---
def get_next_serial(key: str) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM Meta WHERE key = ?", (key,))
    row = cursor.fetchone()
    if row is None:
        conn.close()
        raise ValueError(f"Meta key '{key}' not found. Database may not be initialized.")
    current_value = row['value']
    new_value = current_value + 1
    cursor.execute("UPDATE Meta SET value = ? WHERE key = ?", (new_value, key))
    conn.commit()
    conn.close()
    return new_value


def _get_next_roll_serial(year: int, branch: str, section: str) -> int:
    """
    Returns the next serial number for a given (year, branch, section) tuple,
    creating an entry if needed and updating it atomically.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO RollSerials (year, branch, section, last_serial)
        VALUES (?, ?, ?, 0)
        ON CONFLICT(year, branch, section) DO NOTHING
        """,
        (year, branch, section),
    )
    cursor.execute(
        """
        UPDATE RollSerials
        SET last_serial = last_serial + 1
        WHERE year = ? AND branch = ? AND section = ?
        """,
        (year, branch, section),
    )
    cursor.execute(
        """
        SELECT last_serial FROM RollSerials
        WHERE year = ? AND branch = ? AND section = ?
        """,
        (year, branch, section),
    )
    row = cursor.fetchone()
    conn.commit()
    conn.close()
    if not row:
        raise ValueError("Failed to allocate roll serial.")
    return int(row["last_serial"])


def generate_roll_number(year: int, branch: str, section: str) -> str:
    """
    Generate a unique roll number:
    YY + Branch + Section + Serial (e.g., 26AIA001)

    - YY: last two digits of admission year
    - Branch: uppercase short code (AI / CSE / IT)
    - Section: single letter (A/B/C...), uppercased
    - Serial: zero-padded per (year, branch, section)
    """
    if not branch:
        raise ValueError("Branch is required for roll generation.")
    if not section:
        raise ValueError("Section is required for roll generation.")

    yy = str(year)[-2:]
    branch_code = branch.strip().upper()
    section_code = section.strip().upper()
    serial = _get_next_roll_serial(year, branch_code, section_code)
    serial_str = str(serial).zfill(3)
    return f"{yy}{branch_code}{section_code}{serial_str}"

# --- User Creation ---
def create_teacher(teacher_id, name, email, branch, subject, password):
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO Teachers (teacher_id, name, email, branch, subject, password) VALUES (?, ?, ?, ?, ?, ?)",
            (teacher_id, name, email, branch, subject, password)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def create_student(student_id, name, roll, section, _class, password, photo_path):
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO Students (student_id, name, roll, section, class, password, photo_path) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (student_id, name, roll, section, _class, password, photo_path)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        conn.rollback()
        return False
    finally:
        conn.close()

# --- Data Retrieval ---
def get_admin_by_email(email):
    conn = get_db_connection()
    admin = conn.execute("SELECT * FROM Admins WHERE email = ?", (email,)).fetchone()
    conn.close()
    return admin

def get_teacher(teacher_id):
    conn = get_db_connection()
    teacher = conn.execute("SELECT * FROM Teachers WHERE teacher_id = ?", (teacher_id,)).fetchone()
    conn.close()
    return teacher

def get_student(student_id):
    conn = get_db_connection()
    student = conn.execute("SELECT * FROM Students WHERE student_id = ?", (student_id,)).fetchone()
    conn.close()
    return student

def list_teachers():
    conn = get_db_connection()
    teachers = conn.execute("SELECT teacher_id, name, email, branch, subject FROM Teachers").fetchall()
    conn.close()
    return teachers

def list_students():
    conn = get_db_connection()
    students = conn.execute("SELECT student_id, name, roll, section, class FROM Students").fetchall()
    conn.close()
    return students


def list_students_with_photo():
    """Students with photo_path (and phone) for card display."""
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT student_id, name, roll, section, class, photo_path, phone FROM Students"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def list_classes() -> list[str]:
    """Return all class names."""
    conn = get_db_connection()
    rows = conn.execute("SELECT name FROM Classes ORDER BY name").fetchall()
    conn.close()
    return [r["name"] for r in rows]


def list_classes_detailed() -> list[dict]:
    """Return all classes with id, name, branch, section."""
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT id, name, branch, section FROM Classes ORDER BY name"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def upsert_class(name: str, branch: str | None = None, section: str | None = None) -> None:
    """
    Create or update a class record by name.
    Does not touch student mappings; primarily for adding new classes.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO Classes (name, branch, section)
        VALUES (?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            branch = excluded.branch,
            section = excluded.section
        """,
        (name, branch, section),
    )
    conn.commit()
    conn.close()


def update_class_and_mappings(
    old_name: str,
    new_name: str,
    branch: str | None,
    section: str | None,
) -> None:
    """
    Update a class's name/branch/section while keeping students and teacher mappings consistent.
    - Renames the class in Classes
    - Updates Students.class and TeacherClasses.class_name to the new name
    """
    if not new_name:
        raise ValueError("Class name cannot be empty.")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE Classes
            SET name = ?, branch = ?, section = ?
            WHERE name = ?
            """,
            (new_name, branch, section, old_name),
        )
        cursor.execute(
            "UPDATE Students SET class = ? WHERE class = ?",
            (new_name, old_name),
        )
        cursor.execute(
            "UPDATE TeacherClasses SET class_name = ? WHERE class_name = ?",
            (new_name, old_name),
        )
        conn.commit()
    finally:
        conn.close()

# --- Attendance Functions ---
def mark_attendance(student_id: str, subject: str, date_iso: str, status: str, marked_by: str) -> bool:
    """
    Marks attendance for a student. Validates that student and teacher exist before insert
    to prevent FOREIGN KEY constraint failures.
    Returns True on success, False if validation fails.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Validate: student must exist
        cursor.execute("SELECT 1 FROM Students WHERE student_id = ?", (student_id,))
        if cursor.fetchone() is None:
            return False

        # Validate: teacher (marked_by) must exist
        cursor.execute("SELECT 1 FROM Teachers WHERE teacher_id = ?", (marked_by,))
        if cursor.fetchone() is None:
            return False

        cursor.execute(
            """
            INSERT INTO Attendance (student_id, subject, date, status, marked_by) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(student_id, subject, date) DO UPDATE SET status = excluded.status, marked_by = excluded.marked_by
            """,
            (student_id, subject, date_iso, status, marked_by)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        conn.rollback()
        return False
    finally:
        conn.close()

def get_attendance_by_student(student_id):
    conn = get_db_connection()
    records = conn.execute(
        "SELECT date, subject, status FROM Attendance WHERE student_id = ? ORDER BY date DESC", (student_id,)
    ).fetchall()
    conn.close()
    return records


def get_attendance_for_subject_date(subject: str, date_iso: str):
    """Returns list of dicts with student_id, status for given subject and date."""
    conn = get_db_connection()
    records = conn.execute(
        "SELECT student_id, status FROM Attendance WHERE subject = ? AND date = ?",
        (subject, date_iso),
    ).fetchall()
    conn.close()
    return [dict(r) for r in records]


def get_present_student_ids_for_subject_date(subject: str, date_iso: str):
    """Set of student_ids marked Present for subject/date (for group photo merge)."""
    rows = get_attendance_for_subject_date(subject, date_iso)
    return {r["student_id"] for r in rows if r.get("status") == "Present"}


def get_attendance_by_teacher_subject_date(teacher_id: str, subject: str, date_iso: str):
    """Attendance records for a teacher's subject on a given date."""
    conn = get_db_connection()
    records = conn.execute(
        """
        SELECT a.student_id, s.name AS student_name, a.status
        FROM Attendance a
        LEFT JOIN Students s ON s.student_id = a.student_id
        WHERE a.marked_by = ? AND a.subject = ? AND a.date = ?
        ORDER BY s.name
        """,
        (teacher_id, subject, date_iso),
    ).fetchall()
    conn.close()
    return [dict(r) for r in records]


def get_all_attendance_filtered(teacher_id=None, subject=None, date_from=None, date_to=None):
    """All attendance with optional filters for teacher, subject, date range."""
    conn = get_db_connection()
    q = """
        SELECT a.date, a.subject, a.status, a.student_id, s.name AS student_name,
               a.marked_by AS teacher_id, t.name AS teacher_name
        FROM Attendance a
        LEFT JOIN Students s ON s.student_id = a.student_id
        LEFT JOIN Teachers t ON t.teacher_id = a.marked_by
        WHERE 1=1
    """
    params = []
    if teacher_id:
        q += " AND a.marked_by = ?"
        params.append(teacher_id)
    if subject:
        q += " AND a.subject = ?"
        params.append(subject)
    if date_from:
        q += " AND a.date >= ?"
        params.append(date_from)
    if date_to:
        q += " AND a.date <= ?"
        params.append(date_to)
    q += " ORDER BY a.date DESC, a.subject"
    records = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in records]


def get_student_attendance_stats(student_id: str, subject: str = None, date_from: str = None, date_to: str = None):
    """Returns (present_count, total_count, percentage) for a student with optional filters."""
    conn = get_db_connection()
    q = "SELECT status FROM Attendance WHERE student_id = ?"
    params = [student_id]
    if subject:
        q += " AND subject = ?"
        params.append(subject)
    if date_from:
        q += " AND date >= ?"
        params.append(date_from)
    if date_to:
        q += " AND date <= ?"
        params.append(date_to)
    rows = conn.execute(q, params).fetchall()
    conn.close()
    total = len(rows)
    present = sum(1 for r in rows if r["status"] == "Present")
    pct = (present / total * 100) if total > 0 else 0.0
    return present, total, round(pct, 2)


def get_students_with_attendance_stats(teacher_id: str, subject: str = None, date_from: str = None, date_to: str = None):
    """List of students with present_count, total_count, percentage, photo_path for teacher's view."""
    students = list_students_with_photo()
    out = []
    for s in students:
        sid = s["student_id"]
        present, total, pct = get_student_attendance_stats(sid, subject=subject, date_from=date_from, date_to=date_to)
        out.append({
            "student_id": sid,
            "name": s["name"],
            "roll": s.get("roll"),
            "section": s.get("section"),
            "class": s.get("class"),
            "photo_path": s.get("photo_path"),
            "phone": s.get("phone"),
            "present_count": present,
            "total_count": total,
            "percentage": pct,
        })
    return out


def assign_teacher_classes(teacher_id: str, class_names: list[str]) -> None:
    """Replace teacher's class assignments with new list."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM TeacherClasses WHERE teacher_id = ?", (teacher_id,))
    for cname in class_names:
        cur.execute(
            "INSERT OR IGNORE INTO TeacherClasses (teacher_id, class_name) VALUES (?, ?)",
            (teacher_id, cname),
        )
    conn.commit()
    conn.close()


def get_teacher_classes(teacher_id: str) -> list[str]:
    """Return list of class names assigned to a teacher."""
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT class_name FROM TeacherClasses WHERE teacher_id = ?",
        (teacher_id,),
    ).fetchall()
    conn.close()
    return [r["class_name"] for r in rows]


def get_all_attendance():
    """
    Returns all attendance records joined with basic student and teacher info.
    """
    conn = get_db_connection()
    records = conn.execute(
        """
        SELECT
            Attendance.date,
            Attendance.subject,
            Attendance.status,
            Attendance.student_id,
            Students.name AS student_name,
            Attendance.marked_by AS teacher_id,
            Teachers.name AS teacher_name
        FROM Attendance
        LEFT JOIN Students ON Students.student_id = Attendance.student_id
        LEFT JOIN Teachers ON Teachers.teacher_id = Attendance.marked_by
        ORDER BY Attendance.date DESC, Attendance.subject
        """
    ).fetchall()
    conn.close()
    return records


def create_message(role: str, user_id: str, phone: str, body: str,
                   provider: str = "", status: str = "") -> None:
    """Log an outgoing message (e.g. SMS)."""
    conn = get_db_connection()
    conn.execute(
        """
        INSERT INTO Messages (role, user_id, phone, body, provider, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (role, user_id, phone, body, provider, status,
         datetime.utcnow().isoformat(timespec="seconds")),
    )
    conn.commit()
    conn.close()


def create_notification(title: str, body: str, audience: str = "all") -> None:
    conn = get_db_connection()
    conn.execute(
        """
        INSERT INTO Notifications (title, body, audience, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (title, body, audience, datetime.utcnow().isoformat(timespec="seconds")),
    )
    conn.commit()
    conn.close()


def list_notifications_for_role(role: str, limit: int = 10) -> list[dict]:
    """Return recent notifications for given role ('Student' or 'Teacher')."""
    audience = "students" if role == "Student" else "teachers"
    conn = get_db_connection()
    rows = conn.execute(
        """
        SELECT * FROM Notifications
        WHERE audience IN ('all', ?)
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (audience, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_complaint(role: str, user_id: str, subject: str, message: str) -> None:
    conn = get_db_connection()
    conn.execute(
        """
        INSERT INTO Complaints (role, user_id, subject, message, status, created_at)
        VALUES (?, ?, ?, ?, 'open', ?)
        """,
        (role, user_id, subject, message,
         datetime.utcnow().isoformat(timespec="seconds")),
    )
    conn.commit()
    conn.close()


def list_complaints(status: str | None = None) -> list[dict]:
    conn = get_db_connection()
    q = "SELECT * FROM Complaints"
    params: list[str] = []
    if status:
        q += " WHERE status = ?"
        params.append(status)
    q += " ORDER BY created_at DESC"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def set_complaint_status(complaint_id: int, status: str) -> None:
    conn = get_db_connection()
    conn.execute(
        "UPDATE Complaints SET status = ?, resolved_at = ? WHERE id = ?",
        (status, datetime.utcnow().isoformat(timespec="seconds"), complaint_id),
    )
    conn.commit()
    conn.close()


# --- Direct Teacher-Student Messages ---
def create_direct_message(teacher_id: str, student_id: str, message: str) -> None:
    """Store a direct message from teacher to student."""
    if not message:
        return
    conn = get_db_connection()
    conn.execute(
        """
        INSERT INTO DirectMessages (teacher_id, student_id, message, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            teacher_id,
            student_id,
            message,
            datetime.utcnow().isoformat(timespec="seconds"),
        ),
    )
    conn.commit()
    conn.close()


def list_messages_for_student(student_id: str) -> list[dict]:
    """List messages received by a student with teacher info."""
    conn = get_db_connection()
    rows = conn.execute(
        """
        SELECT d.id,
               d.message,
               d.created_at,
               d.is_read,
               t.name AS teacher_name,
               t.teacher_id
        FROM DirectMessages d
        LEFT JOIN Teachers t ON t.teacher_id = d.teacher_id
        WHERE d.student_id = ?
        ORDER BY d.created_at DESC
        """,
        (student_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def list_messages_for_teacher(teacher_id: str) -> list[dict]:
    """List messages sent by a teacher with student info."""
    conn = get_db_connection()
    rows = conn.execute(
        """
        SELECT d.id,
               d.message,
               d.created_at,
               d.is_read,
               s.name AS student_name,
               s.student_id
        FROM DirectMessages d
        LEFT JOIN Students s ON s.student_id = d.student_id
        WHERE d.teacher_id = ?
        ORDER BY d.created_at DESC
        """,
        (teacher_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Face Embedding Functions ---
def save_face_embedding(student_id: str, embedding: np.ndarray) -> None:
    """
    Stores or updates a student's face embedding in the database.

    The embedding is stored as a float32 BLOB for efficient retrieval.
    """
    if embedding is None:
        return

    # Ensure 1D float32 vector
    emb = np.asarray(embedding, dtype=np.float32).reshape(-1)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO FaceEmbeddings (student_id, embedding)
        VALUES (?, ?)
        ON CONFLICT(student_id) DO UPDATE SET embedding = excluded.embedding
        """,
        (student_id, emb.tobytes()),
    )
    conn.commit()
    conn.close()


def get_all_face_embeddings() -> Tuple[List[str], np.ndarray]:
    """
    Returns all stored face embeddings and their corresponding student_ids.

    Returns:
        (student_ids, embeddings)
        - student_ids: list of student_id strings
        - embeddings: numpy.ndarray of shape (N, D) or empty array if none
    """
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT student_id, embedding FROM FaceEmbeddings"
    ).fetchall()
    conn.close()

    student_ids: List[str] = []
    embeddings: List[np.ndarray] = []

    for row in rows:
        blob = row["embedding"]
        if blob is None:
            continue
        emb = np.frombuffer(blob, dtype=np.float32)
        if emb.size == 0:
            continue
        student_ids.append(row["student_id"])
        embeddings.append(emb)

    if not embeddings:
        return [], np.empty((0, 0), dtype=np.float32)

    return student_ids, np.vstack(embeddings)

# --- YEH NAYE FUNCTIONS HAIN ---
# --- User Deletion Functions ---
def delete_teacher(teacher_id):
    """Deletes a teacher record from the database."""
    conn = get_db_connection()
    conn.execute("DELETE FROM Teachers WHERE teacher_id = ?", (teacher_id,))
    conn.commit()
    conn.close()

def delete_student(student_id):
    """
    Deletes a student and all related data: face embeddings, attendance, and photo file.
    Order of deletion ensures consistency (child tables first, then Students).
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get photo path before deleting (needed for file cleanup)
    student = cursor.execute(
        "SELECT photo_path FROM Students WHERE student_id = ?", (student_id,)
    ).fetchone()

    # 1. Remove face embeddings first (child of Students)
    cursor.execute("DELETE FROM FaceEmbeddings WHERE student_id = ?", (student_id,))

    # 2. Remove all attendance records for this student
    cursor.execute("DELETE FROM Attendance WHERE student_id = ?", (student_id,))

    # 3. Remove student record (parent)
    cursor.execute("DELETE FROM Students WHERE student_id = ?", (student_id,))

    conn.commit()
    conn.close()

    # 4. Delete photo file from disk
    if student and student["photo_path"]:
        path = student["photo_path"]
        if isinstance(path, str) and os.path.exists(path):
            try:
                os.remove(path)
            except OSError as e:
                print(f"Error deleting photo file {path}: {e}")