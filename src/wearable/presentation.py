"""What the web app shows next to an answer, kept free of Streamlit so it can be tested.

- chart_for: one small chart built from the tool calls behind an answer.
- headline_numbers: one to three figures from the same tool results, shown large.
- credits: attribution lines that tool results ask to be shown.
- UsageLimiter: a per-visitor question limit and an app-wide daily spend cap.
- visitor_key: who a question is counted against (forwarded address, address, or session).
- api_error_message / STATUS_MESSAGES: friendly text for failures.

Charts are drawn from tool results, or from the user's daily table with the same
arguments the tool was called with, never from the model's text.
"""

from __future__ import annotations

import ipaddress
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
# Material Symbols (rounded) names, shown as ":material/<name>:" in chart titles and pills.
METRIC_ICONS = {
    "steps": "directions_walk",
    "minutes_asleep": "bedtime",
    "minutes_in_bed": "bedtime",
    "mean_hr": "monitor_heart",
    "fairly_active_minutes": "directions_run",
    "very_active_minutes": "directions_run",
}
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
    icons: list[str] = field(default_factory=list)     # Material icon names for the title
    x_angle: int = -45                                  # x label angle for bar charts


def _axis(metric: str, values: pd.Series) -> pd.Series:
    return values / 60 if metric in TO_HOURS else values


def _days(dates: list[str]) -> list[str]:
    """Short horizontal axis labels for dates, e.g. "Wed 4 May"."""
    return [_short_date(d) for d in dates]


def _weekly_summary(out: dict[str, Any], _df: pd.DataFrame, _args: dict[str, Any]) -> ChartSpec:
    metric = out["metric"]
    dates = [d["date"] for d in out["daily"]]
    data = pd.DataFrame({"day": _days(dates), "date": dates,
                         "value": [d["value"] for d in out["daily"]]})
    data["value"] = _axis(metric, data["value"].astype("float64"))
    label = LABELS[metric]
    return ChartSpec(f"{label} per day, {out['start']} to {out['end']}", "bar",
                     data.rename(columns={"value": label}), "day", label, "Day", label,
                     tooltip=["date", label], x_angle=0, icons=[METRIC_ICONS[metric]])


def _weekly_active_minutes(out: dict[str, Any], _df: pd.DataFrame,
                           _args: dict[str, Any]) -> ChartSpec:
    fairly, very = LABELS["fairly_active_minutes"], LABELS["very_active_minutes"]
    dates = [d["date"] for d in out["daily"]]
    data = pd.DataFrame({
        "day": _days(dates), "date": dates,
        fairly: [d["fairly_active_minutes"] for d in out["daily"]],
        very: [d["very_active_minutes"] for d in out["daily"]],
    })
    return ChartSpec(f"Active minutes per day, {out['start']} to {out['end']}", "bar",
                     data, "day", [fairly, very], "Day", "Minutes", x_angle=0,
                     icons=[METRIC_ICONS["fairly_active_minutes"]])


def _most_active_day(out: dict[str, Any], df: pd.DataFrame, _args: dict[str, Any]) -> ChartSpec:
    window = df.loc[out["start"]:out["end"], "steps"]
    dates = list(window.index.strftime("%Y-%m-%d"))
    data = pd.DataFrame({"day": _days(dates), "date": dates, "Steps": window.to_numpy()})
    return ChartSpec(f"Steps per day, {out['start']} to {out['end']}", "bar", data,
                     "day", "Steps", "Day", "Steps", tooltip=["date", "Steps"], x_angle=0,
                     icons=[METRIC_ICONS["steps"]])


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
                     tooltip=["Period", "Dates", label], x_angle=0,
                     icons=[METRIC_ICONS[metric]])


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
    icons = list(dict.fromkeys([METRIC_ICONS[x], METRIC_ICONS[y]]))
    return ChartSpec(f"Each point is one day (n = {out['n']})", "scatter", data,
                     x_label, y_label, x_label, y_label, icons=icons)


