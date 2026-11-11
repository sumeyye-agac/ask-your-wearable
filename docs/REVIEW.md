# Review of the project brief

Date: 2026-11-11
Reviewer: Claude Code, at your request
Scope: `docs/PROJECT_BRIEF.md`, review request section. No code written.

**Verdict: change, then go.** The core idea is sound and worth building. Four things in the
brief are wrong or unverified and must be settled before day 1: the deployment host is not
free any more, the Zepp export has no verified specification, the dataset license on Kaggle
conflicts with the original, and the RAG layer as proposed is decoration rather than
engineering. The 6-day plan is not realistic at the quality bar in `CLAUDE.md`; 8 days is.

---

## 1. Fact check

Each item says what I verified, from where, and what I could not verify.

### 1.1 The Fitbit dataset — license is wrong in the brief

| Claim in brief | Finding |
|---|---|
| "Kaggle FitBit Fitness Tracker Data ... reportedly CC0" | **Partly wrong.** The Kaggle page `arashnic/fitbit` is labelled CC0 Public Domain, but the original is Zenodo record 53894, Furberg, Brinton, Keating & Ortiz (RTI International), *Crowd-sourced Fitbit datasets 03.12.2016–05.12.2016*, published 31 May 2016 under **CC BY 4.0**. A re-uploader cannot relicense someone else's CC BY work as CC0. |
| "30 users" | **Verified at the source:** "Thirty eligible Fitbit users consented to the submission of personal tracker data", collected via a distributed survey on Amazon Mechanical Turk. |
| "daily activity, sleep, minute-level heart rate" | **Verified in general terms:** Zenodo describes minute-level physical activity, heart rate and sleep data, and warns that "output varies with the type of Fitbit tracker used and individual tracking habits". |

**Action:** treat it as CC BY 4.0. Attribute Furberg et al. and cite the Zenodo DOI in the
README and in the app's data panel. This costs one sentence and removes a licensing problem.

**Could not verify (and this matters):** the exact file list, the per-file unique-user counts,
and which date folder the Kaggle copy actually contains. The Zenodo title says
03.12.2016–05.12.2016 and the file names reference two windows (`3.12.16-4.11.16` and
`4.12.16-5.12.16`), so the Kaggle copy may hold **about one month**, not two. The commonly
repeated figures (~33 users in daily activity, ~24 with sleep, ~14 with heart rate) appear in
many student projects but I found no authoritative confirmation, and search results actively
disagreed with them.

This is the single most consequential unknown in the plan. If only ~24 users have sleep and
~14 have heart rate, and the window is ~31 days, then:
- "Do I walk less on days after short sleep?" is a per-user correlation with n ≈ 31 at best.
- Any "this month vs last month" question is unanswerable.

**Action:** before writing a single tool, load the files and print a coverage table (rows,
unique users, date range, users per data type, missing days per user). Build the tool list and
the question set from what is actually there. One hour on day 1, and it de-risks days 1 and 5.

### 1.2 Zepp / Amazfit export — no verified specification. Cut it.

Sources conflict on whether the Zepp app exports data at all. A March-2026 guide states the
app "does not include a built-in data export feature" and lists only workarounds: manual
screenshots, the **undocumented** Zepp API ("undocumented and changes often"), open-source
scrapers (`zepp-fit-extractor`, `ZeppBridge`, `Mi-Fit-and-Zepp-workout-exporter`), or a paid
third-party service. A GitHub project simultaneously claims "Zepp bulk export only provides
CSV files", and a November-2026 issue reports a user unable to find any CSV export. I found
**no documented field list** anywhere.

So day 6's "Zepp upload" is a reverse-engineering task against a moving, undocumented target,
scheduled on the last day before buffer. That is the wrong shape of risk for a CV project.

**Recommendation:** replace it with *"upload a CSV that matches this documented schema"* —
ship a downloadable template, a schema validator, and clear error messages. It demonstrates
the same reviewable skills (schema validation, defensive parsing, useful errors) with zero
dependency on a vendor's undocumented behaviour, and it works for *any* device whose data the
user can get into a spreadsheet. If you later want one real vendor format, pick one with
published documentation and do it as a separate, scoped task.

### 1.3 Hugging Face Spaces — the free Docker tier the plan depends on no longer exists

From the official Hub docs (`spaces-overview`), verbatim:

