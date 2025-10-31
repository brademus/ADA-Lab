from datetime import datetime

from ada.core.schemas import Contact, Message


def test_contact_roundtrip():
    c = Contact(
        id="1",
        email="a@b.com",
        first_name="A",
        last_name="B",
        owner_id=None,
        lifecycle=None,
        last_modified=None,
        score=1.2,
    )
    d = c.to_dict()
    c2 = Contact.from_dict(d)
    assert c2.email == "a@b.com"


def test_message_fields():
    m = Message(
        id="m1",
        client_slug="acme",
        contact_id="1",
        subject="hi",
        body="hello",
        ts=datetime.utcnow(),
    )
    assert m.status == "draft"
