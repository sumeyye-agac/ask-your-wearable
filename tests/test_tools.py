import math
import statistics

import pandas as pd
import pytest

from wearable.schema import to_daily_frame
from wearable.guidelines import ACTIVITY_CAVEAT
from wearable.tools import (compare_periods, correlation, correlation_ci, last_complete_day,
                            missing_data_report, most_active_day, weekly_active_minutes,
                            weekly_summary)


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
    assert out["mean"] == 4167  # 25000 / 6 = 4166.67, shown as a whole number
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
        "dates_at_or_above": ["2024-01-01", "2024-01-03", "2024-01-04", "2024-01-05",
                              "2024-01-06"],
        "dates_below": ["2024-01-02"],
        "mean_minus_threshold": 20.5, "mean_minus_threshold_text": "20 min"}
    below = weekly_summary(_frame(minutes_asleep=[300.0] * 7), "minutes_asleep", threshold=420)
    assert below["threshold"]["mean_minus_threshold"] == -120.0
    assert below["threshold"]["mean_minus_threshold_text"] == "-2 h 00 min"
    with pytest.raises(ValueError, match="threshold"):
        weekly_summary(_frame(minutes_asleep=[300.0] * 7), "minutes_asleep", threshold="7h")


def test_weekly_summary_threshold_on_a_week_without_data(two_weeks):
    out = weekly_summary(two_weeks, "minutes_asleep", end_date="2024-01-07", threshold=420)
    assert out["threshold"]["days_at_or_above"] == 0 and out["threshold"]["days_below"] == 0
    assert out["threshold"]["dates_at_or_above"] == [] and out["threshold"]["dates_below"] == []
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
    assert out["period_a"]["mean"] == 4167
    assert out["period_b"]["mean"] == 11000
    assert out["difference_b_minus_a"] == 6833  # the difference of the two means shown
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
                                  "steps_above_mean": 2833, "steps_above_second": 1000}
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


# --- whole-number steps --------------------------------------------------------

def test_step_values_are_whole_numbers_and_halves_round_up():
    # Mean 8570.5, as in demo user 6962181067's last week.
    out = weekly_summary(_frame(steps=[5908, 6815, 4188, 12342, 15448, 6722]), "steps")
    numbers = [out["mean"], out["median"], out["range"], out["highest"]["value"],
               out["highest"]["above_mean"], out["lowest"]["below_mean"],
               *[d["value"] for d in out["daily"] if d["value"] is not None]]
    assert len(numbers) == 12 and all(isinstance(n, int) for n in numbers)
    assert out["mean"] == 8571 and out["median"] == 6769  # 8570.5 and 6768.5
    # Differences are those of the numbers shown: 15448 - 8571 and 8571 - 4188.
    assert out["highest"]["above_mean"] == 6877 and out["lowest"]["below_mean"] == 4383
    active = most_active_day(_frame(steps=[5908, 6815, 4188, 12342, 15448, 6722]))
    assert active["mean_steps"] == 8571
    assert active["most_active"]["steps_above_mean"] == 6877
    assert isinstance(active["mean_steps"], int)


def test_step_statistics_in_compare_periods_are_whole_numbers():
    df = _frame(steps=[1000, 1001, 1003, 2000, 2001, 2004])
    out = compare_periods(df, "steps", period_a_start="2024-01-01", period_a_end="2024-01-03",
                          period_b_start="2024-01-04", period_b_end="2024-01-06")
    a, b = out["period_a"], out["period_b"]
    assert (a["mean"], b["mean"], out["difference_b_minus_a"]) == (1001, 2002, 1001)
    assert all(isinstance(v, int) for v in (a["mean"], a["std"], b["mean"], b["std"]))
    assert out["percent_change"] == 100.0  # percentages keep one decimal


def test_sleep_and_heart_rate_keep_one_decimal():
    out = weekly_summary(_frame(minutes_asleep=[443, 298, 541, 489, 469, 452, 516]),
                         "minutes_asleep")
    assert out["mean"] == 458.3
    assert weekly_summary(_frame(mean_hr=[70.0, 71.0, 71.0]), "mean_hr")["mean"] == 70.7


# --- active minutes ------------------------------------------------------------

def _active(fairly, very):
    return _frame(fairly_active_minutes=fairly, very_active_minutes=very)


