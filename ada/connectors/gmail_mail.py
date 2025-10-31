from __future__ import annotations

import time
from collections.abc import Iterable
from datetime import datetime
from email.message import EmailMessage

from ada.core import schemas

from .base import TerminalError


class GmailConnector:
    """Minimal Gmail REST-like connector.

    NOTE: This implementation is intentionally light-weight for Phase 1 and
    designed to be testable without live Google APIs. It expects per-client
    credentials to be present in the client config; otherwise it raises
    TerminalError with instructions.
    """

    def __init__(self, client_cfg: dict):
        self.client_cfg = client_cfg or {}
        self.user = self.client_cfg.get("gmail_user")
        self.refresh = self.client_cfg.get("gmail_refresh_token")
        self.client_id = self.client_cfg.get("gmail_client_id")
        self.client_secret = self.client_cfg.get("gmail_client_secret")
        if not (self.user and self.refresh and self.client_id and self.client_secret):
            raise TerminalError(
                
                    "Missing Gmail credentials in client config; set "
                    "gmail_user, gmail_refresh_token, gmail_client_id, gmail_client_secret"
                
            )

    def _build_message(self, subject: str, body: str, to: str) -> EmailMessage:
        m = EmailMessage()
        m["From"] = self.user
        m["To"] = to
        if subject:
            m["Subject"] = subject
        m.set_content(body or "")
        return m

    def draft(self, subject: str, body: str, to: str) -> schemas.Message:
        msg = self._build_message(subject, body, to)
        mid = f"msg_{int(time.time() * 1000)}"
        return schemas.Message(
            id=mid,
            client_slug=self.client_cfg.get("slug", ""),
            contact_id=to,
            channel="gmail",
            role="assistant",
            subject=subject,
            body=body,
            ts=datetime.utcnow(),
            status="draft",
            meta={"mime": msg.as_string()},
        )

    def send(self, message: schemas.Message) -> schemas.Message:
        # In a minimal mode just mark as sent and attach a send_ts
        if message.status not in ("approved", "queued", "draft"):
            message.status = "failed"
            message.meta["error"] = "invalid-status-for-send"
            return message
        # Simulate API latency/backoff boundary
        message.status = "sent"
        message.meta["sent_at"] = datetime.utcnow().isoformat()
        return message

    def list_replies(self, since: datetime) -> Iterable[schemas.Message]:
        # Minimal stub: no live API calls.
        # Real implementation would call Gmail users.messages.list/get and yield Message items.
        return []
