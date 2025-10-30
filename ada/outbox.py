from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol
from pathlib import Path
from .crm import db as crmdb


@dataclass
class Outbound:
    id: str
    to: str
    subject: str
    body: str


class Provider(Protocol):
    def send(self, msg: Outbound) -> None: ...


class DryOutbox:
    def send(self, msg: Outbound) -> None:
        # For now just print; persistence handled by DB helpers
        print(f"[dry-send] to={msg.to} subj={msg.subject[:60]!r}")


def send_approved(dbpath: Path, provider: Provider, limit: int = 50) -> int:
    rows = crmdb.fetch_drafts(dbpath, limit)
    sent = 0
    for r in rows:
        msg = Outbound(id=r["id"], to="", subject=r["subject"], body=r["body"])  # 'to' not stored yet
        provider.send(msg)
        crmdb.mark_sent(dbpath, r["id"])
        sent += 1
    return sent
