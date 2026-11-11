"""The tools as a language model sees them: names, descriptions and argument schemas.

This is the single place that maps a tool name to its function. The agent uses it now and
the MCP server will reuse it. Descriptions say what each tool returns, the valid values,
the units and how to read the result; the functions themselves live in tools.py.

Schemas are written for strict tool use: every object sets additionalProperties to false
and closed sets of values are enums, so a call that reaches run_tool has valid names and
types. Value errors (a date outside the data, overlapping periods) are still raised by the
tools as ValueError and are meant to be shown to the model.
"""

from __future__ import annotations

from typing import Any, Callable

import pandas as pd

from wearable import tools
from wearable.guidelines import TOPICS, get_guideline
from wearable.schema import METRICS

_METRIC = {
    "type": "string", "enum": list(METRICS),
    "description": "steps (steps/day), minutes_asleep (minutes/night), minutes_in_bed "
                   "(minutes/night), mean_hr (bpm, mean of the day's readings; not "
                   "resting heart rate), fairly_active_minutes or very_active_minutes "
                   "(minutes/day at Fitbit intensity level 2 or 3; Fitbit's own estimate "
                   "of moderate and vigorous activity). Sleep is dated by the wake-up day.",
}


def _date(what: str) -> dict[str, Any]:
    return {"type": "string", "format": "date", "description": f"{what} YYYY-MM-DD, inclusive."}


def _spec(name: str, description: str, properties: dict[str, Any],
          required: list[str]) -> dict[str, Any]:
    return {
        "name": name, "description": description, "strict": True,
        "input_schema": {"type": "object", "properties": properties,
                         "required": required, "additionalProperties": False},
    }


