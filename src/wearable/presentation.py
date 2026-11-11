"""What the web app shows next to an answer, kept free of Streamlit so it can be tested.

- chart_for: one small chart built from the tool calls behind an answer.
- credits: attribution lines that tool results ask to be shown.
- UsageLimiter: a per-visitor question limit and an app-wide daily spend cap.
- api_error_message / STATUS_MESSAGES: friendly text for failures.

Charts are drawn from tool results, or from the user's daily table with the same
arguments the tool was called with, never from the model's text.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Callable

import altair as alt
import pandas as pd

from wearable.tools import data_range, paired_days

LABELS = {
    "steps": "Steps",
    "minutes_asleep": "Hours asleep",
    "minutes_in_bed": "Hours in bed",
    "mean_hr": "Mean heart rate (bpm)",
    "fairly_active_minutes": "Fairly active minutes",
    "very_active_minutes": "Very active minutes",
}
# Sleep is stored in minutes; charts show hours because they are easier to read on an axis.
TO_HOURS = {"minutes_asleep", "minutes_in_bed"}
ACCENT = "#2A7F7A"   # the theme's primaryColor in .streamlit/config.toml
# Short names for the two periods of each compare_periods preset (earlier period first).
PERIOD_NAMES = {
    "first_half_vs_second_half": ("First half", "Second half"),
    "last_4_weeks_vs_previous_4_weeks": ("Previous 4 weeks", "Last 4 weeks"),
    None: ("Period A", "Period B"),
}


@dataclass
class ChartSpec:
    title: str
    kind: str                  # "bar" or "scatter"
    data: pd.DataFrame
    x: str
    y: str | list[str]
    x_label: str
    y_label: str
    tooltip: list[str] = field(default_factory=list)   # columns; default is x and y
    x_angle: int = -45                                  # x label angle for bar charts


def _axis(metric: str, values: pd.Series) -> pd.Series:
    return values / 60 if metric in TO_HOURS else values


def _weekly_summary(out: dict[str, Any], _df: pd.DataFrame, _args: dict[str, Any]) -> ChartSpec:
    metric = out["metric"]
    data = pd.DataFrame({"date": [d["date"] for d in out["daily"]],
                         "value": [d["value"] for d in out["daily"]]})
    data["value"] = _axis(metric, data["value"].astype("float64"))
    return ChartSpec(f"{LABELS[metric]} per day, {out['start']} to {out['end']}", "bar",
                     data.rename(columns={"value": LABELS[metric]}), "date", LABELS[metric],
                     "Date", LABELS[metric])


def _weekly_active_minutes(out: dict[str, Any], _df: pd.DataFrame,
                           _args: dict[str, Any]) -> ChartSpec:
    fairly, very = LABELS["fairly_active_minutes"], LABELS["very_active_minutes"]
    data = pd.DataFrame({
        "date": [d["date"] for d in out["daily"]],
        fairly: [d["fairly_active_minutes"] for d in out["daily"]],
        very: [d["very_active_minutes"] for d in out["daily"]],
    })
    return ChartSpec(f"Active minutes per day, {out['start']} to {out['end']}", "bar",
                     data, "date", [fairly, very], "Date", "Minutes")


def _most_active_day(out: dict[str, Any], df: pd.DataFrame, _args: dict[str, Any]) -> ChartSpec:
    window = df.loc[out["start"]:out["end"], "steps"]
    data = pd.DataFrame({"date": window.index.strftime("%Y-%m-%d"), "Steps": window.to_numpy()})
    return ChartSpec(f"Steps per day, {out['start']} to {out['end']}", "bar", data,
                     "date", "Steps", "Date", "Steps")


def _compare_periods(out: dict[str, Any], _df: pd.DataFrame,
                     _args: dict[str, Any]) -> ChartSpec | None:
    if not out["enough_data"]:
        return None
    metric = out["metric"]
    periods = [out["period_a"], out["period_b"]]
    label = LABELS[metric]
    data = pd.DataFrame({
        "Period": list(PERIOD_NAMES.get(out["preset"], PERIOD_NAMES[None])),
        "Dates": [f"{p['start']} to {p['end']}" for p in periods],
        label: [p["mean"] for p in periods],
    })
    data[label] = _axis(metric, data[label].astype("float64"))
    return ChartSpec(f"{label}: daily average in each period", "bar", data, "Period", label,
                     "Period", f"{label}, daily average",
                     tooltip=["Period", "Dates", label], x_angle=0)


def _correlation(out: dict[str, Any], df: pd.DataFrame, _args: dict[str, Any]) -> ChartSpec | None:
    if out["n"] == 0:
        return None
    x, y = out["metric_x"], out["metric_y"]
    pairs = paired_days(df, x, y, out["lag_days"], pd.Timestamp(out["start"]),
                        pd.Timestamp(out["end"]))
    x_label = LABELS[x]
    y_label = LABELS[y] + (f", {out['lag_days']} day(s) later" if out["lag_days"] else "")
    if x_label == y_label:
        y_label += " (later)"
    data = pd.DataFrame({x_label: _axis(x, pairs["x"]).to_numpy(),
                         y_label: _axis(y, pairs["y"]).to_numpy()})
    return ChartSpec(f"Each point is one day (n = {out['n']})", "scatter", data,
                     x_label, y_label, x_label, y_label)


CHARTS: dict[str, Callable[[dict[str, Any], pd.DataFrame, dict[str, Any]], ChartSpec | None]] = {
    "weekly_summary": _weekly_summary,
    "weekly_active_minutes": _weekly_active_minutes,
    "most_active_day": _most_active_day,
    "compare_periods": _compare_periods,
    "correlation": _correlation,
}


def chart_for(tool_calls: list[Any], df: pd.DataFrame) -> ChartSpec | None:
    """A chart for the last successful tool call that has one, or None.

    tool_calls are agent.ToolCall objects (anything with name, input, output, is_error).
    The last call is used because the model usually ends on the result it answers from.
    """
    for call in reversed(tool_calls):
        if call.is_error or call.name not in CHARTS:
            continue
        spec = CHARTS[call.name](call.output, df, call.input)
        if spec is not None:
            return spec
    return None


def _tint(color: str, amount: float) -> str:
    """color mixed with white; amount 0 keeps it, 1 gives white."""
    rgb = [int(color.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    return "#" + "".join(f"{round(c + (255 - c) * amount):02X}" for c in rgb)


def to_altair(spec: ChartSpec, accent: str = ACCENT) -> alt.Chart:
    """The chart in the accent color. Field names are passed explicitly because labels such
    as "Mean heart rate (bpm)" would otherwise be parsed as aggregate shorthand."""
    data = spec.data
    numeric = {c for c in data.columns if pd.api.types.is_numeric_dtype(data[c])}

    def enc_type(column: str) -> str:
        return "quantitative" if column in numeric else "nominal"

    tips = [alt.Tooltip(field=c, type=enc_type(c), title=c,
                        format=".1f" if c in numeric else "")
            for c in (spec.tooltip or [spec.x, *([spec.y] if isinstance(spec.y, str) else spec.y)])]
    if spec.kind == "scatter":
        return alt.Chart(data).mark_circle(color=accent, size=60, opacity=0.8).encode(
            x=alt.X(field=spec.x, type="quantitative", title=spec.x_label,
                    scale=alt.Scale(zero=False)),
            y=alt.Y(field=spec.y, type="quantitative", title=spec.y_label,
                    scale=alt.Scale(zero=False)),
            tooltip=tips)
    x = alt.X(field=spec.x, type="nominal", title=spec.x_label, sort=None,
              axis=alt.Axis(labelAngle=spec.x_angle))
    if isinstance(spec.y, list):  # stacked bars, one colour step per series
        colors = [accent, _tint(accent, 0.55)][:len(spec.y)]
        return alt.Chart(data).transform_fold(spec.y, as_=["series", "value"]).mark_bar().encode(
            x=x, y=alt.Y(field="value", type="quantitative", title=spec.y_label),
            color=alt.Color(field="series", type="nominal", title=None,
                            scale=alt.Scale(domain=spec.y, range=colors),
                            legend=alt.Legend(orient="bottom")),
            tooltip=[alt.Tooltip(field=spec.x, type="nominal", title=spec.x_label),
                     alt.Tooltip(field="series", type="nominal", title="Series"),
                     alt.Tooltip(field="value", type="quantitative", title=spec.y_label)])
    return alt.Chart(data).mark_bar(color=accent).encode(
        x=x, y=alt.Y(field=spec.y, type="quantitative", title=spec.y_label), tooltip=tips)


def credits(tool_calls: list[Any]) -> list[str]:
    """Distinct "credit" lines from successful tool results, in the order they appeared."""
    seen: list[str] = []
    for call in tool_calls:
        if not call.is_error and isinstance(call.output, dict):
            line = call.output.get("credit")
            if line and line not in seen:
                seen.append(line)
    return seen


def user_label(user_id: str, df: pd.DataFrame) -> str:
    first, last = data_range(df)
    return f"Demo user {user_id} ({first:%d %b} to {last:%d %b %Y})"


def person_names(user_ids: list[str]) -> dict[str, str]:
    """'Person A', 'Person B', ... in sorted id order, so a name always means the same id."""
    ordered = sorted(user_ids)
    if len(ordered) > 26:
        raise ValueError("At most 26 people can be named with a letter.")
    return {uid: f"Person {chr(ord('A') + i)}" for i, uid in enumerate(ordered)}


def person_option(name: str, df: pd.DataFrame) -> str:
    """Short text for the person picker, e.g. "Person A · 59 days of steps"."""
    return f"{name} · {int(df['steps'].notna().sum())} days of steps"


def person_profile(df: pd.DataFrame) -> str:
    """One line describing a person's data coverage, from counts in the daily table only."""
    first, last = data_range(df)
    hr = df["mean_hr"].dropna()
    hr_part = (f"heart rate on {hr.size} days (from {hr.index.min():%-d %b})" if hr.size
               else "no heart rate")
    return (f"{first:%-d %b} to {last:%-d %b %Y}: {int(df['steps'].notna().sum())} days of "
            f"steps, {int(df['minutes_asleep'].notna().sum())} nights of sleep, {hr_part}.")


