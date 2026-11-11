# Ask Your Wearable

Ask plain-language questions about daily wearable data (steps, sleep, heart rate) and get
answers that come from tested Python functions, not from a language model doing arithmetic.

Status: in progress. The data layer and the first three analysis tools exist and are tested.
The language-model loop, the web app and the evaluation are not built yet.

## Data: what the demo data can and cannot answer

The demo uses the public Fitbit dataset by Furberg, Brinton, Keating & Ortiz (RTI International),
*Crowd-sourced Fitbit datasets 03.12.2016–05.12.2016*, Zenodo, 2016,
[doi:10.5281/zenodo.53894](https://doi.org/10.5281/zenodo.53894), licensed CC BY 4.0.
It has two monthly exports from Amazon Mechanical Turk volunteers, 12 March to 12 May 2016.

`data/demo/demo_daily.csv` is a derived file: one row per user and day for three users,
built from that dataset with `scripts/build_daily.py`.

### What is in the exports

- 35 users in total, 33 of them in both months.
- The first export has 11 tables, the second 18. Only the second has `sleepDay` and the
  separate daily steps, calories and intensities tables.
- The first export's `dailyActivity` table is incomplete: most users only have rows for
  1–12 April. The hourly and minute tables cover the whole month, so daily steps are
  built from `hourlySteps`.
- 12 April 2016 appears in both exports. The duplicate rows agree and are dropped.
- Sleep is in Fitbit's older format: each minute is asleep, restless or awake. There are no
  sleep stages.
- Heart rate is raw readings every few seconds. It starts on 29 March and exists for 15 users.

### How a day is counted

- **Steps:** the sum of the day's hourly steps, only if all 24 hours are present and the total
  is above 0. This drops 12 May, which the export cut off partway through for most users.
- **Sleep:** Fitbit sleep logs for one user that are separated by 60 minutes or less are merged
  into one block. A block shorter than 3 hours is a nap and is not counted. A night is dated by
  the day the block ends, the wake-up day. `minutes_asleep` counts minutes scored as asleep;
  `minutes_in_bed` counts all recorded minutes of the block.
- **Heart rate:** the mean of all readings in the day, only if the day has readings in 12 or
  more different hours. This mostly reflects how active the day was; it is not resting heart rate.

As a check, the nightly sleep built this way was compared with Fitbit's own `sleepDay` table
for the second month. On nights with a single Fitbit sleep record, minutes asleep match exactly
on 332 of 346 nights.

### Coverage

| Metric | Users | Days per user, median (range) | Users with ≥ 28 days | Users with ≥ 10 days in each half |
|---|---|---|---|---|
| Steps | 34 | 54 (3–61) | 31 | 30 |
| Sleep | 22 | 43 (2–62) | 13 | 14 |
| Mean heart rate | 13 | 34 (10–44) | 10 | 9 |

Only 8 users have at least 7 days on which all three metrics are present. The demo offers
the three users with the most complete data: `6962181067`, `5553957443` and `5577150313`.
Even these have gaps; user `5577150313` has sleep on only 2 of the last 7 nights.

### What this means for questions

- Questions about a week, a single day or a comparison of two weeks are answerable for steps
  and sleep.
- Longer comparisons are "first half vs second half" or "last 4 weeks vs the 4 weeks before".
  The data spans about 9 weeks, so there is no meaningful month-over-month comparison.
- Heart rate begins on 29 March, so a first-half vs second-half comparison of heart rate
  compares about 2 weeks with about 4.
- A relation such as "do I walk less after short sleep" rests on roughly 40–60 nights for one
  person, so any estimate comes with a wide interval.

## Limits

- Out of scope because the data does not support them: sleep stages, heart rate variability,
  SpO2, stress, weight (8–11 users with a handful of manual entries), and resting heart rate
  (it would have to be derived, and was left out).
- 35 volunteers in 2016, with older Fitbit devices. Not a representative sample of anything.
- In the first month, where both exist, the `dailyActivity` step total and the sum of
  `hourlySteps` agree within 1% on 92% of 428 user-days. The other 8% are not explained yet.
- On 14 of 346 single-record nights, our minutes asleep are higher than Fitbit's `sleepDay`
  value, mostly by 1–20 minutes and once by 99 minutes. Not explained yet.
- The 60-minute merge threshold is a choice, not a fact. Gaps between sleep logs have no clean
  natural break: 66 are 30 minutes or less, 86 are 60 or less, 116 are 120 or less.
- Wellness information only. The app does not diagnose anything.

## Reproducing

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Download both zips of Zenodo record 53894 into data/raw/ and unzip them there
mkdir -p data/raw && cd data/raw
for f in mturkfitbit_export_3.12.16-4.11.16.zip mturkfitbit_export_4.12.16-5.12.16.zip; do
  curl -sSL -o "$f" "https://zenodo.org/api/records/53894/files/$f/content"
  unzip -q -o "$f" -d "${f%.zip}"
done
cd ../..

.venv/bin/python scripts/data_coverage.py data/raw   # raw coverage, per table
.venv/bin/python scripts/build_daily.py data/raw     # daily tables + coverage summary above
.venv/bin/python -m pytest
```
