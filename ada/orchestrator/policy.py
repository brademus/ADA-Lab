from __future__ import annotations
from typing import List, Dict
from ada.core.schemas import OutreachPlan, Contact
from datetime import datetime


def build_plan(client_slug: str, contacts: List[Contact], daily_cap: int = 25, limit: int | None = None, variant: str | None = None) -> OutreachPlan:
    """Select top-scored contacts and enforce simple rules.

    - Exclude contacts without email
    - Sort by score descending (None -> 0)
    - Apply daily_cap and optional limit
    """
    scored = [c for c in contacts if c.email]
    scored.sort(key=lambda c: (c.score or 0.0), reverse=True)
    take = min(daily_cap, len(scored)) if limit is None else min(limit, daily_cap, len(scored))
    targets = [c.id for c in scored[:take]]
    return OutreachPlan(client_slug=client_slug, generated_at=datetime.utcnow(), targets=targets, daily_cap=daily_cap, variant=variant or "default")
