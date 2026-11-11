"""The tool specs shown to the model must match the functions they describe."""

import inspect

import pytest

from wearable import tools
from wearable.registry import TOOL_FUNCTIONS, TOOL_SPECS, run_tool
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
    assert run_tool(two_weeks, "weekly_summary", {"metric": "steps"}) == \
        tools.weekly_summary(two_weeks, "steps")
    assert run_tool(two_weeks, "most_active_day", {"top_n": 1}) == \
        tools.most_active_day(two_weeks, top_n=1)


def test_run_tool_rejects_unknown_tools_and_arguments(two_weeks):
    with pytest.raises(ValueError, match="Unknown tool 'sleep_score'"):
        run_tool(two_weeks, "sleep_score", {})
    with pytest.raises(ValueError, match="Unknown argument.*days"):
        run_tool(two_weeks, "weekly_summary", {"metric": "steps", "days": 14})
