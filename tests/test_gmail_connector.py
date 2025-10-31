import pytest

from ada.connectors.base import TerminalError
from ada.connectors.gmail_mail import GmailConnector
from ada.core.schemas import Message


def test_gmail_connector_missing_creds():
    with pytest.raises(TerminalError):
        GmailConnector({})


def test_gmail_connector_draft_and_send():
    cfg = {
        "gmail_user": "me@example.com",
        "gmail_refresh_token": "refresh",
        "gmail_client_id": "cid",
        "gmail_client_secret": "secret",
        "slug": "acme",
    }
    g = GmailConnector(cfg)
    m = g.draft("Subject", "Body text", "you@example.com")
    assert isinstance(m, Message)
    assert m.status == "draft"
    s = g.send(m)
    assert s.status == "sent"
