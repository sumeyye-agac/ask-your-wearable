"""Analysis tools over one user's daily table.

Every function is deterministic, takes the daily frame from schema.to_daily_frame plus
JSON-friendly arguments (metric names, ISO dates), and returns a dict of plain Python
values that can be shown to a language model as-is. Errors are raised as ValueError with
a message that says what was wrong and what is valid.
"""

from __future__ import annotations

import math
from statistics import NormalDist
from typing import Any

import numpy as np
import pandas as pd

from wearable.guidelines import (ACTIVITY_CAVEAT, ACTIVITY_CONVERSION, ACTIVITY_WEEKLY_MINUTES,
                                 GUIDELINES, VIGOROUS_TO_MODERATE)
from wearable.schema import METRICS, Metric, check_metric

MIN_DAYS_PER_PERIOD = 3     # compare_periods refuses to compare periods with fewer days
MAX_LISTED_DATES = 60       # cap on date lists returned to the model
PRESETS = ("first_half_vs_second_half", "last_4_weeks_vs_previous_4_weeks")
MIN_PAIRS = 10              # correlation reports no coefficient below this many paired days
MAX_LAG_DAYS = 7
MAX_TOP_N = 10
CORRELATION_METHODS = ("spearman", "pearson")


# --- helpers ----------------------------------------------------------------

def _num(x: float | None, digits: int = 1) -> float | int | None:
    """Round for output. digits=0 gives a whole number, with halves rounded up."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    if digits == 0:
        return int(math.floor(float(x) + 0.5))
    return round(float(x), digits)


def _day(ts: pd.Timestamp) -> str:
    return ts.strftime("%Y-%m-%d")


def _hm(minutes: float) -> str:
    """Minutes as text, rounded to the minute: 458.3 -> '7 h 38 min', 13.9 -> '14 min'."""
    total = int(round(abs(minutes)))
    sign = "-" if minutes < 0 and total else ""
    if total < 60:
        return f"{sign}{total} min"
    return f"{sign}{total // 60} h {total % 60:02d} min"


def _add_text(out: dict[str, Any], m: Metric, *keys: str) -> dict[str, Any]:
    """For the sleep metrics, add '<key>_text' with the value as hours and minutes."""
    if m.as_hours:
        for key in keys:
            if out.get(key) is not None:
                out[f"{key}_text"] = _hm(out[key])
    return out


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


def last_complete_day(df: pd.DataFrame) -> pd.Timestamp:
    """The day that "this week" and "the last 4 weeks" end on.

    Steps and active minutes only get a value when all 24 hours of a day were recorded,
    so the last date on which one of them has a value is the last complete day. An export
    usually stops partway through its final day; that day is left out. A table without
    any of these metrics falls back to the last date with any data.
    """
    whole = [name for name, m in METRICS.items() if m.whole_day]
    has_whole = df[whole].notna().any(axis=1)
    return df.index[has_whole].max() if has_whole.any() else data_range(df)[1]


def _window(df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Rows from start to end inclusive, with absent dates as missing rows."""
    if start > end:
        raise ValueError(f"Start {_day(start)} is after end {_day(end)}.")
    first, last = data_range(df)
    if end < first or start > last:
        raise ValueError(f"No data between {_day(start)} and {_day(end)}; "
                         f"data covers {_day(first)} to {_day(last)}.")
    return df.reindex(pd.date_range(start, end, freq="D", name="date"))


def _stats(values: pd.Series, digits: int) -> dict[str, Any]:
    v = values.dropna()
    return {
        "days_with_data": int(v.size),
        "mean": _num(v.mean(), digits) if v.size else None,
        "std": _num(v.std(ddof=1), digits) if v.size > 1 else None,
    }


def _dates(index: pd.Index) -> dict[str, Any]:
    listed = [_day(d) for d in index[:MAX_LISTED_DATES]]
    return {"dates": listed, "truncated": len(index) > MAX_LISTED_DATES}


# --- tools ------------------------------------------------------------------

