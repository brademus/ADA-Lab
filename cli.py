from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from rich import print

from ada import hubspot
from ada.analysis import owner_rollup, score_contacts
from ada.clients import ClientConfig, get_client, load_clients
from ada.connectors import gmail_mail, hubspot_contacts
from ada.connectors.outlook_mail import OutlookConnector
from ada.core import schemas
from ada.crm import db as crmdb
from ada.dashboard import render_master_index
from ada.learning import variants as variants_engine
from ada.orchestrator import policy, templates
from ada.outbox import DryOutbox, send_approved
from ada.reporting import write_outputs
from ada.store import sqlite as store
from ada.templates import render as tmpl_render
from ada.templates.library import get_variants_for_set
from ada.templates.selector import choose_variant


def cmd_owners(args):
    owners = hubspot.list_owners()
    for o in owners:
        print(
            {
                "id": o.get("id"),
                "email": o.get("email"),
                "firstName": o.get("firstName"),
                "lastName": o.get("lastName"),
            }
        )


def _pull_contacts(limit: int, out_path: Path) -> int:
    # Request a very small, safe set of properties to avoid API errors
    # caused by requesting properties that don't exist in the target
    # HubSpot account. If you need owner load and lastmodifieddate in
    # reports, we can fetch them in a follow-up call per-contact
    # (but keep initial requests conservative for CI reliability).
    props = ["email", "firstname", "lastname", "lifecyclestage"]
    rows = []
    for c in hubspot.stream_contacts(max_total=limit, properties=props):
        p = c.get("properties", {}) or {}
        rows.append(
            {
                "id": c.get("id"),
                "email": p.get("email"),
                "firstName": p.get("firstname"),
                "lastName": p.get("lastname"),
                "lifecyclestage": p.get("lifecyclestage"),
                "ownerId": p.get("hubspot_owner_id"),
                "lastmodifieddate": p.get("lastmodifieddate"),
            }
        )
    pd.DataFrame(rows).to_csv(out_path, index=False)
    return len(rows)


def cmd_pull_contacts(args):
    out = Path(args.out or "contacts.csv")
    n = _pull_contacts(limit=int(args.limit), out_path=out)
    print(f"[green]Wrote {n} contacts → {out}")


def _analyze_csv(csv_path: Path, out_dir: Path, *, pure_html: bool = False) -> None:
    df = pd.read_csv(csv_path)
    df = score_contacts(df)
    _ = owner_rollup(df)
    write_outputs(df, str(out_dir), pure_html=pure_html)
    print(f"[green]Reports written to {out_dir}")


def cmd_analyze(args):
    if args.source != "csv":
        raise SystemExit("Only --source csv is currently supported.")
    pure = bool(getattr(args, "pure_html", False) or getattr(args, "html_only", False))
    _analyze_csv(Path(args.path), Path(args.out_dir), pure_html=pure)


