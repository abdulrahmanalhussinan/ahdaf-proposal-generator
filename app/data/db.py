"""SQLite storage. The repositories in `repositories.py` are the only code that
touches SQL, so moving to PostgreSQL later means re-implementing that layer only."""
from __future__ import annotations

import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

from app import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS clients (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    sector TEXT,
    contact_name TEXT,
    contact_email TEXT,
    contact_phone TEXT,
    about TEXT,
    website TEXT,
    logo TEXT,
    is_demo INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS proposals (
    id TEXT PRIMARY KEY,
    number TEXT NOT NULL,
    client_id TEXT,
    client_name TEXT NOT NULL,
    project_name TEXT NOT NULL,
    project_type TEXT,
    sector TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    version TEXT NOT NULL DEFAULT '1.0',
    inputs TEXT NOT NULL,
    doc TEXT NOT NULL,
    meta TEXT NOT NULL DEFAULT '{}',
    search_text TEXT NOT NULL DEFAULT '',
    is_demo INTEGER NOT NULL DEFAULT 0,
    owner TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_proposals_updated ON proposals(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_proposals_client ON proposals(client_id);

CREATE TABLE IF NOT EXISTS proposal_revisions (
    id TEXT PRIMARY KEY,
    proposal_id TEXT NOT NULL,
    version TEXT NOT NULL,
    note TEXT,
    inputs TEXT NOT NULL,
    doc TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_revisions_proposal ON proposal_revisions(proposal_id);

CREATE TABLE IF NOT EXISTS library_items (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    key TEXT,
    title TEXT NOT NULL,
    data TEXT NOT NULL DEFAULT '{}',
    sort INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1,
    is_demo INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_library_kind ON library_items(kind, sort);

CREATE TABLE IF NOT EXISTS templates (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    project_type TEXT,
    inputs TEXT NOT NULL,
    is_builtin INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS uploads (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    mime TEXT NOT NULL,
    size INTEGER NOT NULL,
    stored_name TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- Celebrities / influencers imported from the team's own sheets. Proposals only ever name people from here.
CREATE TABLE IF NOT EXISTS celebrities (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    handle TEXT,
    platforms TEXT,
    followers TEXT,
    category TEXT,
    city TEXT,
    gender TEXT,
    notes TEXT,
    extra TEXT NOT NULL DEFAULT '{}',
    source TEXT,
    created_at TEXT NOT NULL
);

-- Uploaded reference documents (client profiles) and the text extracted from them.
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    mime TEXT,
    size INTEGER NOT NULL DEFAULT 0,
    stored_name TEXT,
    pages INTEGER,
    text TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
"""

_lock = threading.RLock()
_conn: sqlite3.Connection | None = None


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
    conn.row_factory = sqlite3.Row
    if os.getenv("AHDAF_SQLITE_WAL", "1") != "0":  # the in-browser build has no shared memory for WAL
        conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def get_connection() -> sqlite3.Connection:
    global _conn
    with _lock:
        if _conn is None:
            _conn = _connect(config.DB_PATH)
            _conn.executescript(SCHEMA)
        return _conn


def reset_connection(path: Path | None = None) -> sqlite3.Connection:
    """Used by tests to point the app at a throwaway database."""
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
        _conn = _connect(path or config.DB_PATH)
        _conn.executescript(SCHEMA)
        return _conn


@contextmanager
def transaction():
    conn = get_connection()
    with _lock:
        conn.execute("BEGIN")
        try:
            yield conn
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