def weekly_summary(df: pd.DataFrame, metric: str, end_date: str | None = None,
                   threshold: float | None = None) -> dict[str, Any]:
    """Summarise one metric over the 7 days ending on end_date (inclusive).

    Args:
        metric: one of "steps" (steps/day), "minutes_asleep" (minutes/night),
            "minutes_in_bed" (minutes/night), "mean_hr" (bpm, mean of the day's readings),
            "fairly_active_minutes" or "very_active_minutes" (minutes/day at Fitbit
            intensity level 2 or 3).
        end_date: last day of the week, YYYY-MM-DD. Defaults to the last complete day
            (see last_complete_day), which is what "this week" means for this data.
        threshold: optional value in the metric's unit (for example 420 for 7 hours of
            sleep) to compare the week against.

    Returns the window, days with and without data, mean, median, the highest and lowest
    day with their distance from the mean, the range (highest minus lowest), every day's
    value (None when missing), and for steps and active minutes the weekly total. With a
    threshold it also returns how many days are at or above it and below it, and the mean
    minus the threshold. For the sleep metrics every value also comes as text in hours and
    minutes ("<key>_text"), so nothing has to be converted by the reader. Steps and active
    minutes are whole numbers. Every difference is the difference of the rounded values
    shown, so a reader who checks the subtraction gets the same number.
    """
    m = check_metric(metric)
    end = _parse_date(end_date, "end_date") if end_date else last_complete_day(df)
    start = end - pd.Timedelta(days=6)
    values = _window(df, start, end)[metric]
    present = values.dropna()
    out: dict[str, Any] = {
        "metric": metric, "unit": m.unit, "start": _day(start), "end": _day(end),
        "days_with_data": int(present.size),
        "missing_dates": [_day(d) for d in values.index[values.isna()]],
        "mean": None, "median": None, "highest": None, "lowest": None, "range": None,
        "daily": [_add_text({"date": _day(d), "value": _num(v, m.digits)}, m, "value")
                  for d, v in values.items()],
    }
    mean = None
    if present.size:
        mean = _num(present.mean(), m.digits)
        high, low = _num(present.max(), m.digits), _num(present.min(), m.digits)
        out["mean"] = mean
        out["median"] = _num(present.median(), m.digits)
        # idxmax/idxmin return the first date on ties, which keeps the result deterministic.
        out["highest"] = _add_text(
            {"date": _day(present.idxmax()), "value": high,
             "above_mean": _num(high - mean, m.digits)}, m, "value", "above_mean")
        out["lowest"] = _add_text(
            {"date": _day(present.idxmin()), "value": low,
             "below_mean": _num(mean - low, m.digits)}, m, "value", "below_mean")
        out["range"] = _num(high - low, m.digits)
    if m.weekly_total:
        out["total"] = int(present.sum()) if present.size else None
    if threshold is not None:
        if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) \
                or not math.isfinite(threshold):
            raise ValueError(f"threshold={threshold!r} is not valid; use a number in {m.unit}.")
        shown = _num(threshold, m.digits)
        out["threshold"] = _add_text({
            "value": shown,
            "days_at_or_above": int((present >= threshold).sum()),
            "days_below": int((present < threshold).sum()),
            "mean_minus_threshold": _num(mean - shown, m.digits) if present.size else None,
        }, m, "value", "mean_minus_threshold")
    return _add_text(out, m, "mean", "median", "range")


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
        last = last_complete_day(df)
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
        metric: "steps", "minutes_asleep", "minutes_in_bed", "mean_hr",
            "fairly_active_minutes" or "very_active_minutes".
        preset: "first_half_vs_second_half" (the user's data range split in two) or
            "last_4_weeks_vs_previous_4_weeks" (the 28 days ending on the last complete
            day against the 28 days before). Period A is always the earlier one.

    Returns per-period mean, standard deviation and days with data, the difference
    B minus A in the metric's unit and in percent, and which period is higher. For metrics
    in minutes the means and the difference also come as text in hours and minutes.
    If either period has fewer than 3 days with data, enough_data is False and the
    difference is None.
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

    a = _add_text({"start": _day(a0), "end": _day(a1),
                   **_stats(_window(df, a0, a1)[metric], m.digits)}, m, "mean")
    b = _add_text({"start": _day(b0), "end": _day(b1),
                   **_stats(_window(df, b0, b1)[metric], m.digits)}, m, "mean")
    enough = min(a["days_with_data"], b["days_with_data"]) >= MIN_DAYS_PER_PERIOD
    diff = pct = higher = None
    if enough:
        diff = _num(b["mean"] - a["mean"], m.digits)
        pct = _num(100 * (b["mean"] - a["mean"]) / a["mean"]) if a["mean"] else None
        higher = "period_b" if diff > 0 else "period_a" if diff < 0 else "equal"
    return _add_text({
        "metric": metric, "unit": m.unit, "preset": preset,
        "period_a": a, "period_b": b,
        "difference_b_minus_a": diff, "percent_change": pct, "higher_period": higher,
        "enough_data": enough,
        "note": None if enough else
        f"At least {MIN_DAYS_PER_PERIOD} days with data are needed in each period.",
    }, m, "difference_b_minus_a")


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


def most_active_day(df: pd.DataFrame, start_date: str | None = None,
                    end_date: str | None = None, top_n: int = 3) -> dict[str, Any]:
    """Find the day with the most steps, and the next most active days, in a date range.

    Activity here means steps per day; the data has no other activity measure.

    Args:
        start_date, end_date: YYYY-MM-DD, inclusive. Default to the first and last date
            on which any metric has data. For "this week", pass the 7 days ending on the
            last complete day.
        top_n: how many of the most active days to list, 1 to 10. Default 3.

    Returns the window, days with step data, the dates without step data (at most 60
    listed), the most active day (date, weekday, steps, and how many steps it is above the
    second most active day and above the window's mean), the top_n days in descending
    order of steps, each with its distance from the mean, and the mean steps/day in the
    window. Ties go to the earlier date. Days without step data are never counted as
    inactive.
    """
    if isinstance(top_n, bool) or not isinstance(top_n, int) or not 1 <= top_n <= MAX_TOP_N:
        raise ValueError(f"top_n={top_n!r} is not valid; use a whole number from 1 to {MAX_TOP_N}.")
    first, last = data_range(df)
    start = _parse_date(start_date, "start_date") if start_date else first
    end = _parse_date(end_date, "end_date") if end_date else last
    in_window = _window(df, start, end)["steps"]
    steps = in_window.dropna()
    mean = _num(steps.mean(), 0) if steps.size else None
    # A stable sort on descending steps keeps the earlier date first on ties.
    ranked = steps.sort_values(ascending=False, kind="stable")
    top = [{"date": _day(d), "weekday": d.day_name(), "steps": int(v),
            "steps_above_mean": int(v) - mean}
           for d, v in ranked.iloc[:top_n].items()]
    most = None
    if top:
        second = int(ranked.iloc[0] - ranked.iloc[1]) if steps.size > 1 else None
        most = {**top[0], "steps_above_second": second}
    return {
        "metric": "steps", "unit": "steps",
        "start": _day(start), "end": _day(end),
        "days": (end - start).days + 1,
        "days_with_data": int(steps.size),
        "missing": _dates(in_window.index[in_window.isna()]),
        "most_active": most,
        "top_days": top,
        "mean_steps": mean,
        "note": None if steps.size else "No step data in this window.",
    }


def weekly_active_minutes(df: pd.DataFrame, end_date: str | None = None) -> dict[str, Any]:
    """Add up a week's active minutes and compare them with CDC's weekly recommendation.

    Moderate activity is taken as Fitbit's fairly active minutes and vigorous activity as
    Fitbit's very active minutes. That mapping is an approximation: the result always
    carries a caveat saying so, and it must be passed on to the reader.

    Args:
        end_date: last day of the week, YYYY-MM-DD. Defaults to the last complete day.

    The main result is "combined": fairly active minutes plus 2 x very active minutes,
    against 150. The factor is CDC's rule of thumb that 1 minute of vigorous activity is
    about the same as 2 minutes of moderate activity. "moderate" and "vigorous" give the
    two totals on their own against 150 and 75, as detail. Each part has the total, the
    recommended minutes, total minus recommended, and reaches_recommendation. With missing
    days a total is a lower bound, so reaches_recommendation is True if the total already
    reaches the target and None (unknown) otherwise; it is False only for a complete week.
    Also returns the 7-day window, days with data, the missing dates and each day's minutes.
    """
    end = _parse_date(end_date, "end_date") if end_date else last_complete_day(df)
    start = end - pd.Timedelta(days=6)
    columns = {"moderate": "fairly_active_minutes", "vigorous": "very_active_minutes"}
    window = _window(df, start, end)[list(columns.values())]
    have = window.dropna()
    n, complete = len(have), len(have) == 7

    def against(total: int | None, target: int) -> dict[str, Any]:
        reaches = None
        if total is not None:
            reaches = True if total >= target else (False if complete else None)
        return {"recommended_minutes": target,
                "total_minus_recommended": total - target if total is not None else None,
                "reaches_recommendation": reaches}

    def part(kind: str) -> dict[str, Any]:
        total = int(have[columns[kind]].sum()) if n else None
        return {"fitbit_metric": columns[kind], "total_minutes": total,
                **against(total, ACTIVITY_WEEKLY_MINUTES[kind])}

    moderate, vigorous = part("moderate"), part("vigorous")
    equivalent = None
    if n:
        equivalent = moderate["total_minutes"] + VIGOROUS_TO_MODERATE * vigorous["total_minutes"]
    combined = {
        "moderate_equivalent_minutes": equivalent,
        "formula": f"fairly active minutes + {VIGOROUS_TO_MODERATE} x very active minutes",
        **against(equivalent, ACTIVITY_WEEKLY_MINUTES["moderate"]),
        "conversion": ACTIVITY_CONVERSION,
    }
    note = None
    if n == 0:
        note = "No active-minute data in this week."
    elif not complete:
        note = (f"Only {n} of 7 days have data, so the totals are a lower bound for the "
                f"week and a total below the recommendation does not show it was missed.")
    source = GUIDELINES["physical_activity"]
    return {
        "start": _day(start), "end": _day(end), "days_with_data": n,
        "missing_dates": [_day(d) for d in window.index[window.isna().any(axis=1)]],
        "complete_week": complete,
        "combined": combined,
        "moderate": moderate, "vigorous": vigorous,
        "daily": [{"date": _day(d),
                   "fairly_active_minutes": _num(row["fairly_active_minutes"], 0),
                   "very_active_minutes": _num(row["very_active_minutes"], 0)}
                  for d, row in window.iterrows()],
        "note": note,
        "caveat": ACTIVITY_CAVEAT,
        "recommendation_source": source["source"], "url": source["url"],
        "credit": source["credit"],
    }


def _ranks(values: np.ndarray) -> np.ndarray:
    """Ranks starting at 1, with ties given their average rank."""
    return pd.Series(values).rank(method="average").to_numpy()


def correlation_ci(r: float, n: int, method: str, level: float = 0.95) -> tuple[float, float]:
    """Confidence interval for a correlation coefficient via Fisher's z transform.

    Pearson uses the standard error 1/sqrt(n-3). Spearman uses the Bonett & Wright (2000,
    Psychometrika 65:23-28) standard error sqrt((1 + r^2/2) / (n-3)). Both are normal
    approximations; they assume independent pairs, which consecutive days are not quite.
    """
    if n <= 3:
        raise ValueError("A confidence interval needs more than 3 pairs.")
    if abs(r) >= 1.0:
        return float(r), float(r)
    variance = (1 + r * r / 2) if method == "spearman" else 1.0
    se = math.sqrt(variance / (n - 3))
    zq = NormalDist().inv_cdf(0.5 + level / 2)
    z = math.atanh(r)
    return math.tanh(z - zq * se), math.tanh(z + zq * se)


def paired_days(df: pd.DataFrame, metric_x: str, metric_y: str, lag_days: int,
                start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """The days correlation uses: metric_x on day d (start <= d <= end) as column "x" and
    metric_y on day d+lag_days as column "y", indexed by d, only where both exist."""
    # The daily frame has one row per calendar day, so a row shift is a day shift.
    y_later = df[metric_y].shift(-lag_days)
    in_range = (df.index >= start) & (df.index <= end)
    return pd.DataFrame({"x": df[metric_x], "y": y_later})[in_range].dropna()


def correlation(df: pd.DataFrame, metric_x: str, metric_y: str, lag_days: int = 0,
                method: str = "spearman", start_date: str | None = None,
                end_date: str | None = None) -> dict[str, Any]:
    """Correlate two daily metrics, pairing metric_x on day d with metric_y on day d+lag_days.

    Sleep metrics are dated by the wake-up day, so with lag_days=0 a night's sleep is
    already paired with the day that follows it ("do I walk less after short sleep?" is
    metric_x="minutes_asleep", metric_y="steps", lag_days=0).

    Args:
        metric_x, metric_y: "steps", "minutes_asleep", "minutes_in_bed", "mean_hr",
            "fairly_active_minutes" or "very_active_minutes".
        lag_days: 0 to 7. metric_y is taken this many days after metric_x.
        method: "spearman" (default; rank-based, robust to unusual days) or "pearson"
            (linear).
        start_date, end_date: YYYY-MM-DD, inclusive range for the metric_x day. Default to
            the user's whole data range.

    Returns n (days where both values exist), the coefficient r from -1 to 1 (positive
    means the two rise together), its 95% confidence interval, and whether that interval
    excludes 0. With fewer than 10 pairs, or if a metric does not vary, r and the interval
    are None and note says why. A correlation says nothing about cause.
    """
    check_metric(metric_x)
    check_metric(metric_y)
    if method not in CORRELATION_METHODS:
        raise ValueError(f"Unknown method {method!r}. Valid methods: "
                         f"{', '.join(CORRELATION_METHODS)}.")
    if isinstance(lag_days, bool) or not isinstance(lag_days, int) \
            or not 0 <= lag_days <= MAX_LAG_DAYS:
        raise ValueError(f"lag_days={lag_days!r} is not valid; use a whole number "
                         f"from 0 to {MAX_LAG_DAYS}.")
    if metric_x == metric_y and lag_days == 0:
        raise ValueError("A metric correlated with itself on the same day is always 1; "
                         "pick two different metrics or a lag of at least 1 day.")

    first, last = data_range(df)
    start = _parse_date(start_date, "start_date") if start_date else first
    end = _parse_date(end_date, "end_date") if end_date else last
    _window(df, start, end)  # validates the range
    pairs = paired_days(df, metric_x, metric_y, lag_days, start, end)
    n = len(pairs)

    out: dict[str, Any] = {
        "metric_x": metric_x, "metric_y": metric_y, "lag_days": lag_days,
        "pairing": f"{metric_x} on day d with {metric_y} on day d+{lag_days}",
        "method": method, "start": _day(start), "end": _day(end),
        "n": n, "r": None, "ci_95": None, "ci_excludes_zero": None,
        "enough_data": False, "note": None,
    }
    if n < MIN_PAIRS:
        out["note"] = f"Only {n} days have both values; at least {MIN_PAIRS} are needed."
        return out
    x, y = pairs["x"].to_numpy(), pairs["y"].to_numpy()
    if method == "spearman":
        x, y = _ranks(x), _ranks(y)
    if np.std(x) == 0 or np.std(y) == 0:
        out["note"] = "One of the metrics has the same value on every paired day."
        return out
    r = float(np.corrcoef(x, y)[0, 1])
    low, high = correlation_ci(r, n, method)
    out.update({
        "r": round(r, 3), "ci_95": [round(low, 3), round(high, 3)],
        "ci_excludes_zero": bool(low > 0 or high < 0), "enough_data": True,
    })
    return out
