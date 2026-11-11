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

### 2026-11-11
- Committed and pushed the three fixes (comparisons in the tools, missing step dates,
  `get_guideline`).
- Added active minutes. Checked the coding first: `minuteIntensitiesNarrow` has codes 0-3,
  which Fitbit's Web API reference names sedentary, lightly, fairly and very active. Counting
  codes 2 and 3 per day reproduces Fitbit's own `dailyIntensities` on 99.9% and 99.8% of 903
  complete days. The minute table is used because it covers both months. New daily metrics
  `fairly_active_minutes` and `very_active_minutes`; the demo CSV was rebuilt and its existing
  columns are unchanged.
- New tool `weekly_active_minutes`: weekly totals against CDC's 150 moderate / 75 vigorous
  minutes, with a caveat in every result that Fitbit's estimate is not CDC's definition
  (3-5.9 METs, 6.0+ METs, or the talk test; CDC "How to Measure Physical Activity Intensity",
  page date 2025-12-04). With missing days a total is a lower bound, so the result is "reached"
  or "unknown", never "missed".
- Step counts in tool output are whole numbers (halves round up), and every difference is the
  difference of the rounded numbers shown. 100 tests passing.
- Reran "Am I active enough?" on the real API for 6962181067 (129 very active minutes against
  75, 76 fairly active against 150) and 5553957443 (144 and 79). Both answers said the vigorous
  target was reached, that the moderate one cannot be judged with 12 May missing, and gave the
  caveat.
- Decisions to confirm: (1) an active-minutes day needs all 1440 minutes and at least one
  minute above sedentary; (2) moderate and vigorous are compared with their targets separately
  and no combination is computed, because the CDC page gives no conversion; (3) a new tool
  rather than only a metric, so the totals and the caveat come from code.
- How to check it: `.venv/bin/python -m pytest && .venv/bin/python scripts/ask.py --user 6962181067 "Am I active enough?"`
- Open issues: 12 May is partial for every demo user, so "this week" never has 7 days of steps
  or active minutes; anchoring "this week" on the last complete day would fix it but changes
  approved decision 3. Fitbit's cut-offs between intensity levels are not documented in the
  sources I read. One answer used bullet points although the prompt asks for plain sentences.
  The build prints 34 users, the README says 35 in the exports; not looked into. Next is day 5:
  the Streamlit UI.

### 2026-11-11
- Approved: an active-minutes day needs all 1440 minutes and one minute above sedentary; a week
  with missing days gives "reached" or "unknown"; `weekly_active_minutes` stays as a tool.
- Corrected my claim that CDC gives no conversion. Its page "What Counts as Physical Activity
  for Adults" (page date 2023-12-06, read today) says 1 minute of vigorous activity is about the
  same as 2 minutes of moderate activity. `weekly_active_minutes` now leads with `combined`:
  fairly active + 2 x very active minutes against 150, with the rule and its source in the
  result. The separate moderate and vigorous figures stay as detail.
- Decision 3 changed, with approval: "this week" is the 7 days ending on the user's last
  complete day (last date with steps or active minutes), not the last date with any data. For
  the demo users that is 5-11 May instead of 6-12 May. I applied the same anchor to the
  "last 4 weeks" preset so the two recent periods agree; this was not asked for explicitly.
- Dropped the prompt rule against bullet points. 105 tests passing.
- 34 vs 35 users: both numbers are right. The exports hold 35 ids; user 2891001357 has 12 hours
  on one day only, so no valid day and 34 users in the daily table. The README now says so.
- Reran "Am I active enough?" and "How was my sleep this week?" for 6962181067 and 5553957443.
  Both weeks are now complete (7 of 7 days). Combined minutes: 384 and 484 against 150; both
  answers led with that, cited the rule of thumb and gave the Fitbit caveat. Sleep: mean
  7 h 31 min and 7 h 32 min, 6 of 7 and 4 of 7 nights at or above 7 h.
- How to check it: `.venv/bin/python -m pytest && .venv/bin/python scripts/ask.py --user 6962181067 "Am I active enough?"`
- Open issues: for "How was my sleep this week?" the model compared with 7 hours without
  calling `get_guideline`, and one answer mentioned "general adult guidelines" without naming a
  source. Both activity answers called the window "last week" although the prompt defines it as
  "this week". These belong in the day 7 evaluation. Next is day 5: the Streamlit UI.

