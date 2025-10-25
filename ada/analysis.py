from __future__ import annotations
import pandas as pd

def _col(df: pd.DataFrame, name: str, default: str = "") -> pd.Series:
    """Return a string series for column `name`, or a default-filled series if missing."""
    if name in df.columns:
        return df[name].astype(str)
    return pd.Series([default] * len(df))

def score_contacts(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Normalize commonly used columns
    email = _col(df, "email")
    owner = _col(df, "ownerId")
    lifecycle = _col(df, "lifecyclestage")

    # Binary features
    has_email = email.ne("").astype(int)
    has_owner = owner.ne("").astype(int)

    # Recency score (0..40) based on lastmodifieddate if present
    if "lastmodifieddate" in df.columns:
        recency = pd.to_datetime(df["lastmodifieddate"], errors="coerce")
        recency_rank = recency.rank(pct=True).fillna(0)
        recency_score = (recency_rank * 40).round(2)
    else:
        recency_score = pd.Series([0] * len(df))

    # Lifecycle boost (0 or 20)
    lifecycle_boost = lifecycle.str.contains(
        r"(opportunity|customer|marketingqualifiedlead|salesqualifiedlead)",
        case=False, regex=True
    ).astype(int) * 20

    # Final score (0..100)
    df["lead_score"] = (20*has_email + 20*has_owner + lifecycle_boost + recency_score).clip(0, 100)
    return df

def owner_rollup(df: pd.DataFrame) -> pd.DataFrame:
    if "ownerId" not in df.columns:
        return pd.DataFrame({"ownerId": [], "count": [], "avg_score": []})
    return (
        df.groupby("ownerId", dropna=False)
          .agg(count=("id", "count"), avg_score=("lead_score", "mean"))
          .reset_index()
          .sort_values(["avg_score", "count"], ascending=[False, False])
    )
