"""Write a small raw sample for the app's Data tab: one day per demo user, as exported.

    python scripts/build_raw_sample.py data/raw

For each demo user, the representative day is the day on which every metric of the daily
table is present and whose step count is closest to that user's median over those days
(the earlier day on ties). For that day it copies the raw rows, with the original columns
and timestamp strings, of the four export tables the app reads:

- hourlySteps: the 24 hours of the day
- minuteIntensitiesNarrow: the 1440 minutes of the day
- minuteSleep: every minute of the sleep logs that end on that day (the night before it)
- heartrate_seconds: every reading of the day

Rows of 12 April 2016, which is in both exports, are de-duplicated. Output goes to
data/demo/raw_sample/<table>.csv.gz.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from wearable.schema import METRICS, to_daily_frame
from wearable.zenodo import TS_FORMAT

REPO = Path(__file__).resolve().parents[1]
DEMO = REPO / "data/demo/demo_daily.csv"
OUT = REPO / "data/demo/raw_sample"
TABLES = {"hourlySteps": "ActivityHour", "minuteIntensitiesNarrow": "ActivityMinute",
          "minuteSleep": "date", "heartrate_seconds": "Time"}


def representative_day(df: pd.DataFrame) -> pd.Timestamp:
    """The complete day whose steps are closest to the median of the complete days."""
    complete = df.dropna(subset=list(METRICS))
    if complete.empty:
        raise ValueError("No day has every metric.")
    distance = (complete["steps"] - complete["steps"].median()).abs()
    return distance[distance == distance.min()].index.min()


def read_raw(root: Path, table: str, ids: set[int]) -> pd.DataFrame:
    paths = sorted(root.glob(f"*/*/{table}_merged.csv"))
    if not paths:
        raise FileNotFoundError(f"No {table}_merged.csv under {root}")
    raw = pd.concat([pd.read_csv(p) for p in paths], ignore_index=True)
    raw = raw[raw["Id"].isin(ids)].drop_duplicates()
    raw["_ts"] = pd.to_datetime(raw[TABLES[table]], format=TS_FORMAT)
    return raw


def main(root: Path) -> None:
    table = pd.read_csv(DEMO)
    days = {uid: representative_day(to_daily_frame(rows.drop(columns="user_id")))
            for uid, rows in table.groupby("user_id")}
    OUT.mkdir(parents=True, exist_ok=True)
    for name in TABLES:
        raw = read_raw(root, name, set(days))
        parts = []
        for uid, day in days.items():
            rows = raw[raw["Id"] == uid]
            if name == "minuteSleep":
                ends = rows.groupby("logId")["_ts"].max().dt.normalize()
                rows = rows[rows["logId"].isin(ends[ends == day].index)]
            else:
                rows = rows[rows["_ts"].dt.normalize() == day]
            parts.append(rows.sort_values("_ts"))
        sample = pd.concat(parts).drop(columns="_ts")
        path = OUT / f"{name}.csv.gz"
        sample.to_csv(path, index=False, compression={"method": "gzip", "mtime": 0})
        print(f"{name}: {len(sample):,} rows, {path.stat().st_size / 1024:.0f} KB")
    for uid, day in days.items():
        print(f"user {uid}: {day:%Y-%m-%d}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(Path(sys.argv[1]))
