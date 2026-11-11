# Ask Your Wearable

Ask plain-language questions about daily wearable data (steps, sleep, heart rate) and get
answers that come from tested Python functions, not from a language model doing arithmetic.

Status: in progress. The data layer, seven tools, the language-model loop and a local web app
exist and are tested. The app is not deployed yet, and the evaluation is not built.

## Data: what the demo data can and cannot answer

The demo uses the public Fitbit dataset by Furberg, Brinton, Keating & Ortiz (RTI International),
*Crowd-sourced Fitbit datasets 03.12.2016–05.12.2016*, Zenodo, 2016,
[doi:10.5281/zenodo.53894](https://doi.org/10.5281/zenodo.53894), licensed CC BY 4.0.
It has two monthly exports from Amazon Mechanical Turk volunteers, 12 March to 12 May 2016.

`data/demo/demo_daily.csv` is a derived file: one row per user and day for three users,
built from that dataset with `scripts/build_daily.py`. `data/demo/raw_sample/` holds one
unchanged day of four raw tables per demo user (about 110 KB, built with
`scripts/build_raw_sample.py`), for the app's Data tab. Both are shared under the dataset's
CC BY 4.0 licence.

### What is in the exports

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

### How a day is counted

- **Steps:** the sum of the day's hourly steps, only if all 24 hours are present and the total
  is above 0. This drops 12 May, which the export cut off partway through for most users.
- **Sleep:** Fitbit sleep logs for one user that are separated by 60 minutes or less are merged
  into one block. A block shorter than 3 hours is a nap and is not counted. A night is dated by
  the day the block ends, the wake-up day. `minutes_asleep` counts minutes scored as asleep;
  `minutes_in_bed` counts all recorded minutes of the block.
- **Heart rate:** the mean of all readings in the day, only if the day has readings in 12 or
  more different hours. This mostly reflects how active the day was; it is not resting heart rate.

- **Active minutes:** `fairly_active_minutes` and `very_active_minutes` count the day's minutes
  at intensity level 2 and 3, only if all 1440 minutes are present and at least one minute is
  above sedentary. A day that passes can have 0 active minutes; that is a measurement, not a gap.
- **"This week":** the 7 days ending on the user's last complete day, which is the last date
  with steps or active minutes (both need the whole day recorded). The export stops partway
  through 12 May, so for the demo users "this week" is 5–11 May. The sleep and heart rate
  recorded on 12 May stay in the table and can be asked for by date. "The last 4 weeks" ends on
  the same day.

As a check, the nightly sleep built this way was compared with Fitbit's own `sleepDay` table
for the second month. On nights with a single Fitbit sleep record, minutes asleep match exactly
on 332 of 346 nights. The active minutes were compared with Fitbit's `dailyIntensities` table
in the same way: on 903 complete days, fairly active minutes match exactly on 99.9% and very
active minutes on 99.8%.

### Coverage

| Metric | Users | Days per user, median (range) | Users with ≥ 28 days | Users with ≥ 10 days in each half |
|---|---|---|---|---|
| Steps | 34 | 54 (3–61) | 31 | 30 |
| Sleep | 22 | 43 (2–62) | 13 | 14 |
| Mean heart rate | 13 | 34 (10–44) | 10 | 9 |
| Active minutes | 34 | 54 (3–61) | 31 | 30 |

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
- The correlation tool's 95% intervals (Fisher z) assume every day is independent of the
  others. Consecutive days are not: an active week or a run of short nights makes neighbouring
  days alike. The intervals are therefore likely too narrow, and this is not corrected for.
  A correlation also says nothing about cause.
- Wellness information only. The app does not diagnose anything.
- The guideline lookup holds two CDC pages (sleep duration, physical activity for adults) and
  nothing else. The sleep comparison uses 7 hours, the lower bound for every adult age group, because the app does
  not know the user's age, and it counts the night's main sleep only (no naps).
- "Am I active enough?" adds fairly active minutes and twice the very active minutes and
  compares the sum with CDC's 150 moderate minutes a week. The factor of 2 is CDC's rule of
  thumb, not a measurement. The comparison is approximate for a second reason: Fitbit's levels
  are the device's own per-minute estimate, while CDC defines intensity by effort (3 to 5.9 METs
  and 6.0 METs or more, or the talk test). Every answer carries that caveat.
  Muscle-strengthening activity is not in the data and cannot be checked.
