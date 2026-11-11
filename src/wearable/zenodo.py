"""Turn the raw Zenodo Fitbit export (record 53894) into the daily table.

Furberg, Brinton, Keating & Ortiz, "Crowd-sourced Fitbit datasets 03.12.2016-05.12.2016",
Zenodo, doi:10.5281/zenodo.53894, CC BY 4.0.

Both monthly exports are read and concatenated; rows that appear in both (12 April 2016)
are dropped as duplicates. Month 1's dailyActivity table is incomplete, so steps come
from hourlySteps. Month 1 has no sleepDay table, so sleep comes from minuteSleep. Month 1
has no dailyIntensities table, so active minutes come from minuteIntensitiesNarrow.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

TS_FORMAT = "%m/%d/%Y %I:%M:%S %p"

MIN_NIGHT_MINUTES = 180   # a sleep block shorter than 3 h is a nap and is not counted
MERGE_GAP_MINUTES = 60    # episodes split by a gap this short are one night
MIN_HR_HOURS = 12         # a day needs this many hours with readings to get a mean HR
ASLEEP = 1                # minuteSleep value codes: 1 asleep, 2 restless, 3 awake
# minuteIntensitiesNarrow codes, as in Fitbit's Web API: 0 sedentary, 1 lightly active,
# 2 fairly active, 3 very active. Counting codes 2 and 3 per day reproduces Fitbit's own
# FairlyActiveMinutes and VeryActiveMinutes in dailyIntensities on 99.9% and 99.8% of the
# 903 complete days where both tables exist.
FAIRLY_ACTIVE, VERY_ACTIVE = 2, 3
MINUTES_PER_DAY = 1440


def read_table(root: Path, name: str) -> pd.DataFrame:
    """Read one table from both monthly exports, parse timestamps into 'ts', drop duplicates."""
    paths = sorted(root.glob(f"*/*/{name}_merged.csv"))
    if not paths:
        raise FileNotFoundError(f"No {name}_merged.csv under {root}")
    df = pd.concat([pd.read_csv(p) for p in paths], ignore_index=True)
    time_col = {"hourlySteps": "ActivityHour", "minuteSleep": "date",
                "heartrate_seconds": "Time", "minuteIntensitiesNarrow": "ActivityMinute"}[name]
    df["ts"] = pd.to_datetime(df[time_col], format=TS_FORMAT)
    return df.drop(columns=time_col).drop_duplicates(["Id", "ts"]).reset_index(drop=True)


def daily_steps(hourly: pd.DataFrame) -> pd.DataFrame:
    """Daily step totals from hourly rows (columns Id, ts, StepTotal).

    A day is kept only if all 24 hours are present and the total is above 0.
    """
    hourly = hourly.assign(date=hourly["ts"].dt.normalize())
    g = hourly.groupby(["Id", "date"]).agg(hours=("ts", "size"), steps=("StepTotal", "sum"))
    g = g[(g["hours"] == 24) & (g["steps"] > 0)]
    return g[["steps"]].reset_index()


def sleep_episodes(minutes: pd.DataFrame) -> pd.DataFrame:
    """One row per Fitbit sleep log (columns Id, ts, value, logId per minute)."""
    return (minutes.groupby(["Id", "logId"])
            .agg(start=("ts", "min"), end=("ts", "max"),
                 in_bed=("ts", "size"), asleep=("value", lambda v: int((v == ASLEEP).sum())))
            .reset_index()
            .sort_values(["Id", "start"], ignore_index=True))


def merge_episodes(episodes: pd.DataFrame, gap_minutes: float = MERGE_GAP_MINUTES) -> pd.DataFrame:
    """Merge a user's consecutive episodes whose gap is at most gap_minutes.

    The gap itself is not counted as time in bed or asleep. Returns one row per merged
    block with Id, start, end, in_bed, asleep.
    """
    eps = episodes.sort_values(["Id", "start"], ignore_index=True)
    prev_end = eps.groupby("Id")["end"].cummax().groupby(eps["Id"]).shift()
    gap = (eps["start"] - prev_end).dt.total_seconds() / 60
    new_block = gap.isna() | (gap > gap_minutes)
    eps["block"] = new_block.cumsum()
    return (eps.groupby(["Id", "block"])
            .agg(start=("start", "min"), end=("end", "max"),
                 in_bed=("in_bed", "sum"), asleep=("asleep", "sum"))
            .reset_index().drop(columns="block"))


def daily_sleep(minutes: pd.DataFrame, gap_minutes: float = MERGE_GAP_MINUTES,
                min_minutes: int = MIN_NIGHT_MINUTES) -> pd.DataFrame:
    """Nightly sleep, dated by the wake-up day.

    Blocks shorter than min_minutes are dropped. If two qualifying blocks end on the same
    date, their minutes are added.
    """
    blocks = merge_episodes(sleep_episodes(minutes), gap_minutes)
    blocks = blocks[blocks["in_bed"] >= min_minutes]
    blocks = blocks.assign(date=blocks["end"].dt.normalize())
    night = blocks.groupby(["Id", "date"])[["asleep", "in_bed"]].sum().reset_index()
    return night.rename(columns={"asleep": "minutes_asleep", "in_bed": "minutes_in_bed"})


def daily_heart_rate(hr: pd.DataFrame, min_hours: int = MIN_HR_HOURS) -> pd.DataFrame:
    """Mean heart rate per day (columns Id, ts, Value), only for days with enough readings."""
    hr = hr.assign(date=hr["ts"].dt.normalize(), hour=hr["ts"].dt.floor("h"))
    g = hr.groupby(["Id", "date"]).agg(hours=("hour", "nunique"), mean_hr=("Value", "mean"))
    g = g[g["hours"] >= min_hours]
    return g[["mean_hr"]].reset_index()


def daily_active_minutes(minutes: pd.DataFrame) -> pd.DataFrame:
    """Fairly and very active minutes per day (columns Id, ts, Intensity per minute).

    A day is kept only if all 1440 minutes are present and at least one of them is above
    sedentary. A kept day can have 0 fairly or very active minutes; that is a measurement.
    """
    minutes = minutes.assign(date=minutes["ts"].dt.normalize(),
                             fairly=minutes["Intensity"] == FAIRLY_ACTIVE,
                             very=minutes["Intensity"] == VERY_ACTIVE,
                             moving=minutes["Intensity"] > 0)
    g = minutes.groupby(["Id", "date"]).agg(
        n=("ts", "size"), moving=("moving", "sum"),
        fairly_active_minutes=("fairly", "sum"), very_active_minutes=("very", "sum"))
    g = g[(g["n"] == MINUTES_PER_DAY) & (g["moving"] > 0)]
    return g[["fairly_active_minutes", "very_active_minutes"]].astype(int).reset_index()


def build_daily(root: Path) -> pd.DataFrame:
    """All users' daily tables in long form: user_id, date, and the metric columns."""
    parts = [
        daily_steps(read_table(root, "hourlySteps")),
        daily_sleep(read_table(root, "minuteSleep")),
        daily_heart_rate(read_table(root, "heartrate_seconds")),
        daily_active_minutes(read_table(root, "minuteIntensitiesNarrow")),
    ]
    out = parts[0]
    for p in parts[1:]:
        out = out.merge(p, on=["Id", "date"], how="outer")
    out = out.rename(columns={"Id": "user_id"}).sort_values(["user_id", "date"])
    out["mean_hr"] = out["mean_hr"].round(1)
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    return out[["user_id", "date", "steps", "minutes_asleep", "minutes_in_bed", "mean_hr",
                "fairly_active_minutes", "very_active_minutes"]]
