"""Step 5.3 - verified-number endpoints the advisor calls. (Written by B, reviewed by D.)

ADAPT THESE 5 IMPORTS to D's/C's real names:
  get_current_user -> returns the logged-in User (has .id)
  get_db           -> sync SQLAlchemy Session dependency
  Transaction, Goal, ChatMessage -> models from Step 1.3
  settings.ml_forecast_url
The user comes ONLY from get_current_user (the JWT). No endpoint takes a user id.
Include in main.py:  app.include_router(advisor_tools.router)
"""
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user  # D's dependency
from app.db import get_db  # D's dependency
from app.models import ChatMessage, Goal, Transaction  # Step 1.3 models
from app.settings import settings
from shared.contracts.advisor import (
    AffordabilityRequest, AffordabilityResult, CategorySpend, ChatLogRequest,
    ForecastSummary, GoalItem, GoalStatus, Period, SpendingSummary,
)

router = APIRouter(prefix="/api/advisor-tools", tags=["advisor-tools"])
CENT = Decimal("0.01")


def _q(x: Decimal) -> Decimal:
    return x.quantize(CENT, rounding=ROUND_HALF_UP)


def period_bounds(period: Period, now: datetime) -> tuple[datetime, datetime]:
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    first = today.replace(day=1)
    if period == "this_month":
        return first, now
    if period == "last_month":
        return (first - timedelta(days=1)).replace(day=1), first
    return today - timedelta(days=30 if period == "last_30_days" else 90), now


def _forecast(user) -> ForecastSummary:
    # ASSUMED contract with C's ml-forecast - align with Step 4.4 and edit here only:
    #   POST /forecast {"user_id": "...", "horizon_days": 30}
    #   -> {"total_spend": 41000.0, "total_income": 60000.0, "low_confidence": false}
    try:
        r = httpx.post(f"{settings.ml_forecast_url}/forecast",
                       json={"user_id": str(user.id), "horizon_days": 30}, timeout=3.0)
        r.raise_for_status()
        d = r.json()
    except httpx.HTTPError:
        raise HTTPException(503, "Forecast service unavailable") from None
    spend, income = Decimal(str(d["total_spend"])), Decimal(str(d["total_income"]))
    return ForecastSummary(predicted_spend_inr=_q(spend), predicted_income_inr=_q(income),
                           predicted_surplus_inr=_q(income - spend), low_confidence=bool(d["low_confidence"]))


def _goal_items(db: Session, user) -> list[GoalItem]:
    # Same formula as C's goal planner: (target - saved) / months_left. Keep them identical!
    items = []
    for g in db.scalars(select(Goal).where(Goal.user_id == user.id)):
        remaining = max(Decimal(g.target_amount) - Decimal(g.saved_amount), Decimal(0))
        months_left = max(Decimal((g.target_date - date.today()).days) / Decimal("30.4375"), Decimal(1))
        required = _q(remaining / months_left)
        pct = float(Decimal(g.saved_amount) / Decimal(g.target_amount) * 100) if g.target_amount else 0.0
        items.append(GoalItem(name=g.name, target_inr=_q(Decimal(g.target_amount)), saved_inr=_q(Decimal(g.saved_amount)),
                              target_date=g.target_date, required_monthly_inr=required,
                              progress_pct=round(pct, 1), on_track=False))  # on_track filled by caller
    return items


@router.get("/spending-summary", response_model=SpendingSummary)
def spending_summary(period: Period = "this_month", user=Depends(get_current_user), db: Session = Depends(get_db)):
    start, end = period_bounds(period, datetime.now(timezone.utc))
    base = (Transaction.user_id == user.id, Transaction.ts >= start, Transaction.ts < end)

    def total(direction: str) -> Decimal:
        return db.scalar(select(func.coalesce(func.sum(Transaction.amount), 0))
                         .where(*base, Transaction.direction == direction)) or Decimal(0)

    spend, income = Decimal(total("debit")), Decimal(total("credit"))
    rows = db.execute(
        select(Transaction.category, func.sum(Transaction.amount))
        .where(*base, Transaction.direction == "debit")
        .group_by(Transaction.category).order_by(func.sum(Transaction.amount).desc()).limit(8)
    ).all()
    cats = [CategorySpend(category=c or "Uncategorized", total_inr=_q(Decimal(t)),
                          share_pct=round(float(Decimal(t) / spend * 100), 1) if spend else 0.0)
            for c, t in rows]
    return SpendingSummary(period=period, start=start.date(), end=end.date(),
                           total_spend_inr=_q(spend), total_income_inr=_q(income), by_category=cats)


@router.get("/forecast", response_model=ForecastSummary)
def forecast(user=Depends(get_current_user)):
    return _forecast(user)


def _free_cash(db: Session, user) -> tuple[ForecastSummary, Decimal, Decimal]:
    f = _forecast(user)
    commitments = sum((g.required_monthly_inr for g in _goal_items(db, user)), Decimal(0))
    return f, _q(commitments), _q(f.predicted_surplus_inr - commitments)


@router.post("/affordability", response_model=AffordabilityResult)
def affordability(body: AffordabilityRequest, user=Depends(get_current_user), db: Session = Depends(get_db)):
    f, commitments, free = _free_cash(db, user)
    amount = _q(body.amount_inr)
    if free <= 0 or amount > free:
        verdict = "not_recommended"
    elif amount <= free * Decimal("0.5"):
        verdict = "comfortable"
    else:
        verdict = "tight"
    return AffordabilityResult(amount_inr=amount, verdict=verdict, free_cash_inr=free,
                               goal_commitments_inr=commitments,
                               remaining_after_purchase_inr=_q(free - amount), low_confidence=f.low_confidence)


@router.get("/goal-status", response_model=GoalStatus)
def goal_status(user=Depends(get_current_user), db: Session = Depends(get_db)):
    _, _, free = _free_cash(db, user)
    items = _goal_items(db, user)
    for g in items:
        g.on_track = free >= 0  # surplus already net of ALL goal commitments
    return GoalStatus(goals=items)


@router.post("/chat-messages", status_code=204)
def save_chat(body: ChatLogRequest, user=Depends(get_current_user), db: Session = Depends(get_db)):
    db.add(ChatMessage(user_id=user.id, role="user", content=body.question, sources=[]))
    db.add(ChatMessage(user_id=user.id, role="assistant", content=body.answer,
                       sources=[s.model_dump() for s in body.sources]))
    db.commit()