# --- limits -------------------------------------------------------------------

def _utc_today() -> date:
    return datetime.now(timezone.utc).date()


@dataclass
class UsageLimiter:
    """Questions per visitor per UTC day, and estimated API spend per UTC day for the app.

    Kept in memory, so both reset when the app restarts. That makes them a guard against
    one visitor using up the credit, not an accounting system; the spend limit set in the
    Claude Console is the hard backstop.
    """
    per_visitor: int
    daily_usd: float
    today: Callable[[], date] = _utc_today
    _day: date | None = None
    _counts: dict[str, int] = field(default_factory=dict)
    _spent: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def _roll(self) -> None:
        day = self.today()
        if day != self._day:
            self._day, self._counts, self._spent = day, {}, 0.0

    def remaining(self, visitor: str) -> int:
        with self._lock:
            self._roll()
            return max(self.per_visitor - self._counts.get(visitor, 0), 0)

    def start(self, visitor: str) -> str | None:
        """Reserve one question for visitor. Returns None if allowed, else a message."""
        with self._lock:
            self._roll()
            if self._spent >= self.daily_usd:
                return ("The app has reached its budget for today, so it is not answering new "
                        "questions. Please come back tomorrow.")
            if self._counts.get(visitor, 0) >= self.per_visitor:
                return (f"You have asked {self.per_visitor} questions today, which is the limit "
                        f"per visitor. Please come back tomorrow.")
            self._counts[visitor] = self._counts.get(visitor, 0) + 1
            return None

    def finish(self, visitor: str, cost_usd: float, failed: bool = False) -> None:
        """Record what a question cost. A question that failed before an answer, because
        of an API error, is given back to the visitor."""
        with self._lock:
            self._roll()
            self._spent += cost_usd
            if failed and self._counts.get(visitor, 0) > 0:
                self._counts[visitor] -= 1


