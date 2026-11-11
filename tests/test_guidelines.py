"""The curated guideline reference: fixed content, every statement with its source."""

import pytest

from wearable.guidelines import ACTIVITY_CAVEAT, GUIDELINES, TOPICS, get_guideline
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


def test_activity_guideline_numbers_and_the_limits_of_the_comparison():
    g = get_guideline("physical_activity")
    text = g["statements"][0]["recommendation"]
    assert "At least 150 minutes of moderate-intensity" in text
    assert "75 minutes of vigorous-intensity" in text and "equivalent combination" in text
    assert g["threshold"]["moderate_minutes_per_week"] == 150
    assert g["threshold"]["vigorous_minutes_per_week"] == 75
    assert "fairly_active_minutes" in g["comparable_metric"]
    assert "very_active_minutes" in g["comparable_metric"]
    # The comparison is approximate and strength training cannot be checked at all.
    assert g["applies_to_data"].startswith(ACTIVITY_CAVEAT)
    assert "not the same" in g["applies_to_data"]
    assert "muscle-strengthening" in g["applies_to_data"]
    assert g["intensity_definition_source"].startswith("CDC, How to Measure")
    assert "no conversion" not in g["applies_to_data"]
    assert g["conversion"]["source"] == "CDC, What Counts as Physical Activity for Adults"
    assert g["conversion"]["page_date"] == "2023-12-06"
    assert "about the same as 2 minutes of moderate-intensity" in g["conversion"]["rule"]


def test_result_is_a_copy_so_callers_cannot_change_the_reference():
    get_guideline("sleep_duration")["statements"].clear()
    assert len(GUIDELINES["sleep_duration"]["statements"]) == 3


def test_unknown_topic_lists_the_valid_ones():
    with pytest.raises(ValueError, match="Valid topics: sleep_duration, physical_activity"):
        get_guideline("nutrition")


def test_reachable_through_the_registry(two_weeks):
    assert run_tool(two_weeks, "get_guideline", {"topic": "sleep_duration"}) == \
        get_guideline("sleep_duration")