def _run_audit_for_client(
    c: ClientConfig, limit: int, out_root: Path, skip_pull: bool, *, pure_html: bool = False
) -> None:
    c_dir = out_root / c.slug
    c_dir.mkdir(parents=True, exist_ok=True)
    try:
        # Use per-client token only if it validates; otherwise fall back
        # to the global HUBSPOT_TOKEN. This prevents placeholder or
        # malformed per-client tokens in `clients.toml` from breaking the
        # whole audit. We validate by calling a lightweight owners check.
        original_token = os.getenv("HUBSPOT_TOKEN")
        used_per_client_token = False
        if c.hubspot_token:
            os.environ["HUBSPOT_TOKEN"] = c.hubspot_token
            try:
                # lightweight validation; will raise on auth/permission errors
                hubspot.list_owners()
                used_per_client_token = True
                print(f"[blue]Using per-client HubSpot token for {c.slug}")
            except Exception as e:
                # Restore original and continue with global token
                if original_token is not None:
                    os.environ["HUBSPOT_TOKEN"] = original_token
                else:
                    os.environ.pop("HUBSPOT_TOKEN", None)
                print(
                    f"[yellow]Per-client token for {c.slug} failed validation, "
                    f"falling back to global token: {e}"
                )
        contacts_csv = c_dir / "contacts.csv"
        if not skip_pull:
            n = _pull_contacts(limit=limit, out_path=contacts_csv)
            print(f"[blue]{c.name}: downloaded {n} contacts")
        else:
            if not contacts_csv.exists():
                raise FileNotFoundError(
                    f"{contacts_csv} not found (cannot --skip-pull without an existing CSV)"
                )
        _analyze_csv(contacts_csv, c_dir, pure_html=pure_html)
    except Exception as e:
        # Write a full traceback to the per-client error file for easier
        # debugging in CI; also print a short message to the console.
        import traceback

        tb = traceback.format_exc()
        # If this was a HubSpot listing failure, append actionable
        # troubleshooting guidance so the CI artifact is helpful to users.
        guidance = ""
        if isinstance(e, RuntimeError) and "HubSpot API listing failed" in str(e):
            guidance = (
                "\n\n---\nTroubleshooting guidance:\n"
                "- The HubSpot token used may be missing required scopes "
                "(e.g. 'crm.objects.contacts.read').\n"
                "- Some HubSpot portals restrict the v3 listing/search endpoints; consider "
                "providing a per-client 'hubspot_token' in your clients config, or pre-exporting a "
                "'contacts.csv' and using --skip-pull.\n"
                "- You can run 'python cli.py owners' locally to validate the token "
                "and its access.\n"
                "- See the diagnostics above for raw response bodies from the API.\n"
            )
        (c_dir / "error.txt").write_text(tb + guidance, encoding="utf-8")
        print(f"[red]Audit FAILED for {c.name} ({c.slug}) → {type(e).__name__}: {e}")
    finally:
        # Ensure we restore the original HUBSPOT_TOKEN after the client run
        try:
            if "original_token" in locals():
                if original_token is not None:
                    os.environ["HUBSPOT_TOKEN"] = original_token
                else:
                    os.environ.pop("HUBSPOT_TOKEN", None)
        except Exception:
            pass


def cmd_audit(args):
    clients = load_clients(args.config)
    out_root = Path(args.out_root or "audits")
    out_root.mkdir(parents=True, exist_ok=True)
    if args.client and args.all:
        raise SystemExit("Use either --client <slug> or --all (not both).")
    targets = clients if args.all else [get_client(clients, args.client)]
    for c in targets:
        print(f"[bold]Auditing: {c.name} ({c.slug})[/bold]")
        pure = bool(getattr(args, "pure_html", False) or getattr(args, "html_only", False))
        _run_audit_for_client(
            c,
            limit=int(args.limit),
            out_root=out_root,
            skip_pull=bool(args.skip_pull),
            pure_html=pure,
        )
    if args.all:
        render_master_index(clients, out_root, out_root / "index.html")
        print(f"[green]Master dashboard written → {out_root / 'index.html'}")


def _plan_outreach_for_client(c: ClientConfig, limit: int, out_root: Path) -> int:
    c_dir = out_root / c.slug
    c_dir.mkdir(parents=True, exist_ok=True)
    # Pull contacts via connector and score them using existing analysis
    rows = []
    for ct in hubspot_contacts.get_contacts(limit=limit):
        rows.append(ct)
    # Very small in-memory scoring: attach a dummy score if missing
    for r in rows:
        if r.score is None:
            r.score = 0.0
    plan = policy.build_plan(
        c.slug,
        rows,
        daily_cap=getattr(c, "daily_cap", 25),
        limit=limit,
        overrides=getattr(c, "overrides", {}) or {},
    )
    (c_dir / "plan.json").write_text(json.dumps(plan.dict(), default=str), encoding="utf-8")
    return len(plan.targets)


def cmd_outreach_plan(args):
    clients = load_clients(args.config)
    out_root = Path(args.out_root or "audits")
    out_root.mkdir(parents=True, exist_ok=True)
    targets = clients if args.all else [get_client(clients, args.client)]
    total = 0
    for c in targets:
        n = _plan_outreach_for_client(c, limit=int(args.limit), out_root=out_root)
        print(f"[green]{c.slug}: planned {n} targets")
        total += n
    print(f"[blue]Planned total: {total}")


def _mail_connector_for_client(c: ClientConfig):
    cfg = {**c.__dict__}
    if getattr(c, "overrides", None):
        cfg.update(c.overrides)
    channel = cfg.get("channel", "gmail")
    if channel == "outlook":
        return OutlookConnector(cfg)
    return gmail_mail.GmailConnector(cfg)


