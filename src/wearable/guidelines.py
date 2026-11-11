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
             "recommendation": "150 minutes of moderate-intensity physical activity a week; "
                               "this can also be 75 minutes of vigorous-intensity activity"},
            {"population": "Adults",
             "recommendation": "At least 2 days of muscle-strengthening activity each week"},
        ],
        "comparable_metric": None,
        "threshold": None,
        "applies_to_data": "This data has steps per day only. It has no minutes of activity, "
                           "no intensity and no strength training, so it cannot be checked "
                           "against this recommendation. The CDC page gives no step-count "
                           "target.",
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
