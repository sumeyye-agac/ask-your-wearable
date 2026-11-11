import pandas as pd

from wearable.zenodo import daily_active_minutes, daily_heart_rate, daily_sleep, daily_steps

T0 = pd.Timestamp("2024-01-01")


def _minutes(user, log_id, start, n, value=1):
    ts = pd.date_range(start, periods=n, freq="min")
    return pd.DataFrame({"Id": user, "logId": log_id, "ts": ts, "value": value})


def test_daily_steps_needs_24_hours_and_positive_total():
    full = pd.DataFrame({"Id": 1, "ts": pd.date_range(T0, periods=24, freq="h"), "StepTotal": 100})
    zero = full.assign(ts=full["ts"] + pd.Timedelta(days=1), StepTotal=0)
    partial = full.iloc[:10].assign(ts=full["ts"].iloc[:10] + pd.Timedelta(days=2))
    out = daily_steps(pd.concat([full, zero, partial]))
    assert out.to_dict("records") == [{"Id": 1, "date": T0, "steps": 2400}]


def test_episodes_split_by_short_gap_are_one_night():
    # 23:00-01:00 (120 min), 30-min gap, 01:30-04:30 (180 min): merged = 300 min in bed.
    a = _minutes(1, 10, "2024-01-01 23:00", 120)
    b = _minutes(1, 11, "2024-01-02 01:30", 180)
    b.loc[b.index[:20], "value"] = 2  # 20 restless minutes
    out = daily_sleep(pd.concat([a, b]))
    assert out.to_dict("records") == [
        {"Id": 1, "date": pd.Timestamp("2024-01-02"), "minutes_asleep": 280, "minutes_in_bed": 300}]


def test_long_gap_keeps_episodes_apart_and_drops_the_short_one():
    # Two 2-h episodes 3 h apart: neither reaches 3 h on its own, so no night is counted.
    a = _minutes(1, 10, "2024-01-01 22:00", 120)
    b = _minutes(1, 11, "2024-01-02 03:00", 120)
    assert daily_sleep(pd.concat([a, b])).empty
    # With a looser merge threshold they become one night.
    assert len(daily_sleep(pd.concat([a, b]), gap_minutes=240)) == 1


def test_nap_is_not_a_night_and_night_is_dated_by_wake_day():
    night = _minutes(1, 10, "2024-01-01 23:00", 420)   # ends 2024-01-02 05:59
    nap = _minutes(1, 11, "2024-01-02 14:00", 60)
    out = daily_sleep(pd.concat([night, nap]))
    assert out["date"].tolist() == [pd.Timestamp("2024-01-02")]
    assert out["minutes_in_bed"].tolist() == [420]


def test_merging_does_not_cross_users():
    a = _minutes(1, 10, "2024-01-01 23:00", 200)
    b = _minutes(2, 11, "2024-01-02 02:25", 200)  # starts 5 min after user 1 ends
    out = daily_sleep(pd.concat([a, b]))
    assert sorted(out["Id"]) == [1, 2]
    assert out["minutes_in_bed"].tolist() == [200, 200]


def test_heart_rate_needs_12_hours():
    ts12 = pd.date_range(T0, periods=12, freq="h")
    ts11 = pd.date_range(T0 + pd.Timedelta(days=1), periods=11, freq="h")
    hr = pd.concat([
        pd.DataFrame({"Id": 1, "ts": ts12, "Value": [60] * 6 + [80] * 6}),
        pd.DataFrame({"Id": 1, "ts": ts11, "Value": 70}),
    ])
    out = daily_heart_rate(hr)
    assert out.to_dict("records") == [{"Id": 1, "date": T0, "mean_hr": 70.0}]


def _intensity(user, day, codes):
    ts = pd.date_range(T0 + pd.Timedelta(days=day), periods=len(codes), freq="min")
    return pd.DataFrame({"Id": user, "ts": ts, "Intensity": codes})


def test_active_minutes_count_levels_2_and_3_on_complete_days():
    # Day 0: 1440 minutes with 30 lightly (1), 12 fairly (2) and 7 very (3) active minutes.
    full = _intensity(1, 0, [1] * 30 + [2] * 12 + [3] * 7 + [0] * 1391)
    out = daily_active_minutes(full)
    assert out.to_dict("records") == [
        {"Id": 1, "date": T0, "fairly_active_minutes": 12, "very_active_minutes": 7}]


def test_active_minutes_drop_partial_days_and_days_without_any_movement():
    partial = _intensity(1, 0, [2] * 100 + [0] * 800)          # 900 minutes recorded
    still = _intensity(1, 1, [0] * 1440)                       # device not worn
    light_only = _intensity(1, 2, [1] * 60 + [0] * 1380)       # worn, nothing above light
    out = daily_active_minutes(pd.concat([partial, still, light_only]))
    # A worn day with no fairly or very active minutes is a real zero, not a missing day.
    assert out.to_dict("records") == [
        {"Id": 1, "date": T0 + pd.Timedelta(days=2), "fairly_active_minutes": 0,
         "very_active_minutes": 0}]


def test_active_minutes_are_counted_per_user():
    a = _intensity(1, 0, [2] * 10 + [0] * 1430)
    b = _intensity(2, 0, [3] * 20 + [0] * 1420)
    out = daily_active_minutes(pd.concat([a, b]))
    assert out["fairly_active_minutes"].tolist() == [10, 0]
    assert out["very_active_minutes"].tolist() == [0, 20]
