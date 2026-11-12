# Methods: pipeline, checks and tools

The dataset and its coverage are described in [DATA.md](DATA.md). Hosting, usage limits and CI
are in [DEPLOY.md](DEPLOY.md).

## How a day is counted

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

## Checks against Fitbit's own tables

As a check, the nightly sleep built this way was compared with Fitbit's own `sleepDay` table
for the second month. On nights with a single Fitbit sleep record, minutes asleep match exactly
on 332 of 346 nights. The active minutes were compared with Fitbit's `dailyIntensities` table
in the same way: on 903 complete days, fairly active minutes match exactly on 99.9% and very
active minutes on 99.8%.

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
  nothing else. The sleep comparison uses 7 hours, the lower bound for every adult age group,
  because the app does not know the user's age, and it counts the night's main sleep only
  (no naps).
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

## Asking questions from the terminal

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

## The web app

Same key setup as above. Then:

```bash
.venv/bin/streamlit run streamlit_app.py     # opens http://localhost:8501
```

The page has three tabs. "Ask" is the question box. "How it works" shows the pipeline with
the decisions and checks recorded here. "Data" describes the dataset and shows the selected
person's daily table (sortable, downloadable as CSV) and their raw sample day. People are shown
as Person A, B and C; the real Zenodo id is in each answer's trace and on the Data tab.

Type a question or click an example (it fills the box; nothing is sent until Ask), and pick
one of the three demo people on the cards under the box. The answer card shows the question,
one to three headline numbers, the explanation, a small chart where one fits (the week's sleep
or steps, active minutes, two periods, or a scatter for a correlation) and a "How this answer
was computed" section listing each tool call with its arguments and result. The headline
numbers are read from the tool results and only formatted, like the chart. Before the first
question the page shows one example answer, a real run saved in
`data/demo/example_answer.json`; a test checks that today's tools still return the results
stored in it. All styling is in `assets/style.css`. When an answer uses the CDC guideline lookup,
CDC's credit line is shown under it. Charts are drawn from tool results or from the daily table
with the tool's own arguments, never from the model's text.

The per-visitor and per-day usage limits, and how a visitor is identified, are in
[DEPLOY.md](DEPLOY.md#usage-limits-and-visitor-identification).
