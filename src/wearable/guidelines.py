"""A small curated reference of public health recommendations, with their sources.

This is a lookup over a few hand-checked statements, not retrieval. Each topic comes from
one page of the US Centers for Disease Control and Prevention (CDC), read on the date in
"retrieved". CDC states that most of its website text is in the public domain and may be
reproduced without permission, provided the agency is credited, the substantive content
is not changed, no endorsement is implied, and readers are told the material is available
free on the agency's website (https://www.cdc.gov/other/agencymaterials.html). The
"credit" field carries that attribution and must be shown wherever a statement is shown.

The numbers below are the ones on the CDC pages; the wording around them is shortened.
"""

from __future__ import annotations

import copy
from typing import Any

_CREDIT = ("Source: CDC. The material is available on the CDC website at no charge. "
           "Its use here does not imply endorsement by CDC, ATSDR, HHS or the United "
           "States Government.")
_LICENCE = ("Public domain (CDC website text), reproduced with credit and without changing "
            "the recommendation; see https://www.cdc.gov/other/agencymaterials.html")
# Weekly aerobic targets on the CDC page, in minutes. tools.weekly_active_minutes uses them.
ACTIVITY_WEEKLY_MINUTES = {"moderate": 150, "vigorous": 75}

# CDC's rule of thumb for combining the two, from its page "What Counts as Physical
# Activity for Adults" (page date 2023-12-06, read 2026-11-11).
VIGOROUS_TO_MODERATE = 2
ACTIVITY_CONVERSION = {
    "rule": "A rule of thumb is that 1 minute of vigorous-intensity activity is about the "
            "same as 2 minutes of moderate-intensity activity.",
    "source": "CDC, What Counts as Physical Activity for Adults",
    "url": "https://www.cdc.gov/physical-activity-basics/adding-adults/what-counts.html",
    "page_date": "2023-12-06",
}

ACTIVITY_CAVEAT = (
    "Fitbit's fairly active and very active minutes are the device's own per-minute "
    "estimate of intensity. CDC defines moderate and vigorous intensity by effort (3 to "
    "5.9 METs and 6.0 METs or more, or the talk test). The two are not the same, so "
    "comparing Fitbit minutes with the CDC recommendation is approximate.")

_NOT_ADVICE = ("A general recommendation for the public, not a personal target and not "
               "medical advice. The person's age is not known to this app.")

GUIDELINES: dict[str, dict[str, Any]] = {
    "sleep_duration": {
        "topic": "sleep_duration",
        "summary": "Recommended hours of sleep per day for adults, by age.",
        "statements": [
            {"population": "Adults 18-60 years", "recommendation": "7 or more hours per day"},
            {"population": "Adults 61-64 years", "recommendation": "7-9 hours per day"},
            {"population": "Adults 65 years and older", "recommendation": "7-8 hours per day"},
        ],
        # What the tools can check, in the metric's own unit so nothing has to be converted.
        "comparable_metric": "minutes_asleep",
        "threshold": {"value": 420, "unit": "minutes", "text": "7 h 00 min",
                      "meaning": "The lower bound shared by all three adult age groups. "
                                 "Pass it as threshold to weekly_summary."},
        "applies_to_data": "minutes_asleep counts the night's main sleep only. Naps are not "
                           "included, so a person's sleep per day can be higher than this "
                           "metric shows.",
        "source": "CDC, About Sleep",
        "url": "https://www.cdc.gov/sleep/about/index.html",
        "page_date": "2024-05-15",
        "based_on": "Watson et al. 2015, Sleep 38(6):843-844 (ages 18-60); Hirshkowitz et al. "
                    "2015, Sleep Health 1(1):40-43 (ages 61 and older), as cited by CDC.",
    },
    "physical_activity": {
        "topic": "physical_activity",
        "summary": "Recommended weekly physical activity for adults.",
        "statements": [
            {"population": "Adults",
             "recommendation": "At least 150 minutes of moderate-intensity physical activity "
                               "a week; this can also be 75 minutes of vigorous-intensity "
                               "activity or an equivalent combination of the two"},
            {"population": "Adults",
             "recommendation": "At least 2 days of muscle-strengthening activity each week"},
        ],
        "comparable_metric": "fairly_active_minutes (moderate) and very_active_minutes "
                             "(vigorous)",
        "threshold": {"moderate_minutes_per_week": ACTIVITY_WEEKLY_MINUTES["moderate"],
                      "vigorous_minutes_per_week": ACTIVITY_WEEKLY_MINUTES["vigorous"],
                      "meaning": "Call weekly_active_minutes to compare a week with these; "
                                 "it combines the two with the conversion below."},
        "conversion": ACTIVITY_CONVERSION,
        "applies_to_data": ACTIVITY_CAVEAT + " CDC gives no step-count target. The data has "
                           "nothing on muscle-strengthening activity, so that part cannot "
                           "be checked.",
        "intensity_definition_source": "CDC, How to Measure Physical Activity Intensity, "
                                       "https://www.cdc.gov/physical-activity-basics/"
                                       "measuring/index.html (page date 2025-12-04)",
        "source": "CDC, Adult Activity: An Overview",
        "url": "https://www.cdc.gov/physical-activity-basics/guidelines/adults.html",
        "page_date": "2023-12-20",
        "based_on": "Physical Activity Guidelines for Americans, as cited by CDC.",
    },
}

for _g in GUIDELINES.values():
    _g.update({"retrieved": "2026-11-11", "licence": _LICENCE, "credit": _CREDIT,
               "note": _NOT_ADVICE})

TOPICS = tuple(GUIDELINES)


def get_guideline(topic: str) -> dict[str, Any]:
    """Look up the public health recommendation on one topic.

    Args:
        topic: "sleep_duration" (hours of sleep per day for adults, by age) or
            "physical_activity" (weekly activity for adults).

    Returns the recommendation statements with the population each applies to, the source
    page with its URL and date, the credit line to show with it, which metric in the data
    it can be compared with (None if it cannot) and, where it can, the threshold in that
    metric's unit.
    """
    if topic not in GUIDELINES:
        raise ValueError(f"Unknown topic {topic!r}. Valid topics: {', '.join(TOPICS)}.")
    return copy.deepcopy(GUIDELINES[topic])