def test_weekly_summary_totals_active_minutes_without_hour_text():
    out = weekly_summary(_active([10, 20, 30, 0, 40, 25, 26], [0] * 7), "fairly_active_minutes")
    assert out["unit"] == "minutes" and out["total"] == 151
    assert out["mean"] == 22 and isinstance(out["mean"], int)  # 21.57
    assert "mean_text" not in out and "value_text" not in out["daily"][0]


def test_weekly_active_minutes_complete_week_reaching_the_moderate_target():
    out = weekly_active_minutes(_active([10, 20, 30, 0, 40, 25, 26], [5, 0, 10, 0, 0, 20, 0]))
    assert (out["start"], out["end"]) == ("2024-01-01", "2024-01-07")
    assert out["days_with_data"] == 7 and out["complete_week"] is True
    assert out["missing_dates"] == [] and out["note"] is None
    assert out["moderate"] == {
        "fitbit_metric": "fairly_active_minutes", "total_minutes": 151,
        "recommended_minutes": 150, "total_minus_recommended": 1,
        "reaches_recommendation": True}
    assert out["vigorous"] == {
        "fitbit_metric": "very_active_minutes", "total_minutes": 35,
        "recommended_minutes": 75, "total_minus_recommended": -40,
        "reaches_recommendation": False}
    # Main result: 151 + 2 x 35 = 221 moderate-equivalent minutes, 71 above 150.
    combined = out["combined"]
    assert combined["moderate_equivalent_minutes"] == 221
    assert combined["formula"] == "fairly active minutes + 2 x very active minutes"
    assert (combined["recommended_minutes"], combined["total_minus_recommended"]) == (150, 71)
    assert combined["reaches_recommendation"] is True
    assert "1 minute of vigorous-intensity activity is about the same as 2 minutes" in \
        combined["conversion"]["rule"]
    assert combined["conversion"]["url"].endswith("/adding-adults/what-counts.html")
    assert list(out).index("combined") < list(out).index("moderate")  # main result first
    assert out["daily"][2] == {"date": "2024-01-03", "fairly_active_minutes": 30,
                               "very_active_minutes": 10}


def test_weekly_active_minutes_complete_week_below_both_targets():
    out = weekly_active_minutes(_active([10] * 7, [10] * 7))
    assert out["moderate"]["total_minus_recommended"] == -80
    assert out["vigorous"]["total_minus_recommended"] == -5
    assert out["moderate"]["reaches_recommendation"] is False
    assert out["vigorous"]["reaches_recommendation"] is False
    # Neither target is reached alone, but together they are: 70 + 2 x 70 = 210.
    assert out["combined"]["moderate_equivalent_minutes"] == 210
    assert out["combined"]["reaches_recommendation"] is True
    low = weekly_active_minutes(_active([10] * 7, [5] * 7))   # 70 + 2 x 35 = 140
    assert low["combined"]["total_minus_recommended"] == -10
    assert low["combined"]["reaches_recommendation"] is False


def test_weekly_active_minutes_incomplete_week_is_unknown_not_missed():
    # 5 days with data: 100 moderate minutes so far (below 150), 80 vigorous (above 75).
    out = weekly_active_minutes(_active([20, 20, None, 20, 20, None, 20],
                                        [16, 16, None, 16, 16, None, 16]))
    assert out["days_with_data"] == 5 and out["complete_week"] is False
    assert out["missing_dates"] == ["2024-01-03", "2024-01-06"]
    assert out["moderate"]["total_minutes"] == 100
    assert out["moderate"]["reaches_recommendation"] is None   # may still have been reached
    assert out["vigorous"]["reaches_recommendation"] is True   # already reached
    assert out["combined"]["moderate_equivalent_minutes"] == 260
    assert out["combined"]["reaches_recommendation"] is True
    assert "Only 5 of 7 days" in out["note"] and "lower bound" in out["note"]
    assert out["daily"][2]["fairly_active_minutes"] is None
    below = weekly_active_minutes(_active([20, None, 20, 20, 20, 20, 20], [0, None] + [0] * 5))
    assert below["combined"]["moderate_equivalent_minutes"] == 120
    assert below["combined"]["reaches_recommendation"] is None  # unknown, not missed