# --- failure messages ---------------------------------------------------------

STATUS_MESSAGES = {
    "step_cap": "Sorry, this question needed more steps than the app allows, so there is no "
                "answer. Try asking it more simply, or one part at a time.",
    "spend_cap": "Sorry, this question reached the cost limit for one question before it was "
                 "answered. Try asking it more simply.",
    "refused": "The model declined to answer this question.",
    "truncated": "Sorry, the answer was cut off before it was complete. Please try again.",
}

NOT_CONFIGURED = ("The app is not connected to the language model right now (no API key is "
                  "set), so it cannot answer questions.")


def api_error_message(status_code: int | None, error_type: str | None) -> str:
    """Friendly text for an API failure. status_code is None for network errors."""
    if status_code == 402 or error_type == "billing_error":
        return ("The app has run out of credit with its language-model provider, so it cannot "
                "answer questions right now. Please try again later.")
    if status_code in (401, 403):
        return ("The app's connection to the language model is not set up correctly, so it "
                "cannot answer questions right now.")
    if status_code == 429:
        return "Many questions are being asked right now. Please wait a minute and try again."
    if status_code is None or status_code >= 500:
        return ("The language model service could not be reached or is busy. Please try again "
                "in a few minutes.")
    return "Something went wrong while answering. Please try again or rephrase the question."


__all__ = ["ChartSpec", "chart_for", "credits", "user_label", "UsageLimiter",
           "STATUS_MESSAGES", "NOT_CONFIGURED", "api_error_message", "LABELS", "person_names",
           "person_option", "person_profile", "to_altair", "ACCENT"]
