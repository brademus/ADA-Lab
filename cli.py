from __future__ import annotations
import argparse, os
from pathlib import Path
import pandas as pd
from rich import print
from ada import hubspot
from ada.analysis import score_contacts, owner_rollup
from ada.reporting import write_outputs
from ada.clients import load_clients, get_client, ClientConfig
from ada.dashboard import render_master_index

def cmd_owners(args):
    owners = hubspot.list_owners()
    for o in owners:
        print({"id": o.get("id"), "email": o.get("email"), "firstName": o.get("firstName"), "lastName": o.get("lastName")})

def _pull_contacts(limit: int, out_path: Path) -> int:
    props = ["email","firstname","lastname","lifecyclestage","hs_object_id","hubspot_owner_id","lastmodifieddate"]
    rows = []
    for c in hubspot.stream_contacts(max_total=limit, properties=props):
        p = c.get("properties", {}) or {}
        rows.append({
            "id": c.get("id"),
            "email": p.get("email"),
            "firstName": p.get("firstname"),
            "lastName": p.get("lastname"),
            "lifecyclestage": p.get("lifecyclestage"),
            "ownerId": p.get("hubspot_owner_id"),
            "lastmodifieddate": p.get("lastmodifieddate"),
        })
    pd.DataFrame(rows).to_csv(out_path, index=False)
    return len(rows)

def cmd_pull_contacts(args):
    out = Path(args.out or "contacts.csv")
    n = _pull_contacts(limit=int(args.limit), out_path=out)
    print(f"[green]Wrote {n} contacts → {out}")

def _analyze_csv(csv_path: Path, out_dir: Path) -> None:
    df = pd.read_csv(csv_path)
    df = score_contacts(df)
    _ = owner_rollup(df)
    write_outputs(df, str(out_dir))
    print(f"[green]Reports written to {out_dir}")

def cmd_analyze(args):
    if args.source != "csv":
        raise SystemExit("Only --source csv is currently supported.")
    _analyze_csv(Path(args.path), Path(args.out_dir))

def _run_audit_for_client(c: ClientConfig, limit: int, out_root: Path, skip_pull: bool) -> None:
    c_dir = out_root / c.slug
    c_dir.mkdir(parents=True, exist_ok=True)
    try:
        os.environ["HUBSPOT_TOKEN"] = c.hubspot_token
        contacts_csv = c_dir / "contacts.csv"
        if not skip_pull:
            n = _pull_contacts(limit=limit, out_path=contacts_csv)
            print(f"[blue]{c.name}: downloaded {n} contacts")
        else:
            if not contacts_csv.exists():
                raise FileNotFoundError(f"{contacts_csv} not found (cannot --skip-pull without an existing CSV)")
        _analyze_csv(contacts_csv, c_dir)
    except Exception as e:
        (c_dir / "error.txt").write_text(f"{type(e).__name__}: {e}", encoding="utf-8")
        print(f"[red]Audit FAILED for {c.name} ({c.slug}) → {e}")

def cmd_audit(args):
    clients = load_clients(args.config)
    out_root = Path(args.out_root or "audits"); out_root.mkdir(parents=True, exist_ok=True)
    if args.client and args.all:
        raise SystemExit("Use either --client <slug> or --all (not both).")
    targets = clients if args.all else [get_client(clients, args.client)]
    for c in targets:
        print(f"[bold]Auditing: {c.name} ({c.slug})[/bold]")
        _run_audit_for_client(c, limit=int(args.limit), out_root=out_root, skip_pull=bool(args.skip_pull))
    if args.all:
        render_master_index(clients, out_root, out_root / "index.html")
        print(f"[green]Master dashboard written → {out_root / 'index.html'}")

def main():
    ap = argparse.ArgumentParser("ada")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p0 = sub.add_parser("owners", help="List HubSpot owners"); p0.set_defaults(func=cmd_owners)
    p1 = sub.add_parser("pull-contacts", help="Pull contacts from HubSpot")
    p1.add_argument("--limit", default="2000"); p1.add_argument("--out", default="contacts.csv"); p1.set_defaults(func=cmd_pull_contacts)
    p2 = sub.add_parser("analyze", help="Analyze contacts CSV → reports")
    p2.add_argument("--source", choices=["csv"], default="csv")
    p2.add_argument("--path", required=True)
    p2.add_argument("--out-dir", default="reports"); p2.set_defaults(func=cmd_analyze)
    p3 = sub.add_parser("audit", help="Consultant Mode: multi-client batch audits")
    scope = p3.add_mutually_exclusive_group(required=True)
    scope.add_argument("--client", help="Client slug to audit (e.g., acme_corp)")
    scope.add_argument("--all", action="store_true", help="Run for all clients in config")
    p3.add_argument("--config", required=True, help="Path to clients.toml / .yaml")
    p3.add_argument("--limit", default="5000", help="Contact limit per client")
    p3.add_argument("--out-root", default="audits", help="Root directory for per-client outputs")
    p3.add_argument("--skip-pull", action="store_true", help="Skip HubSpot pull and reuse existing contacts.csv")
    p3.set_defaults(func=cmd_audit)
    args = ap.parse_args(); args.func(args)

if __name__ == "__main__":
    main()