def cmd_outreach_draft(args):
    clients = load_clients(args.config)
    out_root = Path(args.out_root or "audits")
    targets = clients if args.all else [get_client(clients, args.client)]
    for c in targets:
        c_dir = out_root / c.slug
        plan_path = c_dir / "plan.json"
        if not plan_path.exists():
            print(f"[yellow]No plan for {c.slug}; run outreach plan first")
            continue
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        # load contacts map from last contacts.csv
        contacts_map = {}
        csvp = c_dir / "contacts.csv"
        if csvp.exists():
            import pandas as pd

            df = pd.read_csv(csvp)
            # Replace NaN with None so Pydantic Optional[str]/float fields validate
            # correctly when we construct schema models from CSV rows.
            df = df.where(pd.notnull(df), None)
            for _, r in df.iterrows():
                contacts_map[str(r.get("id"))] = r.to_dict()
        dbpath = c_dir / "outbox.sqlite"
        store.init_db(dbpath)
        count = 0
        # Prepare connector (fail fast and record connector error for dashboard)
        try:
            connector = _mail_connector_for_client(c)
        except Exception as e:
            (c_dir / "connector_error.txt").write_text(str(e), encoding="utf-8")
            print(f"[yellow]Skipping drafts for {c.slug}: {e}")
            continue
        for cid in plan.get("targets", [])[: int(args.limit)]:
            info = contacts_map.get(cid, {})

            # Guard against pandas NaN values coming from CSV by converting them to None
            def _clean(v):
                try:
                    import pandas as pd  # type: ignore

                    return None if pd.isna(v) else v
                except Exception:
                    try:
                        import math

                        return None if isinstance(v, float) and math.isnan(v) else v
                    except Exception:
                        return v

            contact = schemas.Contact(
                id=cid,
                email=_clean(info.get("email")),
                first_name=_clean(info.get("firstName")),
                last_name=_clean(info.get("lastName")),
                owner_id=_clean(info.get("ownerId")),
                lifecycle=_clean(info.get("lifecyclestage")),
                last_modified=None,
                score=None,
            )
            # default render
            subj, body = templates.render(contact, getattr(c, "brand_voice", None))
            # If variant templates exist for this client/variant-set, choose and render per-contact
            variant_set = getattr(args, "variant_set", "baseline")
            try:
                variant_defs = get_variants_for_set(Path("ada/templates/library"), variant_set)
            except Exception:
                variant_defs = []
            chosen_variant = None
            if variant_defs:
                try:
                    chosen_variant = variants_engine.choose_variant(
                        variant_defs, Path(args.out_root or "audits"), c.slug, variant_set
                    )
                    if chosen_variant:
                        subj, body = templates.render_variant(contact, chosen_variant)
                except Exception:
                    chosen_variant = None

            # create draft message and save
            try:
                m = connector.draft(subj, body, contact.email or cid)
            except Exception as e:
                print(f"[red]Failed to draft for {cid}: {e}")
                continue
            # annotate message meta with variant info for learning
            try:
                if chosen_variant is not None:
                    m.meta = m.meta or {}
                    m.meta["variant_id"] = chosen_variant.id
                    m.meta["variant_set"] = variant_set
            except Exception:
                pass
            store.save_message(dbpath, m)
            count += 1
        print(f"[green]{c.slug}: drafted {count} messages")


def cmd_outreach_approve(args):
    clients = load_clients(args.config)
    out_root = Path(args.out_root or "audits")
    targets = clients if args.all else [get_client(clients, args.client)]
    for c in targets:
        dbpath = out_root / c.slug / "outbox.sqlite"
        if not dbpath.exists():
            print(f"[yellow]No outbox for {c.slug}")
            continue
        ids = args.id or []
        # Support CSV via --ids
        if getattr(args, "ids", None):
            ids.extend([s.strip() for s in (args.ids or "").split(",") if s.strip()])
        if args.all:
            rows = store.fetch_pending(dbpath, status="draft", limit=10000)
            ids = [r["id"] for r in rows]
        # Enforce per-client approval cap
        cap = int(
            getattr(c, "overrides", {}).get("daily_cap", 25)
            if getattr(c, "overrides", None)
            else 25
        )
        ids = ids[:cap]
        for mid in ids:
            store.update_status(dbpath, mid, "approved")
        print(f"[green]{c.slug}: approved {len(ids)} messages")


