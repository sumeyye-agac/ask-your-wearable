from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from wearable.agent import ToolCall
from wearable.guidelines import get_guideline
from wearable.presentation import (NOT_CONFIGURED, UsageLimiter, api_error_message, chart_for,
                                   credits, person_names, person_profile,
                                   to_altair, ACCENT, PERIOD_NAMES)
from wearable.registry import run_tool
from wearable.schema import to_daily_frame


def call(df, name, arguments, step=1):
    return ToolCall(step, name, arguments, run_tool(df, name, arguments), False)


# --- chart_for ----------------------------------------------------------------

def test_weekly_summary_chart_shows_sleep_in_hours(two_weeks):
    spec = chart_for([call(two_weeks, "weekly_summary",
                           {"metric": "minutes_asleep", "end_date": "2024-01-14"})], two_weeks)
    assert spec.kind == "bar" and spec.y == "Hours asleep"
    assert list(spec.data["date"]) == [f"2024-01-{d:02d}" for d in range(8, 15)]
    assert list(spec.data["Hours asleep"]) == [7.0] * 7    # 420 minutes


def test_weekly_summary_chart_keeps_missing_days(two_weeks):
    spec = chart_for([call(two_weeks, "weekly_summary",
                           {"metric": "steps", "end_date": "2024-01-14"})], two_weeks)
    assert len(spec.data) == 7
    assert spec.data["Steps"].isna().sum() == 3            # 10th to 12th missing


def test_most_active_day_chart_covers_the_tool_window(two_weeks):
    spec = chart_for([call(two_weeks, "most_active_day",
                           {"start_date": "2024-01-01", "end_date": "2024-01-07"})], two_weeks)
    assert list(spec.data["Steps"].fillna(-1)) == [1000, 2000, -1, 4000, 5000, 6000, 7000]


def test_correlation_chart_plots_the_pairs_the_tool_counted():
    x = list(range(1, 21))
    df = to_daily_frame(pd.DataFrame({"date": pd.date_range("2024-01-01", periods=20),
                                      "minutes_asleep": [360 + 6 * v for v in x],
                                      "steps": [1000 * v for v in x]}))
    c = call(df, "correlation", {"metric_x": "minutes_asleep", "metric_y": "steps"})
    spec = chart_for([c], df)
    assert spec.kind == "scatter" and len(spec.data) == c.output["n"] == 20
    assert spec.data["Hours asleep"].iloc[0] == pytest.approx(366 / 60)


def test_compare_periods_chart_needs_enough_data(two_weeks):
    c = call(two_weeks, "compare_periods",
             {"metric": "minutes_asleep", "preset": "first_half_vs_second_half"})
    assert c.output["enough_data"] is False
    assert chart_for([c], two_weeks) is None


def test_chart_uses_last_chartable_call_and_skips_errors(two_weeks):
    calls = [
        call(two_weeks, "weekly_summary", {"metric": "steps", "end_date": "2024-01-14"}),
        call(two_weeks, "get_guideline", {"topic": "sleep_duration"}),
        ToolCall(2, "weekly_summary", {"metric": "hrv"}, "Unknown metric", True),
    ]
    spec = chart_for(calls, two_weeks)
    assert spec.y == "Steps"
    assert chart_for(calls[1:], two_weeks) is None


# --- credits ------------------------------------------------------------------

def test_credit_shown_once_per_distinct_line(two_weeks):
    guideline = call(two_weeks, "get_guideline", {"topic": "sleep_duration"})
    calls = [guideline, guideline,
             call(two_weeks, "weekly_summary", {"metric": "steps", "end_date": "2024-01-14"})]
    assert credits(calls) == [get_guideline("sleep_duration")["credit"]]
    assert credits(calls)[0].startswith("Source: CDC.")


def test_no_credit_without_guideline(two_weeks):
    assert credits([call(two_weeks, "most_active_day", {})]) == []


# --- UsageLimiter -------------------------------------------------------------

def test_limiter_counts_questions_per_visitor():
    lim = UsageLimiter(per_visitor=2, daily_usd=1.0)
    assert lim.start("a") is None and lim.start("a") is None
    assert "limit per visitor" in lim.start("a")
    assert lim.start("b") is None and lim.remaining("b") == 1


def test_failed_question_is_given_back():
    lim = UsageLimiter(per_visitor=1, daily_usd=1.0)
    assert lim.start("a") is None
    lim.finish("a", 0.0, failed=True)
    assert lim.remaining("a") == 1


def test_daily_budget_stops_everyone():
    lim = UsageLimiter(per_visitor=10, daily_usd=0.01)
    assert lim.start("a") is None
    lim.finish("a", 0.012)
    assert "budget for today" in lim.start("b")


def test_limits_reset_on_a_new_day():
    today = [date(2026, 11, 11)]
    lim = UsageLimiter(per_visitor=1, daily_usd=0.01, today=lambda: today[0])
    lim.start("a")
    lim.finish("a", 0.02)
    assert lim.start("a") is not None
    today[0] = date(2026, 11, 12)
    assert lim.start("a") is None


