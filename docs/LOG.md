# Log

One entry per working session. Newest at the bottom. Format is in `CLAUDE.md`.

### 2026-11-11
- Reviewed the project proposal against current documentation and wrote `docs/REVIEW.md`.
  Four findings changed the plan: Hugging Face Spaces no longer offers a free Docker tier,
  the Kaggle dataset copy is mislabelled CC0 (the Zenodo original is CC BY 4.0), the Zepp
  export has no documented format, and the proposed RAG layer was too small to be real retrieval.
- Applied six decisions: Streamlit Community Cloud for hosting (Docker kept for CI only),
  the Zenodo dataset instead of the Kaggle copy, a documented CSV upload instead of Zepp,
  a `get_guideline(topic)` tool instead of RAG, Claude Haiku 5.5 as the model, and an 8-day plan.
- Marked `docs/PROJECT_BRIEF.md` as approved and rewrote it with those decisions and the plan.
- Replaced the multi-file documentation system with this single log. Rewrote `CLAUDE.md`,
  replaced the `wrap-up` command, deleted `docs/LEARNING.md`.
- How to check it: read `docs/PROJECT_BRIEF.md` for the agreed scope and `docs/REVIEW.md` §1 for
  the verified facts behind each decision.
- Open issues: no code written yet. Day 1 starts with loading the two Zenodo zips and printing a
  coverage table — how many users have sleep and heart rate data, and how many days each covers,
  is still unverified and decides the tool list and the question set.

### 2026-11-11
- Day 1: downloaded both Zenodo zips (md5 verified) into git-ignored `data/raw/` and wrote
  `scripts/data_coverage.py`. Findings: 35 users; month 1's `dailyActivity` is incomplete
  (mostly 1-12 April only), `sleepDay` exists only in month 2, sleep has no stages, heart rate
  starts 29 March for 15 users. Steps therefore come from `hourlySteps`, sleep from `minuteSleep`.
- Built the `wearable` package: `zenodo.py` turns the raw export into one daily row per user
  (`steps`, `minutes_asleep`, `minutes_in_bed`, `mean_hr`); `scripts/build_daily.py` writes the
  three demo users (6962181067, 5553957443, 5577150313) to `data/demo/demo_daily.csv`.
  Nightly sleep matches Fitbit's `sleepDay` exactly on 332 of 346 single-record nights.
- Day 2: three tools with 30 passing tests: `weekly_summary`, `compare_periods` (presets
  first half vs second half, last 4 weeks vs previous 4), `missing_data_report`.
- Wrote the README data section, Limits and Reproducing. Out of scope: derived resting heart
  rate, sleep stages, HRV, SpO2, stress, weight. No month-over-month comparisons.
- Decisions approved: (1) sleep logs split by a gap of 60 min or less are one night;
  (2) a steps day needs all 24 hours recorded and more than 0 steps; (3) "this week" is the
  7 days ending on the user's last date with data; (4) `compare_periods` gives no difference
  if a period has fewer than 3 days with data, and reports no confidence interval;
  (5) the derived demo CSV is committed under CC BY 4.0 with attribution.
- How to check it: `.venv/bin/python scripts/build_daily.py data/raw && .venv/bin/python -m pytest`
- Open issues: in month 1, `dailyActivity` and summed `hourlySteps` disagree on 8% of 428
  user-days (unexplained, not blocking); 14 of 346 single-record nights are 1-99 min above
  Fitbit's `sleepDay`; demo user 5577150313 has sleep on only 2 of the last 7 nights. Next is
  day 3: most-active day and correlation with n and a confidence interval.

### 2026-11-11
- Day 3: two more tools, 52 tests passing (22 new). `most_active_day` ranks days by steps in a
  date range (default: whole range; top 3; ties go to the earlier date). `correlation` pairs
  metric_x on day d with metric_y on day d+lag (lag 0-7), reports n, r, a 95% CI and whether
  it excludes 0. No SciPy: Spearman is Pearson on average ranks, the quantile comes from
  `statistics.NormalDist`.
- CI method: Fisher z, standard error 1/sqrt(n-3) for Pearson and Bonett & Wright (2000,
  Psychometrika 65:23-28) sqrt((1 + r^2/2)/(n-3)) for Spearman. Tested against a textbook
  value (r=0.5, n=28 gives 0.156..0.735) and `statistics.correlation`.
- Since sleep is dated by the wake-up day, "do I walk less after short sleep?" is
  minutes_asleep vs steps at lag 0. On the demo users: Spearman r = -0.16 (n=61, CI -0.39..0.10),
  -0.52 (n=57, CI -0.69..-0.28), 0.02 (n=53, CI -0.25..0.29). Steps vs mean_hr is positive for
  all three (0.41, 0.73, 0.60), as expected.
