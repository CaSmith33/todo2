"""Local development project store. Replace persistence layer for production sharing."""
import json
import os
import sqlite3
from pathlib import Path

DB_PATH = Path(os.getenv("TOOLBOX_DB_PATH", "data/toolbox.sqlite3"))

def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def initialize():
    with connect() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS companies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS wells (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL REFERENCES companies(id),
                name TEXT NOT NULL,
                api_uwi TEXT NOT NULL DEFAULT '',
                location TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'Planning',
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(company_id, name)
            );
            CREATE TABLE IF NOT EXISTS cement_scenarios (
                well_id INTEGER NOT NULL REFERENCES wells(id),
                tally_id INTEGER NOT NULL REFERENCES casing_tallies(id),
                payload_json TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(well_id, tally_id)
            );
            CREATE TABLE IF NOT EXISTS casing_tallies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                well_id INTEGER NOT NULL REFERENCES wells(id),
                name TEXT NOT NULL,
                section TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                payload_json TEXT NOT NULL
            );
        """)

def companies():
    with connect() as con:
        return [dict(row) for row in con.execute("SELECT * FROM companies ORDER BY name")]

def wells():
    with connect() as con:
        return [dict(row) for row in con.execute("""
            SELECT w.*, c.name AS company_name
            FROM wells AS w JOIN companies AS c ON c.id=w.company_id
            ORDER BY c.name, w.name
        """)]

def create_company(name):
    name = name.strip()
    if not name:
        raise ValueError("Company name is required.")
    with connect() as con:
        cur = con.execute("INSERT INTO companies(name) VALUES (?)", (name,))
        return cur.lastrowid

def create_well(company_id, name, api_uwi="", location="", status="Planning", notes=""):
    if not name.strip():
        raise ValueError("Well name is required.")
    if status not in {"Planning", "Active", "Completed", "Archived"}:
        raise ValueError("Invalid well status.")
    with connect() as con:
        cur = con.execute("""
            INSERT INTO wells(company_id, name, api_uwi, location, status, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (int(company_id), name.strip(), api_uwi.strip(), location.strip(), status, notes.strip()))
        return cur.lastrowid

def update_well(well_id, api_uwi, location, status, notes):
    if status not in {"Planning", "Active", "Completed", "Archived"}:
        raise ValueError("Invalid well status.")
    with connect() as con:
        con.execute("""
            UPDATE wells SET api_uwi=?, location=?, status=?, notes=? WHERE id=?
        """, (api_uwi.strip(), location.strip(), status, notes.strip(), int(well_id)))

def export_json():
    with connect() as con:
        tallies = [dict(row) for row in con.execute(
            "SELECT id, well_id, name, section, created_at, payload_json FROM casing_tallies ORDER BY id"
        )]
    for item in tallies:
        item["rows"] = json.loads(item.pop("payload_json"))
    with connect() as con:
        cement = [dict(row) for row in con.execute(
            "SELECT well_id, tally_id, payload_json, updated_at FROM cement_scenarios"
        )]
    for item in cement:
        item["payload"] = json.loads(item.pop("payload_json"))
    return json.dumps({
        "schema_version": 3, "companies": companies(), "wells": wells(),
        "casing_tallies": tallies, "cement_scenarios": cement,
    }, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")

def save_casing_tally(well_id, name, section, rows):
    """Store a snapshot of ordered joints including Used state and diameters."""
    if not name.strip():
        raise ValueError("Tally name is required.")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Tally needs at least one joint.")
    with connect() as con:
        cur = con.execute(
            "INSERT INTO casing_tallies(well_id, name, section, payload_json) VALUES (?,?,?,?)",
            (int(well_id), name.strip(), section.strip(), json.dumps(rows, allow_nan=False)),
        )
        return cur.lastrowid

def list_casing_tallies(well_id):
    with connect() as con:
        return [dict(row) for row in con.execute(
            """SELECT id, well_id, name, section, created_at
               FROM casing_tallies WHERE well_id=? ORDER BY id DESC""", (int(well_id),)
        )]

def load_casing_tally(tally_id, well_id):
    """Require a matching well id when reading a tally."""
    with connect() as con:
        row = con.execute(
            "SELECT * FROM casing_tallies WHERE id=? AND well_id=?",
            (int(tally_id), int(well_id)),
        ).fetchone()
    return ({**dict(row), "rows": json.loads(row["payload_json"])} if row else None)

def save_cement_scenario(well_id, tally_id, payload):
    """Save or replace the most recent cementing worksheet for this well/tally."""
    # Confirm that the selected tally belongs to the selected well.
    if load_casing_tally(tally_id, well_id) is None:
        raise ValueError("Tally does not belong to the selected well.")
    with connect() as con:
        con.execute("""
            INSERT INTO cement_scenarios(well_id, tally_id, payload_json)
            VALUES (?, ?, ?)
            ON CONFLICT(well_id, tally_id) DO UPDATE
            SET payload_json=excluded.payload_json, updated_at=CURRENT_TIMESTAMP
        """, (int(well_id), int(tally_id), json.dumps(payload, allow_nan=False)))

def load_cement_scenario(well_id, tally_id):
    with connect() as con:
        row = con.execute(
            "SELECT payload_json FROM cement_scenarios WHERE well_id=? AND tally_id=?",
            (int(well_id), int(tally_id))
        ).fetchone()
    return json.loads(row["payload_json"]) if row else None
