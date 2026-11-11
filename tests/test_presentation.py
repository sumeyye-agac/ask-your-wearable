from datetime import date

import pandas as pd
import pytest

from wearable.agent import ToolCall
from wearable.guidelines import get_guideline
from wearable.presentation import (NOT_CONFIGURED, UsageLimiter, api_error_message, chart_for,
                                   credits)
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
