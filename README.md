# Ask Your Wearable

Ask plain-language questions about daily wearable data (steps, sleep, heart rate) and get
answers that come from tested Python functions, not from a language model doing arithmetic.

**Live app:** https://ask-your-wearable.streamlit.app

![Ask Your Wearable](docs/screenshot.png)

- [docs/DATA.md](docs/DATA.md): the dataset, what is in it, coverage tables, rebuilding the demo files.
- [docs/METHODS.md](docs/METHODS.md): how a day is counted, the validations, the tools, the full list of limits.
- [docs/DEPLOY.md](docs/DEPLOY.md): the Streamlit Community Cloud guide, usage limits, Docker and CI.

## What it does

You pick one of three demo people from a public Fitbit dataset and ask a question in plain
language. An LLM agent built on the Claude API with tool use (Claude Haiku 5.5) decides which
Python functions to call; the functions compute every number from the data, and the model only
turns their results into words. Each answer shows the tool calls behind it, so every figure can
be checked.

> **Which day was I most active?**
> You were most active on Thursday, 14 April 2016, with 17,022 steps. That was 466 steps more
> than the next most active day, Friday 15 April (16,556 steps). [...] Three days in that range
> have no step data: 19 and 20 March and 12 May.

## What was found

The daily table is built from Fitbit's raw hourly and per-minute exports, then compared with
Fitbit's own daily tables:

- **Sleep:** on nights with a single Fitbit sleep record, minutes asleep match `sleepDay`
  exactly on 332 of 346 nights.
- **Active minutes:** on 903 complete days, fairly and very active minutes match
  `dailyIntensities` exactly on 99.9% and 99.8% of days.
- **Steps:** in the first month, the sum of `hourlySteps` and the `dailyActivity` total agree
  within 1% on 92% of 428 user-days.
- **Coverage is thin:** of 35 volunteers, 34 have usable steps, 22 sleep and 13 a daily heart rate. Only
  8 have at least 7 days on which all three are present.

## Limits

- 35 volunteers in 2016 with older Fitbit devices; not a representative sample of anything.
  Even the three demo people have gaps.
- No sleep stages, heart rate variability, SpO2, stress or resting heart rate. Daily heart rate
  is a mean of all readings and mostly reflects activity.
- The 14 sleep mismatches and the 8% of step mismatches above are not explained yet.
- Correlation intervals assume independent days, so they are likely too narrow. A correlation
  says nothing about cause.
- "Am I active enough?" is approximate: Fitbit's per-minute intensity levels are not CDC's
  effort-based definition, and the 2× weight for very active minutes is CDC's rule of thumb.
- Not deployed yet, and the evaluation is not built. Wellness information only; the app does
  not diagnose anything.

The full list is in [docs/METHODS.md](docs/METHODS.md#limits).

## Run it

Python 3.11. The demo data is committed. The app and the terminal script need
`ANTHROPIC_API_KEY=...` in a git-ignored `.env` file in the repo root; the tests do not.

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
.venv/bin/streamlit run streamlit_app.py      # http://localhost:8501
.venv/bin/python scripts/ask.py --user 6962181067 "How was my sleep this week?"
```

## Data

Furberg, Brinton, Keating & Ortiz (RTI International), *Crowd-sourced Fitbit datasets
03.12.2016–05.12.2016*, Zenodo, 2016, [doi:10.5281/zenodo.53894](https://doi.org/10.5281/zenodo.53894),
CC BY 4.0. The files in `data/demo/` are derived from it under the same licence. Guideline
figures are from CDC pages (public domain); their use does not imply endorsement by CDC.

## Next steps

Not planned for this version:

- Compare models on the evaluation question set (tool-selection accuracy, numeric accuracy,
  unsupported-claim rate), not only Claude Haiku 5.5.
- A raw-signal layer: IMU data from a Movesense sensor, with my own human activity
  recognition model as a tool.
- An on-device version with a small model, to measure what is lost against the API model.