def cmd_outreach_send(args):
    clients = load_clients(args.config)
    out_root = Path(args.out_root or "audits")
    targets = clients if args.all else [get_client(clients, args.client)]
    for c in targets:
        dbpath = out_root / c.slug / "outbox.sqlite"
        if not dbpath.exists():
            print(f"[yellow]No outbox for {c.slug}")
            continue
        pending = store.fetch_pending(dbpath, status="approved", limit=int(args.max))
        sent = 0
        # Prepare connector per client
        try:
            connector = _mail_connector_for_client(c)
        except Exception as e:
            (out_root / c.slug / "connector_error.txt").write_text(str(e), encoding="utf-8")
            print(f"[yellow]Skipping send for {c.slug}: {e}")
            continue
        # Apply per-channel send caps (fallback to daily_cap)
        cfg = {**c.__dict__}
        if getattr(c, "overrides", None):
            cfg.update(c.overrides)
        channel = cfg.get("channel", "gmail")
        cap = int(cfg.get(f"{channel}_cap", cfg.get("daily_cap", 25)))
        for row in pending[:cap]:
            msg = schemas.Message(**{k: row[k] for k in row.keys() if k in row})
            try:
                updated = connector.send(msg)
                store.save_message(dbpath, updated)
                # Log a 'sent' event with channel context
                ev = schemas.Event(
                    id=f"ev_{int(datetime.utcnow().timestamp()*1000)}",
                    client_slug=c.slug,
                    kind="sent",
                    contact_id=updated.contact_id,
                    message_id=updated.id,
                    ts=datetime.utcnow(),
                    meta={"channel": updated.channel},
                )
                store.log_event(dbpath, ev)
                sent += 1
            except Exception as e:
                store.update_status(dbpath, msg.id, "failed", {"error": str(e)})
        print(f"[green]{c.slug}: sent {sent} messages")


def cmd_outreach_replies(args):
    clients = load_clients(args.config)
    out_root = Path(args.out_root or "audits")
    since = datetime.utcnow() - timedelta(days=int(args.since_days))
    targets = clients if args.all else [get_client(clients, args.client)]
    for c in targets:
        dbpath = out_root / c.slug / "outbox.sqlite"
        if not dbpath.exists():
            print(f"[yellow]No outbox for {c.slug}")
            continue
        try:
            conn = _mail_connector_for_client(c)
        except Exception as e:
            print(f"[yellow]Gmail connector not configured for {c.slug}: {e}")
            continue
        replies = conn.list_replies(since)
        cnt = 0
        for r in replies:
            ev = schemas.Event(
                id=f"ev_{int(datetime.utcnow().timestamp()*1000)}",
                client_slug=c.slug,
                kind="replied",
                contact_id=r.contact_id,
                message_id=r.id,
                ts=datetime.utcnow(),
                meta={"channel": r.channel},
            )
            store.log_event(out_root / c.slug / "outbox.sqlite", ev)
            cnt += 1
        print(f"[green]{c.slug}: logged {cnt} replies")


