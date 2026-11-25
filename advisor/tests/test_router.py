from decimal import Decimal

from app.router import ToolCall, extract_amount, route


def test_affordability_phone():
    assert route("Can I afford a 20,000 rupee phone this month?") == [ToolCall("check_affordability", {"amount": Decimal("20000")})]


def test_amount_formats():
    assert extract_amount("phone for ₹25k") == Decimal("25000")
    assert extract_amount("a 2 lakh bike") == Decimal("200000")
    assert extract_amount("Rs. 5000 shoes") == Decimal("5000")
    assert extract_amount("in 2026 what is 80C") is None
    assert extract_amount("last 30 days") is None


def test_spending_period():
    assert route("How much did I spend last month?") == [ToolCall("get_spending_summary", {"period": "last_month"})]


def test_goal_and_forecast():
    assert [c.name for c in route("Am I on track for my goal?")] == ["get_goal_status"]
    assert [c.name for c in route("Will I overspend next month?")] == ["get_forecast"]


def test_general_questions_use_no_tools():
    assert route("What is Section 80C?") == []
    assert route("Which is better, PPF or ELSS?") == []


def test_amount_is_decimal_not_float():
    a = extract_amount("a phone for Rs. 20,000.55")
    assert isinstance(a, Decimal) and a == Decimal("20000.55")