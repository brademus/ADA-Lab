from __future__ import annotations
import os
from typing import Dict, List, Optional
import httpx
from tenacity import retry, wait_exponential, stop_after_attempt

API = "https://api.hubapi.com"

def _token() -> str:
    t = os.getenv("HUBSPOT_TOKEN")
    if not t:
        raise RuntimeError("HUBSPOT_TOKEN is not set")
    return t

def _client() -> httpx.Client:
    return httpx.Client(
        base_url=API,
        headers={"Authorization": f"Bearer {_token()}", "Content-Type": "application/json"},
        timeout=30.0,
    )

@retry(wait=wait_exponential(min=1, max=10), stop=stop_after_attempt(5))
def list_owners() -> List[Dict]:
    with _client() as c:
        r = c.get("/crm/v3/owners")
        r.raise_for_status()
        return r.json().get("results", [])

@retry(wait=wait_exponential(min=1, max=10), stop=stop_after_attempt(5))
def list_contacts(limit:int=200, after:Optional[str]=None, properties:Optional[List[str]]=None) -> Dict:
    # Use repeated 'properties' query params instead of a single
    # comma-separated value. HubSpot's API accepts both, but some
    # requests can return 400 for the comma form; sending as a list
    # of tuples matches the server's expectations and avoids that error.
    params: List[tuple] = [("limit", str(min(limit, 100)))]
    if properties:
        for p in properties:
            params.append(("properties", p))
    if after:
        params.append(("after", after))
    with _client() as c:
        r = c.get("/crm/v3/objects/contacts", params=params)
        r.raise_for_status()
        return r.json()

def stream_contacts(max_total:int=2000, properties:Optional[List[str]]=None):
    total, after = 0, None
    while total < max_total:
        page = list_contacts(limit=100, after=after, properties=properties)
        for row in page.get("results", []):
            yield row
            total += 1
            if total >= max_total: return
        after = page.get("paging", {}).get("next", {}).get("after")
        if not after: break
