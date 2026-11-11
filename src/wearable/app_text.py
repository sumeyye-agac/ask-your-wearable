"""Text shown in the web app's "How it works" and "Data" tabs.

Every number here comes from docs/LOG.md or README.md, or was checked against the raw
Zenodo export on 2026-11-11 (heart-rate timing, value codes, user counts per table).
Keep it in sync with those records when they change.
"""

from __future__ import annotations

INTRO = (
    "Ask questions about wearable data: sleep, steps, activity and heart rate. Every number "
    "in an answer is computed by tested Python functions. The language model only picks "
    "which functions to call and explains their results in plain words."
)

PIPELINE_DOT = """
digraph {
  rankdir=LR;
  node [shape=box, style="rounded,filled", fillcolor="#E6F0EF", color="#2A7F7A",
        fontname="Helvetica", fontsize=11, margin="0.15,0.08"];
  edge [color="#5B7C7A"];
  raw [label="Raw Fitbit export\\n(Zenodo, 2016)"];
  daily [label="Cleaning and\\ndaily table"];
  tools [label="Tested tools\\n(7 Python functions)"];
  agent [label="Agent\\nclaude-haiku-5-5"];
  ui [label="This app"];
  raw -> daily -> tools -> agent -> ui;
}
"""

PIPELINE: list[dict] = [
    {
        "title": "1. Raw Fitbit export",
        "text": "Two monthly exports from Zenodo record 53894, 12 March to 12 May 2016, "
                "downloaded and checked against their published md5 checksums. They hold "
                "35 user ids. The first export has 11 tables and the second has 18.",
        "decisions": [
            "12 April 2016 is in both exports. The duplicate rows agree and are dropped.",
            "The first month's `dailyActivity` table is incomplete (mostly 1 to 12 April "
            "only), so daily steps are built from `hourlySteps`, which covers both months.",
            "`sleepDay` exists only in the second month, so sleep is built from the "
            "per-minute `minuteSleep` table.",
            "One user id has 12 hours of data on a single day and nothing else, so no day of "
            "theirs counts and the daily table has 34 users.",
        ],
    },
    {
        "title": "2. Cleaning and the daily table",
        "text": "The export is turned into one row per person and day with six metrics: "
                "steps, minutes asleep, minutes in bed, mean heart rate, and fairly and very "
                "active minutes. A missing value means no valid measurement that day, never "
                "zero. The app shows the three people with the most complete data.",
        "decisions": [
            "Steps: the sum of the day's hourly steps, only if all 24 hours are present and "
            "the total is above 0. This drops 12 May, which the export cut off partway.",
            "Sleep: Fitbit sleep logs 60 minutes or less apart are merged into one night; a "
            "block shorter than 3 hours is a nap and is not counted; a night is dated by the "
            "wake-up day. Check: on nights with a single Fitbit sleep record, minutes asleep "
            "match Fitbit's own `sleepDay` exactly on 332 of 346 nights. On the other 14 they "
            "are 1 to 99 minutes higher, not yet explained.",
            "Heart rate: the mean of all readings in the day, only if the day has readings "
            "in 12 or more different hours. It mostly reflects how active the day was; it is "
            "not resting heart rate.",
            "Active minutes: the day's minutes at intensity level 2 (fairly active) and 3 "
            "(very active), only if all 1440 minutes are present and at least one is above "
            "sedentary. Check: on 903 complete days they match Fitbit's own "
            "`dailyIntensities` exactly on 99.9% (fairly) and 99.8% (very) of days.",
            "Steps cross-check: in the first month, `dailyActivity` and the summed "
            "`hourlySteps` agree within 1% on 92% of 428 person-days. The other 8% are not "
            "yet explained.",
        ],
    },
    {
        "title": "3. Tested tools",
        "text": "Seven deterministic Python functions do all the computing: "
                "`weekly_summary`, `compare_periods`, `missing_data_report`, "
                "`most_active_day`, `correlation`, `weekly_active_minutes` and "
                "`get_guideline`. Each has pytest tests, and each returns the comparisons a "
                "reader wants, so the model never has to do arithmetic.",
        "decisions": [
            "\"This week\" is the 7 days ending on the person's last complete day "
            "(5 to 11 May for the people shown here). \"The last 4 weeks\" ends on the same day.",
            "Two periods are compared only if each has at least 3 days with data.",
            "A correlation reports n, r and a 95% confidence interval (Fisher z; for "
            "Spearman, the Bonett and Wright standard error). Below 10 paired days it reports "
            "no r at all.",
            "\"Am I active enough?\" adds fairly active minutes and twice the very active "
            "minutes and compares the sum with CDC's 150 minutes a week. The factor of 2 is "
            "CDC's rule of thumb that 1 minute of vigorous activity is about the same as 2 "
            "minutes of moderate activity. With missing days the answer is \"reached\" or "
            "\"unknown\", never \"missed\".",
            "`get_guideline` is a lookup over two hand-checked CDC pages (sleep duration and "
            "adult physical activity), each with its source and credit line. It is not "
            "retrieval.",
            "Sleep durations also come as text (\"7 h 32 min\"), and every difference is "
            "computed from the rounded values shown, so a reader who checks the subtraction "
            "gets the same number.",
        ],
    },
    {
        "title": "4. Agent",
        "text": "Each question goes to Claude Haiku 5.5 (`claude-haiku-5-5`) through the "
                "Claude API with tool use. The model chooses tools, the code runs them on the "
                "selected person's data and sends the results back, and the model writes the "
                "answer. Every tool call and its result is recorded.",
        "decisions": [
            "A question stops after 6 model requests or an estimated $0.01, whichever comes "
            "first, and then says it stopped instead of answering.",
            "Questions recorded so far cost about $0.001 to $0.003 each.",
            "The instructions say: every number must come from a tool result; no saying "
            "which days were above or below a value unless a tool returned it with that "
            "threshold; no guideline that `get_guideline` did not return; only questions "
            "about the data; no diagnosis.",
            "Each question is answered on its own; there is no memory between questions.",
        ],
    },
    {
        "title": "5. This app",
        "text": "Streamlit shows the answer, one chart drawn from the tool results (never "
                "from the model's text), and the full list of tool calls under \"How this "
                "answer was computed\".",
        "decisions": [
            "10 questions per visitor per day and an estimated $1.00 of API spend per day "
            "for the whole app. Both reset when the app restarts.",
            "If the API fails or the credit runs out, the app shows a short message instead "
            "of an error page.",
        ],
    },
]

