from __future__ import annotations

# Outlook Mail connector (stub for Phase 2).
#
# This minimal MS Graph-like connector mirrors the GmailConnector shape and
# is suitable for tests and CI without real network calls.
#
# Expected client config keys (can be provided via ClientConfig.overrides):
# - outlook_user
# - tenant_id
# - client_id
# - client_secret
# - refresh_token
#
# Behavior:
# - draft(): constructs a Message with channel="outlook" and status="draft".
# - send(): transitions approved/draft/queued messages to status="sent" and
#   annotates meta with sent_at; simulates light backoff boundaries.
# - list_replies(since): returns an empty iterable; real implementation would
#   call MS Graph /messages with filters.
#
# Rate limiting and quiet hours policy are handled in higher layers (policy/CLI).
import time
from collections.abc import Iterable
from datetime import datetime
from email.message import EmailMessage

from ada.core import schemas

from .base import TerminalError


class OutlookConnector:
    """Minimal Outlook connector for Phase 2 tests.

    Raises TerminalError if required credentials are missing to surface a clear
    actionable error in dashboards and logs.
    """

    def __init__(self, client_cfg: dict):
        self.client_cfg = client_cfg or {}
        self.user = self.client_cfg.get("outlook_user")
        self.tenant = self.client_cfg.get("tenant_id")
        self.client_id = self.client_cfg.get("client_id")
        self.client_secret = self.client_cfg.get("client_secret")
        self.refresh = self.client_cfg.get("refresh_token")
        # Minimal checks; real implementation would also validate tokens/scopes.
        if not (
            self.user
            and self.tenant
            and self.client_id
            and self.client_secret
            and self.refresh
        ):
            raise TerminalError(
                
                    "Missing Outlook credentials in client config; set "
                    "outlook_user, tenant_id, client_id, client_secret, refresh_token"
                
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
        mid = f"omsg_{int(time.time() * 1000)}"
        _ = self._build_message(subject, body, to)
        return schemas.Message(
            id=mid,
            client_slug=self.client_cfg.get("slug", ""),
            contact_id=to,
            channel="outlook",
            role="assistant",
            subject=subject,
            body=body,
            ts=datetime.utcnow(),
            status="draft",
            meta={"transport": "outlook"},
        )

    def send(self, message: schemas.Message) -> schemas.Message:
        if message.status not in ("approved", "queued", "draft"):
            message.status = "failed"
            message.meta["error"] = "invalid-status-for-send"
            return message
        # Simulate success
        message.status = "sent"
        message.meta["sent_at"] = datetime.utcnow().isoformat()
        return message

    def list_replies(self, since: datetime) -> Iterable[schemas.Message]:
        # Stub: no live API calls in CI
        return []
