"""Advisor API contract (Step 1.4).

Imported by the advisor service AND the backend, so both sides agree on shapes.
Money convention: every rupee field ends with `_inr` (Decimal -> JSON string).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

# ---------- public: frontend -> advisor /chat ----------


class HistoryItem(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=1500)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    history: list[HistoryItem] = Field(default_factory=list, max_length=6)
    stream: bool = True


class Source(BaseModel):
    index: int  # matches the [1], [2] markers in the answer
    title: str
    source_url: str
    section: str = ""
    as_of: str  # YYYY-MM-DD, shown to the user
    snippet: str


class ChatResponse(BaseModel):  # used when stream=false
    answer: str
    sources: list[Source]
    used_tools: list[str]
    refused: bool = False


# ---------- internal: advisor -> backend tool endpoints ----------
Period = Literal["this_month", "last_month", "last_30_days", "last_90_days"]


class CategorySpend(BaseModel):
    category: str
    total_inr: Decimal
    share_pct: float


class SpendingSummary(BaseModel):
    period: Period
    start: date
    end: date
    total_spend_inr: Decimal
    total_income_inr: Decimal
    by_category: list[CategorySpend]


class ForecastSummary(BaseModel):
    horizon_days: int = 30
    predicted_spend_inr: Decimal
    predicted_income_inr: Decimal
    predicted_surplus_inr: Decimal
    low_confidence: bool  # True when < 60 days of history (Step 4.2)


class AffordabilityRequest(BaseModel):
    amount_inr: Decimal = Field(gt=0, lt=Decimal("1000000000"))


class AffordabilityResult(BaseModel):
    amount_inr: Decimal
    verdict: Literal["comfortable", "tight", "not_recommended"]
    free_cash_inr: Decimal  # forecast surplus minus goal commitments
    goal_commitments_inr: Decimal
    remaining_after_purchase_inr: Decimal
    low_confidence: bool


class GoalItem(BaseModel):
    name: str
    target_inr: Decimal
    saved_inr: Decimal
    target_date: date
    required_monthly_inr: Decimal
    progress_pct: float
    on_track: bool


class GoalStatus(BaseModel):
    goals: list[GoalItem]


class ChatLogRequest(BaseModel):
    question: str = Field(max_length=500)
    answer: str = Field(max_length=6000)
    sources: list[Source] = Field(default_factory=list)