LIMITS = [
    "Three people from a sample of 35 volunteers in 2016, with older Fitbit trackers. Not a "
    "representative sample of anyone.",
    "About two months of data, so there are no month-over-month comparisons. Heart rate "
    "starts on 29 March.",
    "Not in the data: sleep stages, heart rate variability, SpO2, resting heart rate and raw "
    "sensor signals.",
    "Fitbit's activity levels are the device's own estimate, not CDC's definition of "
    "moderate and vigorous activity, so \"active enough\" answers are approximate.",
    "Correlation intervals treat each day as independent. Neighbouring days are alike, so "
    "the intervals are likely too narrow. A correlation does not show cause.",
    "The model is instructed, not forced. It can still occasionally state a small number "
    "that no tool returned; the list of tool calls under each answer lets you check.",
    "General wellness information, not medical advice.",
]

ABOUT_DATA = """\
The demo uses *Crowd-sourced Fitbit datasets 03.12.2016–05.12.2016* by Furberg, Brinton, \
Keating & Ortiz (RTI International), published on Zenodo in 2016 under CC BY 4.0. People \
who answered a survey on Amazon Mechanical Turk shared their Fitbit data for about two \
months, 12 March to 12 May 2016. The dataset description speaks of thirty eligible users; \
the exports contain 35 user ids.

**What the export contains.** No raw accelerometer or PPG signals, only what Fitbit's own \
software computed from them:

- per minute: steps, an intensity level from 0 to 3 (sedentary, lightly, fairly, very \
active), METs and calories, and, inside sleep logs, a sleep state (asleep, restless, awake);
- heart-rate readings every few seconds at irregular intervals (most are 5 seconds apart; \
the 10th to 90th percentile is 3 to 15 seconds), for 15 of the 35 users and only from \
29 March;
- hourly and daily totals of the same, a daily sleep summary in the second month only, and \
a few manually entered weights.

The dataset description says the differences between people's data partly reflect \
different types of Fitbit trackers; the export does not say which model each person used.

**What the app uses.** A derived daily table: one row per person and day with steps, \
minutes asleep, minutes in bed, mean heart rate, and fairly and very active minutes, for \
the three people with the most complete data.

**What is not available.** Sleep stages, heart rate variability, SpO2, resting heart rate, \
and raw sensor data.
"""

RAW_TABLES = {
    "hourlySteps": ("Hourly steps",
                    "Steps in each hour. The app adds up a day's 24 hours into daily steps."),
    "minuteIntensitiesNarrow": ("Minute intensity",
                                "Fitbit's intensity level for each minute: 0 sedentary, "
                                "1 lightly, 2 fairly, 3 very active. Levels 2 and 3 become "
                                "the active minutes."),
    "minuteSleep": ("Minute sleep",
                    "One row per minute of a sleep log: 1 asleep, 2 restless, 3 awake. "
                    "logId names the log; logs close together become one night."),
    "heartrate_seconds": ("Heart rate",
                          "Heart-rate readings in beats per minute, every few seconds at "
                          "irregular intervals. The app averages a day's readings."),
}

RAW_SAMPLE_NOTE = (
    "One representative day per person, copied unchanged from the raw export: the day on "
    "which every metric is present and the step count is closest to that person's median. "
    "The full export stays outside the repository."
)

DATASET_CREDIT = (
    "Data: Furberg, Brinton, Keating & Ortiz (RTI International), *Crowd-sourced Fitbit "
    "datasets 03.12.2016–05.12.2016*, Zenodo, 2016, "
    "[doi:10.5281/zenodo.53894](https://doi.org/10.5281/zenodo.53894), "
    "[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The app shows a daily table "
    "derived from it and small unchanged raw samples. Fitbit is a trademark of Google; this "
    "app is not affiliated with or endorsed by Fitbit, Google or the dataset's authors."
)

AUTHOR = ("Built by Sümeyye Ağaç · [GitHub](https://github.com/sumeyye-agac) · "
          "[LinkedIn](https://www.linkedin.com/in/sumeyyeagac/)")
