from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from tabulate import tabulate

try:
    import markdown as _markdown
except Exception:
    _markdown = None


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
    cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=days)
    return ts.isna() | (ts < cutoff)


def write_outputs(df: pd.DataFrame, out_dir: str = "reports", *, pure_html: bool = False):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Defensive: sort by lead_score only if present (score_contacts normally adds it)
    top = df.sort_values("lead_score", ascending=False) if "lead_score" in df.columns else df
    top.to_csv(out / "lead_scores.csv", index=False)
    top.to_json(out / "lead_scores.jsonl", orient="records", lines=True)

    insights = pd.DataFrame(
        [
            {"metric": "total_contacts", "value": int(len(df))},
            {
                "metric": "avg_lead_score",
                "value": (
                    round(float(df["lead_score"].mean()), 2) if "lead_score" in df.columns else None
                ),
            },
            {
                "metric": "pct_has_email",
                "value": (
                    round(float(df["email"].notna().mean() * 100), 2)
                    if "email" in df.columns
                    else None
                ),
            },
        ]
    )
    insights.to_json(out / "insights.jsonl", orient="records", lines=True)

    summary_md = [
        "# ADA Analysis Summary",
        "",
        f"- Total contacts: **{len(df)}**",
        (
            f"- Avg lead score: **{round(float(df['lead_score'].mean()),2)}**"
            if "lead_score" in df.columns
            else "- Avg lead score: N/A"
        ),
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
        "ts_utc": datetime.now(UTC).isoformat(),
    }
    # Merge outreach metrics (including channel splits) if present
    try:
        outreach_file = out / "outreach_metrics.json"
        if outreach_file.exists():
            outreach = json.loads(outreach_file.read_text(encoding="utf-8"))
            # copy known fields into summary
            for k in (
                "contacted",
                "replies",
                "meetings",
                "open_rate",
                "reply_rate",
                "conversion_rate",
            ):
                if k in outreach:
                    summary_json[k] = outreach[k]
            # channel splits
            for k in ("contacted_by_channel", "replies_by_channel", "meetings_by_channel"):
                if k in outreach:
                    summary_json[k] = outreach[k]
            # variant performance
            if "variant_perf" in outreach:
                summary_json["variant_perf"] = outreach["variant_perf"]
    except Exception:
        # non-fatal
        pass
    (out / "summary.json").write_text(json.dumps(summary_json, indent=2), encoding="utf-8")

    # Also emit an HTML version of the summary for nicer in-browser viewing.
    try:
        if pure_html:
            # Build a small, dependency-free HTML page.
            table_html = tabulate(top.head(10).fillna(""), headers="keys", tablefmt="html")
            html_page = (
                '<html><head><meta charset="utf-8"><title>ADA Summary</title>'
                "<style>"
                "body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;margin:32px}"
                "table{border-collapse:collapse}th,td{border:1px solid #ddd;padding:6px}"
                "</style>"
                "</head><body>"
                f"<h1>ADA Analysis Summary</h1>"
                f"<p>Total contacts: <strong>{len(df)}</strong></p>"
                + (
                    (
                        "<p>Avg lead score: <strong>"
                        + f"{round(float(df['lead_score'].mean()),2)}"
                        + "</strong></p>"
                    )
                    if "lead_score" in df.columns
                    else "<p>Avg lead score: N/A</p>"
                )
                + "<h2>Top 10 Contacts</h2>"
                + table_html
                + "</body></html>"
            )
            (out / "summary.html").write_text(html_page, encoding="utf-8")
        else:
            if _markdown is not None:
                md = "\n".join(summary_md)
                html = _markdown.markdown(md)
                html_page = f'<html><head><meta charset="utf-8"></head><body>{html}</body></html>'
                (out / "summary.html").write_text(html_page, encoding="utf-8")
            else:
                # Fallback: wrap the markdown in <pre>
                (out / "summary.html").write_text(
                    "<html><body><pre>" + "\n".join(summary_md) + "</pre></body></html>",
                    encoding="utf-8",
                )
    except Exception:
        # non-fatal
        pass
