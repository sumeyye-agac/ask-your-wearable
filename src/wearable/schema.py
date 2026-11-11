"""The daily table that every tool works on, and the metrics it contains.

One row per calendar day for one user. A missing value means "no valid measurement
that day", never zero.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class Metric:
    name: str
    unit: str
    description: str
    direction: str  # what a higher value means, in wellness terms
    digits: int = 1          # decimals in tool output; 0 gives whole numbers
    as_hours: bool = False   # tools also give the value as hours and minutes
    weekly_total: bool = False  # adding the days of a week up makes sense
    whole_day: bool = False  # a value exists only if the whole 24 hours were recorded


METRICS: dict[str, Metric] = {
    "steps": Metric(
        "steps", "steps",
        "Total steps in the day. Only days with all 24 hours recorded and more than 0 steps.",
        "Higher means more walking.",
        digits=0, weekly_total=True, whole_day=True,
    ),
    "minutes_asleep": Metric(
        "minutes_asleep", "minutes",
        "Minutes scored as asleep in the night's main sleep (episodes of 3 h or more, "
        "episodes split by a gap of 60 min or less merged). Dated by the wake-up day.",
        "Neither direction is better in itself; adults are usually advised 7-9 h.",
        as_hours=True,
    ),
    "minutes_in_bed": Metric(
        "minutes_in_bed", "minutes",
        "Minutes recorded in the night's main sleep, including restless and awake minutes. "
        "Dated by the wake-up day.",
        "Neither direction is better in itself.",
        as_hours=True,
    ),
    "mean_hr": Metric(
        "mean_hr", "bpm",
        "Mean of all heart-rate readings in the day. Only days with 12 h or more of readings.",
        "Mostly reflects how active the day was; it is not resting heart rate.",
    ),
    "fairly_active_minutes": Metric(
        "fairly_active_minutes", "minutes",
        "Minutes in the day that Fitbit scored as fairly active (intensity level 2 of 0-3). "
        "Only days with all 1440 minutes recorded and at least one minute above sedentary.",
        "Higher means more moderate activity as Fitbit estimates it. Fitbit's levels are the "
        "device's own estimate and are not the same as CDC's definition of moderate intensity.",
        digits=0, weekly_total=True, whole_day=True,
    ),
    "very_active_minutes": Metric(
        "very_active_minutes", "minutes",
        "Minutes in the day that Fitbit scored as very active (intensity level 3 of 0-3). "
        "Only days with all 1440 minutes recorded and at least one minute above sedentary.",
        "Higher means more vigorous activity as Fitbit estimates it. Fitbit's levels are the "
        "device's own estimate and are not the same as CDC's definition of vigorous intensity.",
        digits=0, weekly_total=True, whole_day=True,
    ),
}

DAILY_COLUMNS = ["date", *METRICS]


def check_metric(metric: str) -> Metric:
    """Return the metric definition, or raise a ValueError that lists valid names."""
    if metric not in METRICS:
        raise ValueError(f"Unknown metric {metric!r}. Valid metrics: {', '.join(METRICS)}.")
    return METRICS[metric]


def to_daily_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Index a one-user daily table by date and fill in absent dates as missing rows.

    Accepts a frame with a 'date' column (strings or datetimes) and any subset of the
    metric columns. Missing metric columns are added as all-missing.
    """
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"]).dt.normalize()
    if out["date"].duplicated().any():
        raise ValueError("The daily table has more than one row for the same date.")
    for name in METRICS:
        if name not in out.columns:
            out[name] = float("nan")
        out[name] = pd.to_numeric(out[name], errors="raise").astype("float64")
    out = out.set_index("date").sort_index()[list(METRICS)]
    full = pd.date_range(out.index.min(), out.index.max(), freq="D", name="date")
    return out.reindex(full)
