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
    return json.dumps({"schema_version": 1, "companies": companies(), "wells": wells()},
                      ensure_ascii=False, indent=2).encode("utf-8")
