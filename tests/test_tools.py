import pandas as pd
import pytest

from wearable.schema import to_daily_frame
from wearable.tools import compare_periods, missing_data_report, weekly_summary


# --- weekly_summary -----------------------------------------------------------

def test_weekly_summary_defaults_to_last_week(two_weeks):
    out = weekly_summary(two_weeks, "steps")
    assert (out["start"], out["end"]) == ("2024-01-08", "2024-01-14")
    # Present: 8000, 9000, 13000, 14000 (10th-12th missing).
    assert out["days_with_data"] == 4
    assert out["missing_dates"] == ["2024-01-10", "2024-01-11", "2024-01-12"]
    assert out["mean"] == 11000.0
    assert out["median"] == 11000.0
    assert out["total"] == 44000
    assert out["highest"] == {"date": "2024-01-14", "value": 14000.0}
    assert out["lowest"] == {"date": "2024-01-08", "value": 8000.0}
    assert len(out["daily"]) == 7 and out["daily"][2] == {"date": "2024-01-10", "value": None}


def test_weekly_summary_explicit_end_date(two_weeks):
    out = weekly_summary(two_weeks, "steps", end_date="2024-01-07")
    # 1000, 2000, 4000, 5000, 6000, 7000 (3rd missing).
    assert out["days_with_data"] == 6
    assert out["mean"] == 4166.7
    assert "total" in out


def test_weekly_summary_week_without_data(two_weeks):
    out = weekly_summary(two_weeks, "minutes_asleep", end_date="2024-01-07")
    assert out["days_with_data"] == 0
    assert out["mean"] is None and out["highest"] is None
    assert "total" not in out


def test_weekly_summary_tie_picks_first_date(two_weeks):
    out = weekly_summary(two_weeks, "minutes_asleep")
    assert out["highest"]["date"] == "2024-01-08"


def test_weekly_summary_rejects_dates_outside_data(two_weeks):
    with pytest.raises(ValueError, match="data covers 2024-01-01 to 2024-01-14"):
        weekly_summary(two_weeks, "steps", end_date="2023-06-01")
    with pytest.raises(ValueError, match="not a date"):
        weekly_summary(two_weeks, "steps", end_date="last week")


# --- compare_periods ----------------------------------------------------------

def test_compare_first_half_vs_second_half(two_weeks):
    out = compare_periods(two_weeks, "steps", preset="first_half_vs_second_half")
    assert out["period_a"]["start"] == "2024-01-01" and out["period_a"]["end"] == "2024-01-07"
    assert out["period_b"]["start"] == "2024-01-08" and out["period_b"]["end"] == "2024-01-14"
    assert out["period_a"]["mean"] == 4166.7
    assert out["period_b"]["mean"] == 11000.0
    assert out["difference_b_minus_a"] == 6833.3
    assert out["percent_change"] == 164.0
    assert out["enough_data"] is True


def test_compare_explicit_dates(two_weeks):
    out = compare_periods(two_weeks, "steps", period_a_start="2024-01-01",
                          period_a_end="2024-01-02", period_b_start="2024-01-13",
                          period_b_end="2024-01-14")
    # Two days each is below the 3-day minimum.
    assert out["period_a"]["days_with_data"] == 2
    assert out["enough_data"] is False
    assert out["difference_b_minus_a"] is None and out["note"]


def test_compare_needs_data_in_both_periods(two_weeks):
    out = compare_periods(two_weeks, "minutes_asleep", preset="first_half_vs_second_half")
    assert out["period_a"]["days_with_data"] == 0
    assert out["enough_data"] is False


def test_compare_last_4_weeks_preset():
    dates = pd.date_range("2024-01-01", periods=56, freq="D")
    df = to_daily_frame(pd.DataFrame({"date": dates, "steps": [5000] * 28 + [6000] * 28}))
    out = compare_periods(df, "steps", preset="last_4_weeks_vs_previous_4_weeks")
    assert (out["period_a"]["start"], out["period_a"]["end"]) == ("2024-01-01", "2024-01-28")
    assert (out["period_b"]["start"], out["period_b"]["end"]) == ("2024-01-29", "2024-02-25")
    assert out["difference_b_minus_a"] == 1000.0
    assert out["percent_change"] == 20.0
    assert out["period_a"]["std"] == 0.0


def test_compare_last_4_weeks_needs_8_weeks(two_weeks):
    with pytest.raises(ValueError, match="no 4 weeks before"):
        compare_periods(two_weeks, "steps", preset="last_4_weeks_vs_previous_4_weeks")


@pytest.mark.parametrize("kwargs, message", [
    ({"preset": "month_over_month"}, "Valid presets"),
    ({}, "Give a preset, or all four"),
    ({"preset": "first_half_vs_second_half", "period_a_start": "2024-01-01"}, "not both"),
    ({"period_a_start": "2024-01-01", "period_a_end": "2024-01-08",
      "period_b_start": "2024-01-08", "period_b_end": "2024-01-14"}, "overlap"),
])
def test_compare_argument_errors(two_weeks, kwargs, message):
    with pytest.raises(ValueError, match=message):
        compare_periods(two_weeks, "steps", **kwargs)


# --- missing_data_report ------------------------------------------------------

def test_missing_data_report_full_range(two_weeks):
    out = missing_data_report(two_weeks)
    assert (out["start"], out["end"], out["days"]) == ("2024-01-01", "2024-01-14", 14)
    steps = out["metrics"]["steps"]
    assert steps["days_with_data"] == 10 and steps["days_missing"] == 4
    assert steps["coverage_percent"] == 71.4
    assert steps["longest_gap"] == {"days": 3, "start": "2024-01-10", "end": "2024-01-12"}
    assert steps["missing"]["dates"] == ["2024-01-03", "2024-01-10", "2024-01-11", "2024-01-12"]
    sleep = out["metrics"]["minutes_asleep"]
    assert sleep["longest_gap"] == {"days": 7, "start": "2024-01-01", "end": "2024-01-07"}
    hr = out["metrics"]["mean_hr"]
    assert hr["days_with_data"] == 0 and hr["coverage_percent"] == 0.0


def test_missing_data_report_window_and_no_gap(two_weeks):
    out = missing_data_report(two_weeks, start_date="2024-01-13", end_date="2024-01-14")
    assert out["metrics"]["steps"]["longest_gap"] is None
    assert out["metrics"]["steps"]["coverage_percent"] == 100.0


def test_missing_dates_are_capped():
    dates = pd.date_range("2024-01-01", periods=100, freq="D")
    steps = [1000.0] + [float("nan")] * 98 + [1000.0]
    out = missing_data_report(to_daily_frame(pd.DataFrame({"date": dates, "steps": steps})))
    listed = out["metrics"]["steps"]["missing"]
    assert len(listed["dates"]) == 60 and listed["truncated"] is True


def test_tools_are_deterministic(two_weeks):
    assert weekly_summary(two_weeks, "steps") == weekly_summary(two_weeks, "steps")
    assert missing_data_report(two_weeks) == missing_data_report(two_weeks)
