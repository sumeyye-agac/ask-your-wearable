import math
import statistics

import pandas as pd
import pytest

from wearable.schema import to_daily_frame
from wearable.tools import (compare_periods, correlation, correlation_ci, missing_data_report,
                            most_active_day, weekly_summary)


def _frame(**columns) -> pd.DataFrame:
    n = len(next(iter(columns.values())))
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    return to_daily_frame(pd.DataFrame({"date": dates, **columns}))


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
    assert out["highest"] == {"date": "2024-01-14", "value": 14000.0, "above_mean": 3000.0}
    assert out["lowest"] == {"date": "2024-01-08", "value": 8000.0, "below_mean": 3000.0}
    assert out["range"] == 6000.0
    assert "mean_text" not in out and "threshold" not in out  # steps are not minutes
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


def test_weekly_summary_gives_minutes_as_hours_and_minutes():
    out = weekly_summary(_frame(minutes_asleep=[443, 298, 541, 489, 469, 452, 516]),
                         "minutes_asleep")
    assert (out["mean"], out["mean_text"]) == (458.3, "7 h 38 min")
    assert (out["median"], out["median_text"]) == (469.0, "7 h 49 min")
    assert (out["range"], out["range_text"]) == (243.0, "4 h 03 min")
    assert out["lowest"] == {"date": "2024-01-02", "value": 298.0, "value_text": "4 h 58 min",
                             "below_mean": 160.3, "below_mean_text": "2 h 40 min"}
    assert out["highest"]["above_mean_text"] == "1 h 23 min"
    assert out["daily"][6] == {"date": "2024-01-07", "value": 516.0, "value_text": "8 h 36 min"}


def test_weekly_summary_compares_with_a_threshold():
    out = weekly_summary(_frame(minutes_asleep=[443, 298, 541, 489, 420, 452, None]),
                         "minutes_asleep", threshold=420)
    # 420 itself counts as at or above; the missing night counts as neither.
    assert out["threshold"] == {
        "value": 420.0, "value_text": "7 h 00 min", "days_at_or_above": 5, "days_below": 1,
        "mean_minus_threshold": 20.5, "mean_minus_threshold_text": "20 min"}
    below = weekly_summary(_frame(minutes_asleep=[300.0] * 7), "minutes_asleep", threshold=420)
    assert below["threshold"]["mean_minus_threshold"] == -120.0
    assert below["threshold"]["mean_minus_threshold_text"] == "-2 h 00 min"
    with pytest.raises(ValueError, match="threshold"):
        weekly_summary(_frame(minutes_asleep=[300.0] * 7), "minutes_asleep", threshold="7h")


def test_weekly_summary_threshold_on_a_week_without_data(two_weeks):
    out = weekly_summary(two_weeks, "minutes_asleep", end_date="2024-01-07", threshold=420)
    assert out["threshold"]["days_at_or_above"] == 0 and out["threshold"]["days_below"] == 0
    assert out["threshold"]["mean_minus_threshold"] is None


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


# --- most_active_day ----------------------------------------------------------

def test_most_active_day_full_range(two_weeks):
    out = most_active_day(two_weeks)
    assert (out["start"], out["end"], out["days"]) == ("2024-01-01", "2024-01-14", 14)
    assert out["days_with_data"] == 10
    # 14000 leads the second day (13000) by 1000 and the mean (6900) by 7100.
    assert out["most_active"] == {"date": "2024-01-14", "weekday": "Sunday", "steps": 14000,
                                  "steps_above_mean": 7100.0, "steps_above_second": 1000}
    assert [d["steps"] for d in out["top_days"]] == [14000, 13000, 9000]
    assert [d["steps_above_mean"] for d in out["top_days"]] == [7100.0, 6100.0, 2100.0]
    assert out["missing"] == {"dates": ["2024-01-03", "2024-01-10", "2024-01-11",
                                        "2024-01-12"], "truncated": False}
    # 1+2+4+5+6+7+8+9+13+14 thousand over 10 days.
    assert out["mean_steps"] == 6900.0


def test_most_active_day_window_and_top_n(two_weeks):
    out = most_active_day(two_weeks, start_date="2024-01-01", end_date="2024-01-07", top_n=1)
    # The lead over the second day is reported even when top_n=1 hides that day.
    assert out["most_active"] == {"date": "2024-01-07", "weekday": "Sunday", "steps": 7000,
                                  "steps_above_mean": 2833.3, "steps_above_second": 1000}
    assert len(out["top_days"]) == 1
    assert out["missing"]["dates"] == ["2024-01-03"]


def test_most_active_day_with_a_single_day_has_no_second_day():
    out = most_active_day(_frame(steps=[5000, None, None]))
    assert out["most_active"]["steps_above_second"] is None
    assert out["most_active"]["steps_above_mean"] == 0.0


def test_most_active_day_without_steps(two_weeks):
    out = most_active_day(two_weeks, start_date="2024-01-10", end_date="2024-01-12")
    assert out["days_with_data"] == 0
    assert out["most_active"] is None and out["top_days"] == [] and out["note"]
    assert out["missing"]["dates"] == ["2024-01-10", "2024-01-11", "2024-01-12"]


def test_most_active_day_tie_picks_first_date():
    out = most_active_day(_frame(steps=[5000, 7000, 7000]))
    assert out["most_active"]["date"] == "2024-01-02"
    assert [d["date"] for d in out["top_days"]] == ["2024-01-02", "2024-01-03", "2024-01-01"]


@pytest.mark.parametrize("top_n", [0, 11, 2.5, True])
def test_most_active_day_rejects_bad_top_n(two_weeks, top_n):
    with pytest.raises(ValueError, match="top_n"):
        most_active_day(two_weeks, top_n=top_n)


# --- correlation --------------------------------------------------------------