def cmd_outreach_metrics(args):
    clients = load_clients(args.config)
    out_root = Path(args.out_root or "audits")
    targets = clients if args.all else [get_client(clients, args.client)]
    for c in targets:
        dbpath = out_root / c.slug / "outbox.sqlite"
        if not dbpath.exists():
            print(f"[yellow]No outbox for {c.slug}")
            continue
        # roll up basic counts from events table
        import sqlite3

        p = dbpath
        conn = sqlite3.connect(str(p))
        cur = conn.cursor()
        # by-channel contacted (sent messages)
        cur.execute("SELECT channel, COUNT(*) FROM messages WHERE status='sent' GROUP BY channel")
        by_channel_contacted = {row[0]: int(row[1]) for row in cur.fetchall()}
        # by-channel replies (join with messages)
        cur.execute(
            """
            SELECT m.channel, COUNT(*)
            FROM events e
            JOIN messages m ON m.id = e.message_id
            WHERE e.kind='replied'
            GROUP BY m.channel
        """
        )
        by_channel_replies = {row[0]: int(row[1]) for row in cur.fetchall()}
        contacted = sum(by_channel_contacted.values())
        replies = sum(by_channel_replies.values())
        # Variant-level rollups: read messages and events and attribute to variant_id in meta
        cur.execute("SELECT id, meta FROM messages WHERE status='sent'")
        variant_counters = {}
        msg_variant = {}
        for mid, meta_text in cur.fetchall():
            try:
                meta = json.loads(meta_text or "{}")
            except Exception:
                meta = {}
            vid = meta.get("variant_id")
            vset = meta.get("variant_set", "baseline")
            key = (vset, vid)
            msg_variant[mid] = key
            if vid:
                variant_counters.setdefault(
                    key,
                    {
                        "variant_set": vset,
                        "variant_id": vid,
                        "sent": 0,
                        "opens": 0,
                        "replies": 0,
                        "meetings": 0,
                    },
                )
                variant_counters[key]["sent"] += 1

        # scan events for opens/replies/meetings and attribute by message->variant
        cur.execute("SELECT kind, message_id FROM events")
        for kind, mid in cur.fetchall():
            key = msg_variant.get(mid)
            if not key:
                continue
            counters = variant_counters.get(key)
            if not counters:
                continue
            if kind == "replied":
                counters["replies"] += 1
            elif kind == "opened":
                counters["opens"] += 1
            elif kind in ("meeting", "booked_meeting"):
                counters["meetings"] += 1

        conn.close()
        metrics = {
            "client_slug": c.slug,
            "window": "day",
            "contacts": 0,
            "contacted": contacted,
            "replies": replies,
            "meetings": 0,
            "open_rate": 0.0,
            "reply_rate": (replies / contacted) if contacted else 0.0,
            "conversion_rate": 0.0,
            "ts": datetime.utcnow().isoformat(),
            "contacted_by_channel": by_channel_contacted,
            "replies_by_channel": by_channel_replies,
            "meetings_by_channel": {},
            # variant-level performance
            "variant_perf": list(variant_counters.values()),
        }
        (out_root / c.slug / "outreach_metrics.json").write_text(
            json.dumps(metrics, indent=2), encoding="utf-8"
        )
        print(f"[green]{c.slug}: metrics written (contacted={contacted}, replies={replies})")


def _ensure_client_context(slug: str, config_path: str | None) -> ClientConfig:
    if config_path and Path(config_path).exists():
        return get_client(load_clients(config_path), slug)
    # Fallback minimal ClientConfig-like object
    from types import SimpleNamespace

    return SimpleNamespace(
        slug=slug, name=slug, overrides={}, brand_voice="Confident, concise, helpful."
    )