> Static Spaces are free for everyone. **Gradio and Docker Spaces run on compute and require a
> paid plan to create**: PRO for personal accounts, Team or Enterprise for organizations. Free
> personal accounts in good standing can still host up to 2 Gradio Spaces running on ZeroGPU.

The pricing page still lists CPU Basic at **FREE** (2 vCPU, 16 GB, 50 GB non-persistent) — the
hardware is free, but **creating** a Docker or Gradio Space is not. PRO is $9/month personal.

The ZeroGPU escape hatch does not fit this project: ZeroGPU is **Gradio SDK only** (so not
Docker), it is GPU infrastructure your CPU-only app has no use for, and free accounts get
5 minutes of GPU quota per day (unauthenticated visitors get 2). Free hosting there requires an
account with a verified email that is older than 30 days, capped at 2 such Spaces.

Other verified Spaces facts, all still true and useful:
- **Secrets:** Settings → *Secrets* for API keys (write-only once set, not copied to duplicated
  Spaces) vs *Variables* for non-sensitive config. Exposed to the app as environment variables;
  Docker Spaces have their own documented mechanism. A secrets scanner warns on hard-coded keys.
- **Sleep:** on free hardware a Space sleeps after a period of inactivity. Paused time is unbilled.
- **Networking:** outbound requests only on ports 80, 443 and 8080. Other ports are blocked
  (fine for the Claude API, worth knowing).
- **Disk is not persistent** — so uploaded user data must not be assumed to survive a restart.
  Good: it matches "never store personal health data".

**Your options (this is a money decision, so it is yours):**

| Option | Cost | Trade-off |
|---|---|---|
| HF **PRO**, Docker Space | $9/mo | Keeps the plan exactly as written. HF is where ML reviewers browse. Lowest friction. |
| **Streamlit Community Cloud** | $0 | Free public apps, sleeps after ~12 h idle. Not Docker, so the Dockerfile becomes a repo artifact rather than the deploy path. Published resource limits are inconsistent across sources — unverified. |
| **Render** free web service | $0 | 512 MB RAM, 0.1 CPU, spins down after 15 min idle, 750 instance-hours/month per workspace, ephemeral disk; Render's own docs say not for production. Tight for pandas. |

My recommendation: **pay the $9** if you want the HF audience and a Docker deploy on your CV,
otherwise Streamlit Community Cloud. Either way keep the Dockerfile and the CI in the repo —
the CV signal is the Dockerfile plus a green test badge, not the hostname.

### 1.4 LLM API — function calling, real cost, and how to rate-limit

**Function calling:** supported on the Claude Messages API (tool use). Two current behaviours
that affect your design:
- Forced tool choice (`tool_choice: {type:"any"}` or `{type:"tool"}`) now returns **400** on the
  newest models. Use `tool_choice: "auto"` plus `strict: true` on each tool definition, and name
  the expected tool in the prompt. Your "the model must call a tool" instinct is right; the
  mechanism is prompt + `strict`, not forcing.
- **Prompt caching** on the system prompt and the tool definitions is worth switching on early:
  cached input tokens do not count toward the input-tokens-per-minute limit and are billed at a
  fraction of the input price. Your tool list is the ideal stable prefix.

**Models and prices** (Anthropic first-party rates):

| Model | ID | Input $/1M | Output $/1M |
|---|---|---|---|
| Claude Haiku 5.5 | `claude-haiku-5-5` | $0.10 | $0.50 |
| Claude Sonnet 5.5 | `claude-sonnet-5-5` | $2.00 | $10.00 |
| Claude Opus 5.5 | `claude-opus-5-5` | $4.00 | $20.00 |

Haiku 5.5's listed price applies to prompts up to 100K tokens ($0.50 / $2.50 above that) — not a
concern here.

**Worked cost estimate for the demo.** One question in a tool-use loop is roughly 3 model calls
(ask → tool_use → tool_result → final answer). Assume ~3K input and ~500 output per call:
~9K input and ~1.5K output per question. On Haiku 5.5 that is
`9,000 × $0.10/1M + 1,500 × $0.50/1M ≈ $0.0009 + $0.00075 ≈ **$0.002 per question**`.
A thousand visitor questions costs about **$2**. Conclusion: **model cost is not a real risk;
abuse and runaway loops are.** Default to Haiku 5.5 and keep the model id in an env var.

**No free tier is documented.** New organizations may start in an **Evaluation tier** with limits
below the published ones, rising automatically with usage history. Published Start-tier limits
for Haiku 5.5 are 4,000 requests/min, 2M input tokens/min, 400K output tokens/min — orders of
magnitude above anything a demo needs — with a **$500 monthly spend cap**.

