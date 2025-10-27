from __future__ import annotations
from typing import Iterable, Protocol
from ada.core.schemas import Contact, Message
from datetime import datetime


class RetryableError(Exception):
    """Transient error that may succeed if retried."""


class TerminalError(Exception):
    """Non-recoverable error; user-facing guidance should be included."""


class CRMConnector(Protocol):
    def get_contacts(self, limit: int = 1000) -> Iterable[Contact]:
        """Yield Contact objects from a CRM.

        Implementations should stream results and be defensive about missing
        fields.
        """


class MailConnector(Protocol):
    def draft(self, subject: str, body: str, to: str) -> Message:
        """Return a Message object in status `draft`."""

    def send(self, message: Message) -> Message:
        """Send a prepared message and return updated Message (status, meta)."""

    def list_replies(self, since: datetime) -> Iterable[Message]:
        """List incoming messages/replies since a cutoff."""