def _ingest_contacts_for_client(
    slug: str, out_root: Path, limit: int, *, csv_only: bool = False
) -> int:
    c_dir = out_root / slug
    c_dir.mkdir(parents=True, exist_ok=True)
    dbpath = c_dir / "outbox.sqlite"
    crmdb.init_db(dbpath)
    # Create minimal business record
    crmdb.upsert_business(dbpath, bid=f"biz_{slug}", slug=slug, name=slug)
    # Prefer CSV if present; else HubSpot if token; else synthesize a small csv
    csvp = c_dir / "contacts.csv"
    rows = []
    if csvp.exists():
        df = pd.read_csv(csvp)
        df = df.where(pd.notnull(df), None)
        for _, r in df.head(limit).iterrows():
            rows.append(
                {
                    "id": str(r.get("id") or f"ct_{_}"),
                    "name": ((r.get("firstName") or "") + " " + (r.get("lastName") or "")).strip()
                    or (r.get("email") or "Contact"),
                    "title": r.get("title") or "",
                    "email": r.get("email"),
                    "company": r.get("company") or "",
                    "domain": (r.get("email") or "").split("@")[-1] if r.get("email") else "",
                    "size": r.get("company_size") or "",
                }
            )
    else:
        token = os.getenv("HUBSPOT_TOKEN")
        if token and not csv_only:
            try:
                # Use conservative property set
                props = ["email", "firstname", "lastname", "jobtitle", "company", "lifecyclestage"]
                i = 0
                for c in hubspot.stream_contacts(max_total=limit, properties=props):
                    p = c.get("properties", {}) or {}
                    rows.append(
                        {
                            "id": c.get("id") or f"ct_{i}",
                            "name": (
                                (p.get("firstname") or "") + " " + (p.get("lastname") or "")
                            ).strip()
                            or (p.get("email") or "Contact"),
                            "title": p.get("jobtitle") or "",
                            "email": p.get("email"),
                            "company": p.get("company") or "",
                            "domain": (
                                (p.get("email") or "").split("@")[-1] if p.get("email") else ""
                            ),
                            "size": "",
                        }
                    )
                    i += 1
            except Exception:
                # Fallback to synthetic on any hubspot failure
                rows = []
        if not rows:
            # Synthesize a tiny set for CI smoke
            domains = ["example.com", "acme.io", "contoso.com", "widgets.co"]
            for i in range(int(limit)):
                rows.append(
                    {
                        "id": f"ct_{i}",
                        "name": f"Test User {i}",
                        "title": "Head of Growth" if i % 2 == 0 else "Marketing Manager",
                        "email": f"user{i}@{domains[i % len(domains)]}",
                        "company": f"Company {i}",
                        "domain": domains[i % len(domains)],
                        "size": "50-200" if i % 2 == 0 else "200-1000",
                    }
                )
            # Also write a csv for visibility
            pd.DataFrame(rows).to_csv(csvp, index=False)
    # Persist contacts
    for r in rows:
        crmdb.upsert_company(
            dbpath,
            cid=f"co_{r['domain'] or r['company'] or 'na'}",
            bid=f"biz_{slug}",
            name=r["company"] or r["domain"] or "N/A",
            domain=r["domain"] or None,
            size=r.get("size") or None,
        )
        crmdb.upsert_contact(
            dbpath,
            cid=str(r["id"]),
            bid=f"biz_{slug}",
            company_id=f"co_{r['domain'] or r['company'] or 'na'}",
            name=r["name"],
            title=r.get("title"),
            email=r.get("email"),
            origin=(
                "csv"
                if csvp.exists()
                else ("hubspot" if os.getenv("HUBSPOT_TOKEN") else "synthetic")
            ),
        )
    return len(rows)


def _score_contacts(slug: str, out_root: Path) -> int:
    # naive scoring based on title/company size/email domain
    import sqlite3

    dbpath = out_root / slug / "outbox.sqlite"
    conn = sqlite3.connect(str(dbpath))
    cur = conn.cursor()
    cur.execute("SELECT id, title, email FROM contacts")
    rows = cur.fetchall()
    conn.close()
    n = 0
    for cid, title, email in rows:
        score = 50.0
        t = (title or "").lower()
        if any(k in t for k in ["head", "director", "vp", "chief"]):
            score += 20
        if any(k in t for k in ["growth", "marketing", "demand", "sales"]):
            score += 10
        domain = (email or "").split("@")[-1] if email else ""
        if domain.endswith(".io") or domain.endswith(".ai"):
            score += 5
        score = min(score, 99.0)
        crmdb.update_fit_score(dbpath, cid, score)
        n += 1
    return n


def _draft_emails(slug: str, out_root: Path, limit: int, brand_voice: str) -> int:
    import sqlite3

    dbpath = out_root / slug / "outbox.sqlite"
    conn = sqlite3.connect(str(dbpath))
    cur = conn.cursor()
    cur.execute(
        "SELECT id, name, title, email, fit_score FROM contacts ORDER BY fit_score DESC NULLS LAST"
    )
    contacts = cur.fetchall()
    conn.close()
    count = 0
    for _idx, (cid, name, title, email, fit_score) in enumerate(contacts[:limit]):
        first_name = (name or "").split(" ")[0] if name else "there"
        size = ""  # kept simple for now
        variant = choose_variant(float(fit_score or 0.0), size)
        ctx = {
            "first_name": first_name,
            "company": (email or "").split("@")[-1].split(".")[0].title() if email else "your team",
            "title": title or "",
            "brand_voice": brand_voice,
            "value_prop": "book more qualified meetings faster",
            "value_hint": "more pipeline with less manual work",
            "peer_group": "similar",
            "value_metric": "reply rates",
            "value_amount": "20–40% in 30 days",
            "sender_name": "ADA",
        }
        subj, body = tmpl_render.render_template(
            "short" if variant == "short" else ("medium" if variant == "medium" else "value"), ctx
        )
        crmdb.insert_email_draft(
            dbpath, eid=f"em_{cid}", bid=f"biz_{slug}", contact_id=cid, subject=subj, body=body
        )
        count += 1
    return count


