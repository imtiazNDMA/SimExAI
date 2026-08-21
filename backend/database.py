import sqlite3
import json
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = Path(os.getenv("SIMEX_DB_PATH", DATA_DIR / "simex.db"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def get_connection():
    """Yield a connection that commits on success, rolls back on error, and always closes.

    sqlite3's own `with conn:` block commits but never closes, which leaked a
    file handle on every call and kept the database file locked on Windows
    (review P2-3). Foreign keys are enabled per-connection — SQLite defaults
    them OFF, which made the ON DELETE CASCADE on `injects` inert.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    """Create tables if they don't exist."""
    DB_PATH.parent.mkdir(exist_ok=True, parents=True)
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scenarios (
                id TEXT PRIMARY KEY,
                name TEXT,
                type TEXT,
                magnitude TEXT,
                location TEXT,
                impact TEXT,
                context TEXT,
                phases TEXT,
                is_uploaded BOOLEAN,
                source_file TEXT,
                source_image_count INTEGER,
                source_visual_page_count INTEGER,
                source_visual_mode TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS injects (
                id TEXT PRIMARY KEY,
                scenario_id TEXT,
                phase_id TEXT,
                time_offset TEXT,
                title TEXT,
                description TEXT,
                severity TEXT,
                target_wings TEXT,
                response_required BOOLEAN,
                status TEXT DEFAULT 'pending',
                FOREIGN KEY(scenario_id) REFERENCES scenarios(id) ON DELETE CASCADE
            )
        """)

        # ── Exercise runs and participant sessions ──────────────────
        # An exercise is one run of a scenario. The phase lives here, not on
        # the session: a SimEx is a shared timeline — every wing sits at D-90
        # together and only the Controller advances it.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS exercises (
                id TEXT PRIMARY KEY,
                scenario_id TEXT,
                injects_id TEXT,
                current_phase_index INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(scenario_id) REFERENCES scenarios(id) ON DELETE SET NULL
            )
        """)

        # One browser taking part in an exercise, optionally focused on a wing.
        # This trusted-LAN deployment gives every active session full control.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                exercise_id TEXT NOT NULL,
                wing_id TEXT,
                participant_label TEXT,
                role TEXT NOT NULL DEFAULT 'controller',
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                FOREIGN KEY(exercise_id) REFERENCES exercises(id) ON DELETE CASCADE
            )
        """)

        # Full transcript. Without this the moderator has no memory (P0-1)
        # and no exercise can be scored after the fact (P0-2).
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                phase_id TEXT,
                wing_id TEXT,
                created_at TEXT NOT NULL,
                token_count INTEGER,
                FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
        """)

        # Per-session inject lifecycle: delivered -> addressed.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS inject_state (
                session_id TEXT NOT NULL,
                inject_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                delivered_at TEXT,
                addressed_at TEXT,
                PRIMARY KEY (session_id, inject_id),
                FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
        """)

        # Structured grading, one row per assessed response.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS assessments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                inject_id TEXT,
                message_id INTEGER,
                scores TEXT,
                evidence TEXT,
                gaps TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
        """)

        for statement in (
            "CREATE INDEX IF NOT EXISTS idx_injects_scenario ON injects(scenario_id, phase_id)",
            "CREATE INDEX IF NOT EXISTS idx_sessions_exercise ON sessions(exercise_id)",
            "CREATE INDEX IF NOT EXISTS idx_messages_session  ON messages(session_id, id)",
            "CREATE INDEX IF NOT EXISTS idx_assessments_session ON assessments(session_id)",
        ):
            conn.execute(statement)

    _migrate()

