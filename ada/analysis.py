from __future__ import annotations
import pandas as pd

def score_contacts(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    has_email = df["email"].notna().astype(int) if "email" in df.columns else 0
    has_owner = df["ownerId"].notna().astype(int) if "ownerId" in df.columns else 0
    lifecycle = (df.get("lifecyclestage") or pd.Series([""]*len(df))).astype(str)
    activity = df.get("lastmodifieddate")
    if activity is not None:
        recency = pd.to_datetime(activity, errors="coerce")
        recency_rank = recency.rank(pct=True).fillna(0)
        recency_score = (recency_rank * 40).round(2)
    else:
        recency_score = 0
    base = 20*has_email + 20*has_owner
    lifecycle_boost = lifecycle.str.contains("opportunity|customer|marketingqualifiedlead|salesqualifiedlead", case=False, regex=True).astype(int) * 20
    df["lead_score"] = (base + lifecycle_boost + recency_score).clip(0, 100)
    return df

def owner_rollup(df: pd.DataFrame) -> pd.DataFrame:
    if "ownerId" not in df.columns:
        return pd.DataFrame({"ownerId": [], "count": [], "avg_score": []})
    return (df.groupby("ownerId", dropna=False)
              .agg(count=("id","count"), avg_score=("lead_score","mean"))
              .reset_index()
              .sort_values(["avg_score","count"], ascending=[False, False]))