def _emit_metrics(slug: str, out_root: Path) -> None:
    dbpath = out_root / slug / "outbox.sqlite"
    m = crmdb.compute_metrics(dbpath)
    out = out_root / slug / "outreach_metrics.json"
    out.write_text(json.dumps(m, indent=2), encoding="utf-8")


def cmd_autopilot(args):
    slug = args.client
    out_root = Path(args.out_root or "audits")
    out_root.mkdir(parents=True, exist_ok=True)
    limit = int(args.limit)
    c = _ensure_client_context(slug, getattr(args, "config", None))
    c_dir = out_root / slug
    c_dir.mkdir(parents=True, exist_ok=True)
    err_file = c_dir / "error.txt"
    try:
        n = _ingest_contacts_for_client(
            slug, out_root, limit, csv_only=bool(getattr(args, "csv_only", False))
        )
        print(f"[blue]{slug}: ingested {n} contacts")
        _ = _score_contacts(slug, out_root)
        drafted = _draft_emails(
            slug, out_root, limit, getattr(c, "brand_voice", "Confident, concise, helpful.")
        )
        print(f"[blue]{slug}: drafted {drafted} emails")
        if getattr(args, "approve_ids", None):
            ids = [s.strip() for s in (args.approve_ids or "").split(",") if s.strip()]
            crmdb.approve_emails(c_dir / "outbox.sqlite", ids)
        else:
            # Approve top N drafts by default
            # Direct SQL to mark some 'draft' rows as 'approved'
            import sqlite3

            conn = sqlite3.connect(str(c_dir / "outbox.sqlite"))
            cur = conn.cursor()
            cur.execute(
                "UPDATE emails SET status='approved' WHERE status='draft' LIMIT ?", (limit,)
            )
            conn.commit()
            conn.close()
        sent = 0
        if bool(args.send_now):
            sent = send_approved(c_dir / "outbox.sqlite", DryOutbox(), limit=limit)
            print(f"[green]{slug}: sent {sent} emails (dry)")
        # replies simulation
        if getattr(args, "replies_since", None):
            try:
                crmdb.simulate_replies(c_dir / "outbox.sqlite", since_days=int(args.replies_since))
            except Exception:
                pass
        _emit_metrics(slug, out_root)
        print(f"[green]{slug}: metrics emitted → {c_dir / 'outreach_metrics.json'}")
    except Exception as e:
        import traceback

        err_file.write_text(traceback.format_exc(), encoding="utf-8")
        print(f"[red]Autopilot FAILED for {slug}: {e}")
        import sys

        sys.exit(2)


