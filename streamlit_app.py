"""Ask Your Wearable: the web app.

    streamlit run streamlit_app.py

Each question is answered on its own by the tool-use loop in wearable.agent, on one demo
user's daily table. The API key is read from ANTHROPIC_API_KEY (a .env file in the repo
root is loaded if present); the model id from WEARABLE_MODEL. Every question's trace is
appended to logs/trace.jsonl, which is git-ignored.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

import anthropic
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from wearable.agent import ANSWERED, DEFAULT_MODEL, AgentResult, append_trace, ask
from wearable.presentation import (NOT_CONFIGURED, STATUS_MESSAGES, ChartSpec, UsageLimiter,
                                   api_error_message, chart_for, credits, user_label)
from wearable.schema import to_daily_frame

REPO = Path(__file__).resolve().parent
DEMO = REPO / "data/demo/demo_daily.csv"
TRACE = REPO / "logs/trace.jsonl"

QUESTIONS_PER_VISITOR = 10    # per UTC day
APP_DAILY_USD = 1.00          # estimated spend per UTC day for the whole app (~500 questions)
MAX_QUESTION_CHARS = 300

EXAMPLES = [
    "How was my sleep this week?",
    "Which day was I most active?",
    "Do I walk less on days after short sleep?",
    "Am I active enough?",
    "Is my sleep enough?",
]

DATA_CREDIT = (
    "Demo data: Furberg, Brinton, Keating & Ortiz (RTI International), *Crowd-sourced Fitbit "
    "datasets 03.12.2016–05.12.2016*, Zenodo, 2016, "
    "[doi:10.5281/zenodo.53894](https://doi.org/10.5281/zenodo.53894), licensed "
    "[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The app uses a daily table "
    "derived from the minute- and hour-level exports of three users. Fitbit is a trademark of "
    "Google; this app is not affiliated with or endorsed by Fitbit, Google or the authors."
)
WELLNESS_NOTE = ("General wellness information about sample data, not medical advice. "
                 "The app cannot diagnose anything; for health questions, ask a clinician.")


@st.cache_data
def load_users() -> dict[str, pd.DataFrame]:
    table = pd.read_csv(DEMO, dtype={"user_id": str})
    return {uid: to_daily_frame(rows.drop(columns="user_id"))
            for uid, rows in table.groupby("user_id")}


@st.cache_resource
def limiter() -> UsageLimiter:
    """One limiter shared by every session in this app process."""
    return UsageLimiter(per_visitor=QUESTIONS_PER_VISITOR, daily_usd=APP_DAILY_USD)


@st.cache_resource
def client() -> anthropic.Anthropic | None:
    load_dotenv(REPO / ".env")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    return anthropic.Anthropic()


def visitor_id() -> str:
    """The visitor's IP address when Streamlit knows it, else this browser session.

    st.context.ip_address is None on localhost and can be spoofed, so this is a guard
    against casual overuse, not a security measure.
    """
    ip = st.context.ip_address
    if isinstance(ip, str) and ip:
        return f"ip:{ip}"
    if "session_id" not in st.session_state:
        st.session_state.session_id = uuid.uuid4().hex
    return f"session:{st.session_state.session_id}"


def answer(question: str, user_id: str, df: pd.DataFrame) -> None:
    """Run one question and store the outcome in session state for display."""
    st.session_state.outcome = None
    visitor = visitor_id()
    refusal = limiter().start(visitor)
    if refusal:
        st.session_state.outcome = {"error": refusal}
        return
    api = client()
    if api is None:
        limiter().finish(visitor, 0.0, failed=True)
        st.session_state.outcome = {"error": NOT_CONFIGURED}
        return
    model = os.environ.get("WEARABLE_MODEL", DEFAULT_MODEL)
    try:
        with st.spinner("Computing the answer..."):
            result = ask(api, df, question, model=model)
    except anthropic.APIStatusError as err:
        limiter().finish(visitor, 0.0, failed=True)
        print(f"API error {err.status_code} {getattr(err, 'type', None)}: {err.message}",
              file=sys.stderr)
        st.session_state.outcome = {"error": api_error_message(err.status_code,
                                                               getattr(err, "type", None))}
        return
    except anthropic.APIConnectionError as err:  # includes timeouts
        limiter().finish(visitor, 0.0, failed=True)
        print(f"API connection error: {err}", file=sys.stderr)
        st.session_state.outcome = {"error": api_error_message(None, None)}
        return
    except Exception as err:  # never show a stack trace to a visitor
        limiter().finish(visitor, 0.0, failed=True)
        print(f"Unexpected error: {err!r}", file=sys.stderr)
        st.session_state.outcome = {"error": api_error_message(0, None)}
        return
    limiter().finish(visitor, result.cost_usd)
    try:
        append_trace(result, TRACE, user_id)
    except OSError as err:  # a read-only disk must not cost the visitor the answer
        print(f"Could not write the trace: {err}", file=sys.stderr)
    st.session_state.outcome = {"result": result, "user_id": user_id}


def show_chart(spec: ChartSpec) -> None:
    st.caption(spec.title)
    if spec.kind == "scatter":
        st.scatter_chart(spec.data, x=spec.x, y=spec.y, x_label=spec.x_label,
                         y_label=spec.y_label)
    else:
        st.bar_chart(spec.data, x=spec.x, y=spec.y, x_label=spec.x_label,
                     y_label=spec.y_label)


def show_result(result: AgentResult, df: pd.DataFrame) -> None:
    if result.status == ANSWERED and result.answer:
        # "$" would start LaTeX in Streamlit markdown.
        st.markdown(result.answer.replace("$", "\\$"))
    else:
        st.warning(STATUS_MESSAGES.get(result.status, STATUS_MESSAGES["truncated"]))

    if result.status == ANSWERED:
        spec = chart_for(result.tool_calls, df)
        if spec is not None:
            show_chart(spec)
    for line in credits(result.tool_calls):
        st.caption(line)

    with st.expander("How this answer was computed"):
        if not result.tool_calls:
            st.write("The model answered without calling any tool, so the answer contains "
                     "no computed numbers.")
        for i, call in enumerate(result.tool_calls, start=1):
            st.markdown(f"**{i}. `{call.name}`** (model request {call.step})")
            st.code(json.dumps(call.input, indent=2), language="json")
            if call.is_error:
                st.markdown("Returned an error, which was passed back to the model:")
                st.code(str(call.output), language="text")
            else:
                st.markdown("Result:")
                st.json(call.output, expanded=False)
        st.caption(f"Model {result.model}, {result.steps} request(s), "
                   f"{result.input_tokens:,} input and {result.output_tokens:,} output tokens, "
                   f"about ${result.cost_usd:.4f}.")


def use_example(question: str) -> None:
    st.session_state.question = question
    st.session_state.submit = True


def main() -> None:
    st.set_page_config(page_title="Ask Your Wearable", layout="centered")
    st.title("Ask Your Wearable")
    st.write("Ask a question about a person's sleep, steps, activity or heart rate. The "
             "numbers come from tested Python functions; the language model only chooses "
             "which to call and puts their results into words.")
    st.info(WELLNESS_NOTE)

    users = load_users()
    user_id = st.selectbox("Whose data", list(users),
                           format_func=lambda uid: user_label(uid, users[uid]))
    df = users[user_id]
    if st.session_state.get("outcome", {}) and \
            st.session_state.outcome.get("user_id") not in (None, user_id):
        st.session_state.outcome = None  # an answer about another user would mislead

    st.write("Try an example:")
    columns = st.columns(2)
    for i, example in enumerate(EXAMPLES):
        columns[i % 2].button(example, key=f"example_{i}", on_click=use_example,
                              args=(example,), width="stretch")

    with st.form("ask", clear_on_submit=False):
        st.text_input("Your question", key="question", max_chars=MAX_QUESTION_CHARS,
                      placeholder="For example: How did my steps change over the two months?")
        submitted = st.form_submit_button("Ask")

    question = st.session_state.get("question", "").strip()
    if (submitted or st.session_state.pop("submit", False)) and question:
        answer(question, user_id, df)

    outcome = st.session_state.get("outcome")
    if outcome:
        if "error" in outcome:
            st.error(outcome["error"])
        else:
            show_result(outcome["result"], df)

    left = limiter().remaining(visitor_id())
    st.caption(f"Questions left today: {left} of {QUESTIONS_PER_VISITOR}. Each question is "
               f"answered on its own; the app does not remember earlier questions.")
    st.divider()
    st.caption(DATA_CREDIT)


main()
