# Project: Ask Your Wearable

All work in this repo is in English: code, comments, docs, commits, and chat replies.

## Current phase
The proposal is in `docs/PROJECT_BRIEF.md` and is **not approved yet**.
Until I approve a plan, do not write application code. Review, verify and plan only.

## What we are building (summary)
A deployed web app where anyone can ask natural-language questions about wearable data
(sleep, activity, heart rate) and get grounded answers. The LLM calls deterministic, tested
Python tools and only turns their results into plain language. Sample data is built in;
users can upload their own export. Details and open questions are in the brief.

## How to work with me
I am an ML engineer (PhD in wearable sensing and model compression). I must understand
everything that ends up in this repo. A working product I don't understand is a failure.

- **Plan before building.** Before any non-trivial step, explain what you will do and why,
  and wait for my OK. Use plan mode for anything touching several files.
- **Verify, don't assume.** For any library, API, dataset or service, check current
  documentation on the web before using it. Say clearly when something is unverified.
- **Small steps.** One feature at a time. Make it run, show me how to run it myself, then move on.
- **Explain new things.** When you introduce a library, API, pattern or concept,
  add a short plain explanation to `docs/LEARNING.md`.
- **Don't hide failures.** If something is broken, a workaround, or a guess, say so.
  Never fake results or hardcode outputs to make a demo look like it works.
- **Ask when a decision is mine** (scope, design trade-offs, cost, anything hard to undo).
- **Protect the scope.** If a task grows beyond the approved plan, stop and tell me.

## Documentation I must be able to read at the end of every day
These files are the single source of truth, not the chat. Short, structured, no filler.

- `docs/PROJECT_BRIEF.md`: the proposal and, once approved, the agreed scope.
- `docs/ROADMAP.md`: checklist of phases and tasks with status (todo / in progress / done).
- `docs/ARCHITECTURE.md`: a Mermaid diagram plus one paragraph per component
  (what it does, which file it lives in). Update it whenever the structure changes.
- `docs/DECISIONS.md`: numbered log. Each entry: date, question, options, choice, reason.
- `docs/journal/YYYY-MM-DD.md`: one file per working day (template below).
- `docs/LEARNING.md`: concepts and tools, each in 2-4 plain sentences, with where it is used.

### Daily journal template
```
# YYYY-MM-DD

## Summary (3 sentences max)
## What was done
- step, files touched, how to run/verify it
## Decisions made (link to DECISIONS.md entries)
## Problems hit and how they were solved
## What I should understand from today (key concepts, with LEARNING.md links)
## Open issues / next steps
```

## Related work of mine
- `sumeyye-agac/mcp-har-benchmark`: my MCP server over a HAR leaderboard, with an ablation on
  tool descriptions. The tool layer here continues that work: curated fields, precise
  docstrings (valid values, units, which direction is better).
- README style: follow my existing repos (e.g. `sumeyye-agac/chest-imu-cough-detection`):
  "What was found", honest "Limits", "Reproducing". Plain sentences, real numbers, no hype.

## Git rules (strict)
- Never add any AI attribution anywhere: no `Co-Authored-By` trailers, no
  "Generated with Claude Code" lines, nothing naming Claude in commits, PRs, code comments or docs.
  Commits are authored by my own git identity only.
- Small, focused commits.
- Commit messages are plain, clear English sentences, written the way a thoughtful
  engineer would write them: say what changed and why, not just a label.
  No prefixes like "feat:" or "fix:", no emoji, no jargon dumps. Keep the first line
  under ~70 characters; add a short body only when the "why" is not obvious.
  Good: "Add a weekly sleep summary and test it on the demo data"
  Good: "Handle days with missing heart rate instead of dropping the whole week"
  Bad:  "feat(tools): impl sleep_summary"   Bad: "updates"
- Never push, force-push, rewrite history or delete branches without asking me first.
- Never commit secrets, API keys, `.env` files or my personal health data.
  Personal data lives in a git-ignored `data/private/` folder.

## Code style
- Python 3.11+, type hints, small functions, a README section on how to run each part.
- Every tool function is deterministic and has pytest tests.
