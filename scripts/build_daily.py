"""Build the daily tables from the raw Zenodo export.

Usage:
    .venv/bin/python scripts/build_daily.py data/raw

Writes data/processed/daily_all.csv (all users, git-ignored) and
data/demo/demo_daily.csv (the three demo users, committed; CC BY 4.0, see README).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from wearable.zenodo import build_daily

DEMO_USERS = [6962181067, 5553957443, 5577150313]


SPLIT = "2016-04-12"  # first day of the second export


def coverage(daily: pd.DataFrame) -> pd.DataFrame:
    """Per metric: users, days per user, and users with enough data in both halves."""
    rows = []
    for metric in ["steps", "minutes_asleep", "mean_hr"]:
        has = daily.dropna(subset=[metric])
        per_user = has.groupby("user_id")["date"].nunique()
        first = has[has["date"] < SPLIT].groupby("user_id").size()
        second = has[has["date"] >= SPLIT].groupby("user_id").size()
        both = pd.concat([first, second], axis=1).fillna(0)
        rows.append({
            "metric": metric, "users": len(per_user),
            "first_date": has["date"].min(), "last_date": has["date"].max(),
            "median_days": int(per_user.median()), "min_days": per_user.min(),
            "max_days": per_user.max(), "users_28d+": int((per_user >= 28).sum()),
            "users_10d+_both_halves": int(((both.iloc[:, 0] >= 10) & (both.iloc[:, 1] >= 10)).sum()),
        })
    return pd.DataFrame(rows)


def main(raw: Path, repo: Path) -> None:
    daily = build_daily(raw)
    (repo / "data/processed").mkdir(parents=True, exist_ok=True)
    daily.to_csv(repo / "data/processed/daily_all.csv", index=False)
    demo = daily[daily["user_id"].isin(DEMO_USERS)]
    demo.to_csv(repo / "data/demo/demo_daily.csv", index=False)
    print(f"all users: {daily['user_id'].nunique()} users, {len(daily)} rows")
    print(f"demo: {demo['user_id'].nunique()} users, {len(demo)} rows")
    print(coverage(daily).to_string(index=False))
    week = daily.dropna(subset=["steps", "minutes_asleep", "mean_hr"], how="any")
    counts = week.groupby("user_id").size()
    print(f"users with >=7 days that have all three metrics: {int((counts >= 7).sum())}")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "data/raw"), Path(__file__).resolve().parents[1])
