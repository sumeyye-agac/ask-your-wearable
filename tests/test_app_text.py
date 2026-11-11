"""The figures on the "How it works" and "Data" tabs must come from the project's records."""

from pathlib import Path

import pytest

from wearable import app_text

REPO = Path(__file__).resolve().parents[1]
RECORDS = (REPO / "README.md").read_text() + (REPO / "docs/LOG.md").read_text()

# Each figure shown in the app, and the phrase in README.md or docs/LOG.md it comes from.
FIGURES = [
    ("332 of 346 nights", "332 of 346"),
    ("99.9% (fairly) and 99.8% (very)", "99.9%"),
    ("on 903 complete days", "903 complete days"),
    ("92% of 428 person-days", "92% of 428"),
    ("1 to 99 minutes higher", "99 minutes"),
    ("60 minutes or less apart", "60 minutes or less"),
    ("shorter than 3 hours", "shorter than 3 hours"),
    ("12 or more different hours", "12 or\nmore different hours"),
    ("all 1440 minutes", "all 1440 minutes"),
    ("The first export has 11 tables and the second has 18", "first export has 11 tables"),
    ("35 user ids", "35 ids"),
    ("daily table has 34 users", "34 users"),
    ("5 to 11 May", "5–11 May"),
    ("at least 3 days with data", "fewer than\n  3 days"),
    ("Below 10 paired days", "no r below 10 paired days"),
    ("after 6 model requests or an estimated $0.01", "6 model requests or an estimated $0.01"),
    ("10 questions per visitor per day", "10 questions per visitor"),
    ("only from\n29 March", "starts on 29 March"),
    ("for 15 of the 35 users", "exists for 15 users"),
]


def shown() -> str:
    parts = [app_text.HEADLINE, app_text.SUBLINE, *(text for _, _, text in app_text.STEPS),
             app_text.ABOUT_DATA, *app_text.LIMITS]
    for step in app_text.PIPELINE:
        parts += [step["text"], *step["decisions"]]
    return "\n".join(parts)


@pytest.mark.parametrize("in_app, in_records", FIGURES)
def test_figure_is_shown_and_recorded(in_app, in_records):
    assert " ".join(in_app.split()) in " ".join(shown().split())
    assert " ".join(in_records.split()) in " ".join(RECORDS.split())


def test_no_branding_in_texts():
    text = shown() + app_text.AUTHOR + app_text.DATASET_CREDIT
    assert "Anthropic" not in text
