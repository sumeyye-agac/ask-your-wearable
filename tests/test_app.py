"""The Streamlit page, run headless with streamlit.testing. No request reaches the API:
wearable.agent.ask is replaced by a stub in every test that gets that far."""

from pathlib import Path

import anthropic
import httpx2
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import wearable.agent
from wearable.agent import AgentResult, ToolCall
from wearable.guidelines import get_guideline

APP = str(Path(__file__).resolve().parents[1] / "streamlit_app.py")


@pytest.fixture(autouse=True)
def fresh_app(monkeypatch):
    # A set but empty key stops load_dotenv from reading a real key out of .env.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    st.cache_data.clear()
    st.cache_resource.clear()
    yield
    st.cache_resource.clear()


def run_example(at: AppTest, index: int = 0) -> AppTest:
    at.button(key=f"example_{index}").click().run()
    return at


def stub_ask(monkeypatch, result=None, error=None):
    def fake(client, df, question, **kwargs):
        if error is not None:
            raise error
        result.question = question
        return result
    monkeypatch.setattr(wearable.agent, "ask", fake)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-used")


def test_page_renders_with_users_examples_and_notes():
    at = AppTest.from_file(APP).run()
    assert not at.exception
    assert len(at.selectbox[0].options) == 3
    assert len([b for b in at.button if b.key and b.key.startswith("example_")]) == 5
    assert "not medical advice" in at.info[0].value
    assert any("zenodo.53894" in c.value and "CC BY 4.0" in c.value for c in at.caption)


def test_missing_api_key_gives_a_message_not_a_crash():
    at = run_example(AppTest.from_file(APP).run())
    assert not at.exception
    assert "no API key" in at.error[0].value


def test_answer_chart_trace_and_cdc_credit(monkeypatch):
    guideline = get_guideline("sleep_duration")
    summary = {"metric": "minutes_asleep", "start": "2016-05-05", "end": "2016-05-11",
               "daily": [{"date": f"2016-05-{d:02d}", "value": 450.0} for d in range(5, 12)]}
    result = AgentResult(question="", answer="You slept about 7 h 30 min a night.",
                         status="answered", model="claude-haiku-5-5", steps=3,
                         tool_calls=[ToolCall(1, "get_guideline", {"topic": "sleep_duration"},
                                              guideline, False),
                                     ToolCall(2, "weekly_summary", {"metric": "minutes_asleep"},
                                              summary, False)],
                         input_tokens=9000, output_tokens=300, cost_usd=0.0012)
    stub_ask(monkeypatch, result)
    at = run_example(AppTest.from_file(APP).run(), 4)
    assert not at.exception
    assert at.text_input(key="question").value == "Is my sleep enough?"
    assert any("7 h 30 min" in m.value for m in at.markdown)
    assert any(c.value == guideline["credit"] for c in at.caption)
    assert any("Hours asleep per day" in c.value for c in at.caption)
    assert at.expander[0].label == "How this answer was computed"
    assert len(at.json) == 2
    assert "Questions left today: 9 of 10" in " ".join(c.value for c in at.caption)


def test_no_credit_line_without_guideline(monkeypatch):
    result = AgentResult(question="", answer="Thursday.", status="answered",
                         model="claude-haiku-5-5", steps=1)
    stub_ask(monkeypatch, result)
    at = run_example(AppTest.from_file(APP).run(), 1)
    assert not any(c.value.startswith("Source: CDC") for c in at.caption)


def test_out_of_credit_is_a_friendly_message(monkeypatch):
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx2.Response(402, request=request)
    body = {"type": "error", "error": {"type": "billing_error",
                                       "message": "Your credit balance is too low."}}
    stub_ask(monkeypatch, error=anthropic.APIStatusError("credit", response=response, body=body))
    at = run_example(AppTest.from_file(APP).run())
    assert not at.exception
    assert "run out of credit" in at.error[0].value
    # A failed question does not count against the visitor.
    assert "Questions left today: 10 of 10" in " ".join(c.value for c in at.caption)


def test_network_failure_is_a_friendly_message(monkeypatch):
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    stub_ask(monkeypatch, error=anthropic.APIConnectionError(request=request))
    at = run_example(AppTest.from_file(APP).run())
    assert not at.exception
    assert "could not be reached" in at.error[0].value


def test_step_cap_shows_a_warning_not_an_answer(monkeypatch):
    result = AgentResult(question="", answer=None, status="step_cap",
                         model="claude-haiku-5-5", steps=6)
    stub_ask(monkeypatch, result)
    at = run_example(AppTest.from_file(APP).run())
    assert "more steps than the app allows" in at.warning[0].value


def test_question_limit_per_visitor(monkeypatch):
    result = AgentResult(question="", answer="Fine.", status="answered",
                         model="claude-haiku-5-5", steps=1)
    stub_ask(monkeypatch, result)
    at = AppTest.from_file(APP).run()
    for _ in range(10):
        at.button(key="example_0").click().run()
    assert not at.error
    at.button(key="example_0").click().run()
    assert "limit per visitor" in at.error[0].value
