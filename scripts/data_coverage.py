"""Print a coverage report for the Zenodo Fitbit dataset (record 53894).

Usage:
    .venv/bin/python scripts/data_coverage.py data/raw

Expects the two zips extracted under the given folder (one subfolder each).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

TS_FORMAT = "%m/%d/%Y %I:%M:%S %p"
DATE_FORMAT = "%m/%d/%Y"

# Table name -> timestamp column.
TIME_COLUMNS = {
    "dailyActivity": "ActivityDate",
    "dailyCalories": "ActivityDay",
    "dailyIntensities": "ActivityDay",
    "dailySteps": "ActivityDay",
    "sleepDay": "SleepDay",
    "minuteSleep": "date",
    "heartrate_seconds": "Time",
    "weightLogInfo": "Date",
}


def parse_time(series: pd.Series) -> pd.Series:
    """Parse Fitabase timestamps; date-only columns use a shorter format."""
    parsed = pd.to_datetime(series, format=TS_FORMAT, errors="coerce")
    missing = parsed.isna()
    if missing.any():
        parsed[missing] = pd.to_datetime(series[missing], format=DATE_FORMAT, errors="coerce")
    return parsed


def find_tables(root: Path) -> dict[str, list[tuple[str, Path]]]:
    """Map table name -> [(month label, csv path)] across both exports."""
    tables: dict[str, list[tuple[str, Path]]] = {}
    for csv in sorted(root.glob("*/*/*_merged.csv")):
        name = csv.name.removesuffix("_merged.csv")
        month = "M1" if "3.12.16" in csv.parent.name else "M2"
        tables.setdefault(name, []).append((month, csv))
    return tables


def time_column(name: str, columns: list[str]) -> str:
    if name in TIME_COLUMNS:
        return TIME_COLUMNS[name]
    return next(c for c in columns if c.startswith("Activity"))


def overview(tables: dict[str, list[tuple[str, Path]]]) -> pd.DataFrame:
    rows = []
    for name, files in tables.items():
        for month, path in files:
            df = pd.read_csv(path)
            t = parse_time(df[time_column(name, list(df.columns))])
            rows.append({
                "table": name, "month": month, "rows": len(df),
                "users": df["Id"].nunique(),
                "first": t.min().date(), "last": t.max().date(),
                "unparsed_ts": int(t.isna().sum()),
            })
    return pd.DataFrame(rows).sort_values(["table", "month"])


def load_both(tables, name: str) -> pd.DataFrame:
    """Concatenate both months of a table with a parsed 'ts' and 'day' column."""
    parts = []
    for month, path in tables.get(name, []):
        df = pd.read_csv(path)
        df["ts"] = parse_time(df[time_column(name, list(df.columns))])
        df["month"] = month
        parts.append(df)
    out = pd.concat(parts, ignore_index=True)
    out["day"] = out["ts"].dt.normalize()
    return out


def describe_days(per_user: pd.Series, label: str) -> None:
    q = per_user.describe(percentiles=[0.25, 0.5, 0.75])
    print(f"  {label}: users={len(per_user)}  min={q['min']:.0f}  p25={q['25%']:.0f}  "
          f"median={q['50%']:.0f}  p75={q['75%']:.0f}  max={q['max']:.0f}")


def threshold_counts(per_user: pd.Series, thresholds=(7, 14, 21, 28, 42, 56)) -> str:
    return "  ".join(f">={k}d:{int((per_user >= k).sum())}" for k in thresholds)


def main(root: Path) -> None:
    tables = find_tables(root)
    pd.set_option("display.width", 160)

    print("=== Files per month ===")
    for month in ("M1", "M2"):
        names = sorted(n for n, f in tables.items() if any(m == month for m, _ in f))
        print(f"{month} ({len(names)}): {', '.join(names)}")

    print("\n=== Overview per table and month ===")
    print(overview(tables).to_string(index=False))

    # --- Daily activity -------------------------------------------------------
    act = load_both(tables, "dailyActivity")
    dup = act.duplicated(["Id", "day"], keep=False)
    print("\n=== dailyActivity ===")
    print(f"  (Id, day) rows duplicated across files: {int(dup.sum())} "
          f"on days {sorted(act.loc[dup, 'day'].dt.date.unique())[:5]}")
    act = act.drop_duplicates(["Id", "day"], keep="last")
    # A day where the device recorded no steps and 1440 sedentary minutes is almost
    # certainly not worn.
    worn = act[(act["TotalSteps"] > 0) & (act["SedentaryMinutes"] < 1440)]
    describe_days(act.groupby("Id")["day"].nunique(), "days with a row")
    describe_days(worn.groupby("Id")["day"].nunique(), "days likely worn (steps>0, sed<1440)")
    ids_m1 = set(act.loc[act.month == "M1", "Id"])
    ids_m2 = set(act.loc[act.month == "M2", "Id"])
    print(f"  users M1={len(ids_m1)}  M2={len(ids_m2)}  in both={len(ids_m1 & ids_m2)}  "
          f"union={len(ids_m1 | ids_m2)}")
    worn_pm = worn.groupby(["Id", "month"])["day"].nunique().unstack(fill_value=0)
    both14 = ((worn_pm.get("M1", 0) >= 14) & (worn_pm.get("M2", 0) >= 14)).sum()
    print(f"  users with >=14 worn days in BOTH months: {int(both14)}")
    print("  worn-days thresholds:", threshold_counts(worn.groupby("Id")["day"].nunique()))

    # --- Sleep ----------------------------------------------------------------
    ms = load_both(tables, "minuteSleep")
    print("\n=== minuteSleep (both months) ===")
    print(f"  value counts: {ms['value'].value_counts().sort_index().to_dict()} "
          "(Fitbit classic: 1=asleep, 2=restless, 3=awake)")
    # One logId = one sleep episode. Assign a night to the date the episode ends (wake day).
    episodes = ms.groupby(["Id", "logId"]).agg(start=("ts", "min"), end=("ts", "max"),
                                                minutes=("ts", "size"),
                                                asleep=("value", lambda v: int((v == 1).sum())))
    episodes["night"] = episodes["end"].dt.normalize()
    episodes["hours"] = episodes["minutes"] / 60
    main_sleep = episodes[episodes["minutes"] >= 180]
    print(f"  episodes={len(episodes)}  of which >=3h={len(main_sleep)}  "
          f"users={episodes.index.get_level_values('Id').nunique()}")
    nights = main_sleep.reset_index().groupby("Id")["night"].nunique()
    describe_days(nights, "nights with a >=3h episode")
    print("  nights thresholds:", threshold_counts(nights))
    ms_month = ms.groupby(["Id", "month"])["day"].nunique().unstack(fill_value=0)
    print(f"  users with sleep minutes in M1={int((ms_month.get('M1', 0) > 0).sum())}  "
          f"M2={int((ms_month.get('M2', 0) > 0).sum())}  "
          f"both={int(((ms_month.get('M1', 0) > 0) & (ms_month.get('M2', 0) > 0)).sum())}")
    nights_m = main_sleep.reset_index().merge(
        pd.DataFrame({"night": pd.date_range("2016-03-12", "2016-05-12")}).assign(
            half=lambda d: d.night.lt("2016-04-12").map({True: "first", False: "second"})),
        on="night", how="left").groupby(["Id", "half"])["night"].nunique().unstack(fill_value=0)
    ok = ((nights_m.get("first", 0) >= 10) & (nights_m.get("second", 0) >= 10)).sum()
    print(f"  users with >=10 nights before AND after 2016-04-12: {int(ok)}")

    if "sleepDay" in tables:
        sd = load_both(tables, "sleepDay")
        print("\n=== sleepDay (only in M2) ===")
        describe_days(sd.groupby("Id")["day"].nunique(), "nights")

    # --- Heart rate -----------------------------------------------------------
    hr = load_both(tables, "heartrate_seconds")
    print("\n=== heartrate_seconds (both months) ===")
    print(f"  rows={len(hr)}  users={hr['Id'].nunique()}  "
          f"value range={hr['Value'].min()}-{hr['Value'].max()} bpm")
    hr["hour"] = hr["ts"].dt.floor("h")
    hours_per_day = hr.groupby(["Id", "day"])["hour"].nunique()
    print(f"  hours with any HR per user-day: median={hours_per_day.median():.0f}  "
          f"p25={hours_per_day.quantile(.25):.0f}")
    describe_days(hours_per_day.groupby("Id").size(), "days with any HR")
    good = hours_per_day[hours_per_day >= 12]
    describe_days(good.groupby("Id").size(), "days with >=12 h of HR")
    print("  days>=12h thresholds:", threshold_counts(good.groupby("Id").size()))
    hr_month = hr.groupby(["Id", "month"])["day"].nunique().unstack(fill_value=0)
    print(f"  users with HR in M1={int((hr_month.get('M1', 0) > 0).sum())}  "
          f"M2={int((hr_month.get('M2', 0) > 0).sum())}  "
          f"both={int(((hr_month.get('M1', 0) > 0) & (hr_month.get('M2', 0) > 0)).sum())}")

    # --- Overlap of data types ------------------------------------------------
    print("\n=== Users per data type (union of months) ===")
    sets = {
        "activity (worn >=7d)": set(worn.groupby("Id")["day"].nunique().loc[lambda s: s >= 7].index),
        "sleep (>=7 nights)": set(nights.loc[nights >= 7].index),
        "HR (>=7 days >=12h)": set(good.groupby("Id").size().loc[lambda s: s >= 7].index),
    }
    for k, v in sets.items():
        print(f"  {k}: {len(v)}")
    all3 = set.intersection(*sets.values())
    print(f"  all three: {len(all3)}")

    # Per-user table for the users with all three types.
    per_user = pd.DataFrame({
        "worn_days": worn.groupby("Id")["day"].nunique(),
        "worn_M1": worn_pm.get("M1"), "worn_M2": worn_pm.get("M2"),
        "sleep_nights": nights,
        "sleep_first": nights_m.get("first"), "sleep_second": nights_m.get("second"),
        "hr_days_12h": good.groupby("Id").size(),
        "hr_M1": hr_month.get("M1"), "hr_M2": hr_month.get("M2"),
    }).fillna(0).astype(int)
    print("\n=== Per-user coverage, users with sleep or HR data ===")
    sub = per_user[(per_user.sleep_nights > 0) | (per_user.hr_days_12h > 0)]
    print(sub.sort_values(["sleep_nights", "hr_days_12h"], ascending=False).to_string())


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "data/raw"))
