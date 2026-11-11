# Project brief: Ask Your Wearable

Status: **approved 2026-11-11.** This is the agreed scope.
The review that led to these decisions is in `docs/REVIEW.md`.

## The idea
A deployed web app where anyone can ask natural-language questions about wearable data
and get grounded answers with numbers and a small chart:

- "How was my sleep this week?"
- "Which day was I most active?"
- "Do I walk less on days after short sleep?"

Visitors use a built-in sample dataset. A user can also upload their own data as a CSV
matching a documented schema.

## Core design
- The LLM never does arithmetic on raw data. It calls deterministic, unit-tested Python tools
  (weekly summary, compare two periods, correlation, missing-data report, etc.) and turns
  their output into plain language.
- The LLM is called through an API with function calling. No model training, no model hosting.
- One agent, not a multi-agent system: a tool-use loop where the model can chain several tool
  calls for one question, with a hard cap on steps.
  Every tool call and its result is logged and visible in the UI ("how this answer was computed").
- Wellness language only, never diagnosis. A diagnosis question gets an explicit refusal.

## Decisions taken at approval

These supersede the corresponding parts of the original proposal. Reasons are in `docs/REVIEW.md`.

1. **Hosting: Streamlit Community Cloud (free).** Not Hugging Face Spaces — creating Docker or
   Gradio Spaces there now requires a paid plan. A `Dockerfile` stays in the repo as an optional
   reproducible build exercised by CI, not as the deployment path.
2. **Data: the original Zenodo dataset**, not the Kaggle copy. Record 53894, Furberg, Brinton,
   Keating & Ortiz (RTI International), *Crowd-sourced Fitbit datasets 03.12.2016–05.12.2016*,
   **CC BY 4.0**, both monthly zips (12 March – 12 May 2016). Attribute the authors and cite the
   DOI in the README and in the app's data panel.
3. **No Zepp / Amazfit upload.** Its export format is undocumented and sources contradict each
   other on whether it exists. Replaced by: a documented CSV schema, a downloadable template
   file, and a validator with useful error messages, for user uploads of any provenance.
4. **No RAG.** Replaced by a deterministic `get_guideline(topic)` tool over a small curated set of
   public guideline statements, each carrying its source and link. Described as a curated
   reference lookup, not as retrieval.
5. **LLM: Claude Haiku 5.5** (`claude-haiku-5-5`) via the Claude API, roughly $0.002 per question.
   The model id lives in an environment variable. A low spend limit is set in the Console.
6. **Plan length: 8 days.**

## Why this project (for my CV)
My CV has no LLM / agent project and no deployed product. This one should show:
1. Time-series analysis on wearable data (my PhD field), as tested tools.
2. An LLM agent with function calling.
3. Evaluation: a question set with answers computed from code; report tool-selection accuracy,
   numeric accuracy and unsupported-claim rate in the README, each with its definition.
4. Production basics: CI with tests, an optional Docker build, rate and spend limits, a public link.
5. The same tools exposed as an MCP server (continues my repo `sumeyye-agac/mcp-har-benchmark`).

## Stack
- Python 3.11+, pandas, pytest
- Data: Zenodo record 53894 (see decision 2)
- LLM: Claude API, `claude-haiku-5-5`, function calling
- UI: Streamlit
- Deploy: Streamlit Community Cloud
- CI: GitHub Actions running the tests and the Docker build

## 8-day plan

| Day | Work | Done when |
|---|---|---|
| 1 | Load the Zenodo data. Print a coverage table: rows, unique users, date range, users per data type, missing days per user. Write the data-reality section of the README first. | I can state with numbers what the demo data can and cannot answer. |
| 2 | 3 tools + tests: weekly summary, compare two periods, missing-data report. | `pytest` green. |
| 3 | 2 more tools + tests: most-active day, correlation reporting n and a confidence interval. | `pytest` green. |
| 4 | Tool-use loop in the terminal. Step cap, spend guard, trace log. | I can ask 5 questions from a shell and read the trace. |
| 5 | Streamlit UI, charts, the "how this answer was computed" panel. | Runs locally; the trace panel works. |
| 6 | Deploy to Streamlit Community Cloud. CI with tests and the Docker build. Nothing else. | Public link works; CI green. |
| 7 | Evaluation: 15 questions, an explicit grading contract, a results table in the README with the date and the model id. | `make eval` reproduces the published numbers. |
| 8 | MCP server over the tool package. CSV upload, template and validator. README polish: honest "Limits" and three real failure examples. | Done. |

The tool layer is a clean importable Python package from day 2 onward, so that day 8's MCP server
is a thin wrapper rather than a rewrite.

## Definition of done
- The public link works and answers most of the question set correctly on the demo data.
- Tests pass in CI.
- README follows my style: "What was found", honest "Limits", "Reproducing".
- Evaluation numbers are reproducible by a reader, and each metric is defined next to its number.

## Out of scope
Mobile app, on-device models, quantization experiments, AWS, model training, data collection,
vendor-specific export parsing, retrieval over a large corpus.
(Possible version 2: run the same tools with a small on-device model and measure what is lost.)

## Known unknowns to settle on day 1
From `docs/REVIEW.md` §7, the ones that affect the plan:
- Which files the Zenodo zips contain, how many users have sleep and heart rate data, and how
  many days each user actually covers. The tool list and the question set follow from this, not
  the other way round.
- Whether month-over-month questions are answerable at all given the real coverage.
