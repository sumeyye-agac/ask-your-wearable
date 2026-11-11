"""The tool-use loop, driven by a scripted stand-in for the API client (no network)."""

import json
from types import SimpleNamespace as NS

import pytest

from wearable import agent
from wearable.registry import TOOL_FUNCTIONS, with_weekdays
from wearable.tools import weekly_summary


def usage(input_tokens=1000, output_tokens=100):
    return NS(input_tokens=input_tokens, output_tokens=output_tokens,
              cache_creation_input_tokens=0, cache_read_input_tokens=0)


def tool_use(name, arguments, id="t1"):
    return NS(type="tool_use", id=id, name=name, input=arguments)


def reply(*content, stop_reason="tool_use", **tokens):
    return NS(content=list(content), stop_reason=stop_reason, usage=usage(**tokens))


def final(text):
    return reply(NS(type="thinking", thinking=""), NS(type="text", text=text),
                 stop_reason="end_turn")


class FakeClient:
    """Returns scripted responses in order and records each request."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []
        self.messages = NS(create=self._create)

    def _create(self, **kwargs):
        # Copy the message list: the loop keeps appending to the one it passed in.
        self.requests.append({**kwargs, "messages": list(kwargs["messages"])})
        return self.responses.pop(0)


def test_tool_result_reaches_the_model_and_the_trace(two_weeks):
    client = FakeClient(reply(tool_use("weekly_summary", {"metric": "steps"})),
                        final("You averaged 11000 steps."))
    result = agent.ask(client, two_weeks, "How active was I this week?")

    # What the model sees is the tool's result with a weekday next to every date.
    expected = with_weekdays(weekly_summary(two_weeks, "steps"))
    assert result.status == agent.ANSWERED and result.answer == "You averaged 11000 steps."
    assert result.steps == 2
    call = result.tool_calls[0]
    assert (call.name, call.input, call.output, call.is_error) == \
        ("weekly_summary", {"metric": "steps"}, expected, False)
    sent = client.requests[1]["messages"][-1]["content"][0]
    assert sent["tool_use_id"] == "t1" and sent["is_error"] is False
    assert json.loads(sent["content"]) == expected


def test_request_carries_the_model_tools_and_data_range(two_weeks):
    client = FakeClient(final("ok"))
    agent.ask(client, two_weeks, "hi", model="claude-haiku-5-5")
    request = client.requests[0]
    assert request["model"] == "claude-haiku-5-5"
    assert [t["name"] for t in request["tools"]] == list(TOOL_FUNCTIONS)
    assert "2024-01-01 to 2024-01-14" in request["system"]
    assert "the last complete day, 2024-01-14 (Sunday)" in request["system"]
    assert "2024-01-08 to 2024-01-14" in request["system"]
    assert "not recorded in full" not in request["system"]
    assert request["messages"][0] == {"role": "user", "content": "hi"}


def test_tool_error_is_returned_to_the_model_not_raised(two_weeks):
    client = FakeClient(
        reply(tool_use("weekly_summary", {"metric": "steps", "end_date": "2030-01-01"})),
        final("There is no data for that week."))
    result = agent.ask(client, two_weeks, "Steps in January 2030?")
    assert result.status == agent.ANSWERED
    assert result.tool_calls[0].is_error is True
    sent = client.requests[1]["messages"][-1]["content"][0]
    assert sent["is_error"] is True and "data covers 2024-01-01 to 2024-01-14" in sent["content"]


def test_parallel_tool_calls_go_back_in_one_message(two_weeks):
    client = FakeClient(
        reply(tool_use("weekly_summary", {"metric": "steps"}, id="a"),
              tool_use("weekly_summary", {"metric": "minutes_asleep"}, id="b")),
        final("done"))
    result = agent.ask(client, two_weeks, "Steps and sleep this week?")
    results = client.requests[1]["messages"][-1]["content"]
    assert [r["tool_use_id"] for r in results] == ["a", "b"]
    assert [c.step for c in result.tool_calls] == [1, 1]


def test_step_cap_stops_the_loop_without_an_answer(two_weeks):
    client = FakeClient(*[reply(tool_use("missing_data_report", {})) for _ in range(5)])
    result = agent.ask(client, two_weeks, "loop forever", max_steps=3)
    assert result.status == agent.STEP_CAP and result.answer is None
    assert result.steps == 3 and len(client.requests) == 3


def test_spend_cap_stops_before_the_next_request(two_weeks):
    # 1,000,000 output tokens on Haiku 5.5 is $0.50, far above the cap.
    client = FakeClient(reply(tool_use("missing_data_report", {}), output_tokens=1_000_000),
                        final("never reached"))
    result = agent.ask(client, two_weeks, "expensive", max_usd=0.01)
    assert result.status == agent.SPEND_CAP and result.answer is None
    assert len(client.requests) == 1


@pytest.mark.parametrize("stop_reason, status", [("refusal", agent.REFUSED),
                                                 ("max_tokens", agent.TRUNCATED)])
def test_refusal_and_truncation_give_no_answer(two_weeks, stop_reason, status):
    client = FakeClient(reply(NS(type="text", text="partial"), stop_reason=stop_reason))
    result = agent.ask(client, two_weeks, "q")
    assert result.status == status and result.answer is None


def test_cost_uses_the_published_haiku_prices():
    # 10,000 input at $0.10/MTok + 2,000 output at $0.50/MTok = $0.001 + $0.001
    assert agent.request_cost(usage(10_000, 2_000), "claude-haiku-5-5") == pytest.approx(0.002)
    # Above 100,000 prompt tokens the rate is five times higher.
    assert agent.request_cost(usage(200_000, 0), "claude-haiku-5-5") == pytest.approx(0.10)


def test_unknown_model_fails_before_any_request(two_weeks):
    client = FakeClient(final("x"))
    with pytest.raises(ValueError, match="No price is known"):
        agent.ask(client, two_weeks, "q", model="some-other-model")
    assert client.requests == []


def test_trace_file_gets_one_json_line_per_question(two_weeks, tmp_path):
    client = FakeClient(reply(tool_use("weekly_summary", {"metric": "steps"})), final("ok"))
    result = agent.ask(client, two_weeks, "q")
    path = tmp_path / "logs" / "trace.jsonl"
    agent.append_trace(result, path, "demo")
    agent.append_trace(result, path, "demo")
    lines = path.read_text().splitlines()
    assert len(lines) == 2
    record = json.loads(lines[0])
    assert record["user_id"] == "demo" and record["status"] == "answered"
    assert record["tool_calls"][0]["name"] == "weekly_summary"


def test_a_trace_record_reads_back_as_the_same_result(two_weeks, tmp_path):
    client = FakeClient(reply(tool_use("weekly_summary", {"metric": "steps"})), final("Done."))
    result = agent.ask(client, two_weeks, "How many steps?")
    agent.append_trace(result, tmp_path / "trace.jsonl", "u1")
    record = json.loads((tmp_path / "trace.jsonl").read_text())
    assert agent.result_from_record(record) == result


def test_prompt_names_the_partial_day_when_the_export_stopped_early(two_weeks):
    partial = two_weeks.copy()
    partial.loc["2024-01-14", "steps"] = float("nan")   # sleep is still there on the 14th
    prompt = agent.system_prompt(partial)
    assert "the last complete day, 2024-01-13 (Saturday)" in prompt
    assert "2024-01-07 to 2024-01-13" in prompt
    assert "Data after 2024-01-13 is from a day that was not recorded in full" in prompt


def test_prompt_limits_scope_to_the_data_in_any_language(two_weeks):
    prompt = agent.system_prompt(two_weeks)
    assert "only answer questions about this person's wearable data" in prompt
    assert "a poem" in prompt and "not even briefly" in prompt
    assert "Every rule here applies in every language." in prompt


def test_prompt_forbids_threshold_comparisons_no_tool_returned(two_weeks):
    prompt = agent.system_prompt(two_weeks)
    assert "Do not compare daily values with a number yourself." in prompt
    assert "call weekly_summary with that value \nas threshold".replace("\n", "") \
        in prompt.replace("\n", "")
    assert "420 for 7 hours of sleep" in prompt


def test_prompt_forbids_guidelines_not_looked_up(two_weeks):
    prompt = agent.system_prompt(two_weeks).replace("\n", "")
    assert "unless get_guideline returned it in this conversation" in prompt


def test_prompt_attributes_the_missing_significance_test_to_the_tool(two_weeks):
    prompt = " ".join(agent.system_prompt(two_weeks).split())
    assert "say that the tool does not run a significance test" in prompt
    assert "never that the data does not include one" in prompt


def test_prompt_says_to_copy_weekdays_from_tool_results(two_weeks):
    prompt = " ".join(agent.system_prompt(two_weeks).split())
    assert "When you name a weekday, copy it from that field." in prompt
    assert "Never work out a weekday yourself" in prompt