# --- messages -----------------------------------------------------------------

@pytest.mark.parametrize("status, kind, words", [
    (402, "billing_error", "run out of credit"),
    (400, "billing_error", "run out of credit"),
    (401, "authentication_error", "not set up correctly"),
    (429, "rate_limit_error", "wait a minute"),
    (529, "overloaded_error", "could not be reached or is busy"),
    (None, None, "could not be reached or is busy"),
    (400, "invalid_request_error", "Something went wrong"),
])
def test_api_error_messages(status, kind, words):
    assert words in api_error_message(status, kind)


def test_not_configured_message_mentions_api_key():
    assert "API key" in NOT_CONFIGURED


# --- people -------------------------------------------------------------------

def test_person_names_follow_sorted_ids():
    assert person_names(["6962181067", "5553957443", "5577150313"]) == {
        "5553957443": "Person A", "5577150313": "Person B", "6962181067": "Person C"}


def test_person_profile_counts_only_what_the_table_has(two_weeks):
    # Steps on 10 of 14 days, sleep on the last 7 nights, no heart rate.
    assert person_profile(two_weeks) == ("1 Jan to 14 Jan 2024: 10 days of steps, "
                                         "7 nights of sleep, no heart rate.")


def test_person_profile_names_first_heart_rate_day():
    df = to_daily_frame(pd.DataFrame({"date": pd.date_range("2024-03-01", periods=5),
                                      "steps": [1000] * 5,
                                      "mean_hr": [None, None, 70, 72, None]}))
    assert person_profile(df).endswith("heart rate on 2 days (from 3 Mar).")


# --- chart titles, period labels, colour -----------------------------------------

def full_frame(n=40):
    """Every metric present on every day, so each chart can be built for each metric."""
    x = list(range(n))
    return to_daily_frame(pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=n),
        "steps": [5000 + 97 * (v % 11) for v in x],
        "minutes_asleep": [400 + 7 * (v % 5) for v in x],
        "minutes_in_bed": [450 + 5 * (v % 7) for v in x],
        "mean_hr": [70 + v % 9 for v in x],
        "fairly_active_minutes": [10 + v % 4 for v in x],
        "very_active_minutes": [5 + v % 3 for v in x]}))


def all_specs():
    df = full_frame()
    specs = []
    for metric in ["steps", "minutes_asleep", "minutes_in_bed", "mean_hr",
                   "fairly_active_minutes", "very_active_minutes"]:
        specs.append(chart_for([call(df, "weekly_summary", {"metric": metric})], df))
        specs.append(chart_for([call(df, "compare_periods", {
            "metric": metric, "preset": "first_half_vs_second_half"})], df))
        specs.append(chart_for([call(df, "correlation", {
            "metric_x": "steps" if metric != "steps" else "mean_hr", "metric_y": metric})], df))
    specs.append(chart_for([call(df, "weekly_active_minutes", {})], df))
    specs.append(chart_for([call(df, "most_active_day", {})], df))
    return specs


def test_no_chart_title_or_axis_repeats_a_word():
    for spec in all_specs():
        for text in (spec.title, spec.x_label, spec.y_label):
            words = text.lower().replace(",", " ").replace(":", " ").split()
            assert all(a != b for a, b in zip(words, words[1:])), text
    titles = {s.title for s in all_specs()}
    assert "Mean heart rate (bpm): daily average in each period" in titles


@pytest.mark.parametrize("preset, names", [
    ("first_half_vs_second_half", ["First half", "Second half"]),
    ("last_4_weeks_vs_previous_4_weeks", ["Previous 4 weeks", "Last 4 weeks"]),
])
def test_compare_chart_uses_short_period_names_with_dates_in_tooltip(preset, names):
    df = full_frame(70)
    spec = chart_for([call(df, "compare_periods", {"metric": "steps", "preset": preset})], df)
    assert list(spec.data["Period"]) == names and spec.x_angle == 0
    assert all(" to " in d for d in spec.data["Dates"])
    assert spec.tooltip == ["Period", "Dates", "Steps"]
    tips = [t["field"] for t in to_altair(spec).to_dict()["encoding"]["tooltip"]]
    assert tips == ["Period", "Dates", "Steps"]


def test_custom_periods_are_named_a_and_b():
    df = full_frame()
    spec = chart_for([call(df, "compare_periods", {
        "metric": "steps", "period_a_start": "2024-01-01", "period_a_end": "2024-01-07",
        "period_b_start": "2024-01-15", "period_b_end": "2024-01-21"})], df)
    assert list(spec.data["Period"]) == list(PERIOD_NAMES[None])


def test_charts_use_the_accent_colour():
    for spec in all_specs():
        chart = to_altair(spec, "#123456").to_dict()
        if isinstance(spec.y, list):
            assert chart["encoding"]["color"]["scale"]["range"][0] == "#123456"
        else:
            assert chart["mark"]["color"] == "#123456"


def test_default_accent_matches_the_theme():
    config = (Path(__file__).resolve().parents[1] / ".streamlit/config.toml").read_text()
    assert f'primaryColor = "{ACCENT}"' in config