def main():
    ap = argparse.ArgumentParser("ada")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p0 = sub.add_parser("owners", help="List HubSpot owners")
    p0.set_defaults(func=cmd_owners)
    p1 = sub.add_parser("pull-contacts", help="Pull contacts from HubSpot")
    p1.add_argument("--limit", default="2000")
    p1.add_argument("--out", default="contacts.csv")
    p1.set_defaults(func=cmd_pull_contacts)
    p2 = sub.add_parser("analyze", help="Analyze contacts CSV → reports")
    p2.add_argument("--source", choices=["csv"], default="csv")
    p2.add_argument("--path", required=True)
    p2.add_argument("--out-dir", default="reports")
    p2.add_argument("--pure-html", action="store_true", help="Deprecated alias; use --html-only")
    p2.add_argument(
        "--html-only",
        action="store_true",
        help="Write summary.html using a pure-HTML fallback (no markdown conversion)",
    )
    p2.set_defaults(func=cmd_analyze)
    p3 = sub.add_parser("audit", help="Consultant Mode: multi-client batch audits")
    scope = p3.add_mutually_exclusive_group(required=True)
    scope.add_argument("--client", help="Client slug to audit (e.g., acme_corp)")
    scope.add_argument("--all", action="store_true", help="Run for all clients in config")
    p3.add_argument("--config", required=True, help="Path to clients.toml / .yaml")
    p3.add_argument("--limit", default="5000", help="Contact limit per client")
    p3.add_argument("--out-root", default="audits", help="Root directory for per-client outputs")
    p3.add_argument(
        "--skip-pull", action="store_true", help="Skip HubSpot pull and reuse existing contacts.csv"
    )
    p3.add_argument("--pure-html", action="store_true", help="Deprecated alias; use --html-only")
    p3.add_argument(
        "--html-only",
        action="store_true",
        help="Write summary.html using a pure-HTML fallback (no markdown conversion)",
    )
    p3.set_defaults(func=cmd_audit)
    # Outreach subcommands (Universal AI Closer Phase 1)
    p_out = sub.add_parser(
        "outreach", help="Outreach workflow: plan, draft, approve, send, replies, metrics"
    )
    out_sub = p_out.add_subparsers(dest="out_cmd", required=True)
    po = out_sub.add_parser("plan", help="Build outreach plan")
    po.add_argument("--client", help="Client slug")
    po.add_argument("--all", action="store_true")
    po.add_argument("--config", required=True)
    po.add_argument("--limit", default="200", help="Limit contacts to consider")
    po.add_argument("--out-root", default="audits")
    po.set_defaults(func=cmd_outreach_plan)

    pdraft = out_sub.add_parser("draft", help="Draft messages for a plan")
    pdraft.add_argument("--client")
    pdraft.add_argument("--all", action="store_true")
    pdraft.add_argument("--config", required=True)
    pdraft.add_argument("--limit", default="50")
    pdraft.add_argument(
        "--variant-set", default="baseline", help="Variant set to use for A/B testing"
    )
    pdraft.add_argument("--out-root", default="audits")
    pdraft.set_defaults(func=cmd_outreach_draft)

    papprove = out_sub.add_parser("approve", help="Approve drafted messages")
    papprove.add_argument("--client")
    papprove.add_argument("--all", action="store_true")
    papprove.add_argument("--config", required=True)
    papprove.add_argument("--id", action="append")
    papprove.add_argument("--ids", help="CSV of message IDs to approve")
    papprove.add_argument("--out-root", default="audits")
    papprove.set_defaults(func=cmd_outreach_approve)

    psend = out_sub.add_parser("send", help="Send approved messages (requires Gmail creds)")
    psend.add_argument("--client")
    psend.add_argument("--all", action="store_true")
    psend.add_argument("--config", required=True)
    psend.add_argument("--max", default="25")
    psend.add_argument("--out-root", default="audits")
    psend.set_defaults(func=cmd_outreach_send)

    preplies = out_sub.add_parser("replies", help="Ingest replies since N days")
    preplies.add_argument("--client")
    preplies.add_argument("--all", action="store_true")
    preplies.add_argument("--config", required=True)
    preplies.add_argument("--since-days", default="7")
    preplies.add_argument("--out-root", default="audits")
    preplies.set_defaults(func=cmd_outreach_replies)

    pmetrics = out_sub.add_parser("metrics", help="Roll up outreach metrics")
    pmetrics.add_argument("--client")
    pmetrics.add_argument("--all", action="store_true")
    pmetrics.add_argument("--config", required=True)
    pmetrics.add_argument("--out-root", default="audits")
    pmetrics.set_defaults(func=cmd_outreach_metrics)
    # Autopilot (ADA 2.0 substrate)
    p_auto = sub.add_parser(
        "autopilot",
        help="ADA 2.0 Autopilot: ingest, score, draft, approve/send, simulate replies, metrics",
    )
    p_auto.add_argument("--client", required=True, help="Client slug (e.g., acme)")
    p_auto.add_argument("--config", help="Optional clients config (toml/yaml)")
    p_auto.add_argument("--limit", default="50")
    p_auto.add_argument("--approve-ids", help="CSV of email IDs to approve")
    p_auto.add_argument(
        "--send-now",
        action="store_true",
        help="Send immediately after draft approval (dry by default)",
    )
    p_auto.add_argument("--replies-since", default=None, help="Simulate replies in last N days")
    p_auto.add_argument(
        "--csv-only",
        action="store_true",
        help="Do not call HubSpot even if token is present; use CSV or synthetic",
    )
    p_auto.add_argument("--out-root", default="audits")
    p_auto.set_defaults(func=cmd_autopilot)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
