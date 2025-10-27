from ada.orchestrator.policy import build_plan
from ada.core.schemas import Contact
from datetime import datetime

def mkc(i: int, email: str, score: float = 0.0) -> Contact:
    return Contact(id=str(i), email=email, first_name=None, last_name=None, owner_id=None, lifecycle=None, last_modified=None, score=score)


def test_quiet_hours_blocks_all():
    contacts = [mkc(i, f"u{i}@x.com", score=float(i)) for i in range(5)]
    plan = build_plan(
        "acme",
        contacts,
        daily_cap=10,
        overrides={"quiet_hours": "22:00-23:59"},
        now=datetime(2025, 1, 1, 22, 30, 0),
    )
    assert plan.targets == []
    # reasons_by_contact should be populated with quiet-hours for each contact
    assert len(plan.reasons_by_contact) == len(contacts)
    assert set(plan.reasons_by_contact.values()) == {"quiet-hours"}


def test_domain_caps_and_blocklist():
    contacts = [
        mkc(1, "a@x.com", 9.0),
        mkc(2, "b@x.com", 8.0),
        mkc(3, "c@y.com", 7.0),
        mkc(4, "d@y.com", 6.0),
        mkc(5, "e@y.com", 5.0),
    ]
    plan = build_plan(
        "acme",
        contacts,
        daily_cap=10,
        overrides={
            "domain_caps": {"y.com": 2},
            "blocklist": ["b@x.com"],
        },
        now=datetime(2025, 1, 1, 12, 0, 0),
    )
    # b@x.com should be blocked; y.com capped at 2 picks top 2 by score
    assert set(plan.targets) == {"1", "3", "4"}