- If a week has days without data, a weekly total is a lower bound: the app says the
  recommendation was reached when the days present already reach it, and otherwise says it
  cannot tell.

## Guideline sources

`get_guideline(topic)` is a lookup over hand-checked CDC pages, not retrieval. All were read on
2026-11-11; the numbers are the ones on the pages and the wording around them is shortened.

| Topic | Page | Page date |
|---|---|---|
| `sleep_duration` | CDC, [About Sleep](https://www.cdc.gov/sleep/about/index.html) | 2024-05-15 |
| `physical_activity` | CDC, [Adult Activity: An Overview](https://www.cdc.gov/physical-activity-basics/guidelines/adults.html) | 2023-12-20 |
| 1 vigorous minute is about 2 moderate minutes | CDC, [What Counts as Physical Activity for Adults](https://www.cdc.gov/physical-activity-basics/adding-adults/what-counts.html) | 2023-12-06 |
| Definition of moderate and vigorous intensity | CDC, [How to Measure Physical Activity Intensity](https://www.cdc.gov/physical-activity-basics/measuring/index.html) | 2025-12-04 |

Source: CDC. The material is available on the CDC website at no charge. Its use here does not
imply endorsement by CDC, ATSDR, HHS or the United States Government. CDC website text is in the
public domain under the conditions on its
[Use of Agency Materials](https://www.cdc.gov/other/agencymaterials.html) page: credit the
agency, do not change the substantive content, do not imply endorsement. The WHO physical
activity pages were not used because WHO material is copyrighted and its licence terms were not
verified.

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
.venv/bin/python scripts/build_raw_sample.py data/raw  # one raw day per demo user, for the app
.venv/bin/python -m pytest
```

### Asking questions from the terminal

This part calls the Claude API and needs a key. Put `ANTHROPIC_API_KEY=...` in a `.env` file in
the repo root (git-ignored) or export it. The demo data is committed, so the raw zips are not
needed.

```bash
.venv/bin/python scripts/ask.py --list-users
.venv/bin/python scripts/ask.py --user 6962181067 "How was my sleep this week?"
.venv/bin/python scripts/ask.py --user 6962181067    # interactive; empty line to quit
```

Each question prints the tool calls the model made, their results, the answer, and the token
count with an estimated cost. The full trace is appended to `logs/trace.jsonl` (git-ignored).
Questions are answered one at a time, with no memory between them.

The model is `claude-haiku-5-5`; set `WEARABLE_MODEL` to change it. A question stops after
6 model requests or an estimated $0.01, whichever comes first, and then reports that it stopped
instead of answering. The cost estimate uses the published prices ($0.10 per million input
tokens, $0.50 per million output tokens, checked 2026-11-11). It is a guard inside the program,
not a replacement for the spend limit set in the Claude Console.

### Running the web app locally

Same key setup as above. Then:

```bash
.venv/bin/streamlit run streamlit_app.py     # opens http://localhost:8501
```

The page has three tabs. "Ask" is the question box. "How it works" shows the pipeline with
the decisions and checks recorded here. "Data" describes the dataset and shows the selected
person's daily table (sortable, downloadable as CSV) and their raw sample day. People are shown
as Person A, B and C; the real Zenodo id is in each answer's trace and on the Data tab.

Pick one of the three demo users, type a question or click an example, and the app shows the
answer, a small chart where one fits (the week's sleep or steps, active minutes, two periods,
or a scatter for a correlation) and a "How this answer was computed" section listing each tool
call with its arguments and result. When an answer uses the CDC guideline lookup, CDC's credit
line is shown under it. Charts are drawn from tool results or from the daily table with the
tool's own arguments, never from the model's text.

Limits, both kept in memory and reset when the app restarts: 10 questions per visitor per UTC
day, and an estimated $1.00 of API spend per UTC day for the whole app. A visitor is the IP
address Streamlit reports, or the browser session when it reports none (as on localhost, where
reloading the page starts a new session). A failed question does not count. API failures
(no credit, rate limits, outages, a missing key) are shown as a short message, not an error
page. The app's tests run it headless with the API call replaced, so they cost nothing.

## Next steps

Future work, not planned for this version:

- Compare models on the evaluation question set (tool-selection accuracy, numeric accuracy,
  unsupported-claim rate), not only Claude Haiku 5.5.
- A raw-signal layer: IMU data from a Movesense sensor, with my own human activity recognition
  model as a tool.
- An on-device version with a small model, to measure what is lost against the API model.