**How to rate-limit, in order of how much it actually protects you:**
1. **Set your own spend limit in the Console** (Billing → Spend limits, below your tier cap).
   This is the only guard a determined abuser cannot route around. Over your own limit the API
   returns HTTP 400 `invalid_request_error`; over the tier cap it returns 429 with error code
   `enforced_spend_limit_reached` and **no** `retry-after`, which the SDK's automatic retries
   cannot recover from — handle that case explicitly rather than retrying.
2. **A hard cap on tool-call steps per question** and a modest `max_tokens`. A looping agent is
   the realistic way to burn money by accident.
3. **A global daily question counter** in the app, with a friendly "demo limit reached" message.
4. **Per-session limits.** Note honestly: Gradio and Streamlit have no built-in rate limiter, and
   a session-state counter is bypassed by opening a new session, so this is politeness, not
   security. Do not rely on it.

Also: never let a user's text reach a tool as a free-form expression to evaluate. Tools take
typed, validated arguments only.

**Could not verify:** whether free credits exist for a new account, and the Gemini free-tier
numbers (third-party reports ranged from ~20 to ~1,500 requests/day and contradicted each other;
one source says Google no longer publishes per-model free-tier figures). If you want Gemini as
the cost hedge, read the quota page in your own AI Studio console — nothing else is trustworthy.

### 1.5 RAG — not worth it in version 1, as proposed

Verified facts:
- **Anthropic has no embeddings endpoint.** Its own docs say so plainly and point to Voyage AI
  (now Voyage AI by MongoDB). So "add RAG" implicitly adds a second vendor and a second API key.
- `voyage-4-nano` is **open-weight, Apache 2.0**, downloadable from Hugging Face — the no-extra-
  vendor option if you do embed. Hosted Voyage models are reported (third party, **unverified**)
  to include a one-time free token allotment; MongoDB's docs mention a free tier of 200M tokens
  for current models. Check before relying on it.
- **WHO 2020 physical activity guidelines: CC BY-NC-SA 3.0 IGO.** Non-commercial *and*
  ShareAlike — an adaptation must be licensed under the same or an equivalent licence. Note the
  trap: the Bull et al. summary in *BJSM* is **CC BY 4.0** from BMJ, different terms, different
  document. Redistributing the WHO text inside your repo drags ShareAlike obligations onto that
  corpus. Short quotations with attribution and a link are the clean path.
- **CDC sleep recommendations: verified directly from the CDC page**, with the sources the CDC
  itself cites — 7 or more hours for adults 18–60 (Watson et al., *Sleep*, 2015, AASM/SRS joint
  statement), 7–9 h for 61–64 and 7–8 h for 65+ (Hirshkowitz et al., *Sleep Health*, 2015), 8–10 h
  for teens and 9–12 h for school age (Paruthi et al., *JCSM*, 2016). US federal works are
  generally not under US copyright, but **the page carries no explicit licence statement**, so
  check its Web Policies before copying tables wholesale. The underlying journal statements are
  publisher-copyrighted — cite them, do not reproduce them.

**The engineering argument against RAG here.** A curated corpus of "a few public health
guidelines" is on the order of 5–20 short statements. Retrieval over 20 items is a dictionary
lookup. Embedding them, storing vectors and calling it RAG is a label on a `dict`, and a
reviewer who works on retrieval will spot that immediately — it reads as CV padding, which is
the opposite of what you want. It also adds a vendor, a key, a licence obligation and a day you
do not have.

**Do this instead (v1):** a deterministic `get_guideline(topic)` tool returning a curated,
attributed statement with its citation and link. Testable, honest, two hours of work, and it
gives you exactly the behaviour you wanted: "Is 6 hours enough?" answered by combining the
user's measured average with a cited recommendation. Call it a *curated reference lookup* in the
README, not RAG.

**If you want a genuine retrieval credential**, build it where it is real: a corpus large enough
that retrieval quality is a question, evaluated with recall@k. That is its own small repo, and it
would pair well with `mcp-har-benchmark`. It does not belong inside day 7 of this one.

If you overrule me and embed anyway: `numpy` dot product over a saved array of normalised
vectors. No FAISS, no Chroma. At this size a vector store is overhead a reviewer will notice.

---

## 2. Feasibility: is 6 days realistic?

