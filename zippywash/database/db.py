"""Database connection and setup. The database is internal storage, not a domain class."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
SCHEMA_VERSION = 2   # must match "PRAGMA user_version" in schema.sql
DEFAULT_DB_PATH = Path(os.environ.get("ZIPPYWASH_DB", Path(__file__).resolve().parents[2] / "zippywash.db"))


def connect(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def drop_all_tables(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys = OFF")
    for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
        conn.execute(f'DROP TABLE IF EXISTS "{name}"')
    conn.commit()
    conn.execute("PRAGMA foreign_keys = ON")


def create_schema(conn: sqlite3.Connection) -> bool:
    """Create every table. A demo database built by an older version of the schema is rebuilt
    from scratch (it only ever holds sample data). Returns True if an old database was replaced."""
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    has_tables = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0] > 0
    rebuilt = has_tables and version != SCHEMA_VERSION
    if rebuilt:
        drop_all_tables(conn)
    conn.executescript(SCHEMA_PATH.read_text())
    conn.commit()
    return rebuilt


def is_empty(conn: sqlite3.Connection) -> bool:
    return conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0] == 0
