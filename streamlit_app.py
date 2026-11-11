"""Ask Your Wearable: the web app.

    streamlit run streamlit_app.py

Each question is answered on its own by the tool-use loop in wearable.agent, on one demo
user's daily table. The API key ANTHROPIC_API_KEY comes from Streamlit secrets when the app
is deployed and from the environment or a .env file in the repo root locally; the model id
WEARABLE_MODEL is looked up the same way. The key is never printed or logged. Every
question's trace is appended to logs/trace.jsonl (git-ignored), or to the file named by
WEARABLE_TRACE.
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

REPO = Path(__file__).resolve().parent
# Streamlit Community Cloud installs requirements.txt but not this repo's own package, so
# src/ is put on the import path here. Harmless where the package is installed.
sys.path.insert(0, str(REPO / "src"))

from wearable.agent import (ANSWERED, DEFAULT_MODEL, AgentResult, append_trace, ask,
                            result_from_record)
from wearable.app_text import (ABOUT_DATA, AUTHOR, DATASET_CREDIT, HEADLINE, LIMITS, PIPELINE,
                               PIPELINE_DOT, RAW_SAMPLE_NOTE, RAW_TABLES, STEPS, SUBLINE)
from wearable.presentation import (NOT_CONFIGURED, STATUS_MESSAGES, ChartSpec, UsageLimiter,
                                   ACCENT, METRIC_ICONS, api_error_message, chart_for,
                                   chart_heading, credits, headline_numbers, person_card,
                                   person_names, to_altair, visitor_key)
from wearable.schema import to_daily_frame

DEMO = REPO / "data/demo/demo_daily.csv"
RAW_SAMPLE = REPO / "data/demo/raw_sample"
LOGO = REPO / "assets/logo.svg"
STYLE = REPO / "assets/style.css"                 # the whole visual system, in one file
EXAMPLE = REPO / "data/demo/example_answer.json"  # one real run, copied from logs/trace.jsonl
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


@st.cache_data
def load_example() -> tuple[AgentResult, str]:
    """The saved run shown before the first question, and the user id it was asked about."""
    record = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    return result_from_record(record), record["user_id"]


@st.cache_resource
def limiter() -> UsageLimiter:
    """One limiter shared by every session in this app process."""
    return UsageLimiter(per_visitor=QUESTIONS_PER_VISITOR, daily_usd=APP_DAILY_USD)


def setting(name: str) -> str | None:
    """A configuration value: Streamlit secrets first (the deployed app), then the
    environment, which locally includes the repo's .env file. None if unset or empty."""
    try:
        if name in st.secrets:
            return str(st.secrets[name]) or None
    except FileNotFoundError:  # no secrets.toml, the normal case on a developer's machine
        pass
    load_dotenv(REPO / ".env")
    return os.environ.get(name) or None


@st.cache_resource
def client() -> anthropic.Anthropic | None:
    key = setting("ANTHROPIC_API_KEY")
    return anthropic.Anthropic(api_key=key) if key else None


def visitor_id() -> str:
    """Who this question is counted against; the rule is in presentation.visitor_key.

    None of the sources is proof of identity (headers can be forged, a session ends on
    reload), so this guards against casual overuse. The app-wide daily budget is what
    protects the API credit.
    """
    if "session_id" not in st.session_state:
        st.session_state.session_id = uuid.uuid4().hex
    forwarded = st.context.headers.get_all("X-Forwarded-For")
    visitor = visitor_key(st.context.ip_address, ",".join(forwarded),
                          st.session_state.session_id)
    if not st.session_state.get("visitor_kind_logged"):
        # Only the kind of source, never the address: enough to see in the host's logs
        # how visitors are being told apart.
        print(f"Visitor identified by: {visitor.split(':', 1)[0]}", file=sys.stderr)
        st.session_state.visitor_kind_logged = True
    return visitor


def answer(question: str, user_id: str, df: pd.DataFrame) -> None:
    """Run one question and store the outcome in session state for display."""
    st.session_state.outcome = None
    st.session_state.asked = True   # from here on the example answer stays hidden
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
    model = setting("WEARABLE_MODEL") or DEFAULT_MODEL
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