**No, not at the quality bar your `CLAUDE.md` sets.** The constraint is not typing speed. It is
the rule that you must understand everything in the repo, plus the daily documentation duty
(`ROADMAP`, `ARCHITECTURE`, `DECISIONS`, `LEARNING`, journal). That is realistically **1 hour per
day** of genuine work that the plan does not budget for. Over six days it is a full day.

Day-by-day risk:

| Day | Task | Slip risk | Why |
|---|---|---|---|
| 1 | Data + 5 tools + tests | **Medium-high** | Real wearable data cleaning always overruns: missing days, non-wear, duplicate rows, users with no sleep or no heart rate, and a possibly-one-month window. Five tools *and* their tests *and* the cleaning in one day is tight. |
| 2 | LLM + function calling in terminal | Low | The best-understood part. The tool-use loop is small. |
| 3 | Web UI + charts | Medium | Charts are where "just one more tweak" lives. Timebox it. |
| 4 | Docker + deploy + CI | **Highest** | All the unknowns live here, and it now contains an unplanned decision (which host) and possibly a payment. Docker build on 2 vCPU, secrets wiring, port rules, cold starts, sleeping Spaces. "Live link by end of day" is the most likely promise to break. |
| 5 | 30-question evaluation | **Highest** | The most underestimated item in the brief — see below. |
| 6 | Zepp + MCP + README | **High as written** | Three unrelated things on one day, one of which (Zepp) has no verified spec. |

**Why day 5 is as risky as day 4.** Writing 30 questions takes an hour. The hard parts are not
in the plan: deciding what counts as a correct *free-text* answer, writing a grader you trust,
and producing a defensible number. "Hallucination rate" in particular has no agreed definition —
if the README reports one without saying exactly how it was measured, a careful reader discounts
the whole results table. Define it operationally or drop the term.

**Most likely to slip: day 4, with day 5 immediately behind it.** The brief's single day-7 buffer
covers one of them, not both.

### Revised plan (8 working days)

| Day | Work | Done when |
|---|---|---|
| 0 | Decisions only: host, model, cut Zepp, cut RAG-as-RAG, eval contract. Write them into `DECISIONS.md`. | Five decisions logged. No code. |
| 1 | Load data. Print the coverage table (rows, users, date range, users per data type, missing days). Write the data-reality section of the README *first*. | You can state, with numbers, what the demo data can and cannot answer. |
| 2 | 3 tools + tests (weekly summary, compare periods, missing-data report). Only 3. | `pytest` green; you can explain every number. |
| 3 | 2 more tools + tests (most-active day, correlation with n and a confidence interval). | `pytest` green. |
| 4 | Tool-use loop in the terminal. Step cap, spend guard, trace log. | You can ask 5 questions from a shell and read the trace. |
| 5 | Web UI, charts, the "how this answer was computed" panel. | Runs locally; the trace panel is the feature you demo. |
| 6 | Docker, CI, deploy. Nothing else. | Public link works; CI badge green. |
| 7 | Evaluation. 15 questions, explicit grading contract, results table in the README with date and model id. | A sceptic can re-run `make eval` and get your numbers. |
| 8 | MCP server over the existing tool package, CSV upload + template, README polish, honest "Limits" and three real failure examples. | Done. |

Same scope minus Zepp and minus RAG, plus the two days the original plan was short.

---

## 3. Top risks and mitigations

