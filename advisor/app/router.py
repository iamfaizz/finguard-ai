"""Deterministic tool routing.

The LLM never picks tools or arguments. Plain regex decides which VERIFIED
backend tools to run, so the same flow works for Claude and Ollama and a
prompt trick cannot make the advisor ask for someone else's data.
"""
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

PERSONAL = re.compile(r"\b(my|mine|i|me|am i|can i|should i|do i|will i)\b|kharch", re.I)
AFFORD = re.compile(r"\b(afford|buy|purchase|spend on|splurge|worth it)\b", re.I)
FORECAST = re.compile(r"\b(forecast|next month|next 30 days|upcoming|predict|overspend|run out)\b", re.I)
SPENDING = re.compile(r"\b(spend|spent|spending|expenses?|expenditure|kharch\w*|categor\w+|merchants?)\b", re.I)
GOAL = re.compile(r"\b(goals?|on track)\b", re.I)

AMOUNT_RE = re.compile(
    r"(?:(₹|rs\.?|inr)\s*)?(\d[\d,]*(?:\.\d+)?)\s*"
    r"(?:(lakhs?|lacs?|crores?|cr|k|thousand|rupees?|rs|inr|₹)(?![a-z]))?",
    re.I,
)


@dataclass(frozen=True)
class ToolCall:
    name: str
    args: dict = field(default_factory=dict)


def extract_amount(text: str) -> Decimal | None:
    """'20,000 rupee phone' -> Decimal('20000'), '25k' -> 25000, '2 lakh' -> 200000. Never float."""
    for m in AMOUNT_RE.finditer(text):
        prefix, num, unit = m.group(1), m.group(2).rstrip(","), (m.group(3) or "").lower()
        try:
            value = Decimal(num.replace(",", ""))
        except InvalidOperation:
            continue
        if unit.startswith(("lakh", "lac")):
            value *= Decimal(100000)
        elif unit in ("k", "thousand"):
            value *= Decimal(1000)
        elif unit in ("crore", "crores", "cr"):
            value *= Decimal(10000000)
        if prefix or unit:
            if value >= 1:
                return value
        elif value >= 500 and not (1900 <= value <= 2100 and "," not in num):
            return value  # bare number; ignore plain years like 2026
    return None


def detect_period(q: str) -> str:
    q = q.lower()
    if "last month" in q or "previous month" in q:
        return "last_month"
    if re.search(r"90 days|3 months|three months|quarter", q):
        return "last_90_days"
    if re.search(r"30 days|past month", q):
        return "last_30_days"
    return "this_month"


def route(question: str) -> list[ToolCall]:
    if not PERSONAL.search(question):
        return []  # general knowledge question -> retrieval only
    calls: list[ToolCall] = []
    amount = extract_amount(question)
    afford = bool(AFFORD.search(question)) and amount is not None
    if afford:
        calls.append(ToolCall("check_affordability", {"amount": amount}))
    elif FORECAST.search(question):
        calls.append(ToolCall("get_forecast"))
    if SPENDING.search(question) and not afford:
        calls.append(ToolCall("get_spending_summary", {"period": detect_period(question)}))
    if GOAL.search(question):
        calls.append(ToolCall("get_goal_status"))
    return calls[:3]


def needs_amount(question: str, calls: list[ToolCall]) -> bool:
    return bool(
        PERSONAL.search(question)
        and re.search(r"\b(afford|can i buy|should i buy)\b", question, re.I)
        and not any(c.name == "check_affordability" for c in calls)
    )