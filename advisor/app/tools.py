"""Client for the backend's verified-number endpoints (Step 5.3).

Security: the only identity sent is the user's own bearer token. There is NO
user_id parameter anywhere, so nothing the LLM writes can change whose data is read.
"""
import asyncio
import logging
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from app.config import settings
from app.router import ToolCall

log = logging.getLogger("advisor.tools")

TOOL_ENDPOINTS = {
    "get_spending_summary": ("GET", "/api/advisor-tools/spending-summary"),
    "get_forecast": ("GET", "/api/advisor-tools/forecast"),
    "check_affordability": ("POST", "/api/advisor-tools/affordability"),
    "get_goal_status": ("GET", "/api/advisor-tools/goal-status"),
}
PERIODS = {"this_month", "last_month", "last_30_days", "last_90_days"}


@dataclass
class ToolResult:
    name: str
    ok: bool
    data: Any = None


def format_inr(value: Any) -> str:
    """8333.33 -> ₹8,333.33 ; 125000 -> ₹1,25,000.00 (lakh/crore grouping)."""
    d = Decimal(str(value)).quantize(Decimal("0.01"))
    sign = "-" if d < 0 else ""
    whole, frac = f"{abs(d):.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        parts: list[str] = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        whole = ",".join(parts + [tail])
    return f"{sign}₹{whole}.{frac}"


def add_display(obj: Any) -> Any:
    """Replace every `xyz_inr` number with `xyz_display` ('₹…') so the LLM copies, never formats."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k.endswith("_inr") and v is not None:
                try:
                    out[k[: -len("_inr")] + "_display"] = format_inr(v)
                    continue
                except (InvalidOperation, ValueError):
                    pass
            out[k] = add_display(v)
        return out
    if isinstance(obj, list):
        return [add_display(i) for i in obj]
    return obj


def _validate(call: ToolCall) -> dict:
    if call.name not in TOOL_ENDPOINTS:
        raise ValueError(f"unknown tool {call.name}")
    if call.name == "get_spending_summary":
        period = call.args.get("period", "this_month")
        if period not in PERIODS:
            raise ValueError("bad period")
        return {"period": period}
    if call.name == "check_affordability":
        amount = float(call.args.get("amount", 0))
        if not 0 < amount < 1e9:
            raise ValueError("bad amount")
        return {"amount_inr": amount}
    return {}


class BackendTools:
    def __init__(self, token: str, base_url: str | None = None,
                 transport: httpx.AsyncBaseTransport | None = None, timeout: float = 5.0) -> None:
        self._token = token
        self._base = base_url or settings.backend_url
        self._transport = transport
        self._timeout = timeout

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base,
            headers={"Authorization": f"Bearer {self._token}"},
            timeout=self._timeout,
            transport=self._transport,
        )

    async def call(self, call: ToolCall) -> ToolResult:
        try:
            params = _validate(call)
            method, path = TOOL_ENDPOINTS[call.name]
            async with self._client() as c:
                if method == "GET":
                    resp = await c.get(path, params=params)
                else:
                    resp = await c.post(path, json=params)
            resp.raise_for_status()
            return ToolResult(call.name, True, add_display(resp.json()))
        except (httpx.HTTPError, ValueError, asyncio.TimeoutError) as exc:
            log.warning("tool %s failed: %s", call.name, type(exc).__name__)
            return ToolResult(call.name, False)

    async def save_chat(self, question: str, answer: str, sources: list[dict]) -> None:
        """Best effort: a logging failure must never break the chat."""
        try:
            async with self._client() as c:
                r = await c.post("/api/advisor-tools/chat-messages",
                                 json={"question": question, "answer": answer[:6000], "sources": sources})
                r.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            log.warning("save_chat failed: %s", type(exc).__name__)