| # | Risk | Mitigation |
|---|---|---|
| 1 | **Deploy host assumption is already broken** (HF Docker now needs a paid plan). | Decide on day 0. Keep the Dockerfile host-agnostic. $9/mo PRO is the lowest-friction path; Streamlit Community Cloud is the $0 path. |
| 2 | **Zepp export has no documented format**; day 6 becomes reverse engineering. | Cut it. Ship a documented CSV schema with a downloadable template and a validator. |
| 3 | **Demo data is thinner than assumed** (sleep and heart rate on subsets of users, possibly ~31 days). | Coverage table on day 1, before any tool is written. Derive the tool list and the question set from the real coverage. Put the numbers in "Limits". |
| 4 | **Public endpoint + your API key = cost and abuse exposure.** | Console spend limit (the real guard), hard step cap per question, modest `max_tokens`, global daily counter, Haiku 5.5 by default, typed tool arguments only. Handle the 429 with no `retry-after` explicitly. |
| 5 | **Evaluation slips or produces numbers you cannot defend.** | Freeze the grading contract on day 0. Start at 15 questions. Define each metric in one sentence in the README, next to the number. |
| 6 | **Health-advice tone and liability.** | Wellness-only system prompt, an explicit refusal path for diagnosis questions, and 2–3 eval questions that check the refusal fires. This is a CV asset, not just a risk — reviewers notice safe handling of health data. |
| 7 | **Agent nondeterminism makes CI flaky.** | Tools get deterministic pytest tests and run in CI. The agent is evaluated by `make eval` run manually, not in CI — live LLM calls in CI are flaky and cost money on every push. Say this in the README. |
| 8 | **Dataset licence mislabelled** (CC0 on Kaggle vs CC BY 4.0 at source). | Attribute Furberg et al., cite the Zenodo DOI, treat as CC BY 4.0. One sentence; log it in `DECISIONS.md`. |
| 9 | **Correlation claims overreach** with n ≈ 31. | The tool returns n and a confidence interval; the system prompt forbids causal language; one eval question checks that a weak correlation is reported as weak. |
| 10 | **Model ids and prices change.** | Model id in an env var, never hardcoded. The README states the model and the date the numbers were measured. |

---

## 4. Gaps and excess

### Missing, and a hiring manager will look for it
- **A reproducible eval artifact.** `eval/questions.yaml` + `make eval` + a results table carrying
  the date and the model id. Numbers a reader cannot reproduce are decoration.
- **Defined metrics.** One sentence per metric, beside the number. Suggested definitions:
  *tool-selection accuracy* = expected tool name and arguments matched exactly;
  *numeric accuracy* = reported value within a stated tolerance of the code-computed truth;
  *unsupported-claim rate* = claims in the answer not traceable to a tool result, graded by a
  written rubric on a stated sample size (say who or what graded it).
- **Graceful failure.** What the app says for "no data in that period", "only 4 of 7 nights
  recorded", "this user has no heart rate". Grounded refusal is the most convincing single
  behaviour in this project. Design it; do not discover it in the demo.
- **A "why tools, not text-to-SQL" paragraph.** You will be asked. Answer it in the README.
- **Latency numbers** (p50 and p90 seconds per question). Cheap to measure, and as a model
  compression person you will be expected to have measured something.
- **Pinned dependencies** and a documented `make run` / `make test` / `make eval`.

### Cut or shrink
- **Zepp upload** → documented CSV upload. (§1.2)
- **RAG** → curated cited `get_guideline` tool. (§1.5)
- **"30 questions"** → 15. The number is arbitrary; the grading contract is what carries weight.
  15 questions with an honest grader beat 30 with a vague one, and you can grow the set later.
- **MCP server** — keep it, it genuinely continues `mcp-har-benchmark`, but it is only cheap if
  the tool layer is a clean importable package from day 1. Design for that on day 1; build the
  server last. If the tools end up tangled with the UI, this becomes a full day.
- **Five tools on day 1** → three, then two. Nothing about "5" is load-bearing.

---

## 5. CV value

The five claims hold, with one weak spot.

1. **Time-series analysis on wearable data** — the strongest part, and the part most people
   applying for these roles cannot do. Lead the README with it. The correlation tool reporting
   n and a confidence interval, and refusing to imply causation, is where your PhD shows.
2. **LLM agent with function calling** — covered. The differentiator is not that it calls tools,
   it is the visible trace plus the step cap. Make the trace panel a screenshot in the README.
3. **Evaluation** — intended as the centrepiece, currently the least specified part of the brief.
   Fix the definitions and this becomes the reason someone calls you. Leave it vague and it
   becomes the reason they do not.
4. **Production basics** — covered once the host is settled. Dockerfile, CI badge, pinned deps,
   secrets never in the repo, a spend limit you can describe.
5. **MCP server** — covered. Link `mcp-har-benchmark` explicitly and say in one line what this
   repo's tool layer adds (curated fields, docstrings carrying valid values, units, and which
   direction is better).

**The highest-return change that does not grow the project:** one honest number a sceptic can
reproduce, plus a "where it fails" section with three real failure examples and your reading of
why. In your existing README style ("What was found" / "Limits" / "Reproducing") that is three
short paragraphs, and it is worth more than any additional feature.

---

## 6. Recommendation

**Change, then go.** Five decisions before day 1, four of which are yours because they cost money
or scope:

