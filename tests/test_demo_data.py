"""Smoke tests on the committed demo file: the tools run on real data for every demo user."""

from pathlib import Path

import pandas as pd
import pytest

from wearable.schema import to_daily_frame
from wearable.tools import (compare_periods, correlation, missing_data_report,
                            most_active_day, weekly_summary)

DEMO = Path(__file__).resolve().parents[1] / "data/demo/demo_daily.csv"
USERS = [6962181067, 5553957443, 5577150313]


@pytest.fixture(scope="module")
def demo() -> pd.DataFrame:
    return pd.read_csv(DEMO)


@pytest.mark.parametrize("user", USERS)
def test_demo_user_runs_all_tools(demo, user):
    df = to_daily_frame(demo[demo["user_id"] == user].drop(columns="user_id"))
    assert df.index.min() >= pd.Timestamp("2016-03-11")
    assert df.index.max() <= pd.Timestamp("2016-05-12")
    # Coverage in the last week differs per user (5577150313 has only 2 nights), so check
    # consistency rather than a fixed number of days.
    week = weekly_summary(df, "minutes_asleep")
    assert len(week["daily"]) == 7
    assert week["days_with_data"] + len(week["missing_dates"]) == 7
    halves = compare_periods(df, "steps", preset="first_half_vs_second_half")
    assert halves["enough_data"] is True
    report = missing_data_report(df)
    assert report["metrics"]["steps"]["coverage_percent"] > 85
    assert report["metrics"]["mean_hr"]["days_with_data"] >= 30
    active = most_active_day(df)
    assert active["most_active"]["steps"] == max(d["steps"] for d in active["top_days"])
    sleep_steps = correlation(df, "minutes_asleep", "steps")
    assert sleep_steps["enough_data"] is True and sleep_steps["n"] >= 10
    low, high = sleep_steps["ci_95"]
    assert -1 <= low <= sleep_steps["r"] <= high <= 1