def _migrate():
    """Bring an existing database up to the current schema.

    Databases created before the sessions work predate `injects.status`, which
    `_normalize_injects` has always set and the schema silently discarded.
    """
    with get_connection() as conn:
        # WAL survives in the file; it lets reads proceed during a write, which
        # matters because FastAPI runs sync routes on a threadpool.
        conn.execute("PRAGMA journal_mode = WAL")

        existing = {row["name"] for row in conn.execute("PRAGMA table_info(injects)")}
        if existing and "status" not in existing:
            conn.execute("ALTER TABLE injects ADD COLUMN status TEXT DEFAULT 'pending'")

        existing_messages = {row["name"] for row in conn.execute("PRAGMA table_info(messages)")}
        if existing_messages and "wing_id" not in existing_messages:
            conn.execute("ALTER TABLE messages ADD COLUMN wing_id TEXT")

        # localhost, loopback, and LAN IPs are separate browser origins. Keep
        # their UI and permissions identical in this trusted-LAN deployment.
        conn.execute(
            "UPDATE sessions SET role = 'controller'"
            " WHERE status = 'active' AND role != 'controller'"
        )


# ── Exercises ───────────────────────────────────────────────


def create_exercise(scenario_id: Optional[str] = None, injects_id: Optional[str] = None) -> str:
    exercise_id = uuid.uuid4().hex
    now = _now()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO exercises (id, scenario_id, injects_id, current_phase_index,"
            " status, created_at, updated_at) VALUES (?, ?, ?, 0, 'active', ?, ?)",
            (exercise_id, scenario_id, injects_id, now, now),
        )
    return exercise_id


def load_exercise(exercise_id: str) -> Dict[str, Any]:
    if not exercise_id:
        return {}
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM exercises WHERE id = ?", (exercise_id,)).fetchone()
    return dict(row) if row else {}


def update_exercise(exercise_id: str, **fields) -> None:
    """Update whitelisted exercise columns. Unknown keys are ignored."""
    allowed = {"scenario_id", "injects_id", "current_phase_index", "status"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    assignments = ", ".join(f"{k} = ?" for k in updates)
    with get_connection() as conn:
        conn.execute(
            f"UPDATE exercises SET {assignments}, updated_at = ? WHERE id = ?",
            (*updates.values(), _now(), exercise_id),
        )


def change_exercise_phase(exercise_id: str, delta: int, max_index: int) -> Dict[str, Any]:
    """Move the shared exercise phase by one bounded step and return its row."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE exercises SET current_phase_index = MAX(0, MIN(?, current_phase_index + ?)),"
            " updated_at = ? WHERE id = ?",
            (max_index, delta, _now(), exercise_id),
        )
        row = conn.execute("SELECT * FROM exercises WHERE id = ?", (exercise_id,)).fetchone()
    return dict(row) if row else {}


def reset_exercise_phase(exercise_id: str) -> Dict[str, Any]:
    """Return an exercise to D-90 without detaching its scenario."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE exercises SET current_phase_index = 0, updated_at = ? WHERE id = ?",
            (_now(), exercise_id),
        )
        row = conn.execute("SELECT * FROM exercises WHERE id = ?", (exercise_id,)).fetchone()
    return dict(row) if row else {}


def get_or_create_active_exercise() -> Dict[str, Any]:
    """Return the most recent active exercise, creating one if none exists."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM exercises WHERE status = 'active' ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    if row:
        return dict(row)
    return load_exercise(create_exercise())


# ── Sessions ────────────────────────────────────────────────


def create_session(
    exercise_id: str,
    wing_id: Optional[str] = None,
    participant_label: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a full-access session for the trusted LAN deployment."""
    session_id = uuid.uuid4().hex
    now = _now()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO sessions (id, exercise_id, wing_id, participant_label, role,"
            " status, created_at, last_seen_at) VALUES (?, ?, ?, ?, ?, 'active', ?, ?)",
            (session_id, exercise_id, wing_id, participant_label, "controller", now, now),
        )
    return load_session(session_id)


