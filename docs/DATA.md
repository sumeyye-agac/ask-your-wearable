# Data: what the demo data can and cannot answer

How each daily value is computed, and how it was checked against Fitbit's own tables, is in
[METHODS.md](METHODS.md).

## Source and licence

The demo uses the public Fitbit dataset by Furberg, Brinton, Keating & Ortiz (RTI International),
*Crowd-sourced Fitbit datasets 03.12.2016–05.12.2016*, Zenodo, 2016,
[doi:10.5281/zenodo.53894](https://doi.org/10.5281/zenodo.53894), licensed CC BY 4.0.
It has two monthly exports from Amazon Mechanical Turk volunteers, 12 March to 12 May 2016.

`data/demo/demo_daily.csv` is a derived file: one row per user and day for three users,
built from that dataset with `scripts/build_daily.py`. `data/demo/raw_sample/` holds one
unchanged day of four raw tables per demo user (about 110 KB, built with
`scripts/build_raw_sample.py`), for the app's Data tab. Both are shared under the dataset's
CC BY 4.0 licence.

## What is in the exports

- 35 users in total, 33 of them in both months. One of the 35 (`2891001357`) has 12 hours of
  data on a single day and nothing else, so no day of theirs counts; that is why the tables
  below never show more than 34 users.
- The first export has 11 tables, the second 18. Only the second has `sleepDay` and the
  separate daily steps, calories and intensities tables.
- The first export's `dailyActivity` table is incomplete: most users only have rows for
  1–12 April. The hourly and minute tables cover the whole month, so daily steps are
  built from `hourlySteps`.
- 12 April 2016 appears in both exports. The duplicate rows agree and are dropped.
- Sleep is in Fitbit's older format: each minute is asleep, restless or awake. There are no
  sleep stages.
- Heart rate is raw readings every few seconds. It starts on 29 March and exists for 15 users.
- Intensity is one code per minute, 0 to 3, in both months. Fitbit's Web API reference names the
  levels: 0 sedentary, 1 lightly active, 2 fairly active, 3 very active. The cut-offs between
  levels are not given there.

## Coverage

| Metric | Users | Days per user, median (range) | Users with ≥ 28 days | Users with ≥ 10 days in each half |
|---|---|---|---|---|
| Steps | 34 | 54 (3–61) | 31 | 30 |
| Sleep | 22 | 43 (2–62) | 13 | 14 |
| Mean heart rate | 13 | 34 (10–44) | 10 | 9 |
| Active minutes | 34 | 54 (3–61) | 31 | 30 |

Only 8 users have at least 7 days on which all three metrics are present. The demo offers
the three users with the most complete data: `6962181067`, `5553957443` and `5577150313`.
Even these have gaps; user `5577150313` has sleep on only 2 of the last 7 nights.

## What this means for questions

- Questions about a week, a single day or a comparison of two weeks are answerable for steps
  and sleep.
- Longer comparisons are "first half vs second half" or "last 4 weeks vs the 4 weeks before".
  The data spans about 9 weeks, so there is no meaningful month-over-month comparison.
- Heart rate begins on 29 March, so a first-half vs second-half comparison of heart rate
  compares about 2 weeks with about 4.
- A relation such as "do I walk less after short sleep" rests on roughly 40–60 nights for one
  person, so any estimate comes with a wide interval.

## Rebuilding the demo files from the raw data

The demo files are committed, so this is only needed to reproduce them or the tables above.

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt   # the app's requirements, pytest, this package

# Download both zips of Zenodo record 53894 into data/raw/ and unzip them there
mkdir -p data/raw && cd data/raw
for f in mturkfitbit_export_3.12.16-4.11.16.zip mturkfitbit_export_4.12.16-5.12.16.zip; do
  curl -sSL -o "$f" "https://zenodo.org/api/records/53894/files/$f/content"
  unzip -q -o "$f" -d "${f%.zip}"
done
cd ../..

.venv/bin/python scripts/data_coverage.py data/raw   # raw coverage, per table
.venv/bin/python scripts/build_daily.py data/raw     # daily tables + coverage summary above
.venv/bin/python scripts/build_raw_sample.py data/raw  # one raw day per demo user, for the app
.venv/bin/python -m pytest
```
