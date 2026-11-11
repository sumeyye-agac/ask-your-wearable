"""Ask questions about a demo user's wearable data from the terminal.

    python scripts/ask.py --user 6962181067 "How was my sleep this week?"
    python scripts/ask.py --user 6962181067          # interactive; empty line to quit
    python scripts/ask.py --list-users

Each question is answered on its own; there is no memory between questions. The API key is
read from ANTHROPIC_API_KEY (a .env file in the repo root is loaded if present). Every
question's trace is appended to logs/trace.jsonl, which is git-ignored.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import anthropic
import pandas as pd
from dotenv import load_dotenv

from wearable.agent import ANSWERED, DEFAULT_MODEL, AgentResult, append_trace, ask
from wearable.schema import to_daily_frame

REPO = Path(__file__).resolve().parents[1]
DEMO = REPO / "data/demo/demo_daily.csv"
TRACE = REPO / "logs/trace.jsonl"
MAX_USD_PER_SESSION = 0.25

STATUS_TEXT = {
    "step_cap": "Stopped: the step cap was reached before the model gave an answer.",
    "spend_cap": "Stopped: the spend cap for one question was reached.",
    "refused": "The model declined to answer this request.",
    "truncated": "Stopped: the response was cut off before it was complete.",
}


def load_users(path: Path) -> dict[str, pd.DataFrame]:
    """Daily frame per user id from a CSV with a user_id column."""
    table = pd.read_csv(path, dtype={"user_id": str})
    return {uid: to_daily_frame(rows.drop(columns="user_id"))
            for uid, rows in table.groupby("user_id")}


def show(result: AgentResult) -> None:
    for call in result.tool_calls:
        print(f"  [step {call.step}] {call.name}({json.dumps(call.input)})")
        label = "error" if call.is_error else "result"
        print(f"      {label}: {json.dumps(call.output)}")
    print()
    print(result.answer if result.status == ANSWERED else STATUS_TEXT[result.status])
    print(f"\n  ({result.steps} model requests, {result.input_tokens} input + "
          f"{result.output_tokens} output tokens, about ${result.cost_usd:.4f})\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("questions", nargs="*", help="questions; none starts interactive mode")
    parser.add_argument("--user", help="demo user id (see --list-users)")
    parser.add_argument("--list-users", action="store_true")
    parser.add_argument("--data", type=Path, default=DEMO, help="CSV with a user_id column")
    args = parser.parse_args()

    users = load_users(args.data)
    if args.list_users or not args.user:
        for uid, df in users.items():
            print(f"{uid}: {df.index.min():%Y-%m-%d} to {df.index.max():%Y-%m-%d}")
        return 0 if args.list_users else 2
    if args.user not in users:
        print(f"Unknown user {args.user}. Valid users: {', '.join(users)}.", file=sys.stderr)
        return 2

    load_dotenv(REPO / ".env")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set (put it in .env or the environment).",
              file=sys.stderr)
        return 2
    model = os.environ.get("WEARABLE_MODEL", DEFAULT_MODEL)
    client = anthropic.Anthropic()

    def questions():
        if args.questions:
            yield from args.questions
            return
        while True:
            try:
                line = input("question> ").strip()
            except EOFError:
                return
            if not line:
                return
            yield line

    spent = 0.0
    for question in questions():
        if spent >= MAX_USD_PER_SESSION:
            print(f"Session spend cap of ${MAX_USD_PER_SESSION:.2f} reached; stopping.")
            return 1
        print(f"\nQ: {question}")
        try:
            result = ask(client, users[args.user], question, model=model)
        except anthropic.AuthenticationError:
            print("The API rejected the key in ANTHROPIC_API_KEY.", file=sys.stderr)
            return 1
        except anthropic.RateLimitError:
            print("Rate limited by the API; try again in a minute.", file=sys.stderr)
            return 1
        except anthropic.APIStatusError as err:
            print(f"API error {err.status_code}: {err.message}", file=sys.stderr)
            return 1
        except anthropic.APIConnectionError:
            print("Could not reach the API; check the network connection.", file=sys.stderr)
            return 1
        spent += result.cost_usd
        append_trace(result, TRACE, args.user)
        show(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
