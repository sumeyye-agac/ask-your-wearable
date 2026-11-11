import pandas as pd
import pytest

from wearable.schema import to_daily_frame


@pytest.fixture
def two_weeks() -> pd.DataFrame:
    """14 days, 2024-01-01..2024-01-14, steps 1000..14000 (day i has i*1000 steps).

    Sleep exists only in the second week (420 min asleep every night, 480 in bed);
    steps are missing on 2024-01-03 and 2024-01-10..12; no heart rate at all.
    """
    dates = pd.date_range("2024-01-01", periods=14, freq="D")
    steps = [1000.0 * (i + 1) for i in range(14)]
    for missing in (2, 9, 10, 11):
        steps[missing] = float("nan")
    asleep = [float("nan")] * 7 + [420.0] * 7
    in_bed = [float("nan")] * 7 + [480.0] * 7
    return to_daily_frame(pd.DataFrame({
        "date": dates.strftime("%Y-%m-%d"), "steps": steps,
        "minutes_asleep": asleep, "minutes_in_bed": in_bed,
    }))
