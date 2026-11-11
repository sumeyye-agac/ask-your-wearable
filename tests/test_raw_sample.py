"""The committed raw sample: small, one representative day per demo person, rows unchanged."""

import importlib.util
from pathlib import Path

import pandas as pd
import pytest

from wearable.app_text import RAW_TABLES
from wearable.schema import to_daily_frame
from wearable.zenodo import TS_FORMAT

REPO = Path(__file__).resolve().parents[1]
SAMPLE = REPO / "data/demo/raw_sample"
USERS = {"5553957443", "5577150313", "6962181067"}

spec = importlib.util.spec_from_file_location("build_raw_sample",
                                              REPO / "scripts/build_raw_sample.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


@pytest.fixture(scope="module")
def days() -> dict[str, pd.Timestamp]:
    table = pd.read_csv(REPO / "data/demo/demo_daily.csv", dtype={"user_id": str})
    return {uid: build.representative_day(to_daily_frame(rows.drop(columns="user_id")))
            for uid, rows in table.groupby("user_id")}


def load(name: str) -> pd.DataFrame:
    return pd.read_csv(SAMPLE / f"{name}.csv.gz", dtype={"Id": str})


def test_sample_is_small():
    total = sum(p.stat().st_size for p in SAMPLE.glob("*.csv.gz"))
    assert total < 300_000
    assert {p.name for p in SAMPLE.glob("*.csv.gz")} == {f"{n}.csv.gz" for n in RAW_TABLES}


@pytest.mark.parametrize("name, time_col, per_person", [
    ("hourlySteps", "ActivityHour", 24),
    ("minuteIntensitiesNarrow", "ActivityMinute", 1440),
    ("heartrate_seconds", "Time", None),
])
def test_one_full_day_per_person(days, name, time_col, per_person):
    rows = load(name)
    assert set(rows["Id"]) == USERS
    for uid, day in days.items():
        ts = pd.to_datetime(rows.loc[rows["Id"] == uid, time_col], format=TS_FORMAT)
        assert set(ts.dt.normalize()) == {day}
        if per_person:
            assert len(ts) == per_person


def test_sleep_sample_is_the_night_ending_on_the_day(days):
    rows = load("minuteSleep")
    for uid, day in days.items():
        ts = pd.to_datetime(rows.loc[rows["Id"] == uid, "date"], format=TS_FORMAT)
        assert ts.max().normalize() == day
        assert ts.min() >= day - pd.Timedelta(days=1)
        assert set(rows.loc[rows["Id"] == uid, "value"]) <= {1, 2, 3}


def test_representative_day_is_complete_and_closest_to_the_median():
    df = to_daily_frame(pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=4),
        "steps": [1000, 5000, 9000, 4000], "minutes_asleep": [400] * 4,
        "minutes_in_bed": [450] * 4, "mean_hr": [70, 71, 72, None],
        "fairly_active_minutes": [10] * 4, "very_active_minutes": [5] * 4}))
    # Complete days: 1000, 5000, 9000 (the 4th has no heart rate); median 5000.
    assert build.representative_day(df) == pd.Timestamp("2024-01-02")