def test_correlation_ci_textbook_value():
    # r = 0.5, n = 28: z = 0.549, se = 0.2, so 95% CI in z is 0.157..0.941 -> r 0.156..0.735.
    low, high = correlation_ci(0.5, 28, "pearson")
    assert low == pytest.approx(0.156, abs=1e-3)
    assert high == pytest.approx(0.735, abs=1e-3)


def test_spearman_ci_is_wider_by_bonett_wright_factor():
    r, n = 0.5, 28
    p_low, p_high = correlation_ci(r, n, "pearson")
    s_low, s_high = correlation_ci(r, n, "spearman")
    factor = math.sqrt(1 + r * r / 2)
    assert math.atanh(s_high) - math.atanh(r) == pytest.approx(
        factor * (math.atanh(p_high) - math.atanh(r)))
    assert s_low < p_low


def test_pearson_matches_statistics_module():
    x = list(range(1, 13))
    y = [2, 1, 4, 3, 6, 5, 8, 7, 10, 9, 12, 11]
    out = correlation(_frame(steps=x, mean_hr=y), "steps", "mean_hr", method="pearson")
    assert out["n"] == 12 and out["enough_data"] is True
    assert out["r"] == round(statistics.correlation(x, y), 3)
    low, high = out["ci_95"]
    assert low < out["r"] < high and out["ci_excludes_zero"] is True


def test_spearman_is_one_for_monotonic_nonlinear():
    x = list(range(1, 13))
    y = [v ** 3 for v in x]
    df = _frame(steps=x, mean_hr=y)
    spearman = correlation(df, "steps", "mean_hr")
    assert spearman["method"] == "spearman"
    assert spearman["r"] == 1.0 and spearman["ci_95"] == [1.0, 1.0]
    assert correlation(df, "steps", "mean_hr", method="pearson")["r"] < 1.0


def test_lag_pairs_x_with_the_next_day():
    x = [3, 9, 1, 7, 2, 8, 5, 6, 4, 10, 0, 11, 2]
    # mean_hr on day d+1 equals steps on day d.
    y = [50.0] + [60 + v for v in x[:-1]]
    df = _frame(steps=x, mean_hr=y)
    lagged = correlation(df, "steps", "mean_hr", lag_days=1, method="pearson")
    assert lagged["n"] == 12 and lagged["r"] == 1.0
    assert lagged["pairing"] == "steps on day d with mean_hr on day d+1"
    assert abs(correlation(df, "steps", "mean_hr", method="pearson")["r"]) < 0.5


def test_correlation_counts_only_days_with_both_values(two_weeks):
    # Sleep exists only in week 2, where steps are present on 4 days.
    out = correlation(two_weeks, "minutes_asleep", "steps")
    assert out["n"] == 4 and out["enough_data"] is False
    assert out["r"] is None and out["ci_95"] is None and "at least 10" in out["note"]


def test_correlation_with_constant_metric():
    out = correlation(_frame(steps=list(range(15)), minutes_asleep=[420] * 15),
                      "minutes_asleep", "steps")
    assert out["n"] == 15 and out["r"] is None and "same value" in out["note"]


def test_correlation_date_range_limits_pairs():
    x = list(range(20))
    out = correlation(_frame(steps=x, mean_hr=x), "steps", "mean_hr", lag_days=1,
                      start_date="2024-01-01", end_date="2024-01-12")
    # x days 1..12, y taken from days 2..13.
    assert out["n"] == 12 and out["r"] == 1.0


@pytest.mark.parametrize("kwargs, message", [
    ({"metric_x": "steps", "metric_y": "steps"}, "itself"),
    ({"metric_x": "steps", "metric_y": "hrv"}, "Valid metrics"),
    ({"metric_x": "steps", "metric_y": "mean_hr", "lag_days": 8}, "lag_days"),
    ({"metric_x": "steps", "metric_y": "mean_hr", "lag_days": -1}, "lag_days"),
    ({"metric_x": "steps", "metric_y": "mean_hr", "method": "kendall"}, "Valid methods"),
])
def test_correlation_argument_errors(two_weeks, kwargs, message):
    with pytest.raises(ValueError, match=message):
        correlation(two_weeks, **kwargs)


def test_new_tools_are_deterministic(two_weeks):
    assert most_active_day(two_weeks) == most_active_day(two_weeks)
    assert correlation(two_weeks, "steps", "minutes_in_bed") == \
        correlation(two_weeks, "steps", "minutes_in_bed")


# --- comparisons returned so the reader never has to compute -------------------

def test_compare_periods_names_the_higher_period_and_gives_text_for_minutes():
    df = _frame(minutes_asleep=[400.0] * 5 + [430.0] * 5, steps=[9000.0] * 5 + [6000.0] * 5)
    dates = dict(period_a_start="2024-01-01", period_a_end="2024-01-05",
                 period_b_start="2024-01-06", period_b_end="2024-01-10")
    sleep = compare_periods(df, "minutes_asleep", **dates)
    assert sleep["higher_period"] == "period_b"
    assert (sleep["difference_b_minus_a"], sleep["difference_b_minus_a_text"]) == \
        (30.0, "30 min")
    assert sleep["period_a"]["mean_text"] == "6 h 40 min"
    steps = compare_periods(df, "steps", **dates)
    assert steps["higher_period"] == "period_a" and steps["difference_b_minus_a"] == -3000.0
    assert "difference_b_minus_a_text" not in steps and "mean_text" not in steps["period_a"]


def test_compare_periods_without_enough_data_names_no_higher_period(two_weeks):
    out = compare_periods(two_weeks, "minutes_asleep", preset="first_half_vs_second_half")
    assert out["enough_data"] is False and out["higher_period"] is None
    assert "difference_b_minus_a_text" not in out
