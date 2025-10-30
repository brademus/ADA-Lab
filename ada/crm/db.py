from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
import sqlite3
from datetime import datetime


def _connect(dbpath: Path) -> sqlite3.Connection:
    dbpath.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(dbpath))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(dbpath: Path) -> None:
    conn = _connect(dbpath)
    cur = conn.cursor()
    cur.executescript(
        """
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS businesses (
            id TEXT PRIMARY KEY,
            slug TEXT UNIQUE,
            name TEXT,
            brand_voice TEXT,
            outreach_mode TEXT,
            daily_send_cap INTEGER DEFAULT 25,
            created_at TEXT,
            updated_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_businesses_slug ON businesses(slug);

        CREATE TABLE IF NOT EXISTS companies (
            id TEXT PRIMARY KEY,
            business_id TEXT,
            name TEXT,
            domain TEXT,
            size TEXT,
            location TEXT,
            industry TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_companies_business ON companies(business_id);
        CREATE INDEX IF NOT EXISTS idx_companies_domain ON companies(domain);

        CREATE TABLE IF NOT EXISTS contacts (
            id TEXT PRIMARY KEY,
            business_id TEXT,
            company_id TEXT,
            name TEXT,
            title TEXT,
            email TEXT,
            phone TEXT,
            fit_score REAL,
            status TEXT,
            origin TEXT,
            last_activity TEXT,
            ada_generated INTEGER DEFAULT 0,
            created_at TEXT,
            updated_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_contacts_business ON contacts(business_id);
        CREATE INDEX IF NOT EXISTS idx_contacts_company ON contacts(company_id);
        CREATE INDEX IF NOT EXISTS idx_contacts_email ON contacts(email);

        CREATE TABLE IF NOT EXISTS emails (
            id TEXT PRIMARY KEY,
            business_id TEXT,
            contact_id TEXT,
            subject TEXT,
            body TEXT,
            mode TEXT,
            status TEXT,
            sent_at TEXT,
            delivered_at TEXT,
            opened_at TEXT,
            replied_at TEXT,
            reply_class TEXT,
            thread_id TEXT,
            error TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_emails_business ON emails(business_id);
        CREATE INDEX IF NOT EXISTS idx_emails_contact ON emails(contact_id);
        CREATE INDEX IF NOT EXISTS idx_emails_status ON emails(status);

        CREATE TABLE IF NOT EXISTS activities (
            id TEXT PRIMARY KEY,
            business_id TEXT,
            contact_id TEXT,
            type TEXT,
            note TEXT,
            ts_utc TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_activities_business ON activities(business_id);

        CREATE TABLE IF NOT EXISTS deals (
            id TEXT PRIMARY KEY,
            business_id TEXT,
            contact_id TEXT,
            stage TEXT,
            value REAL,
            created_at TEXT,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS settings (
            id TEXT PRIMARY KEY,
            business_id TEXT,
            k TEXT,
            v TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_settings_business ON settings(business_id);
        """
    )
    conn.commit(); conn.close()


def upsert_business(dbpath: Path, bid: str, slug: str, name: str, brand_voice: Optional[str] = None, daily_send_cap: int = 25) -> None:
    now = datetime.utcnow().isoformat()
    conn = _connect(dbpath); cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO businesses(id, slug, name, brand_voice, outreach_mode, daily_send_cap, created_at, updated_at)
        VALUES (?, ?, ?, ?, 'email', ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET slug=excluded.slug, name=excluded.name, brand_voice=excluded.brand_voice,
            daily_send_cap=excluded.daily_send_cap, updated_at=excluded.updated_at
        """,
        (bid, slug, name, brand_voice or '', daily_send_cap, now, now),
    )
    conn.commit(); conn.close()


def upsert_company(dbpath: Path, cid: str, bid: str, name: str, domain: Optional[str] = None, size: Optional[str] = None) -> None:
    conn = _connect(dbpath); cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO companies(id, business_id, name, domain, size)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET business_id=excluded.business_id, name=excluded.name, domain=excluded.domain, size=excluded.size
        """,
        (cid, bid, name, domain or '', size or ''),
    )
    conn.commit(); conn.close()


