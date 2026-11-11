"""Analysis tools over one user's daily table.

Every function is deterministic, takes the daily frame from schema.to_daily_frame plus
JSON-friendly arguments (metric names, ISO dates), and returns a dict of plain Python
values that can be shown to a language model as-is. Errors are raised as ValueError with
a message that says what was wrong and what is valid.
"""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

from wearable.schema import METRICS, check_metric

MIN_DAYS_PER_PERIOD = 3     # compare_periods refuses to compare periods with fewer days
MAX_LISTED_DATES = 60       # cap on date lists returned to the model
PRESETS = ("first_half_vs_second_half", "last_4_weeks_vs_previous_4_weeks")


# --- helpers ----------------------------------------------------------------

def _num(x: float | None, digits: int = 1) -> float | None:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    return round(float(x), digits)


def _day(ts: pd.Timestamp) -> str:
    return ts.strftime("%Y-%m-%d")


def _parse_date(value: str, name: str) -> pd.Timestamp:
    try:
        return pd.Timestamp(value).normalize()
    except (ValueError, TypeError):
        raise ValueError(f"{name}={value!r} is not a date; use YYYY-MM-DD.") from None


def data_range(df: pd.DataFrame) -> tuple[pd.Timestamp, pd.Timestamp]:
    """First and last date on which any metric has a value."""
    has_any = df[list(METRICS)].notna().any(axis=1)
    if not has_any.any():
        raise ValueError("The daily table has no measurements at all.")
    dates = df.index[has_any]
    return dates.min(), dates.max()


