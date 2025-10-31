from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ada import hubspot
from ada.core.schemas import Contact


@retry(
    wait=wait_exponential(min=1, max=10),
    stop=stop_after_attempt(4),
    retry=retry_if_exception_type(Exception),
)
def _safe_stream(*args, **kwargs):
    return list(hubspot.stream_contacts(*args, **kwargs))


def get_contacts(limit: int = 1000) -> Iterable[Contact]:
    """Yield Contact models converted from hubspot.stream_contacts payloads."""
    props = [
        "email",
        "firstname",
        "lastname",
        "lifecyclestage",
        "hubspot_owner_id",
        "lastmodifieddate",
    ]
    for raw in _safe_stream(max_total=limit, properties=props):
        p = raw.get("properties", {}) or {}
        try:
            lm = p.get("lastmodifieddate")
            lm_ts = datetime.fromtimestamp(int(lm) / 1000, tz=None) if lm else None
        except Exception:
            lm_ts = None
        yield Contact(
            id=str(raw.get("id")),
            email=p.get("email"),
            first_name=p.get("firstname"),
            last_name=p.get("lastname"),
            owner_id=p.get("hubspot_owner_id"),
            lifecycle=p.get("lifecyclestage"),
            last_modified=lm_ts,
            score=None,
            source="hubspot",
        )
