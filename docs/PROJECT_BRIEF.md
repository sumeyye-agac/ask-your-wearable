# Project brief: Ask Your Wearable (draft for review)

Status: **proposal, not approved.** Review it before any code is written.

## The idea
A deployed web app where anyone can ask natural-language questions about wearable data
and get grounded answers with numbers and a small chart:

- "How was my sleep this week?"
- "Which day was I most active?"
- "Do I walk less on days after short sleep?"

Visitors use a built-in sample dataset. A user can also upload their own export
(first version: Zepp / Amazfit export only).

## Core design
- The LLM never does arithmetic on raw data. It calls deterministic, unit-tested Python tools
  (weekly summary, compare two periods, correlation, missing-data report, etc.) and turns
  their output into plain language.
- The LLM is called through an API with function calling. No model training, no model hosting.
- One agent, not a multi-agent system: a tool-use loop where the model can chain several tool
  calls for one question (e.g. two periods for a comparison), with a hard cap on steps.
  Every tool call and its result is logged and visible in the UI ("how this answer was computed").
- Wellness language only, never diagnosis.

## Candidate addition: small RAG layer (decide in review)
Today the app has no RAG; it is a tool-calling agent over structured data. RAG appears in most
applied LLM job postings, so a small, honest RAG part may be worth adding:
- A curated corpus of a few public health guidelines (e.g. official sleep-duration and
  physical-activity recommendations), chunked and embedded.
- A `search_guidelines(query)` tool. Questions like "Is 6 hours of sleep enough?" combine my data
  (from the tools) with a retrieved guideline, and the answer cites the source.
- Evaluated too: add a few guideline questions to the test set and check citation correctness.
Constraint: it must not push the plan past day 7. If it does, it goes to version 2.

## Why this project (for my CV)
My CV has no LLM / agent project and no deployed product. This one should show:
1. Time-series analysis on wearable data (my PhD field), as tested tools.
2. An LLM agent with function calling.
3. Evaluation: a 30-question test set with answers computed from code; report tool-selection
   accuracy, answer accuracy and hallucination rate in the README.
4. Production basics: Docker, CI with tests, rate limiting, a public link.
5. The same tools exposed as an MCP server (continues my repo `sumeyye-agac/mcp-har-benchmark`).

## Proposed stack (to be verified)
- Python, pandas, pytest
- Demo data: Kaggle "FitBit Fitness Tracker Data" (Fitabase, 30 users, daily activity,
  sleep, minute-level heart rate, reportedly CC0)
- LLM: an API with function calling (Claude or Gemini; decide on cost and free tier)
- UI: Gradio or Streamlit
- Deploy: Docker on Hugging Face Spaces (free CPU tier)
- CI: GitHub Actions running the tests

## Proposed 6-day plan (day 7 is buffer)
1. Load and clean data, first 5 tools, their tests.
2. Connect the LLM with function calling; ask questions from the terminal.
3. Web UI and charts.
4. Docker, deploy to Hugging Face Spaces, CI. Live link by the end of the day.
5. 30-question evaluation; results in the README.
6. Zepp upload, MCP server, README polish.

## Definition of done
- The public link works and answers most of the 30 test questions correctly on the demo data.
- Tests pass in CI.
- README follows my style: "What was found", honest "Limits", "Reproducing".

## Out of scope for now
Mobile app, on-device models, quantization experiments, AWS, model training, data collection.
(Possible version 2: run the same tools with a small on-device model and measure what is lost.)

---

## Review request
Critically review this proposal before we build anything. Do not write code yet.

1. **Feasibility:** Is the 6-day plan realistic for one person working with Claude Code?
   Which day is most likely to slip, and why?
2. **Verify facts** against current documentation and sources (search the web, do not rely on memory):
   - The Fitbit Kaggle dataset: license, what tables exist, date range, how many users have sleep data.
   - The Zepp / Amazfit data export: does it exist, what format, what fields.
   - Hugging Face Spaces: free tier limits for Docker apps, secrets for API keys.
   - LLM API choice: function-calling support, free tier or expected cost for a public demo,
     how to rate-limit.
3. **Risks:** List the top risks and a mitigation for each.
4. **Gaps and excess:** What is missing that a hiring manager would expect? What should be cut?
5. **RAG:** Is the small RAG layer above worth adding in version 1? Which guideline sources are
   public and safe to redistribute? Which embedding / vector store is simplest for this size?
6. **CV value:** Does this clearly show the skills listed above? Suggest changes that would
   make it stronger without making it bigger.
7. **Recommendation:** Go / change / no-go, with a revised plan if needed.

Write the review in English, short and structured. List every assumption you could not verify.
