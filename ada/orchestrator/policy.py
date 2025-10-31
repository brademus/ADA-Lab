from __future__ import annotations

import re
from datetime import datetime

from ada.core.schemas import Contact, OutreachPlan

_HHMM = re.compile(r"^(\d{2}):(\d{2})-(\d{2}):(\d{2})$")


def _in_quiet_hours(now: datetime, quiet_hours: str | None) -> bool:
    if not quiet_hours:
        return False
    m = _HHMM.match(quiet_hours.strip())
    if not m:
        return False
    sh, sm, eh, em = map(int, m.groups())
    start = sh * 60 + sm
    end = eh * 60 + em
    cur = now.hour * 60 + now.minute
    if start <= end:
        return start <= cur < end
    # window wraps midnight
    return cur >= start or cur < end


def build_plan(
    client_slug: str,
    contacts: list[Contact],
    daily_cap: int = 25,
    limit: int | None = None,
    variant: str | None = None,
    overrides: dict | None = None,
    now: datetime | None = None,
) -> OutreachPlan:
    """Select contacts with policy constraints.

    Rules:
    - Exclude contacts without email.
    - Apply allowlist/blocklist (emails or domains).
    - Enforce per-domain caps from overrides.domain_caps (e.g., {"example.com": 2}).
    - Respect quiet hours window (overrides.quiet_hours like "22:00-08:00").
    - Sort by score desc, then truncate by daily_cap and optional limit.
    Returns an OutreachPlan with reasons_by_contact for skip decisions.
    """
    overrides = overrides or {}
    now = now or datetime.utcnow()
    reasons: dict[str, str] = {}

    allowlist = set(overrides.get("allowlist", []) or [])
    blocklist = set(overrides.get("blocklist", []) or [])
    domain_caps: dict[str, int] = overrides.get("domain_caps", {}) or {}
    quiet_hours = overrides.get("quiet_hours")  # "HH:MM-HH:MM" (UTC)

    # Quiet hours: if active, return empty selection but include reasons on all
    if _in_quiet_hours(now, quiet_hours):
        plan = OutreachPlan(
            client_slug=client_slug,
            generated_at=now,
            targets=[],
            daily_cap=daily_cap,
            variant=variant or "default",
            reasons_by_contact={c.id: "quiet-hours" for c in contacts},
        )
        return plan

    # Filter by email presence
    pool: list[Contact] = [c for c in contacts if c.email]

    # Apply allow/block lists
    def email_or_domain(val: str) -> str:
        return val.lower().strip()

    selected: list[Contact] = []
    for c in pool:
        em = c.email or ""
        dom = em.split("@")[-1].lower() if "@" in em else em.lower()
        entry = email_or_domain(em)
        if blocklist and (entry in blocklist or dom in blocklist):
            reasons[c.id] = "blocklisted"
            continue
        if allowlist and not (entry in allowlist or dom in allowlist):
            reasons[c.id] = "not-allowlisted"
            continue
        selected.append(c)

    # Sort by score desc
    selected.sort(key=lambda c: (c.score or 0.0), reverse=True)

    # Enforce per-domain caps
    taken_by_domain: dict[str, int] = {}
    capped: list[Contact] = []
    for c in selected:
        em = c.email or ""
        dom = em.split("@")[-1].lower() if "@" in em else em.lower()
        cap = domain_caps.get(dom)
        if cap is None:
            capped.append(c)
            continue
        cur = taken_by_domain.get(dom, 0)
        if cur < cap:
            capped.append(c)
            taken_by_domain[dom] = cur + 1
        else:
            reasons[c.id] = f"domain-cap-reached:{dom}"

    # Apply global caps
    max_take = len(capped)
    if limit is not None:
        max_take = min(max_take, limit)
    max_take = min(max_take, daily_cap)
    targets = [c.id for c in capped[:max_take]]
    return OutreachPlan(
        client_slug=client_slug,
        generated_at=now,
        targets=targets,
        daily_cap=daily_cap,
        variant=variant or "default",
        reasons_by_contact=reasons,
    )
