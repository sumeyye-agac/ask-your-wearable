import math

import pandas as pd
import pytest

from wearable.schema import METRICS, check_metric, to_daily_frame


def test_to_daily_frame_fills_absent_dates_and_columns():
    df = to_daily_frame(pd.DataFrame({"date": ["2024-01-01", "2024-01-04"], "steps": [5, 7]}))
    assert list(df.index.strftime("%Y-%m-%d")) == [
        "2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"]
    assert list(df.columns) == list(METRICS)
    assert math.isnan(df.loc["2024-01-02", "steps"])
    assert df["mean_hr"].isna().all()


def test_to_daily_frame_rejects_duplicate_dates():
    with pytest.raises(ValueError, match="more than one row"):
        to_daily_frame(pd.DataFrame({"date": ["2024-01-01", "2024-01-01"], "steps": [1, 2]}))


def test_check_metric_lists_valid_names():
    with pytest.raises(ValueError, match="Valid metrics: steps, minutes_asleep"):
        check_metric("sleep")