def ensure_session(session_id: str) -> Dict[str, Any]:
    """Return a browser session, atomically creating it on the active exercise."""
    now = _now()
    with get_connection() as conn:
        # Serialize bootstrap so concurrent visitors share one active exercise.
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if row:
            conn.execute(
                "UPDATE sessions SET role = 'controller', last_seen_at = ? WHERE id = ?",
                (now, session_id),
            )
            session = dict(row)
            session["role"] = "controller"
            session["last_seen_at"] = now
            return session

        exercise = conn.execute(
            "SELECT * FROM exercises WHERE status = 'active' ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        if exercise is None:
            exercise_id = uuid.uuid4().hex
            conn.execute(
                "INSERT INTO exercises (id, scenario_id, injects_id, current_phase_index,"
                " status, created_at, updated_at) VALUES (?, NULL, NULL, 0, 'active', ?, ?)",
                (exercise_id, now, now),
            )
        else:
            exercise_id = exercise["id"]

        conn.execute(
            "INSERT INTO sessions (id, exercise_id, role, status, created_at, last_seen_at)"
            " VALUES (?, ?, 'controller', 'active', ?, ?)",
            (session_id, exercise_id, now, now),
        )
        row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    return dict(row)


def load_session(session_id: str) -> Dict[str, Any]:
    if not session_id:
        return {}
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    return dict(row) if row else {}


def touch_session(session_id: str, wing_id: Optional[str] = None) -> None:
    with get_connection() as conn:
        if wing_id:
            conn.execute(
                "UPDATE sessions SET last_seen_at = ?, wing_id = ? WHERE id = ?",
                (_now(), wing_id, session_id),
            )
        else:
            conn.execute(
                "UPDATE sessions SET last_seen_at = ? WHERE id = ?", (_now(), session_id)
            )


def bind_session_wing(session_id: str, wing_id: str, allow_change: bool = False) -> bool:
    """Bind a participant to its first wing; controllers may switch for facilitation."""
    with get_connection() as conn:
        cursor = conn.execute(
            "UPDATE sessions SET wing_id = ?, last_seen_at = ? WHERE id = ?"
            " AND (wing_id IS NULL OR wing_id = ? OR ?)",
            (wing_id, _now(), session_id, wing_id, allow_change),
        )
        return cursor.rowcount == 1


# ── Transcript ──────────────────────────────────────────────


def save_message(
    session_id: str,
    role: str,
    content: str,
    phase_id: Optional[str] = None,
    token_count: Optional[int] = None,
    wing_id: Optional[str] = None,
) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO messages (session_id, role, content, phase_id, wing_id, created_at, token_count)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (session_id, role, content, phase_id, wing_id, _now(), token_count),
        )
        return cur.lastrowid


def load_messages(session_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Return a session's transcript oldest-first.

    `limit` keeps the most recent N turns while preserving chronological order,
    which is what prompt construction needs.
    """
    if not session_id:
        return []
    with get_connection() as conn:
        if limit:
            rows = conn.execute(
                "SELECT * FROM (SELECT * FROM messages WHERE session_id = ?"
                " ORDER BY id DESC LIMIT ?) ORDER BY id ASC",
                (session_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM messages WHERE session_id = ? ORDER BY id ASC", (session_id,)
            ).fetchall()
    return [dict(row) for row in rows]


# ── Inject lifecycle ledger ─────────────────────────────────


def mark_injects_delivered(session_id: str, inject_ids: list[str]) -> None:
    """Record that the current-phase injects have been shown to the participant."""
    with get_connection() as conn:
        for inject_id in inject_ids:
            conn.execute(
                "INSERT OR IGNORE INTO inject_state (session_id, inject_id, status, delivered_at)"
                " VALUES (?, ?, 'delivered', ?)",
                (session_id, inject_id, _now()),
            )


def mark_inject_addressed(session_id: str, inject_id: str) -> None:
    """Record that the participant has already handled an inject."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE inject_state SET status = 'addressed', addressed_at = ?"
            " WHERE session_id = ? AND inject_id = ?",
            (_now(), session_id, inject_id),
        )