CHARTS: dict[str, Callable[[dict[str, Any], pd.DataFrame, dict[str, Any]], ChartSpec | None]] = {
    "weekly_summary": _weekly_summary,
    "weekly_active_minutes": _weekly_active_minutes,
    "most_active_day": _most_active_day,
    "compare_periods": _compare_periods,
    "correlation": _correlation,
}


# Words that tie a question to metrics, in English and Turkish, most specific first. For
# sleep, minutes asleep comes before time in bed unless the question says "in bed".
_QUESTION_TOPICS: list[tuple[tuple[str, ...], list[str]]] = [
    (("in bed", "yatakta", "yatak"), ["minutes_in_bed"]),
    (("sleep", "slept", "asleep", "night", "uyku", "uyu", "gece"),
     ["minutes_asleep", "minutes_in_bed"]),
    (("heart", "pulse", "bpm", "kalp", "nabız", "nabiz"), ["mean_hr"]),
    (("step", "walk", "adım", "adim", "yürü", "yuru"), ["steps"]),
    (("active", "activity", "exercise", "workout", "moderate", "vigorous", "aktif", "hareket",
      "egzersiz", "spor"), ["fairly_active_minutes", "very_active_minutes", "steps"]),
]


def question_metrics(question: str | None) -> list[str]:
    """The metrics a question is about, most relevant first; empty if it names none."""
    text = (question or "").lower()
    found: list[str] = []
    for words, metrics in _QUESTION_TOPICS:
        if any(word in text for word in words):
            found += [m for m in metrics if m not in found]
    return found


def _call_metrics(call: Any) -> set[str]:
    out = call.output
    if call.name in ("weekly_summary", "compare_periods"):
        return {out["metric"]}
    if call.name == "correlation":
        return {out["metric_x"], out["metric_y"]}
    if call.name == "most_active_day":
        return {"steps"}
    if call.name == "weekly_active_minutes":
        return {"fairly_active_minutes", "very_active_minutes"}
    return set()


def answer_call(tool_calls: list[Any], question: str | None = None) -> Any | None:
    """The tool call an answer's headline numbers and chart are taken from, or None.

    Among successful calls that have headline numbers, the one that covers most of the
    metrics the question is about wins; then the one whose metric comes first for the
    question (minutes asleep before time in bed for a sleep question); then the later call.
    A question that names no metric therefore gets the last such call.
    """
    wanted = question_metrics(question)
    best, best_key = None, None
    for index, call in enumerate(tool_calls):
        if call.is_error or call.name not in HEADLINES or not HEADLINES[call.name](call.output):
            continue
        matched = [wanted.index(m) for m in _call_metrics(call) if m in wanted]
        key = (len(matched), -min(matched, default=len(wanted)), index)
        if best_key is None or key > best_key:
            best, best_key = call, key
    return best


def chart_for(tool_calls: list[Any], df: pd.DataFrame,
              question: str | None = None) -> ChartSpec | None:
    """The chart for the call answer_call picks, or None if that call has no chart.

    tool_calls are agent.ToolCall objects (anything with name, input, output, is_error).
    """
    call = answer_call(tool_calls, question)
    if call is None or call.name not in CHARTS:
        return None
    return CHARTS[call.name](call.output, df, call.input)


def chart_heading(spec: ChartSpec) -> str:
    """The chart title with its metric icons, as Streamlit markdown."""
    return " ".join([*(f":material/{name}:" for name in spec.icons), spec.title])