TOOL_SPECS: list[dict[str, Any]] = [
    _spec(
        "weekly_summary",
        "Summarise one metric over the 7 days ending on end_date. Use it for questions "
        "about a week ('how was my sleep this week?'). Returns the window, days with data, "
        "the missing dates, mean, median, the highest and lowest day with their distance "
        "from the mean, the range (highest minus lowest), every day's value (null when "
        "there is no measurement) and, for steps and active minutes, the weekly total. "
        "Steps and active minutes are whole numbers. With a threshold it also returns "
        "days_at_or_above, days_below and mean_minus_threshold. For the sleep metrics "
        "every value also comes as hours and minutes in a '_text' field. Call it "
        "once per metric.",
        {"metric": _METRIC,
         "end_date": _date("Last day of the week. Omit for 'this week': the 7 days ending "
                           "on the last date with data."),
         "threshold": {"type": "number",
                       "description": "Optional value in the metric's unit to compare the "
                                      "week against, for example 420 for 7 hours of sleep "
                                      "or a threshold returned by get_guideline."}},
        ["metric"],
    ),
    _spec(
        "compare_periods",
        "Compare the daily mean of one metric between two periods that do not overlap. "
        "Give either a preset or all four dates, never both. Returns, per period, the mean, "
        "standard deviation and days with data, plus difference_b_minus_a in the metric's "
        "unit, percent_change (positive means period B is higher) and higher_period. For "
        "metrics in minutes the means and the difference also come as hours and minutes in "
        "'_text' fields. Period A is the "
        "earlier one in both presets. If a period has fewer than 3 days with data, "
        "enough_data is false and no difference is given. No significance test is done.",
        {"metric": _METRIC,
         "preset": {"type": "string", "enum": list(tools.PRESETS),
                    "description": "first_half_vs_second_half splits the whole data range "
                                   "in two. last_4_weeks_vs_previous_4_weeks compares the "
                                   "28 days ending on the last date with data against the "
                                   "28 days before."},
         "period_a_start": _date("First day of period A."),
         "period_a_end": _date("Last day of period A."),
         "period_b_start": _date("First day of period B."),
         "period_b_end": _date("Last day of period B.")},
        ["metric"],
    ),
    _spec(
        "missing_data_report",
        "Report, for every metric at once, how complete the data is in a date range. "
        "Use it for questions about gaps or how much data there is, and before trusting a "
        "result that depends on coverage. Returns, per metric, days with data, days missing, "
        "coverage in percent, the longest run of consecutive missing days and the missing "
        "dates (at most 60 listed).",
        {"start_date": _date("First day. Omit for the first date with data."),
         "end_date": _date("Last day. Omit for the last date with data.")},
        [],
    ),
    _spec(
        "most_active_day",
        "Find the day with the most steps in a date range, and the next most active days. "
        "Activity means steps per day; there is no other activity measure. Returns the most "
        "active day (date, weekday, steps, steps_above_second: its lead over the second "
        "most active day, steps_above_mean: its lead over the window's mean), the top_n "
        "days in descending order, each with steps_above_mean, days with step data, the "
        "dates without step data and the mean steps/day in the window. Days without step "
        "data are skipped, never counted as inactive. For 'this week' pass the 7 days ending on the last date "
        "with data.",
        {"start_date": _date("First day. Omit for the first date with data."),
         "end_date": _date("Last day. Omit for the last date with data."),
         "top_n": {"type": "integer", "enum": list(range(1, tools.MAX_TOP_N + 1)),
                   "description": "How many days to list. Default 3."}},
        [],
    ),
    _spec(
        "correlation",
        "Measure how two daily metrics move together, pairing metric_x on day d with "
        "metric_y on day d+lag_days. Sleep is dated by the wake-up day, so lag_days=0 "
        "already pairs a night with the day that follows it: 'do I walk less after short "
        "sleep?' is metric_x=minutes_asleep, metric_y=steps, lag_days=0. Returns n (days "
        "with both values), r from -1 to 1 (positive means they rise together), its 95% "
        "confidence interval and ci_excludes_zero. If the interval includes 0 the data "
        "shows no clear relationship. With fewer than 10 paired days r is null and note "
        "says why. A correlation says nothing about cause.",
        {"metric_x": _METRIC, "metric_y": _METRIC,
         "lag_days": {"type": "integer", "enum": list(range(tools.MAX_LAG_DAYS + 1)),
                      "description": "metric_y is taken this many days after metric_x. "
                                     "Default 0."},
         "method": {"type": "string", "enum": list(tools.CORRELATION_METHODS),
                    "description": "spearman (default; rank-based, robust to unusual "
                                   "days) or pearson (linear)."},
         "start_date": _date("First metric_x day. Omit for the whole data range."),
         "end_date": _date("Last metric_x day. Omit for the whole data range.")},
        ["metric_x", "metric_y"],
    ),
    _spec(
        "weekly_active_minutes",
        "Add up one week's active minutes and compare them with CDC's weekly "
        "recommendation for adults. Use it for 'am I active enough?'. Moderate activity is "
        "taken as Fitbit's fairly active minutes and vigorous as Fitbit's very active "
        "minutes. Returns, for each, total_minutes, recommended_minutes (150 moderate, 75 "
        "vigorous), total_minus_recommended and reaches_recommendation (true, false, or "
        "null when days are missing and the total so far is below the target), plus "
        "reaches_either_alone, days_with_data, missing_dates, each day's minutes, and a "
        "caveat. The caveat says Fitbit's intensity estimate is not CDC's definition; "
        "always pass it on in the answer.",
        {"end_date": _date("Last day of the week. Omit for 'this week': the 7 days ending "
                           "on the last date with data.")},
        [],
    ),
    _spec(
        "get_guideline",
        "Look up a public health recommendation from a small curated reference (CDC pages). "
        "Use it when a question asks whether an amount is enough, healthy or recommended. "
        "Returns the recommendation statements with the population each applies to, the "
        "source with its URL and date, a credit line, and whether the data can be compared "
        "with it: comparable_metric and threshold say how, and applies_to_data "
        "gives the limits of that comparison. It does not look at the person's data.",
        {"topic": {"type": "string", "enum": list(TOPICS),
                   "description": "sleep_duration (hours of sleep per day for adults, by "
                                  "age) or physical_activity (weekly activity for adults)."}},
        ["topic"],
    ),
]


def _get_guideline(df: pd.DataFrame, topic: str) -> dict[str, Any]:
    """get_guideline does not depend on the user's data; df is accepted and ignored."""
    return get_guideline(topic)


TOOL_FUNCTIONS: dict[str, Callable[..., dict[str, Any]]] = {
    "weekly_summary": tools.weekly_summary,
    "compare_periods": tools.compare_periods,
    "missing_data_report": tools.missing_data_report,
    "most_active_day": tools.most_active_day,
    "correlation": tools.correlation,
    "weekly_active_minutes": tools.weekly_active_minutes,
    "get_guideline": _get_guideline,
}

_ARGUMENTS = {s["name"]: set(s["input_schema"]["properties"]) for s in TOOL_SPECS}


def run_tool(df: pd.DataFrame, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Run one tool by name on a user's daily frame.

    Raises ValueError, with a message fit to show to the model, for an unknown tool, an
    unknown argument or an invalid value.
    """
    if name not in TOOL_FUNCTIONS:
        raise ValueError(f"Unknown tool {name!r}. Valid tools: {', '.join(TOOL_FUNCTIONS)}.")
    unknown = set(arguments) - _ARGUMENTS[name]
    if unknown:
        raise ValueError(f"Unknown argument(s) for {name}: {', '.join(sorted(unknown))}. "
                         f"Valid arguments: {', '.join(sorted(_ARGUMENTS[name]))}.")
    return TOOL_FUNCTIONS[name](df, **arguments)
