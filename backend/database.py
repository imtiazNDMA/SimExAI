import sqlite3
import json
from pathlib import Path
from typing import Dict, List, Any

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "simex.db"

def get_connection():
    """Get a database connection configured to return dict-like rows."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Create tables if they don't exist."""
    DATA_DIR.mkdir(exist_ok=True, parents=True)
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
                FOREIGN KEY(scenario_id) REFERENCES scenarios(id) ON DELETE CASCADE
            )
        """)

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
                    severity, target_wings, response_required
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                inj_id,
                scenario_id,
                inj.get("phase_id"),
                inj.get("time_offset"),
                inj.get("title"),
                inj.get("description"),
                inj.get("severity"),
                json.dumps(inj.get("target_wings", inj.get("required_wings", []))),
                bool(inj.get("response_required", False))
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
