from __future__ import annotations
import sqlite3
from pathlib import Path
import json
from typing import Optional, List, Dict
from datetime import datetime
from ada.core import schemas


def _connect(dbpath: Path) -> sqlite3.Connection:
    dbpath.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(dbpath), detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(dbpath: Path) -> None:
    conn = _connect(dbpath)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            client_slug TEXT,
            contact_id TEXT,
            role TEXT,
            channel TEXT,
            subject TEXT,
            body TEXT,
            ts TEXT,
            status TEXT,
            meta TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY,
            client_slug TEXT,
            kind TEXT,
            message_id TEXT,
            contact_id TEXT,
            ts TEXT,
            meta TEXT
        )
        """
    )
    conn.commit(); conn.close()


def save_message(dbpath: Path, msg: schemas.Message) -> None:
    init_db(dbpath)
    conn = _connect(dbpath)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO messages(id, client_slug, contact_id, role, channel, subject, body, ts, status, meta)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET status=excluded.status, meta=excluded.meta
        """,
        (
            msg.id,
            msg.client_slug,
            msg.contact_id,
            msg.role,
            msg.channel,
            msg.subject,
            msg.body,
            msg.ts.isoformat(),
            msg.status,
            json.dumps(msg.meta),
        ),
    )
    conn.commit(); conn.close()


def update_status(dbpath: Path, message_id: str, status: str, meta: Optional[Dict] = None) -> None:
    init_db(dbpath)
    conn = _connect(dbpath)
    cur = conn.cursor()
    cur.execute("UPDATE messages SET status=?, meta=? WHERE id=?", (status, json.dumps(meta or {}), message_id))
    conn.commit(); conn.close()


def log_event(dbpath: Path, ev: schemas.Event) -> None:
    init_db(dbpath)
    conn = _connect(dbpath)
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO events(id, client_slug, kind, message_id, contact_id, ts, meta) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (ev.id, ev.client_slug, ev.kind, ev.message_id, ev.contact_id, ev.ts.isoformat(), json.dumps(ev.meta)),
    )
    conn.commit(); conn.close()


def fetch_pending(dbpath: Path, status: str = "approved", limit: int = 100) -> List[Dict]:
    init_db(dbpath)
    conn = _connect(dbpath)
    cur = conn.cursor()
    cur.execute("SELECT * FROM messages WHERE status=? LIMIT ?", (status, limit))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def last_reply_ts(dbpath: Path) -> Optional[datetime]:
    init_db(dbpath)
    conn = _connect(dbpath)
    cur = conn.cursor()
    cur.execute("SELECT ts FROM events WHERE kind='replied' ORDER BY ts DESC LIMIT 1")
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return datetime.fromisoformat(row[0])
