from __future__ import annotations

import random
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class Variant(BaseModel):
    id: str
    name: str
    subject_tpl: str
    body_tpl: str
    tags: list[str] = Field(default_factory=list)


DB_FILENAME = "learning.sqlite"


def _db_path(audits_root: Path, slug: str) -> Path:
    return audits_root / slug / DB_FILENAME


def init_learning_db(dbpath: Path) -> None:
    dbpath.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(dbpath))
    cur = conn.cursor()
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


def _inc_stat(dbpath: Path, variant_set: str, variant_id: str, col: str, delta: int = 1) -> None:
    init_learning_db(dbpath)
    conn = sqlite3.connect(str(dbpath))
    cur = conn.cursor()
    now = datetime.utcnow().isoformat()
    # ensure row exists
    cur.execute(
        (
            "INSERT OR IGNORE INTO variant_stats(variant_set, variant_id, last_updated) "
            "VALUES (?, ?, ?)"
        ),
        (variant_set, variant_id, now),
    )
    cur.execute(
        (
            f"UPDATE variant_stats SET {col} = COALESCE({col},0) + ?, last_updated = ? "
            "WHERE variant_set=? AND variant_id=?"
        ),
        (delta, now, variant_set, variant_id),
    )
    conn.commit()
    conn.close()


def record_event(dbpath: Path, variant_set: str, variant_id: str, kind: str) -> None:
    """Increment stats based on event kind: 'sent','opened','replied','meeting'."""
    if not variant_id:
        return
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
        _inc_stat(dbpath, variant_set or "baseline", variant_id, col, 1)


def get_stats(dbpath: Path) -> list[dict[str, Any]]:
    if not dbpath.exists():
        return []
    conn = sqlite3.connect(str(dbpath))
    cur = conn.cursor()
    cur.execute(
        "SELECT variant_set, variant_id, sent, opens, replies, meetings, last_updated "
        "FROM variant_stats ORDER BY variant_set, variant_id"
    )
    rows = [
        dict(
            zip(
                [
                    "variant_set",
                    "variant_id",
                    "sent",
                    "opens",
                    "replies",
                    "meetings",
                    "last_updated",
                ],
                r,
                strict=False,
            )
        )
        for r in cur.fetchall()
    ]
    conn.close()
    return rows


def choose_variant(
    variants: list[Variant],
    audits_root: Path,
    client_slug: str,
    variant_set: str = "baseline",
    epsilon: float = 0.1,
) -> Variant | None:
    """
    Epsilon-greedy: with prob epsilon pick random variant, else pick
    best-performing variant by (replies+meetings)/sent.

    If no stats exist, prefer the first variant (baseline) but allow exploration.
    """
    if not variants:
        return None
    dbpath = _db_path(audits_root, client_slug)
    init_learning_db(dbpath)
    # exploration
    if random.random() < epsilon:
        return random.choice(variants)

    # compute scores
    stats = {r["variant_id"]: r for r in get_stats(dbpath)}
    best = None
    best_score = -1.0
    for v in variants:
        s = stats.get(v.id, {})
        sent = s.get("sent", 0) or 0
        replies = s.get("replies", 0) or 0
        meetings = s.get("meetings", 0) or 0
        # conversion-like metric
        score = (replies + meetings) / sent if sent else 0.0
        if score > best_score:
            best_score = score
            best = v

    # If all untried, return first variant
    if best is None:
        return variants[0]
    return best
