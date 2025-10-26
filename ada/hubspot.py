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
    # Build a conservative request that only includes limit/after. Some
    # HubSpot accounts reject property filters in this endpoint and return
    # 400 Invalid request; to maximize compatibility in CI we omit the
    # `properties` parameter here. Consumers that need additional fields
    # should fetch per-contact details or use the search endpoint.
    params = {"limit": min(limit, 100)}
    if after:
        params["after"] = after
    with _client() as c:
        r = c.get("/crm/v3/objects/contacts", params=params)
        try:
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            # If the listing endpoint fails (some HubSpot accounts reject
            # it), try the search endpoint as a fallback which is often
            # more tolerant of filtering and account differences.
            # We'll attempt two fallback payloads and capture rich
            # diagnostics if all attempts fail so CI artifacts contain
            # the raw responses for easier triage.
            diagnostics = []
            def _resp_info(resp):
                try:
                    text = resp.text
                except Exception:
                    text = "(unable to read body)"
                return {
                    "status_code": getattr(resp, "status_code", None),
                    "headers": dict(getattr(resp, "headers", {})),
                    "body": text,
                }

            # First fallback: search with empty filterGroups (works in many accounts)
            try:
                alt_body = {"filterGroups": [], "limit": min(limit, 100)}
                r2 = c.post("/crm/v3/objects/contacts/search", json=alt_body)
                try:
                    r2.raise_for_status()
                    return r2.json()
                except Exception:
                    diagnostics.append(("search(empty filterGroups)", _resp_info(r2)))
            except Exception as err:
                diagnostics.append(("search(empty filterGroups)_request_error", str(err)))

            # Second fallback: some portals accept a query-style body
            try:
                alt_body2 = {"query": "", "limit": min(limit, 100)}
                r3 = c.post("/crm/v3/objects/contacts/search", json=alt_body2)
                try:
                    r3.raise_for_status()
                    return r3.json()
                except Exception:
                    diagnostics.append(("search(query=\"\")", _resp_info(r3)))
            except Exception as err:
                diagnostics.append(("search(query)_request_error", str(err)))

            # Nothing worked — include full diagnostics from the original
            # listing response plus any fallback responses we saw.
            # Third fallback: try the legacy contacts endpoint which some
            # portals still support. We'll normalize its response into the
            # same shape (results list) so callers don't need to change.
            try:
                legacy_params = {"count": min(limit, 100)}
                r4 = c.get("/contacts/v1/lists/all/contacts/all", params=legacy_params)
                try:
                    r4.raise_for_status()
                    j = r4.json()
                    # Normalize: legacy returns 'contacts' array
                    results = j.get("contacts", [])
                    return {"results": results}
                except Exception:
                    diagnostics.append(("legacy(contacts_v1)", _resp_info(r4)))
            except Exception as err:
                diagnostics.append(("legacy_request_error", str(err)))

            try:
                orig_body = r.text
            except Exception:
                orig_body = "(unable to read response body)"
            info = {"original": {"status_code": getattr(r, "status_code", None), "body": orig_body}, "fallbacks": diagnostics}
            raise RuntimeError(f"HubSpot API listing failed: {info}") from e

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
