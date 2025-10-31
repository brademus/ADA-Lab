from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .clients import ClientConfig


def collect_metrics(client_dir: Path) -> dict[str, Any]:
    """
    Read summary.json; fallback to CSV if missing.
    Returns keys: mean_quality, dormant_pct, owner_imbalance_pct, last_audited, summary_href.
    """
    summary_json = client_dir / "summary.json"
    summary_md = client_dir / "summary.md"
    summary_html = client_dir / "summary.html"
    lead_csv = client_dir / "lead_scores.csv"
    insights: dict[str, Any] = {
        "mean_quality": 0.0,
        "dormant_pct": 0.0,
        "owner_imbalance_pct": 0.0,
        "last_audited": "",
        "summary_href": (
            "summary.html"
            if summary_html.exists()
            else ("summary.md" if summary_md.exists() else "")
        ),
        # Autopilot outreach metrics
        "emails_drafted": 0,
        "emails_sent": 0,
        "replies": 0,
        "meetings": 0,
        "reply_rate": 0.0,
        "outbox_link": "outbox.sqlite" if (client_dir / "outbox.sqlite").exists() else "",
        # legacy per-channel splits (kept for backward compat)
        "contacted_by_channel": {},
        "replies_by_channel": {},
    }
    # Prefer new outreach_metrics.json if present
    outreach_metrics = client_dir / "outreach_metrics.json"
    if outreach_metrics.exists():
        try:
            m = json.loads(outreach_metrics.read_text(encoding="utf-8"))
            insights["emails_drafted"] = int(m.get("emails_drafted", 0))
            insights["emails_sent"] = int(m.get("emails_sent", 0))
            insights["replies"] = int(m.get("replies", 0))
            insights["meetings"] = int(m.get("meetings", 0))
            insights["reply_rate"] = float(m.get("reply_rate", 0.0))
        except Exception:
            pass
    if summary_json.exists():
        try:
            data = json.loads(summary_json.read_text(encoding="utf-8"))
            insights["mean_quality"] = float(data.get("mean_quality", 0.0))
            insights["dormant_pct"] = float(data.get("dormant_pct", 0.0))
            insights["owner_imbalance_pct"] = float(data.get("owner_imbalance_pct", 0.0))
            insights["last_audited"] = str(data.get("ts_utc", ""))
            # legacy outreach merge for backward compat
            insights["replies"] = int(data.get("replies", insights.get("replies", 0)))
            insights["meetings"] = int(data.get("meetings", insights.get("meetings", 0)))
            insights["reply_rate"] = float(data.get("reply_rate", insights.get("reply_rate", 0.0)))
            insights["contacted_by_channel"] = data.get("contacted_by_channel", {})
            insights["replies_by_channel"] = data.get("replies_by_channel", {})
            insights["variant_perf"] = data.get("variant_perf", [])
            return insights
        except Exception:
            pass
    if lead_csv.exists():
        try:
            import pandas as pd  # type: ignore

            df = pd.read_csv(lead_csv)
            if "lead_score" in df.columns:
                insights["mean_quality"] = float(round(df["lead_score"].mean(), 2))
        except Exception:
            # Non-fatal if pandas isn't available in this runtime
            pass
    return insights


