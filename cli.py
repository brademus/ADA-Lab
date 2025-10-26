from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd
from rich import print
from ada import hubspot
from ada.analysis import score_contacts, owner_rollup
from ada.reporting import write_outputs

def cmd_owners(args):
    owners = hubspot.list_owners()
    for o in owners:
        print({"id": o.get("id"), "email": o.get("email"), "firstName": o.get("firstName"), "lastName": o.get("lastName")})

def cmd_pull_contacts(args):
    props = ["email","firstname","lastname","lifecyclestage","hs_object_id","hubspot_owner_id","lastmodifieddate"]
    rows = []
    limit = int(args.limit)
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
    out = Path(args.out or "contacts.csv")
    pd.DataFrame(rows).to_csv(out, index=False)
    print(f"[green]Wrote {len(rows)} contacts → {out}")

def cmd_analyze(args):
    if args.source == "csv":
        df = pd.read_csv(args.path)
    else:
        raise SystemExit("Only --source csv is currently supported.")
    df = score_contacts(df)
    roll = owner_rollup(df)
    write_outputs(df, args.out_dir)
    print(f"[blue]Downloaded/loaded {len(df)} contacts. avg_score={round(df['lead_score'].mean(),2)} owners={len(roll)}")
    print("[green]Reports written to", args.out_dir)

def main():
    ap = argparse.ArgumentParser("ada")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p0 = sub.add_parser("owners", help="List HubSpot owners")
    p0.set_defaults(func=cmd_owners)

    p1 = sub.add_parser("pull-contacts", help="Pull contacts from HubSpot")
    p1.add_argument("--limit", default="2000")
    p1.add_argument("--out", default="contacts.csv")
    p1.set_defaults(func=cmd_pull_contacts)

    p2 = sub.add_parser("analyze", help="Analyze contacts CSV → reports/")
    p2.add_argument("--source", choices=["csv"], default="csv")
    p2.add_argument("--path", required=True)
    p2.add_argument("--out-dir", default="reports")
    p2.set_defaults(func=cmd_analyze)

    args = ap.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
