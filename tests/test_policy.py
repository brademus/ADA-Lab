from ada.orchestrator.policy import build_plan
from ada.core.schemas import Contact
from datetime import datetime


def test_build_plan_respects_cap():
    contacts = [Contact(id=str(i), email=f"u{i}@x.com", first_name=None, last_name=None, owner_id=None, lifecycle=None, last_modified=None, score=float(i)) for i in range(10)]
    plan = build_plan("acme", contacts, daily_cap=3)
    assert len(plan.targets) == 3
    # ensure top scored chosen
    assert plan.targets == ["9", "8", "7"]
