from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

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
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS variant_stats (
            variant_set TEXT,
            variant_id TEXT,
            sent INTEGER DEFAULT 0,
            opens INTEGER DEFAULT 0,
            replies INTEGER DEFAULT 0,
            meetings INTEGER DEFAULT 0,
            last_updated TEXT,
            PRIMARY KEY(variant_set, variant_id)
        )
        """
    )
    conn.commit()
    conn.close()


def save_message(dbpath: Path, msg: schemas.Message) -> None:
    init_db(dbpath)
    conn = _connect(dbpath)
    cur = conn.cursor()
    cur.execute(
        (
            """
        INSERT INTO messages(
            id, client_slug, contact_id, role, channel, subject, body, ts, status, meta
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET status=excluded.status, meta=excluded.meta
        """
        ),
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
    conn.commit()
    conn.close()


def update_status(dbpath: Path, message_id: str, status: str, meta: dict | None = None) -> None:
    init_db(dbpath)
    conn = _connect(dbpath)
    cur = conn.cursor()
    cur.execute(
        "UPDATE messages SET status=?, meta=? WHERE id=?",
        (status, json.dumps(meta or {}), message_id),
    )
    conn.commit()
    conn.close()


def log_event(dbpath: Path, ev: schemas.Event) -> None:
    init_db(dbpath)
    conn = _connect(dbpath)
    cur = conn.cursor()
    cur.execute(
        (
            "INSERT OR REPLACE INTO events("
            "id, client_slug, kind, message_id, contact_id, ts, meta"
            ") VALUES (?, ?, ?, ?, ?, ?, ?)"
        ),
        (
            ev.id,
            ev.client_slug,
            ev.kind,
            ev.message_id,
            ev.contact_id,
            ev.ts.isoformat(),
            json.dumps(ev.meta),
        ),
    )
    conn.commit()
    conn.close()
    # Update variant stats if the message carried a variant_id in its meta
    try:
        if ev.message_id:
            _update_variant_from_message(dbpath, ev.message_id, ev.kind)
    except Exception:
        # non-fatal: best-effort stats update
        pass


def _update_variant_from_message(dbpath: Path, message_id: str, kind: str) -> None:
    """
    Helper: find message by id, parse meta for variant_id/variant_set and
    increment variant_stats accordingly.
    """
    init_db(dbpath)
    conn = _connect(dbpath)
    cur = conn.cursor()
    cur.execute("SELECT meta FROM messages WHERE id=?", (message_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return
    try:
        meta = json.loads(row[0] or "{}")
    except Exception:
        meta = {}
    variant_id = meta.get("variant_id")
    variant_set = meta.get("variant_set", "baseline")
    if not variant_id:
        conn.close()
        return
    now = datetime.utcnow().isoformat()
    # ensure row
    cur.execute(
        (
            "INSERT OR IGNORE INTO variant_stats(variant_set, variant_id, last_updated)"
            " VALUES (?, ?, ?)"
        ),
        (variant_set, variant_id, now),
    )
    col = None
    if kind == "sent":
        col = "sent"
    elif kind in ("opened", "open"):
        col = "opens"
    elif kind in ("replied", "reply"):
        col = "replies"
    elif kind in ("meeting", "booked_meeting"):
        col = "meetings"
    if col:
        cur.execute(
            (
                f"UPDATE variant_stats SET {col} = COALESCE({col},0) + 1, last_updated = ? "
                "WHERE variant_set=? AND variant_id=?"
            ),
            (now, variant_set, variant_id),
        )
        conn.commit()
    conn.close()


def fetch_pending(dbpath: Path, status: str = "approved", limit: int = 100) -> list[dict]:
    init_db(dbpath)
    conn = _connect(dbpath)
    cur = conn.cursor()
    cur.execute("SELECT * FROM messages WHERE status=? LIMIT ?", (status, limit))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def last_reply_ts(dbpath: Path) -> datetime | None:
    init_db(dbpath)
    conn = _connect(dbpath)
    cur = conn.cursor()
    cur.execute("SELECT ts FROM events WHERE kind='replied' ORDER BY ts DESC LIMIT 1")
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return datetime.fromisoformat(row[0])