def upsert_contact(dbpath: Path, cid: str, bid: str, company_id: Optional[str], name: str, title: Optional[str], email: Optional[str], origin: str = 'csv') -> None:
    now = datetime.utcnow().isoformat()
    conn = _connect(dbpath); cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO contacts(id, business_id, company_id, name, title, email, status, origin, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, 'new', ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET company_id=excluded.company_id, name=excluded.name, title=excluded.title, email=excluded.email, updated_at=excluded.updated_at
        """,
        (cid, bid, company_id, name, title or '', email or '', origin, now, now),
    )
    conn.commit(); conn.close()


def update_fit_score(dbpath: Path, cid: str, score: float) -> None:
    conn = _connect(dbpath); cur = conn.cursor()
    cur.execute("UPDATE contacts SET fit_score=? WHERE id=?", (float(score), cid))
    conn.commit(); conn.close()


def insert_email_draft(dbpath: Path, eid: str, bid: str, contact_id: str, subject: str, body: str, mode: str = 'email') -> None:
    conn = _connect(dbpath); cur = conn.cursor()
    cur.execute(
        """
        INSERT OR REPLACE INTO emails(id, business_id, contact_id, subject, body, mode, status)
        VALUES (?, ?, ?, ?, ?, ?, 'draft')
        """,
        (eid, bid, contact_id, subject, body, mode),
    )
    conn.commit(); conn.close()


def approve_emails(dbpath: Path, ids: Iterable[str]) -> int:
    conn = _connect(dbpath); cur = conn.cursor(); n=0
    for mid in ids:
        cur.execute("UPDATE emails SET status='approved' WHERE id=?", (mid,))
        n += cur.rowcount
    conn.commit(); conn.close(); return n


def fetch_drafts(dbpath: Path, limit: int) -> List[sqlite3.Row]:
    conn = _connect(dbpath); cur = conn.cursor()
    cur.execute("SELECT * FROM emails WHERE status='approved' LIMIT ?", (limit,))
    rows = cur.fetchall(); conn.close(); return rows


def mark_sent(dbpath: Path, mid: str) -> None:
    conn = _connect(dbpath); cur = conn.cursor()
    cur.execute("UPDATE emails SET status='sent', sent_at=? WHERE id=?", (datetime.utcnow().isoformat(), mid))
    conn.commit(); conn.close()


def simulate_replies(dbpath: Path, since_days: int = 7) -> int:
    # Mark some sent emails as replied with synthetic classes
    import random
    conn = _connect(dbpath); cur = conn.cursor()
    cur.execute("SELECT id FROM emails WHERE status='sent'")
    rows = [r[0] for r in cur.fetchall()]
    cnt = 0
    for mid in rows:
        if random.random() < 0.2:  # 20% reply rate
            cls = random.choice(['positive', 'meeting', 'objection', 'not_now', 'ooo', 'unsub'])
            cur.execute("UPDATE emails SET replied_at=?, reply_class=? WHERE id=?", (datetime.utcnow().isoformat(), cls, mid))
            cnt += 1
    conn.commit(); conn.close(); return cnt


def compute_metrics(dbpath: Path) -> Dict[str, Any]:
    conn = _connect(dbpath); cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM emails WHERE status='draft'"); drafted = int(cur.fetchone()[0] or 0)
    cur.execute("SELECT COUNT(*) FROM emails WHERE status='sent'"); sent = int(cur.fetchone()[0] or 0)
    cur.execute("SELECT COUNT(*) FROM emails WHERE reply_class IS NOT NULL"); replies = int(cur.fetchone()[0] or 0)
    cur.execute("SELECT COUNT(*) FROM emails WHERE reply_class='meeting'"); meetings = int(cur.fetchone()[0] or 0)
    conn.close()
    return {
        'emails_drafted': drafted,
        'emails_sent': sent,
        'replies': replies,
        'meetings': meetings,
        'reply_rate': (replies / sent) if sent else 0.0,
    }