- Decisions to confirm: (1) no r below 10 paired days; (2) Spearman is the default method;
  (3) lag limited to 0-7 days.
- How to check it: `.venv/bin/python -m pytest`
- Open issues: the CI assumes independent days; consecutive days are autocorrelated, so the
  intervals are likely too narrow. This is not corrected and should go in the README "Limits".
  This log entry is not committed yet. Next is day 4: the tool-use loop in the terminal.

### 2026-11-11
- Approved the three day 3 choices: no r below 10 paired days, Spearman as the default method,
  lag limited to 0-7 days.
- Added the autocorrelation caveat to the README "Limits": the correlation intervals assume
  independent days, so they are likely too narrow. Deliberately not corrected for.
- How to check it: read the last bullet of "Limits" in `README.md`.
- Open issues: none new. Next is day 4: the tool-use loop in the terminal.

### 2026-11-11
- Day 4: the tool-use loop. `wearable/registry.py` holds the five tool specs the model sees
  (strict schemas, enums for metrics, presets, methods, lag and top_n) and `run_tool`;
  `wearable/agent.py` is a hand-written loop around `messages.create` with a step cap
  (6 model requests), a spend guard ($0.01 per question, estimated from the usage block) and a
  trace of every tool call; `scripts/ask.py` is the terminal entry point and appends traces to
  git-ignored `logs/trace.jsonl`. 72 tests passing (20 new, all offline with a scripted client).
- Verified against current docs before use: Haiku 5.5 prices ($0.10 / $0.50 per MTok up to
  100K prompt tokens), strict tool use allows optional properties, `anthropic` 2.8.0 installed.
- Ran 7 real questions on demo users 6962181067 and 5553957443 with `claude-haiku-5-5`. Each
  took 2 model requests and cost about $0.001 (7,700-8,600 input tokens, 320-770 output).
  Tool choice was right on all 7; the diagnosis question got an explicit refusal and the deep
  sleep question was answered with "not in the data".
- One wrong number in the first run: for "most active day" the model wrote "about 6,900 more
  than the next-highest day", which is the gap to the weekly mean, not to the second day
  (3,106). The prompt now forbids deriving any number from tool results; the rerun did not
  repeat it. One rerun is not evidence that it is fixed; day 7's unsupported-claim rate is.
- How to check it: `.venv/bin/python -m pytest && .venv/bin/python scripts/ask.py --user 6962181067 "How was my sleep this week?"`
- Open issues: `most_active_day` reports that a day has no step data but not which one, so the
  model cannot name it. `get_guideline` (decision 4) is not built and not on any day of the
  plan. No memory between questions. The spend guard is an estimate inside the program; the
  Console spend limit is still the real one. Nothing from this session is committed yet.
  Next is day 5: the Streamlit UI.

### 2026-11-11
- Committed day 4 in four commits and pushed to `main`.
- Tools now return the comparisons the model used to compute itself. `most_active_day`: the
  lead over the second day and over the mean, each top day's distance from the mean, and the
  dates without step data. `weekly_summary`: highest/lowest distance from the mean, the range,
  and an optional `threshold` (days at or above, days below, mean minus threshold).
  `compare_periods`: which period is higher. Minute metrics also come as text ("7 h 38 min"),
  so the prompt no longer allows any conversion or arithmetic.
- Added `get_guideline(topic)` in `wearable/guidelines.py` with two topics, both from CDC pages
  read today: sleep duration (7+ h for 18-60, 7-9 h for 61-64, 7-8 h for 65+) and adult
  physical activity (150 min moderate or 75 min vigorous a week, 2 days of strength work).
  Licence checked: CDC website text is public domain with conditions (credit, no change to the
  substance, no implied endorsement); the credit line travels with every result and is in the
  README. WHO was not used: copyrighted, licence terms not verified.
- Reran the 7 questions plus "Is my sleep enough?" and "Am I active enough?" on the real API.
  All 9 picked the right tools, and I found no number in the answers that is not in a tool
  result (checked by reading, not by a script). The sleep question chained get_guideline then
  weekly_summary with threshold 420. The activity question stated the CDC recommendation and
  said steps cannot be checked against it. 87 tests passing.
- How to check it: `.venv/bin/python -m pytest && .venv/bin/python scripts/ask.py --user 6962181067 "Is my sleep enough?"`
- Open issues: tool results are larger, so a question now uses about 9,300-10,200 input tokens
  (was 7,700-8,600) and still costs about $0.001; the guideline chain costs about $0.002. The
  model named "CDC" but did not print the full credit line, so the day 5 UI has to show the
  `credit` field itself. "Is my sleep enough?" looked at the last week only. The sleep
  threshold of 7 h ignores naps and the user's unknown age. The fixes from this session are
  not committed yet. Next is day 5: the Streamlit UI.
