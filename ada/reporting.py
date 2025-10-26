from __future__ import annotations
from pathlib import Path
import pandas as pd
from tabulate import tabulate

def write_outputs(df: pd.DataFrame, out_dir: str="reports"):
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    top = df.sort_values("lead_score", ascending=False)
    top.to_csv(out / "lead_scores.csv", index=False)
    top.to_json(out / "lead_scores.jsonl", orient="records", lines=True)
    insights = pd.DataFrame([
        {"metric": "total_contacts", "value": int(len(df))},
        {"metric": "avg_lead_score", "value": round(float(df["lead_score"].mean()),2) if "lead_score" in df.columns else None},
        {"metric": "pct_has_email", "value": round(float(df["email"].notna().mean()*100),2) if "email" in df.columns else None},
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
