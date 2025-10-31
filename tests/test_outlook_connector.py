import pytest

from ada.connectors.base import TerminalError
from ada.connectors.outlook_mail import OutlookConnector
from ada.core.schemas import Message


def test_outlook_connector_missing_creds():
    with pytest.raises(TerminalError):
        OutlookConnector({})


def test_outlook_connector_draft_and_send():
    cfg = {
        "outlook_user": "me@example.com",
        "tenant_id": "t",
        "client_id": "cid",
        "client_secret": "secret",
        "refresh_token": "refresh",
        "slug": "acme",
    }
    oc = OutlookConnector(cfg)
    m = oc.draft("Hi", "Body", "you@example.com")
    assert isinstance(m, Message)
    assert m.status == "draft"
    s = oc.send(m)
    assert s.status == "sent"
