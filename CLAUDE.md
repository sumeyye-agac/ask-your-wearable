# CLAUDE.md

Guidance for Claude Code and other contributors working in this repository.

## Project

Ask Your Wearable is a web app for asking natural-language questions about daily wearable
data (sleep, activity, heart rate). An LLM agent decides which tools to call; every number in
an answer comes from deterministic, tested Python functions, and the model only phrases the
result. Demo data comes from a public Fitbit dataset (Zenodo, CC BY 4.0).

| Path | Contents |
| --- | --- |
| `src/wearable/` | Tool functions, schema, agent loop, presentation helpers |
| `streamlit_app.py` | The web app |
| `scripts/` | Data building and command-line entry points |
| `data/demo/` | Demo data shipped with the app |
| `tests/` | pytest suite |
| `docs/` | Methods, data and deployment |

Key documents: `docs/METHODS.md` (how a day is counted, validations, tools, limits),
`docs/DATA.md` (dataset and coverage), `docs/DEPLOY.md` (hosting, usage limits, Docker, CI).

## Commands

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt     # app, tests and the wearable package
.venv/bin/python -m pytest                        # run all tests (no API key needed)
.venv/bin/streamlit run streamlit_app.py          # http://localhost:8501
.venv/bin/python scripts/ask.py --user 6962181067 "How was my sleep this week?"
```

The app and `scripts/ask.py` need `ANTHROPIC_API_KEY` in a git-ignored `.env` file in the repo root.

## Working principles

- **Verify external facts.** Check current documentation before relying on any library, API,
  dataset or service, and state clearly when something is unverified.
- **Report failures honestly.** Never hardcode outputs or fake results. Call out workarounds
  and guesses as such.
- **Stay within scope.** Raise new features or changes of direction with the maintainer before
  building them.
- **Confirm before irreversible or outward-facing actions:** pushing, deploying, deleting,
  changing scope or incurring cost.
- **Work incrementally.** Each change should run and pass its tests before the next one starts.

## Code standards

- Python 3.11+, type hints throughout, small focused functions.
- Every tool function is deterministic and covered by pytest tests.
- Tool docstrings are precise: valid values, units, and which direction is better.
- `tests/test_app_text.py` checks figures quoted in `README.md` and `docs/*.md` against the
  data. Update the docs together with any change that moves those figures.

## Documentation

- English throughout: code, comments, docs and commit messages.
- README style: plain sentences, real numbers, no hype. Sections follow the pattern
  "What it does", "What was found", "Limits", "Run it".

## Git

- Small, focused commits.
- Commit messages are plain English sentences that say what changed and why. No
  conventional-commit prefixes, no emoji. Keep the subject under about 70 characters and add a
  body only when the reason is not obvious.
  - Good: `Handle days with missing heart rate instead of dropping the whole week`
  - Avoid: `feat(tools): impl sleep_summary`, `updates`
- Commits made with Claude Code's help carry a co-author trailer:
  `Co-Authored-By: Claude <noreply@anthropic.com>`
- Never push, force-push, rewrite history or delete branches without the maintainer's approval.
- Never commit secrets, API keys, `.env` files or personal health data. Private data belongs in
  the git-ignored `data/private/` folder.

## Related work

- [`sumeyye-agac/mcp-har-benchmark`](https://github.com/sumeyye-agac/mcp-har-benchmark): an MCP
  server over a HAR leaderboard with an ablation on tool descriptions. The tool layer here
  builds on its findings.