def label(text: str, kind: str = "") -> None:
    """A small uppercase section label."""
    st.markdown(f'<div class="ayw-label {kind}">{text}</div>', unsafe_allow_html=True)


def show_result(result: AgentResult, df: pd.DataFrame, user_id: str, name: str) -> None:
    """Headline numbers, the explanation, the chart and the trace, in that order."""
    answered = result.status == ANSWERED and bool(result.answer)
    if answered:
        # Read from the tool results, never from the model's text.
        numbers = headline_numbers(result.tool_calls, result.question)
        for column, number in zip(st.columns(len(numbers)) if numbers else [], numbers):
            column.metric(number.label, number.value)
        # "$" would start LaTeX in Streamlit markdown.
        st.markdown(result.answer.replace("$", "\\$"))
    else:
        st.warning(STATUS_MESSAGES.get(result.status, STATUS_MESSAGES["truncated"]))

    if result.status == ANSWERED:
        spec = chart_for(result.tool_calls, df, result.question)
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


def show_question(question: str) -> None:
    with st.container(key="asked_question"):
        st.markdown(escape_markdown(question))


def show_example(users: dict[str, pd.DataFrame], names: dict[str, str]) -> None:
    """The payoff before the first question: a real saved answer with its chart and trace."""
    result, user_id = load_example()
    with st.container(key="card_example"):
        label(f"Example answer · {names[user_id]} · saved from a real run", "ayw-label-example")
        show_question(result.question)
        show_result(result, users[user_id], user_id, names[user_id])


def show_outcome(outcome: dict, df: pd.DataFrame, user_id: str, name: str) -> None:
    with st.container(key="card_answer"):
        label(f"Your question · {name}")
        show_question(outcome["question"])
        if "error" in outcome:
            st.error(outcome["error"])
        else:
            show_result(outcome["result"], df, user_id, name)


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
    """Three selectable cards; the Data tab reads the same value."""
    label("Whose data to ask about")
    user_id = st.pills("Person", sorted(users), default=sorted(users)[0], required=True,
                       format_func=lambda uid: person_card(names[uid], users[uid]),
                       key="person", label_visibility="collapsed", width="stretch")
    outcome = st.session_state.get("outcome")
    if outcome and outcome.get("user_id") not in (None, user_id):
        st.session_state.outcome = None  # an answer about another person would mislead
    return user_id


def question_box() -> None:
    """The focal point: headline, the question bar with Ask inside it, examples, the note."""
    # A div with a heading role: Streamlit would add an anchor link to a real <h1>.
    st.markdown(f'<div class="ayw-hero"><div class="ayw-headline" role="heading" '
                f'aria-level="1">{HEADLINE.replace(". ", ".<br>", 1)}</div>'
                f'<p>{SUBLINE}</p></div>', unsafe_allow_html=True)
    # The box is emptied after every submit; the question answered is shown above the answer.
    with st.form("ask", border=False):
        with st.container(key="askbar", horizontal=True, wrap=False, gap="small",
                          vertical_alignment="center"):
            st.text_input("Your question", key="question", max_chars=MAX_QUESTION_CHARS,
                          label_visibility="collapsed",
                          placeholder="Ask about sleep, steps, activity or heart rate")
            st.form_submit_button("Ask", on_click=use_typed, type="primary", key="ask_button",
                                  icon=":material/arrow_forward:", icon_position="right")
    st.pills("Try an example", EXAMPLES, key="example", on_change=use_example,
             label_visibility="collapsed",
             format_func=lambda q: f":material/{METRIC_ICONS[EXAMPLE_METRIC[q]]}: {q}")
    st.markdown(f'<p class="ayw-note">{WELLNESS_NOTE}</p>', unsafe_allow_html=True)


def open_how_it_works() -> None:
    st.session_state.tab = "How it works"