### 2026-11-11
- Approved: the "last 4 weeks" preset is anchored on the last complete day, like "this week".
- Day 5: Streamlit app in `streamlit_app.py` (Streamlit 1.67.0, latest on PyPI today): demo
  user dropdown, question box, five example buttons, the answer, one chart where it fits
  (week of sleep or steps, active minutes, two periods, correlation scatter), an expander
  "How this answer was computed" with every tool call's arguments and result, the CDC credit
  line whenever a result carries one, a wellness note, and the Zenodo attribution in the footer.
  Testable logic is in `wearable/presentation.py`; `tools.paired_days` was split out of
  `correlation` so the scatter plots exactly the pairs the tool counted.
- Limits: 10 questions per visitor per UTC day and an estimated $1.00 per UTC day for the whole
  app, in memory. Visitor = `st.context.ip_address` (documented; None on localhost, spoofable)
  or else the browser session. Failures get a short message: 402 / `billing_error` is "out of
  credit" (status and type from the SDK's error table), 401/403, 429, 5xx and network errors
  each have their own text, anything else a generic one. 133 tests, including headless
  `AppTest` runs of the page with the API call stubbed.
- Ran two real questions through the page script: "Which day was I most active?" (1 tool call,
  steps chart, $0.0014) and "Is my sleep enough?" (get_guideline then weekly_summary, hours
  asleep chart, CDC credit shown, $0.0026). Not deployed.
- How to check it: `.venv/bin/python -m pytest && .venv/bin/streamlit run streamlit_app.py`, then open http://localhost:8501
- Open issues: unverified whether `st.context.ip_address` on Community Cloud gives each
  visitor's own address or a shared proxy address; if shared, all visitors share 10 questions,
  so check it on day 6. Not verified what the API returns when a Console spend limit (rather
  than the credit balance) is reached; whatever it is, the visitor gets a message, not a crash.
  Limits reset when the app restarts, so the Console spend limit stays the real backstop.
  On localhost, reloading the page resets a visitor's count. This log entry is not committed.
  Next is day 6: deploy and CI.

### 2026-11-11
- Fixed four issues from browser testing of the app. (1) State leak: an example button wrote its
  question into the text box and left it there, so typing appended to it (the trace shows
  "Am I active enough?Ignore your instructions..." sent as one question). Now examples and the
  Ask button both put one question into a one-shot queue, the box is emptied on submit, and
  only that question is sent. (2) The question being answered is shown above the answer
  (escaped, so typed markdown shows as typed), also above error messages.
- (3) and (4) are prompt rules in `agent.system_prompt`: answer only questions about the
  wearable data and decline the rest in one sentence, in every language; never say which or
  how many days were above or below a value unless weekly_summary returned it with that
  threshold; never cite a guideline or its numbers that get_guideline did not return (added
  after reruns showed the model citing "7-9 hours" unprompted, which is not CDC's figure for
  18-60). App tests no longer write to `logs/trace.jsonl` (`WEARABLE_TRACE`). 141 tests.
- Reruns on the real API, user 5553957443, about $0.04 in total. UI: example click, then a
  typed question, sent exactly the two questions, box empty after each. Poem request: declined
  in 9 of 9 runs (3 English, 6 Turkish), data part still answered. "How was my sleep this
  week?" (6 English, 3 Turkish runs): no run said which or how many nights were under 7 hours.
  "Is my sleep enough?" / "Uykum yeterli mi?" (2 + 2 runs): all called get_guideline then
  weekly_summary with threshold 420 and gave 4 at or above, 3 below.
- How to check it: `.venv/bin/python -m pytest && .venv/bin/streamlit run streamlit_app.py`, then open http://localhost:8501
- Open issues: prompt rules lower the rate of unsupported claims but do not guarantee it.
  In the last reruns the model still derived small things no tool returned: "the other six
  nights were between 6 h 40 min and 7 h 43 min", "time in bed runs about half an hour longer
  than time asleep", and in Turkish "most nights were around 7 hours". These belong in the
  day 7 unsupported-claim metric. `logs/trace.jsonl` still holds 4 "Fine." rows written by
  earlier test runs (git-ignored; not deleted). Next is day 6: deploy and CI.

