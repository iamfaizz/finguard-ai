import asyncio

import httpx

from app.router import ToolCall
from app.tools import BackendTools, add_display, format_inr


def test_format_inr_indian_grouping():
    assert format_inr("8333.33") == "₹8,333.33"
    assert format_inr(125000) == "₹1,25,000.00"
    assert format_inr("-1234567.5") == "-₹12,34,567.50"


def test_add_display_replaces_inr_keys():
    out = add_display({"total_spend_inr": "42500.5", "rows": [{"x_inr": 100}], "flag": True})
    assert out["total_spend_display"] == "₹42,500.50"
    assert out["rows"][0]["x_display"] == "₹100.00"
    assert "total_spend_inr" not in out and out["flag"] is True


def _tools(handler, token="tok123"):
    return BackendTools(token, base_url="http://backend", transport=httpx.MockTransport(handler))


def test_tool_call_sends_only_the_bearer_token():
    seen = {}

    def handler(req: httpx.Request):
        seen["auth"], seen["url"] = req.headers["authorization"], str(req.url)
        return httpx.Response(200, json={"total_spend_inr": "100"})

    res = asyncio.run(_tools(handler).call(ToolCall("get_spending_summary", {"period": "last_month"})))
    assert res.ok and res.data["total_spend_display"] == "₹100.00"
    assert seen["auth"] == "Bearer tok123" and "user" not in seen["url"]


def test_bad_tool_or_args_are_rejected_without_a_request():
    def handler(req):
        raise AssertionError("must not be called")

    t = _tools(handler)
    assert not asyncio.run(t.call(ToolCall("delete_everything"))).ok
    assert not asyncio.run(t.call(ToolCall("check_affordability", {"amount": -5}))).ok
    assert not asyncio.run(t.call(ToolCall("get_spending_summary", {"period": "forever"}))).ok


def test_backend_down_returns_not_ok():
    def handler(req):
        return httpx.Response(500)

    assert not asyncio.run(_tools(handler).call(ToolCall("get_forecast"))).ok


def test_affordability_amount_is_sent_as_exact_decimal_string():
    seen = {}

    def handler(req: httpx.Request):
        seen["body"] = req.content.decode()
        return httpx.Response(200, json={"verdict": "tight"})

    from decimal import Decimal

    res = asyncio.run(_tools(handler).call(ToolCall("check_affordability", {"amount": Decimal("20000.55")})))
    assert res.ok and '"amount_inr":"20000.55"' in seen["body"].replace(" ", "")


def test_non_finite_or_huge_amounts_rejected():
    from decimal import Decimal

    def handler(req):
        raise AssertionError("must not be called")

    t = _tools(handler)
    for bad in [float("nan"), float("inf"), Decimal("NaN"), Decimal("Infinity"), "1e999", 0, -1, "abc"]:
        assert not asyncio.run(t.call(ToolCall("check_affordability", {"amount": bad}))).ok, bad