def steps_strip() -> None:
    """How it works in three steps, with the way to the full explanation."""
    with st.container(key="card_steps"):
        label("How it works")
        items = "".join(
            f'<div class="ayw-step"><span class="ayw-step-icon" aria-hidden="true" translate="no">'
            f'{icon}</span><div><strong>{i}. {title}</strong><p>{text}</p></div></div>'
            for i, (icon, title, text) in enumerate(STEPS, start=1))
        st.markdown(f'<div class="ayw-steps">{items}</div>', unsafe_allow_html=True)
        st.button("See the full pipeline, with its checks and limits", key="to_how",
                  on_click=open_how_it_works, type="tertiary",
                  icon=":material/arrow_forward:", icon_position="right")


def ask_tab(users: dict[str, pd.DataFrame], names: dict[str, str]) -> str:
    """The Ask tab, drawn top to bottom: question box, person cards, answer area, steps.

    The person picker runs first because the answer needs its value, but it is placed
    under the question box so the page explains itself before asking for a choice.
    """
    box, people, answer_area = st.container(key="hero"), st.container(), st.container()
    with people:
        user_id = pick_person(users, names)
    with box:
        question_box()
    name, df = names[user_id], users[user_id]

    with answer_area:
        # Exactly one question per Ask: the box's text at that moment, then the box is emptied.
        question = (st.session_state.pop("pending", None) or "").strip()
        if question:
            answer(question, user_id, df)
        outcome = st.session_state.get("outcome")
        if outcome:
            show_outcome(outcome, df, user_id, name)
        elif not st.session_state.get("asked"):
            show_example(users, names)

    steps_strip()
    left = limiter().remaining(visitor_id())
    st.caption(f"Questions left today: {left} of {QUESTIONS_PER_VISITOR}. Each question is "
               f"answered on its own; the app does not remember earlier questions.")
    return user_id


def how_tab() -> None:
    st.write("From the raw export to an answer, in five steps. The numbers below are the "
             "checks recorded while building the app.")
    st.graphviz_chart(PIPELINE_DOT)
    for i, step in enumerate(PIPELINE, start=1):
        with st.container(key=f"card_step_{i}"):
            st.subheader(step["title"])
            st.markdown(no_latex(step["text"]))
            st.markdown("**Key decisions and checks**\n\n" +
                        "\n".join(f"- {no_latex(d)}" for d in step["decisions"]))
    with st.container(key="card_limits"):
        st.subheader("Limits")
        st.markdown("\n".join(f"- {no_latex(item)}" for item in LIMITS))


def data_tab(user_id: str, name: str, df: pd.DataFrame) -> None:
    with st.container(key="card_about"):
        st.subheader("About the data")
        st.markdown(ABOUT_DATA)

    with st.container(key="card_daily"):
        st.subheader(f"Daily table: {name}")
        st.caption(f"Zenodo user id {user_id}. One row per day; an empty cell means no valid "
                   f"measurement that day. Click a column header to sort.")
        table = df.reset_index()
        table["date"] = table["date"].dt.strftime("%Y-%m-%d")
        st.dataframe(table, hide_index=True, key="daily_table")
        st.download_button("Download this table as CSV", table.to_csv(index=False).encode(),
                           file_name=f"daily_{user_id}.csv", mime="text/csv",
                           key="download_daily")

    with st.container(key="card_raw"):
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
    st.markdown(f"<style>{STYLE.read_text()}</style>", unsafe_allow_html=True)
    with st.container(key="brand"):
        st.markdown(f'<div class="ayw-brand">{LOGO.read_text()}<span>Ask Your Wearable</span>'
                    f'</div>', unsafe_allow_html=True)

    users = load_users()
    names = person_names(list(users))

    # The tabs keep their state so the "How it works" strip on the Ask tab can open its tab.
    ask, how, data = st.tabs(["Ask", "How it works", "Data"], key="tab", on_change="rerun")
    with ask:
        user_id = ask_tab(users, names)
    with how:
        how_tab()
    with data:
        data_tab(user_id, names[user_id], users[user_id])

    st.space("large")
    st.caption(AUTHOR)
    st.caption(DATASET_CREDIT)


main()