def _tint(color: str, amount: float) -> str:
    """color mixed with white; amount 0 keeps it, 1 gives white."""
    rgb = [int(color.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    return "#" + "".join(f"{round(c + (255 - c) * amount):02X}" for c in rgb)


def to_altair(spec: ChartSpec, accent: str = ACCENT) -> alt.Chart:
    """The chart in the accent color, on a transparent background so it sits on a card."""
    return _chart(spec, accent).configure(background="transparent")


def _chart(spec: ChartSpec, accent: str) -> alt.Chart:
    """Field names are passed explicitly because labels such as "Mean heart rate (bpm)"
    would otherwise be parsed as aggregate shorthand."""
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
    # Horizontal labels; on long ranges the ones that would overlap are left out. The
    # domain lists every row, so a day without data keeps its empty slot instead of being
    # dropped (Vega-Lite drops rows whose value is missing).
    x = alt.X(field=spec.x, type="nominal", title=spec.x_label, sort=None,
              scale=alt.Scale(domain=[str(v) for v in data[spec.x]]),
              axis=alt.Axis(labelAngle=spec.x_angle, labelOverlap="greedy",
                            labelSeparation=6))
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


def person_stats(df: pd.DataFrame) -> dict[str, int]:
    """How many days of each kind a person has, from counts in the daily table only."""
    return {"nights_of_sleep": int(df["minutes_asleep"].notna().sum()),
            "days_of_steps": int(df["steps"].notna().sum()),
            "days_of_heart_rate": int(df["mean_hr"].notna().sum())}


def person_card(name: str, df: pd.DataFrame) -> str:
    """A person's card as Streamlit label markdown: a letter avatar (inline code), the
    name (bold) and one line per mini stat (italic, each starting with its Material icon).
    The page's CSS lays these three kinds of element out as a card."""
    stats = person_stats(df)
    return " ".join([
        f"`{name.split()[-1]}`", f"**{name}**",
        f"*:material/{METRIC_ICONS['minutes_asleep']}: {stats['nights_of_sleep']} nights of sleep*",
        f"*:material/{METRIC_ICONS['steps']}: {stats['days_of_steps']} days of steps*",
        f"*:material/{METRIC_ICONS['mean_hr']}: {stats['days_of_heart_rate']} days of heart rate*",
    ])


# --- headline numbers ----------------------------------------------------------

@dataclass(frozen=True)
class Headline:
    label: str
    value: str


HEADLINE_NAMES = {
    "steps": "steps",
    "minutes_asleep": "sleep",
    "minutes_in_bed": "time in bed",
    "mean_hr": "heart rate",
    "fairly_active_minutes": "fairly active minutes",
    "very_active_minutes": "very active minutes",
}
_UNITS = {"mean_hr": " bpm", "fairly_active_minutes": " min", "very_active_minutes": " min"}


def _number(value: float, metric: str | None = None, signed: bool = False) -> str:
    """A tool's number as text: thousands separators, no ".0", the metric's unit."""
    number = int(value) if float(value).is_integer() else value
    return f"{number:{'+,' if signed else ','}}{_UNITS.get(metric, '')}"


def _shown(part: dict[str, Any], key: str, metric: str, signed: bool = False) -> str:
    """part[key] the way the tool gave it: as hours and minutes for sleep ("<key>_text"),
    otherwise the number itself with its unit."""
    return part.get(f"{key}_text") or _number(part[key], metric, signed)


def _short_date(day: str, year: bool = False) -> str:
    return f"{pd.Timestamp(day):%a %-d %b{' %Y' if year else ''}}"


def _headline_weekly_summary(out: dict[str, Any]) -> list[Headline]:
    metric = out["metric"]
    name = HEADLINE_NAMES[metric]
    unit = "Nights" if metric in TO_HOURS else "Days"
    coverage = Headline(f"{unit} with data", f"{out['days_with_data']} of {len(out['daily'])}")
    if out["mean"] is None:
        return [coverage]
    shown = [Headline(f"Average {name}", _shown(out, "mean", metric))]
    limit = out.get("threshold")
    if limit:
        shown.append(Headline(f"{unit} at or above {_shown(limit, 'value', metric)}",
                              f"{limit['days_at_or_above']} of {out['days_with_data']}"))
    else:
        top = out["highest"]
        shown.append(Headline(f"Highest, {_short_date(top['date'])}",
                              _shown(top, "value", metric)))
    return [*shown, coverage]


def _headline_most_active_day(out: dict[str, Any]) -> list[Headline]:
    top = out["most_active"]
    if top is None:
        return [Headline("Days with step data", f"{out['days_with_data']} of {out['days']}")]
    return [Headline("Most active day", _short_date(top["date"], year=True)),
            Headline("Steps that day", _number(top["steps"])),
            Headline("Average steps per day", _number(out["mean_steps"]))]


def _headline_weekly_active_minutes(out: dict[str, Any]) -> list[Headline]:
    combined = out["combined"]
    coverage = Headline("Days with data", f"{out['days_with_data']} of {len(out['daily'])}")
    if combined["moderate_equivalent_minutes"] is None:
        return [coverage]
    return [Headline("Moderate-equivalent minutes",
                     _number(combined["moderate_equivalent_minutes"])),
            Headline("CDC weekly recommendation",
                     f"{_number(combined['recommended_minutes'])} min"),
            coverage]


def _headline_compare_periods(out: dict[str, Any]) -> list[Headline]:
    if not out["enough_data"]:
        return []
    metric = out["metric"]
    first, second = PERIOD_NAMES.get(out["preset"], PERIOD_NAMES[None])
    return [Headline(f"{first}, daily average", _shown(out["period_a"], "mean", metric)),
            Headline(f"{second}, daily average", _shown(out["period_b"], "mean", metric)),
            Headline(f"{second} minus {first}",
                     _shown(out, "difference_b_minus_a", metric, signed=True))]


def _headline_correlation(out: dict[str, Any]) -> list[Headline]:
    pairs = Headline("Days with both values", _number(out["n"]))
    if out["r"] is None:
        return [pairs]
    low, high = out["ci_95"]
    return [Headline("Correlation (r)", str(out["r"])),
            Headline("95% confidence interval", f"{low} to {high}"),
            pairs]


HEADLINES: dict[str, Callable[[dict[str, Any]], list[Headline]]] = {
    "weekly_summary": _headline_weekly_summary,
    "weekly_active_minutes": _headline_weekly_active_minutes,
    "most_active_day": _headline_most_active_day,
    "compare_periods": _headline_compare_periods,
    "correlation": _headline_correlation,
}


def headline_numbers(tool_calls: list[Any], question: str | None = None) -> list[Headline]:
    """One to three headline figures for an answer, or none.

    They are read from the call answer_call picks (the same call chart_for draws), and
    only formatted here: nothing is computed, and nothing is taken from the model's text.
    """
    call = answer_call(tool_calls, question)
    return HEADLINES[call.name](call.output) if call is not None else []


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


def _public_address(text: str | None) -> str | None:
    """text as a normalised IP address if it is a public one, else None."""
    try:
        address = ipaddress.ip_address((text or "").strip())
    except ValueError:
        return None
    return str(address) if address.is_global else None


def visitor_key(ip: str | None, forwarded_for: str | None, session_id: str) -> str:
    """Who a question is counted against: "forwarded:<ip>", "ip:<ip>" or "session:<id>".

    ip is the address of the connection that reached the app. Behind a hosting platform's
    proxy that is the proxy, not the visitor, so the X-Forwarded-For header is looked at
    first: its last public address is the one the nearest proxy added, and the entries
    before it can be typed in by the client. Without a public address from either source
    the browser session is used; a reload starts a new one, so in that case only the
    app-wide daily budget of UsageLimiter really holds.
    """
    for entry in reversed((forwarded_for or "").split(",")):
        address = _public_address(entry)
        if address:
            return f"forwarded:{address}"
    address = _public_address(ip)
    if address:
        return f"ip:{address}"
    return f"session:{session_id}"


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


__all__ = ["ChartSpec", "chart_for", "credits", "user_label", "UsageLimiter", "visitor_key",
           "STATUS_MESSAGES", "NOT_CONFIGURED", "api_error_message", "LABELS", "person_names",
           "person_stats", "person_card", "to_altair", "ACCENT",
           "METRIC_ICONS", "chart_heading", "Headline", "headline_numbers"]