def render_master_index(clients: list[ClientConfig], audits_root: Path, out_path: Path) -> None:
    rows: list[str] = []

    def fmt_split(d: dict[str, Any]) -> str:
        try:
            return ", ".join(f"{k}:{int(v)}" for k, v in d.items()) if d else "—"
        except Exception:
            return "—"

    for c in clients:
        cdir = audits_root / c.slug
        m = collect_metrics(cdir)
        link = m.get("summary_href") or ""
        link_html = f'<a href="{c.slug}/{link}">Open</a>' if link else "—"
        failed = (cdir / "error.txt").exists()
        conn_err = (cdir / "connector_error.txt").exists()
        status_txt = "FAILED" if failed or conn_err else ""
        title_attr = ""
        if conn_err:
            try:
                tip = (
                    (cdir / "connector_error.txt")
                    .read_text(encoding="utf-8")
                    .strip()
                    .splitlines()[0]
                )
                title_attr = f' title="{tip}"'
            except Exception:
                title_attr = ""
        status_html = (
            f'<span style="color:red;font-weight:600"{title_attr}>{status_txt}</span>'
            if status_txt
            else ""
        )

        rows.append(
            "<tr>"
            f"<td>{c.name} <small>({c.slug})</small> {status_html}</td>"
            f"<td>{m.get('last_audited','')}</td>"
            f"<td>{m.get('mean_quality',0.0):.2f}</td>"
            f"<td>{m.get('dormant_pct',0.0):.2f}%</td>"
            f"<td>{m.get('owner_imbalance_pct',0.0):.2f}%</td>"
            f"<td>{int(m.get('emails_drafted',0))}</td>"
            f"<td>{int(m.get('emails_sent',0))}</td>"
            f"<td>{int(m.get('replies',0))}</td>"
            f"<td>{int(m.get('meetings',0))}</td>"
            f"<td>{link_html}</td>"
            "</tr>"
        )

        # Variant sections per client
        variant_sections: list[str] = []
        for c in clients:
            sfile = audits_root / c.slug / "summary.json"
            if not sfile.exists():
                continue
            try:
                data = json.loads(sfile.read_text(encoding="utf-8"))
                vperf = data.get("variant_perf") or []
                if not vperf:
                    continue
                rows_v = []
                for v in vperf:
                    sent = int(v.get("sent", 0) or 0)
                    replies = int(v.get("replies", 0) or 0)
                    rr = (replies / sent) if sent else 0.0
                    rows_v.append(
                        "<tr>"
                        f"<td>{v.get('variant_id','')}</td>"
                        f"<td>{sent}</td>"
                        f"<td>{int(v.get('opens',0) or 0)}</td>"
                        f"<td>{replies}</td>"
                        f"<td>{int(v.get('meetings',0) or 0)}</td>"
                        f"<td>{rr:.2f}</td>"
                        f"<td>{float(v.get('conversion_rate',0.0) or 0.0):.2f}</td>"
                        "</tr>"
                    )
                variant_sections.append(
                    
                        f"<h3>Variants & Tests — {c.name} ({c.slug})</h3>\n"
                        "<table><thead><tr>"
                        "<th>Variant ID</th>"
                        "<th>Sent</th>"
                        "<th>Opens</th>"
                        "<th>Replies</th>"
                        "<th>Meetings</th>"
                        "<th>Reply Rate</th>"
                        "<th>Conversion</th>"
                        "</tr></thead><tbody>"
                        + "".join(rows_v)
                        + "</tbody></table>"
                    
                )
            except Exception:
                continue

        html = f"""<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\">
  <title>ADA Consultant Dashboard</title>
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <style>
  body{{font-family:system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin:40px;}}
  table{{border-collapse:collapse; width:100%; max-width:1100px;}}
  th,td{{border:1px solid #ddd; padding:8px; text-align:left;}}
  th{{background:#f6f8fa;}}
  tr:nth-child(even){{background:#fafafa;}}
  .muted{{color:#666; font-size:12px}}
  </style>
  </head>
  <body>
  <h1>ADA Consultant Dashboard</h1>
  <p class=\"muted\">Per-client audit summaries generated by ADA.</p>
  <table>
    <thead>
      <tr>
        <th>Client</th>
        <th>Last Audited (UTC)</th>
        <th>Avg Quality</th>
        <th>% Dormant</th>
        <th>Owner Load</th>
        <th>Emails Drafted</th>
        <th>Emails Sent</th>
        <th>Replies</th>
        <th>Meetings</th>
        <th>Report</th>
      </tr>
    </thead>
    <tbody>
  {''.join(rows) if rows else '<tr><td colspan="10">No audits yet.</td></tr>'}
    </tbody>
  </table>
  {''.join(variant_sections)}
  </body>
  </html>
"""
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(html, encoding="utf-8")