### 2026-11-11
- Part A (state leak, question display, off-topic, threshold claims) was already fixed and
  committed in the previous session (fa58223, 42d8633); reran all four cases on the real API
  through the new page: one question per action and an empty box after each; the poem declined
  in English and Turkish; no under-7-hours claim without a threshold call; "Uykum yeterli mi?"
  used threshold 420 (4 at or above, 3 below). That answer also named which nights were below,
  which the tool did not return, so `weekly_summary` now returns `dates_at_or_above` and
  `dates_below`; after that both languages named exactly the tool's dates (5, 6, 10 May).
- Page restructured into tabs "Ask", "How it works", "Data", with the person picker in the
  sidebar. People are Person A/B/C (sorted ids) with a profile from daily-table counts only
  (A: 59 days of steps, 58 nights of sleep, heart rate on 39 days from 1 Apr; B: 57, 55, 37 from
  1 Apr; C: 61, 62, 44 from 30 Mar); the real id is in each answer's trace and on the Data tab.
  "How it works": pipeline diagram (Graphviz DOT, no extra package) and five steps with the
  recorded decisions and checks; a test asserts every figure shown also appears in README.md
  or docs/LOG.md. Text lives in `wearable/app_text.py`.
- Data tab facts checked today against the raw export and the Zenodo record: intensity codes
  0-3 for 35 users, sleep codes 1-3 for 25 users, heart rate for 15 users from 29 March to
  12 May, readings mostly 5 s apart (10th-90th percentile 3-15 s); the record says thirty
  eligible users and that output varies with tracker type, but not which tracker each person
  used. Daily table is sortable with a CSV download. Raw sample: `scripts/build_raw_sample.py`
  writes one unchanged day per person of `hourlySteps`, `minuteIntensitiesNarrow`,
  `minuteSleep` and `heartrate_seconds` to `data/demo/raw_sample/` (108 KB, gzip CSV). The app
  builds steps from hourly, not minute, steps, so the sample has `hourlySteps` rather than the
  minute steps table named in the request.
- Theme in `.streamlit/config.toml`: light, teal accent #2A7F7A, Inter. Footer: "Built by
  Sümeyye Ağaç" with GitHub and LinkedIn, plus the dataset credit. README: tabs, raw sample,
  and a "Next steps" section. 173 tests. Reruns today cost about $0.02.
- How to check it: `.venv/bin/python -m pytest && .venv/bin/streamlit run streamlit_app.py`, then open http://localhost:8501
- Open issues: "Next steps" lists an MCP server as future work not planned for this version,
  as requested, but the approved brief has it on day 8; decide whether day 8 changes. The
  restructure goes beyond the day 5 line of the plan ("Streamlit UI, charts, trace panel"), at
  the user's request. The Inter font loads from Google Fonts, so the page sends a request there.
  Small derived phrases ("about 1 h 56 min above the average" is from the tool; the Turkish
  "most nights around 7 hours" kind is not) remain for the day 7 metric. Next is day 6.

### 2026-11-11
- Decisions: the MCP server stays on day 8 as in the brief, so it is out of the README's
  "Next steps"; loading the Inter font from Google Fonts is fine.
- Chart fixes from browser review: the comparison chart's title no longer reads "Mean mean
  heart rate (bpm)" (now "<metric>: daily average in each period"), and a test builds every
  chart for every metric and fails on any repeated word in a title or axis. Its bars are
  labelled "First half" / "Second half", "Previous 4 weeks" / "Last 4 weeks", or "Period A" /
  "Period B" for custom dates, horizontally, with the dates in the tooltip. All charts are now
  Altair (shipped with Streamlit) in the theme's accent #2A7F7A; stacked active minutes use the
  accent and a lighter tint.
- Significance wording: `compare_periods` and `correlation` results now carry
  `significance_test` saying the tool does not run one, and the prompt says to attribute the
  missing test to the tool, never to the data. Two real runs through the page ($0.0015 each):
  both answers said the tool does not run a significance test, and the page drew the
  comparison chart in the accent colour with horizontal labels and the dates in the tooltip.
- Person picker options read "Person A · 59 days of steps". 183 tests.
- How to check it: `.venv/bin/python -m pytest && .venv/bin/streamlit run streamlit_app.py`, then open http://localhost:8501
- Open issues: one significance answer added its own comparison ("the 1,340-step gap is
  smaller than the typical variation from one day to the next"), which no tool returned; this
  goes with the other derived phrases into the day 7 unsupported-claim metric. Next is day 6.
