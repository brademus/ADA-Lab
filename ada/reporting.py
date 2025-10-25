from __future__ import annotations
from pathlib import Path
import json
from datetime import datetime, timezone
import pandas as pd
from tabulate import tabulate

def _percentile(s: pd.Series, q: float) -> float:
    try:
        return float(s.quantile(q))
    except Exception:
        return 0.0

def _owner_imbalance_pct(df: pd.DataFrame) -> float:
    """Simple load-imbalance across owners: (max_count - mean)/mean * 100."""
    if "ownerId" not in df.columns or df["ownerId"].dropna().eq("").all():
        return 0.0
    counts = df["ownerId"].fillna("").value_counts()
    if counts.empty:
        return 0.0
    mean = counts.mean()
    maxc = counts.max()
    if mean <= 0:
        return 0.0
    return round(float((maxc - mean) / mean * 100.0), 2)

def _dormant_mask(df: pd.DataFrame, days: int = 180) -> pd.Series:
    """Dormant if lastmodifieddate older than N days or missing."""
    if "lastmodifieddate" not in df.columns:
        return pd.Series([True] * len(df))
    ts = pd.to_datetime(df["lastmodifieddate"], errors="coerce", utc=True)
    cutoff = pd.Timestamp.utcnow().tz_localize("UTC") - pd.Timedelta(days=days)
    return ts.isna() | (ts < cutoff)

def write_outputs(df: pd.DataFrame, out_dir: str = "reports"):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    top = df.sort_values("lead_score", ascending=False)
    top.to_csv(out / "lead_scores.csv", index=False)
    top.to_json(out / "lead_scores.jsonl", orient="records", lines=True)

    insights = pd.DataFrame([
        {"metric": "total_contacts", "value": int(len(df))},
        {"metric": "avg_lead_score", "value": round(float(df["lead_score"].mean()), 2) if "lead_score" in df.columns else None},
        {"metric": "pct_has_email", "value": round(float(df["email"].notna().mean() * 100), 2) if "email" in df.columns else None},
    ])
    insights.to_json(out / "insights.jsonl", orient="records", lines=True)

    summary_md = [
        "# ADA Analysis Summary",
        "",
        f"- Total contacts: **{len(df)}**",
        f"- Avg lead score: **{round(float(df['lead_score'].mean()),2)}**" if "lead_score" in df.columns else "- Avg lead score: N/A",
        "",
        "## Top 10 Contacts",
        "",
        tabulate(top.head(10).fillna(""), headers="keys", tablefmt="github"),
    ]
    (out / "summary.md").write_text("\n".join(summary_md), encoding="utf-8")

    # NEW: summary.json for master dashboard
    contacts = int(len(df))
    lead = df["lead_score"] if "lead_score" in df.columns else pd.Series([0] * contacts)
    dormant = _dormant_mask(df)
    dormant_count = int(dormant.sum())
    dormant_pct = round(float((dormant_count / contacts) * 100.0), 2) if contacts else 0.0

    summary_json = {
        "contacts": contacts,
        "mean_quality": round(float(lead.mean()), 2) if contacts else 0.0,
        "p50_quality": round(_percentile(lead, 0.50), 2),
        "p90_quality": round(_percentile(lead, 0.90), 2),
        "dormant_count": dormant_count,
        "dormant_pct": dormant_pct,
        "owner_imbalance_pct": _owner_imbalance_pct(df),
        "ts_utc": datetime.now(timezone.utc).isoformat(),
    }
    (out / "summary.json").write_text(json.dumps(summary_json, indent=2), encoding="utf-8")