1. **Host.** HF PRO at $9/month (keeps Docker, keeps the HF audience) or Streamlit Community
   Cloud at $0. My recommendation: pay the $9 — but it is your money.
2. **Model.** Claude Haiku 5.5 (`claude-haiku-5-5`) as the default, roughly $0.002 per question.
   Model id in an env var.
3. **Drop Zepp**, ship a documented CSV schema with a template and a validator instead.
4. **Drop RAG**, ship a curated cited `get_guideline` tool, and do not call it RAG.
5. **Replan to 8 days**, with evaluation and deployment each getting a day of their own.

Then day 1 starts with the coverage table, not with tools.

---

## 7. Assumptions I could not verify

Listed honestly, worst first.

1. **The Kaggle copy's contents.** File list, per-file unique user counts, and actual date range
   are unconfirmed. The widely repeated "33 activity / 24 sleep / 14 heart rate" figures have no
   authoritative source I could find, and search results contradicted them. **Check by loading
   the files on day 1.**
2. **Whether the Kaggle copy covers one month or two.** The Zenodo title says 03.12.2016–
   05.12.2016; the file names suggest two windows. The popular Kaggle upload may contain only
   one. This decides whether month-over-month questions are possible at all.
3. **Zepp export, in every respect.** Whether a built-in export exists, in what format, with what
   fields. Sources directly contradict each other. Nothing in the plan should depend on it.
4. **HF Spaces free-tier wording may keep moving.** The paid-plan requirement is quoted from the
   official docs as of today, but one third-party report claimed a CPU price rise and a
   2,000 CPU-hour monthly free allowance from 1 June 2026 with no corroboration — I discounted
   it. Re-read the official page on the day you deploy.
5. **Anthropic free credits for a new account** — not documented either way in what I read. Assume
   none and set a spend limit.
6. **Your actual starting rate limits.** New organizations may begin in an Evaluation tier below
   the published Start-tier numbers. Read your own figures at `platform.claude.com/usage/limits`.
7. **Gemini free-tier quotas.** Third-party figures ranged from ~20 to ~1,500 requests/day and
   disagreed on which models are free at all; one source says Google no longer publishes per-model
   free-tier numbers. Only your own AI Studio console is trustworthy here.
8. **Voyage AI free allotment** (reported as a one-time 200M tokens for current models, not
   recurring, not covering the Batch API) — from third-party aggregators. Only matters if you
   overrule the RAG recommendation.
9. **Streamlit Community Cloud resource limits.** Reported RAM figures ranged from ~1 GB to
   ~2.7 GB across sources, one explicitly citing 2024 data. The 12-hour idle sleep was consistent.
10. **CDC content reuse terms.** The recommendations and their cited sources are verified from the
    CDC page itself; the page shows no explicit licence statement, and I did not read its Web
    Policies. US federal works are generally not under US copyright — I am not a lawyer, and this
    is not legal advice.
11. **My per-question cost estimate** rests on assumed token counts (~3K in, ~500 out, 3 calls per
    question). The prices are current; the token counts are a guess until you measure them. Log
    real `usage` figures from day 4 and replace my estimate with yours.

---

## Sources

- Zenodo 53894, Furberg, Brinton, Keating & Ortiz, *Crowd-sourced Fitbit datasets
  03.12.2016–05.12.2016* — https://zenodo.org/records/53894
- Kaggle, *FitBit Fitness Tracker Data* — https://www.kaggle.com/datasets/arashnic/fitbit
- Hugging Face Hub docs, *Spaces Overview* —
  https://huggingface.co/docs/hub/en/spaces-overview
- Hugging Face Hub docs, *Spaces ZeroGPU* —
  https://huggingface.co/docs/hub/en/spaces-zerogpu
- Hugging Face pricing — https://huggingface.co/pricing
- Claude docs, *Rate limits* — https://platform.claude.com/docs/en/api/rate-limits
- Claude docs, *Embeddings* — https://platform.claude.com/docs/en/build-with-claude/embeddings
- CDC, *About Sleep* — https://www.cdc.gov/sleep/about/index.html
- WHO, *Guidelines on physical activity and sedentary behaviour* (CC BY-NC-SA 3.0 IGO) —
  https://iris.who.int/items/2abc9ed0-2a55-4a07-a65f-ab4b7c412ecc
- Zepp export guide (third party, March 2026) —
  https://zeppdashboard.sarmkadan.com/guide/export-amazfit-data
- Render, *Deploy for Free* — https://render.com/docs/free
