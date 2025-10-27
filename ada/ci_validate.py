from __future__ import annotations
import sys
from pathlib import Path
import json

def fail(msg: str):
    print("ERROR:", msg)
    sys.exit(2)

def validate_audits(root: Path) -> None:
    if not root.exists():
        fail(f"audits root {root} does not exist")
    clients = [p for p in root.iterdir() if p.is_dir()]
    if not clients:
        fail(f"no client directories found under {root}")
    required_files = ["contacts.csv", "lead_scores.csv", "summary.json", "summary.md"]
    ok = True
    for c in clients:
        for rf in required_files:
            p = c / rf
            if not p.exists():
                print(f"MISSING: {p}")
                ok = False
        # basic summary.json content check
        sj = c / "summary.json"
        try:
            data = json.loads(sj.read_text(encoding="utf-8"))
            for k in ["contacts", "mean_quality", "ts_utc"]:
                if k not in data:
                    print(f"summary.json missing key {k} for {c}")
                    ok = False
        except Exception as e:
            print(f"summary.json invalid for {c}: {e}")
            ok = False
    if not ok:
        fail("audit validation failed")
    print("Audit validation passed")

if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('audits_root', nargs='?', default='audits')
    args = ap.parse_args()
    validate_audits(Path(args.audits_root))