def get_inject_state(session_id: str) -> dict[str, str]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT inject_id, status FROM inject_state WHERE session_id = ?",
            (session_id,),
        ).fetchall()
    return {row["inject_id"]: row["status"] for row in rows}


def save_scenario(scenario_data: Dict[str, Any]):
    """Insert or replace scenario data into the scenarios table."""
    with get_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO scenarios (
                id, name, type, magnitude, location, impact, context, phases,
                is_uploaded, source_file, source_image_count, source_visual_page_count, source_visual_mode
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            scenario_data.get("id"),
            scenario_data.get("name"),
            scenario_data.get("type"),
            str(scenario_data.get("magnitude", "")),
            json.dumps(scenario_data.get("location", {})),
            json.dumps(scenario_data.get("impact", {})),
            scenario_data.get("context", ""),
            json.dumps(scenario_data.get("phases", [])),
            bool(scenario_data.get("is_uploaded", False)),
            scenario_data.get("source_file"),
            scenario_data.get("source_image_count", 0),
            scenario_data.get("source_visual_page_count", 0),
            scenario_data.get("source_visual_mode", "none")
        ))

def save_injects(scenario_id: str, injects: List[Dict[str, Any]]):
    """Insert inject records linked to the scenario_id. Clears existing first."""
    with get_connection() as conn:
        # Clear existing injects for this scenario
        conn.execute("DELETE FROM injects WHERE scenario_id = ?", (scenario_id,))
        
        # Insert new injects
        for idx, inj in enumerate(injects):
            raw_id = str(inj.get("id") or "").strip()
            if not raw_id:
                raw_id = f"inj_{idx}"
                
            # Guarantee global uniqueness across all scenarios
            inj_id = raw_id if raw_id.startswith(scenario_id) else f"{scenario_id}_{raw_id}"
                
            conn.execute("""
                INSERT INTO injects (
                    id, scenario_id, phase_id, time_offset, title, description,
                    severity, target_wings, response_required, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                inj_id,
                scenario_id,
                inj.get("phase_id"),
                inj.get("time_offset"),
                inj.get("title"),
                inj.get("description"),
                inj.get("severity"),
                json.dumps(inj.get("target_wings", inj.get("required_wings", []))),
                bool(inj.get("response_required", False)),
                inj.get("status") or "pending",
            ))

def load_scenario(scenario_id: str) -> Dict[str, Any]:
    """Retrieve scenario and parse JSON fields back to dicts."""
    if not scenario_id:
        return {}
        
    with get_connection() as conn:
        cur = conn.execute("SELECT * FROM scenarios WHERE id = ?", (scenario_id,))
        row = cur.fetchone()
        
    if not row:
        return {}
        
    data = dict(row)
    # Parse JSON fields back to objects
    for field in ["location", "impact", "phases"]:
        if data.get(field):
            try:
                data[field] = json.loads(data[field])
            except json.JSONDecodeError:
                data[field] = {} if field != "phases" else []
                
    # Ensure boolean is properly cast
    data["is_uploaded"] = bool(data["is_uploaded"])
    return data

def load_injects(scenario_id: str) -> Dict[str, Any]:
    """Retrieve all injects for a scenario. Returns dict format matching old JSON structure."""
    if not scenario_id:
        return {"injects": []}
        
    with get_connection() as conn:
        cur = conn.execute("SELECT * FROM injects WHERE scenario_id = ?", (scenario_id,))
        rows = cur.fetchall()
        
    injects = []
    for row in rows:
        data = dict(row)
        if data.get("target_wings"):
            try:
                data["target_wings"] = json.loads(data["target_wings"])
            except json.JSONDecodeError:
                data["target_wings"] = []
        # Support old `required_wings` alias used in some places
        data["required_wings"] = data.get("target_wings", [])
        data["response_required"] = bool(data["response_required"])
        injects.append(data)
        
    return {"injects": injects}