def _window(df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Rows from start to end inclusive, with absent dates as missing rows."""
    if start > end:
        raise ValueError(f"Start {_day(start)} is after end {_day(end)}.")
    first, last = data_range(df)
    if end < first or start > last:
        raise ValueError(f"No data between {_day(start)} and {_day(end)}; "
                         f"data covers {_day(first)} to {_day(last)}.")
    return df.reindex(pd.date_range(start, end, freq="D", name="date"))


def _stats(values: pd.Series) -> dict[str, Any]:
    v = values.dropna()
    return {
        "days_with_data": int(v.size),
        "mean": _num(v.mean()) if v.size else None,
        "std": _num(v.std(ddof=1)) if v.size > 1 else None,
    }


def _dates(index: pd.Index) -> dict[str, Any]:
    listed = [_day(d) for d in index[:MAX_LISTED_DATES]]
    return {"dates": listed, "truncated": len(index) > MAX_LISTED_DATES}


# --- tools ------------------------------------------------------------------

def weekly_summary(df: pd.DataFrame, metric: str, end_date: str | None = None) -> dict[str, Any]:
    """Summarise one metric over the 7 days ending on end_date (inclusive).

    Args:
        metric: one of "steps" (steps/day), "minutes_asleep" (minutes/night),
            "minutes_in_bed" (minutes/night), "mean_hr" (bpm, mean of the day's readings).
        end_date: last day of the week, YYYY-MM-DD. Defaults to the last date with any data,
            which is what "this week" means for this data.

    Returns the window, days with and without data, mean, median, the highest and lowest
    day, every day's value (None when missing), and for steps the weekly total.
    """
    m = check_metric(metric)
    end = _parse_date(end_date, "end_date") if end_date else data_range(df)[1]
    start = end - pd.Timedelta(days=6)
    values = _window(df, start, end)[metric]
    present = values.dropna()
    out: dict[str, Any] = {
        "metric": metric, "unit": m.unit, "start": _day(start), "end": _day(end),
        "days_with_data": int(present.size),
        "missing_dates": [_day(d) for d in values.index[values.isna()]],
        "mean": None, "median": None, "highest": None, "lowest": None,
        "daily": [{"date": _day(d), "value": _num(v)} for d, v in values.items()],
    }
    if present.size:
        out["mean"] = _num(present.mean())
        out["median"] = _num(present.median())
        # idxmax/idxmin return the first date on ties, which keeps the result deterministic.
        out["highest"] = {"date": _day(present.idxmax()), "value": _num(present.max())}
        out["lowest"] = {"date": _day(present.idxmin()), "value": _num(present.min())}
    if metric == "steps":
        out["total"] = int(present.sum()) if present.size else None
    return out


def preset_periods(df: pd.DataFrame, preset: str) -> tuple[tuple[pd.Timestamp, pd.Timestamp],
                                                           tuple[pd.Timestamp, pd.Timestamp]]:
    """Resolve a named comparison into two (start, end) periods, earlier period first."""
    first, last = data_range(df)
    if preset == "first_half_vs_second_half":
        n_days = (last - first).days + 1
        if n_days < 2 * MIN_DAYS_PER_PERIOD:
            raise ValueError(f"Data covers only {n_days} days; too short to split in half.")
        mid = first + pd.Timedelta(days=n_days // 2 - 1)
        return (first, mid), (mid + pd.Timedelta(days=1), last)
    if preset == "last_4_weeks_vs_previous_4_weeks":
        b_start = last - pd.Timedelta(days=27)
        a_end = b_start - pd.Timedelta(days=1)
        a_start = a_end - pd.Timedelta(days=27)
        if a_end < first:
            raise ValueError(f"Data starts {_day(first)}; there are no 4 weeks before "
                             f"{_day(b_start)} to compare with.")
        return (a_start, a_end), (b_start, last)
    raise ValueError(f"Unknown preset {preset!r}. Valid presets: {', '.join(PRESETS)}.")


def compare_periods(df: pd.DataFrame, metric: str, preset: str | None = None,
                    period_a_start: str | None = None, period_a_end: str | None = None,
                    period_b_start: str | None = None, period_b_end: str | None = None,
                    ) -> dict[str, Any]:
    """Compare the daily mean of one metric between two non-overlapping periods.

    Give either a preset or all four dates (YYYY-MM-DD, inclusive), not both.

    Args:
        metric: "steps", "minutes_asleep", "minutes_in_bed" or "mean_hr".
        preset: "first_half_vs_second_half" (the user's data range split in two) or
            "last_4_weeks_vs_previous_4_weeks" (the 28 days ending on the last date with
            data against the 28 days before). Period A is always the earlier one.

    Returns per-period mean, standard deviation and days with data, and the difference
    B minus A in the metric's unit and in percent. If either period has fewer than
    3 days with data, enough_data is False and the difference is None.
    """
    m = check_metric(metric)
    dates = [period_a_start, period_a_end, period_b_start, period_b_end]
    if preset is not None:
        if any(d is not None for d in dates):
            raise ValueError("Give either a preset or the four period dates, not both.")
        (a0, a1), (b0, b1) = preset_periods(df, preset)
    else:
        if any(d is None for d in dates):
            raise ValueError("Give a preset, or all four of period_a_start, period_a_end, "
                             "period_b_start, period_b_end.")
        a0, a1, b0, b1 = (_parse_date(d, n) for d, n in zip(
            dates, ["period_a_start", "period_a_end", "period_b_start", "period_b_end"]))
        if a0 <= b1 and b0 <= a1:
            raise ValueError("The two periods overlap; they must not share any day.")

    a = {"start": _day(a0), "end": _day(a1), **_stats(_window(df, a0, a1)[metric])}
    b = {"start": _day(b0), "end": _day(b1), **_stats(_window(df, b0, b1)[metric])}
    enough = min(a["days_with_data"], b["days_with_data"]) >= MIN_DAYS_PER_PERIOD
    diff = pct = None
    if enough:
        diff = _num(b["mean"] - a["mean"])
        pct = _num(100 * (b["mean"] - a["mean"]) / a["mean"]) if a["mean"] else None
    return {
        "metric": metric, "unit": m.unit, "preset": preset,
        "period_a": a, "period_b": b,
        "difference_b_minus_a": diff, "percent_change": pct,
        "enough_data": enough,
        "note": None if enough else
        f"At least {MIN_DAYS_PER_PERIOD} days with data are needed in each period.",
    }


def missing_data_report(df: pd.DataFrame, start_date: str | None = None,
                        end_date: str | None = None) -> dict[str, Any]:
    """Report, for every metric, which days have no valid measurement.

    Args:
        start_date, end_date: YYYY-MM-DD, inclusive. Default to the first and last date
            on which any metric has data.

    Returns, per metric: days with data, days missing, coverage in percent, the longest run
    of consecutive missing days, and the missing dates (at most 60 listed).
    """
    first, last = data_range(df)
    start = _parse_date(start_date, "start_date") if start_date else first
    end = _parse_date(end_date, "end_date") if end_date else last
    window = _window(df, start, end)
    n = len(window)
    metrics = {}
    for name, m in METRICS.items():
        missing = window[name].isna()
        run = longest = 0
        longest_end = None
        for date, is_missing in missing.items():
            run = run + 1 if is_missing else 0
            if run > longest:
                longest, longest_end = run, date
        gap = None
        if longest:
            gap = {"days": longest, "start": _day(longest_end - pd.Timedelta(days=longest - 1)),
                   "end": _day(longest_end)}
        metrics[name] = {
            "unit": m.unit,
            "days_with_data": int(n - missing.sum()),
            "days_missing": int(missing.sum()),
            "coverage_percent": _num(100 * (n - missing.sum()) / n),
            "longest_gap": gap,
            "missing": _dates(window.index[missing]),
        }
    return {"start": _day(start), "end": _day(end), "days": n, "metrics": metrics}
