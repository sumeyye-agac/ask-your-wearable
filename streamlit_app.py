"""Ask Your Wearable: the web app.

    streamlit run streamlit_app.py

Each question is answered on its own by the tool-use loop in wearable.agent, on one demo
user's daily table. The API key is read from ANTHROPIC_API_KEY (a .env file in the repo
root is loaded if present); the model id from WEARABLE_MODEL. Every question's trace is
appended to logs/trace.jsonl (git-ignored), or to the file named by WEARABLE_TRACE.
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
from wearable.app_text import (ABOUT_DATA, AUTHOR, DATASET_CREDIT, INTRO, LIMITS, PIPELINE,
                               PIPELINE_DOT, RAW_SAMPLE_NOTE, RAW_TABLES)
from wearable.presentation import (NOT_CONFIGURED, STATUS_MESSAGES, ChartSpec, UsageLimiter,
                                   ACCENT, METRIC_ICONS, api_error_message, chart_for,
                                   chart_heading, credits, person_names, person_profile,
                                   to_altair)
from wearable.schema import to_daily_frame

REPO = Path(__file__).resolve().parent
DEMO = REPO / "data/demo/demo_daily.csv"
RAW_SAMPLE = REPO / "data/demo/raw_sample"
LOGO = REPO / "assets/logo.svg"
TRACE = Path(os.environ.get("WEARABLE_TRACE", REPO / "logs/trace.jsonl"))

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
# The metric each example is mostly about, for its icon. The question itself stays plain text.
EXAMPLE_METRIC = {
    "How was my sleep this week?": "minutes_asleep",
    "Which day was I most active?": "steps",
    "Do I walk less on days after short sleep?": "steps",
    "Am I active enough?": "fairly_active_minutes",
    "Is my sleep enough?": "minutes_asleep",
}

ACCENT_TINT = "#E3F0EE"
# A faint pulse line drawn behind the right side of the header band.
_PULSE = ("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 260 60'>"
          "<polyline points='0,32 70,32 84,32 94,14 108,50 120,22 130,32 170,32 180,26 188,38 "
          "196,32 260,32' fill='none' stroke='%232A7F7A' stroke-opacity='0.22' stroke-width='3' "
          "stroke-linecap='round' stroke-linejoin='round'/></svg>")
STYLE = f"""
<style>
.ayw-header {{
  display: flex; align-items: center; gap: 16px; padding: 22px 26px; border-radius: 16px;
  background: {ACCENT_TINT} url("{_PULSE}") no-repeat right 22px center / 240px 56px;
}}
.ayw-header svg {{ width: 56px; height: 56px; flex: none; }}
.ayw-header h1 {{ margin: 0; padding: 0; font-size: 2.3rem; font-weight: 700;
                  letter-spacing: -0.01em; color: #1E2A2C; }}
/* Selected person: solid accent. !important because Streamlit sets the selected
   background with a more specific generated class. */
button[data-variant="segmented_control"][aria-checked="true"] {{
  background-color: {ACCENT} !important; border-color: {ACCENT} !important;
}}
button[data-variant="segmented_control"][aria-checked="true"] p {{ color: #FFFFFF !important; }}
@media (max-width: 640px) {{
  .ayw-header {{ background-image: none; padding: 16px 18px; }}
  .ayw-header h1 {{ font-size: 1.8rem; }}
  .ayw-header svg {{ width: 44px; height: 44px; }}
}}
/* Active tab: accent text and a firm underline. */
[data-testid="stTab"][aria-selected="true"] {{ box-shadow: inset 0 -3px 0 {ACCENT}; }}
[data-testid="stTab"][aria-selected="true"] p {{ color: {ACCENT}; font-weight: 600; }}
</style>
"""

WELLNESS_NOTE = ("General wellness information about sample data, not medical advice. "
                 "The app cannot diagnose anything; for health questions, ask a clinician.")


@st.cache_data
def load_users() -> dict[str, pd.DataFrame]:
    table = pd.read_csv(DEMO, dtype={"user_id": str})
    return {uid: to_daily_frame(rows.drop(columns="user_id"))
            for uid, rows in table.groupby("user_id")}


@st.cache_data
def load_raw_sample() -> dict[str, pd.DataFrame]:
    return {name: pd.read_csv(RAW_SAMPLE / f"{name}.csv.gz", dtype={"Id": str})
            for name in RAW_TABLES}


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
        st.session_state.outcome = {"error": refusal, "question": question}
        return
    api = client()
    if api is None:
        limiter().finish(visitor, 0.0, failed=True)
        st.session_state.outcome = {"error": NOT_CONFIGURED, "question": question}
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
                                                               getattr(err, "type", None)),
                                     "question": question}
        return
    except anthropic.APIConnectionError as err:  # includes timeouts
        limiter().finish(visitor, 0.0, failed=True)
        print(f"API connection error: {err}", file=sys.stderr)
        st.session_state.outcome = {"error": api_error_message(None, None),
                                     "question": question}
        return
    except Exception as err:  # never show a stack trace to a visitor
        limiter().finish(visitor, 0.0, failed=True)
        print(f"Unexpected error: {err!r}", file=sys.stderr)
        st.session_state.outcome = {"error": api_error_message(0, None),
                                     "question": question}
        return
    limiter().finish(visitor, result.cost_usd)
    try:
        append_trace(result, TRACE, user_id)
    except OSError as err:  # a read-only disk must not cost the visitor the answer
        print(f"Could not write the trace: {err}", file=sys.stderr)
    st.session_state.outcome = {"result": result, "user_id": user_id, "question": question}


def escape_markdown(text: str) -> str:
    """Show a visitor's text as typed, not as markdown, LaTeX or HTML."""
    for ch in "\\`*_{}[]<>()#+-.!|$~":
        text = text.replace(ch, "\\" + ch)
    return text


def show_chart(spec: ChartSpec) -> None:
    st.caption(chart_heading(spec))
    accent = st.get_option("theme.primaryColor") or ACCENT
    st.altair_chart(to_altair(spec, accent), width="stretch")


def show_result(result: AgentResult, df: pd.DataFrame, user_id: str, name: str) -> None:
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
        st.markdown(f"Data: {name}, Zenodo user id `{user_id}`.")
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


def use_example() -> None:
    # Put the clicked example into the box, replacing whatever was there, and clear the
    # pill so the same example can be picked again. Nothing is sent until Ask is pressed.
    picked = st.session_state.get("example")
    if picked:
        st.session_state.question = picked
    st.session_state.example = None


def use_typed() -> None:
    # Move the typed text into the same one-shot queue and empty the box, so the next
    # question starts from a blank box and nothing is sent twice.
    st.session_state.pending = st.session_state.get("question", "")
    st.session_state.question = ""


def no_latex(text: str) -> str:
    """Markdown treats a pair of "$" as LaTeX; prices must stay prices."""
    return text.replace("$", "\\$")


def pick_person(users: dict[str, pd.DataFrame], names: dict[str, str]) -> str:
    """One compact selection for the whole page; the Data tab reads the same value."""
    user_id = st.segmented_control("Person", sorted(users), default=sorted(users)[0],
                                   required=True, format_func=names.get, key="person",
                                   label_visibility="collapsed")
    st.caption(person_profile(users[user_id]))
    outcome = st.session_state.get("outcome")
    if outcome and outcome.get("user_id") not in (None, user_id):
        st.session_state.outcome = None  # an answer about another person would mislead
    return user_id


def ask_tab(user_id: str, name: str, df: pd.DataFrame) -> None:
    st.write(INTRO)
    st.caption(WELLNESS_NOTE)
    st.space("small")

    st.pills("Try an example", EXAMPLES, key="example", on_change=use_example,
             format_func=lambda q: f":material/{METRIC_ICONS[EXAMPLE_METRIC[q]]}: {q}")

    # The box is emptied after every submit; the question answered is shown above the answer.
    with st.form("ask", border=False):
        st.text_input("Your question", key="question", max_chars=MAX_QUESTION_CHARS,
                      placeholder="For example: How did my steps change over the two months?")
        st.form_submit_button("Ask", on_click=use_typed, type="primary")

    # Exactly one question per Ask: the box's text at that moment, then the box is emptied.
    question = (st.session_state.pop("pending", None) or "").strip()
    if question:
        answer(question, user_id, df)

    outcome = st.session_state.get("outcome")
    if outcome:
        st.space("small")
        st.markdown(f"**Question:** {escape_markdown(outcome['question'])}")
        if "error" in outcome:
            st.error(outcome["error"])
        else:
            show_result(outcome["result"], df, user_id, name)

    st.space("small")
    left = limiter().remaining(visitor_id())
    st.caption(f"Questions left today: {left} of {QUESTIONS_PER_VISITOR}. Each question is "
               f"answered on its own; the app does not remember earlier questions.")


def how_tab() -> None:
    st.write("From the raw export to an answer, in five steps. The numbers below are the "
             "checks recorded while building the app.")
    st.graphviz_chart(PIPELINE_DOT)
    for step in PIPELINE:
        st.subheader(step["title"])
        st.markdown(no_latex(step["text"]))
        st.markdown("**Key decisions and checks**\n\n" +
                    "\n".join(f"- {no_latex(d)}" for d in step["decisions"]))
    st.subheader("Limits")
    st.markdown("\n".join(f"- {no_latex(item)}" for item in LIMITS))


def data_tab(user_id: str, name: str, df: pd.DataFrame) -> None:
    st.subheader("About the data")
    st.markdown(ABOUT_DATA)

    st.subheader(f"Daily table: {name}")
    st.caption(f"Zenodo user id {user_id}. One row per day; an empty cell means no valid "
               f"measurement that day. Click a column header to sort.")
    table = df.reset_index()
    table["date"] = table["date"].dt.strftime("%Y-%m-%d")
    st.dataframe(table, hide_index=True, key="daily_table")
    st.download_button("Download this table as CSV", table.to_csv(index=False).encode(),
                       file_name=f"daily_{user_id}.csv", mime="text/csv", key="download_daily")

    st.subheader(f"Raw sample: {name}")
    st.caption(RAW_SAMPLE_NOTE)
    sample = load_raw_sample()
    tabs = st.tabs([label for label, _ in RAW_TABLES.values()])
    for tab, (table_name, (_, line)) in zip(tabs, RAW_TABLES.items()):
        with tab:
            rows = sample[table_name][sample[table_name]["Id"] == user_id]
            st.caption(f"`{table_name}`: {line} {len(rows):,} rows.")
            st.dataframe(rows, hide_index=True, key=f"raw_{table_name}")


def main() -> None:
    st.set_page_config(page_title="Ask Your Wearable", page_icon=str(LOGO), layout="centered")
    st.markdown(STYLE, unsafe_allow_html=True)
    st.markdown(f'<div class="ayw-header">{LOGO.read_text()}<h1>Ask Your Wearable</h1></div>',
                unsafe_allow_html=True)

    users = load_users()
    names = person_names(list(users))

    ask, how, data = st.tabs(["Ask", "How it works", "Data"])
    with ask:
        # The picker is drawn first, inside the Ask tab, and its value drives the whole page.
        user_id = pick_person(users, names)
        st.space("small")
        ask_tab(user_id, names[user_id], users[user_id])
    with how:
        how_tab()
    with data:
        data_tab(user_id, names[user_id], users[user_id])

    st.space("large")
    st.caption(AUTHOR)
    st.caption(DATASET_CREDIT)


main()
