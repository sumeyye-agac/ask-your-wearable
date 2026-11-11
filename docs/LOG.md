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
