"""The curated guideline reference: fixed content, every statement with its source."""

import pytest

from wearable.guidelines import GUIDELINES, TOPICS, get_guideline
from wearable.registry import run_tool
from wearable.schema import METRICS


def test_topics():
    assert TOPICS == ("sleep_duration", "physical_activity")


@pytest.mark.parametrize("topic", TOPICS)
def test_every_guideline_carries_its_source_and_credit(topic):
    g = get_guideline(topic)
    assert g["topic"] == topic and g["statements"]
    assert all(s["population"] and s["recommendation"] for s in g["statements"])
    assert g["url"].startswith("https://www.cdc.gov/")
    assert g["source"].startswith("CDC") and g["credit"].startswith("Source: CDC.")
    assert "does not imply endorsement" in g["credit"] and "no charge" in g["credit"]
    assert g["retrieved"] == "2026-11-11" and g["page_date"] and g["licence"] and g["note"]


def test_sleep_guideline_numbers_and_threshold():
    g = get_guideline("sleep_duration")
    assert [s["recommendation"] for s in g["statements"]] == [
        "7 or more hours per day", "7-9 hours per day", "7-8 hours per day"]
    assert g["comparable_metric"] in METRICS
    assert (g["threshold"]["value"], g["threshold"]["unit"]) == (420, "minutes")
    assert g["threshold"]["unit"] == METRICS[g["comparable_metric"]].unit


def test_activity_guideline_cannot_be_compared_with_step_data():
    g = get_guideline("physical_activity")
    assert "150 minutes of moderate-intensity" in g["statements"][0]["recommendation"]
    assert "75 minutes of vigorous-intensity" in g["statements"][0]["recommendation"]
    assert g["comparable_metric"] is None and g["threshold"] is None
    assert "cannot be checked" in g["applies_to_data"]


def test_result_is_a_copy_so_callers_cannot_change_the_reference():
    get_guideline("sleep_duration")["statements"].clear()
    assert len(GUIDELINES["sleep_duration"]["statements"]) == 3


def test_unknown_topic_lists_the_valid_ones():
    with pytest.raises(ValueError, match="Valid topics: sleep_duration, physical_activity"):
        get_guideline("nutrition")


def test_reachable_through_the_registry(two_weeks):
    assert run_tool(two_weeks, "get_guideline", {"topic": "sleep_duration"}) == \
        get_guideline("sleep_duration")
