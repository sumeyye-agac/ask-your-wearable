"""The tool specs shown to the model must match the functions they describe."""

import inspect
import re
from pathlib import Path

import pandas as pd
import pytest

from wearable import tools
from wearable.registry import TOOL_FUNCTIONS, TOOL_SPECS, run_tool, with_weekdays
from wearable.schema import METRICS


def test_every_tool_function_has_a_spec_and_the_reverse():
    assert [s["name"] for s in TOOL_SPECS] == list(TOOL_FUNCTIONS)


@pytest.mark.parametrize("spec", TOOL_SPECS, ids=lambda s: s["name"])
def test_spec_arguments_match_the_function_signature(spec):
    params = inspect.signature(TOOL_FUNCTIONS[spec["name"]]).parameters
    arguments = {n: p for n, p in params.items() if n != "df"}
    schema = spec["input_schema"]
    assert set(schema["properties"]) == set(arguments)
    no_default = [n for n, p in arguments.items() if p.default is inspect.Parameter.empty]
    assert schema["required"] == no_default
    assert schema["additionalProperties"] is False and spec["strict"] is True


def test_enums_follow_the_constants_in_tools():
    props = {s["name"]: s["input_schema"]["properties"] for s in TOOL_SPECS}
    assert props["weekly_summary"]["metric"]["enum"] == list(METRICS)
    assert props["compare_periods"]["preset"]["enum"] == list(tools.PRESETS)
    assert props["correlation"]["method"]["enum"] == list(tools.CORRELATION_METHODS)
    assert props["correlation"]["lag_days"]["enum"] == list(range(tools.MAX_LAG_DAYS + 1))
    assert props["most_active_day"]["top_n"]["enum"] == list(range(1, tools.MAX_TOP_N + 1))


def test_run_tool_gives_the_same_result_as_the_function(two_weeks):
    # The same result, with a weekday next to every date.
    assert run_tool(two_weeks, "weekly_summary", {"metric": "steps"}) == \
        with_weekdays(tools.weekly_summary(two_weeks, "steps"))
    assert run_tool(two_weeks, "most_active_day", {"top_n": 1}) == \
        with_weekdays(tools.most_active_day(two_weeks, top_n=1))


def test_run_tool_rejects_unknown_tools_and_arguments(two_weeks):
    with pytest.raises(ValueError, match="Unknown tool 'sleep_score'"):
        run_tool(two_weeks, "sleep_score", {})
    with pytest.raises(ValueError, match="Unknown argument.*days"):
        run_tool(two_weeks, "weekly_summary", {"metric": "steps", "days": 14})


# --- weekdays next to dates ------------------------------------------------------

DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def checked_dates(obj) -> int:
    """Assert every date in a tool result has its weekday beside it; return how many."""
    count = 0
    if isinstance(obj, list):
        return sum(checked_dates(item) for item in obj)
    if not isinstance(obj, dict):
        return 0
    for key, value in obj.items():
        if isinstance(value, str) and DATE.fullmatch(value):
            name = "weekday" if key == "date" else f"{key}_weekday"
            assert obj[name] == pd.Timestamp(value).day_name(), (key, value, obj.get(name))
            count += 1
        elif isinstance(value, list) and value and all(
                isinstance(v, str) and DATE.fullmatch(v) for v in value):
            assert obj[f"{key}_weekdays"] == [pd.Timestamp(v).day_name() for v in value], key
            count += len(value)
        count += checked_dates(value)
    return count


CALLS = [
    *[("weekly_summary", {"metric": m}) for m in METRICS],
    ("weekly_summary", {"metric": "minutes_asleep", "threshold": 420}),
    ("compare_periods", {"metric": "steps", "preset": "first_half_vs_second_half"}),
    ("compare_periods", {"metric": "mean_hr", "preset": "last_4_weeks_vs_previous_4_weeks"}),
    ("missing_data_report", {}),
    ("most_active_day", {"top_n": 10}),
    ("correlation", {"metric_x": "minutes_asleep", "metric_y": "steps"}),
    ("weekly_active_minutes", {}),
    ("get_guideline", {"topic": "sleep_duration"}),
    ("get_guideline", {"topic": "physical_activity"}),
]


@pytest.fixture(scope="module")
def demo_people():
    from wearable.schema import to_daily_frame
    table = pd.read_csv(Path(__file__).resolve().parents[1] / "data/demo/demo_daily.csv",
                        dtype={"user_id": str})
    return {uid: to_daily_frame(rows.drop(columns="user_id"))
            for uid, rows in table.groupby("user_id")}


@pytest.mark.parametrize("name, arguments", CALLS)
def test_every_weekday_in_tool_output_matches_its_date(demo_people, name, arguments):
    for df in demo_people.values():
        assert checked_dates(run_tool(df, name, arguments)) > 0


def test_every_tool_is_covered_by_the_weekday_check():
    assert {name for name, _ in CALLS} == set(TOOL_FUNCTIONS)


def test_with_weekdays_handles_nested_results_and_keeps_existing_keys():
    out = with_weekdays({"start": "2016-05-04", "daily": [{"date": "2016-05-05", "value": 1}],
                         "missing": {"dates": ["2016-05-06", "2016-05-07"], "truncated": False},
                         "most_active": {"date": "2016-05-08", "weekday": "Sunday"},
                         "note": "2016-05-04 is a Wednesday", "n": 3})
    assert out["start_weekday"] == "Wednesday"
    assert out["daily"][0] == {"date": "2016-05-05", "weekday": "Thursday", "value": 1}
    assert out["missing"]["dates_weekdays"] == ["Friday", "Saturday"]
    assert out["most_active"] == {"date": "2016-05-08", "weekday": "Sunday"}
    assert "note_weekday" not in out and out["n"] == 3