def test_weekly_active_minutes_without_data_and_with_an_end_date(two_weeks):
    out = weekly_active_minutes(two_weeks)   # the fixture has no active minutes
    assert out["days_with_data"] == 0 and out["moderate"]["total_minutes"] is None
    assert out["moderate"]["reaches_recommendation"] is None
    assert out["combined"]["moderate_equivalent_minutes"] is None
    assert out["combined"]["reaches_recommendation"] is None
    assert out["note"] == "No active-minute data in this week."
    dated = weekly_active_minutes(_active([30] * 10, [0] * 10), end_date="2024-01-08")
    assert (dated["start"], dated["end"]) == ("2024-01-02", "2024-01-08")
    assert dated["moderate"]["total_minutes"] == 210


def test_weekly_active_minutes_always_carries_the_caveat_and_the_source():
    out = weekly_active_minutes(_active([30] * 7, [0] * 7))
    assert out["caveat"] == ACTIVITY_CAVEAT
    assert "not the same" in out["caveat"] and "Fitbit" in out["caveat"] and "CDC" in out["caveat"]
    assert out["recommendation_source"].startswith("CDC") and out["credit"].startswith("Source: CDC.")
    assert out["url"] == "https://www.cdc.gov/physical-activity-basics/guidelines/adults.html"


# --- the last complete day -----------------------------------------------------

def _partial_last_day() -> pd.DataFrame:
    """8 days; on the last one the export stopped early: sleep and heart rate, no steps."""
    return _frame(steps=[1000, 2000, 3000, 4000, 5000, 6000, 7000, None],
                  fairly_active_minutes=[10, 20, 30, 0, 40, 25, 26, None],
                  very_active_minutes=[0] * 7 + [None],
                  minutes_asleep=[400.0] * 7 + [500.0], mean_hr=[70.0] * 8)


def test_last_complete_day_skips_a_partial_final_day():
    df = _partial_last_day()
    assert last_complete_day(df) == pd.Timestamp("2024-01-07")
    # Either whole-day metric is enough to make a day complete.
    df.loc["2024-01-08", "very_active_minutes"] = 0.0
    assert last_complete_day(df) == pd.Timestamp("2024-01-08")


def test_last_complete_day_falls_back_when_there_is_no_whole_day_metric():
    assert last_complete_day(_frame(minutes_asleep=[400.0, 410.0, 420.0])) == \
        pd.Timestamp("2024-01-03")


def test_this_week_ends_on_the_last_complete_day_for_every_metric():
    df = _partial_last_day()
    steps = weekly_summary(df, "steps")
    assert (steps["start"], steps["end"]) == ("2024-01-01", "2024-01-07")
    assert steps["days_with_data"] == 7 and steps["missing_dates"] == []
    # Sleep uses the same week, so the night ending on the partial day is not in it.
    sleep = weekly_summary(df, "minutes_asleep")
    assert (sleep["start"], sleep["end"]) == ("2024-01-01", "2024-01-07")
    assert sleep["mean"] == 400.0
    active = weekly_active_minutes(df)
    assert active["end"] == "2024-01-07" and active["complete_week"] is True
    # An explicit end date still reaches the partial day.
    assert weekly_summary(df, "minutes_asleep", end_date="2024-01-08")["highest"]["value"] == 500.0


def test_last_4_weeks_preset_ends_on_the_last_complete_day():
    n = 60
    df = _frame(steps=[1000.0] * (n - 1) + [None], minutes_asleep=[420.0] * n)
    out = compare_periods(df, "minutes_asleep", preset="last_4_weeks_vs_previous_4_weeks")
    assert out["period_b"]["end"] == "2024-02-28"      # day 59, not the partial day 60
    assert out["period_b"]["start"] == "2024-02-01" and out["period_a"]["end"] == "2024-01-31"
    # The whole-range split still uses every date with data.
    halves = compare_periods(df, "minutes_asleep", preset="first_half_vs_second_half")
    assert halves["period_b"]["end"] == "2024-02-29"


def test_comparisons_say_the_tool_runs_no_significance_test(two_weeks):
    out = compare_periods(two_weeks, "steps", preset="first_half_vs_second_half")
    assert out["significance_test"].startswith("This tool does not run a significance test")
    corr = correlation(two_weeks, "steps", "minutes_asleep")
    assert corr["significance_test"].startswith("This tool does not run a significance test")
