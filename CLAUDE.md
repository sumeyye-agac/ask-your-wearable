# Project: Ask Your Wearable

All work in this repo is in English: code, comments, docs, commits, and chat replies.

## Current phase
The plan in `docs/PROJECT_BRIEF.md` is **approved** (2026-11-11). Day 1 has not started.
`docs/REVIEW.md` is the record of why the plan looks the way it does — don't reopen settled
decisions without a reason.

## What we are building
A deployed web app where anyone can ask natural-language questions about wearable data
(sleep, activity, heart rate) and get grounded answers. The LLM calls deterministic, tested
Python tools and only turns their results into plain language. Sample data is built in; users
can upload their own CSV matching a documented schema. Scope, stack and the 8-day plan are in
`docs/PROJECT_BRIEF.md`.

## How to work with me
I am an ML engineer (PhD in wearable sensing and model compression).

- **Verify, don't assume.** For any library, API, dataset or service, check current documentation
  on the web before using it. Say clearly when something is unverified.
- **Don't hide failures.** If something is broken, a workaround, or a guess, say so.
  Never fake results or hardcode outputs to make a demo look like it works.
- **Ask before big or hard-to-undo steps** — scope, cost, deleting things, anything outward-facing.
- **Protect the scope.** If a task grows beyond the approved plan, stop and tell me.
- **Work in small steps.** Make each piece run and pass its tests before starting the next.

## Logging
One file: `docs/LOG.md`. At the end of each session, append:

```
### YYYY-MM-DD
- What was done (2-5 bullets)
- How to run / check it (one line)
- Open issues
```

Newest entry at the bottom. No other documentation duty.

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


