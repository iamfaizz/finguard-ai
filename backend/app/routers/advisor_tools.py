"""Step 5.3 - verified-number endpoints the advisor calls. (Written by B, reviewed by D.)

ADAPT THESE 5 IMPORTS to D's/C's real names:
  get_current_user -> returns the logged-in User (has .id)
  get_db           -> sync SQLAlchemy Session dependency
  Transaction, Goal, ChatMessage -> models from Step 1.3
  settings.ml_forecast_url
Forecast contract = C's finguard_ml_forecast.py (see _forecast). Income is computed here from the user's credits.
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


HISTORY_DAYS = 180  # how much spending history we send to ml-forecast


def _ml_transactions(db: Session, user) -> list[dict]:
    """The user's own DEBIT history in the shape C's /forecast expects.

    ADAPTER: if C changes the request field names, change ONLY this function.
    (float() is fine here: this is ML input, not a number shown to the user.)
    """
    since = datetime.now(timezone.utc) - timedelta(days=HISTORY_DAYS)
    rows = db.execute(
        select(Transaction.amount, Transaction.category, Transaction.ts)
        .where(Transaction.user_id == user.id, Transaction.direction == "debit", Transaction.ts >= since)
        .order_by(Transaction.ts)
    ).all()
    return [
        {"amount": float(a), "category": c or "Uncategorized", "timestamp": t.isoformat(), "type": "debit"}
        for a, c, t in rows
    ]


def _income_estimate(db: Session, user) -> Decimal:
    """Expected income for the next 30 days, from the user's own credits (plain SQL, no ML).

    = credits in the last 90 days, scaled to 30 days. New users with < 90 days of history
    are scaled by their real history length (minimum 30 days) so income is not underestimated.
    """
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=90)
    mine = (Transaction.user_id == user.id,)
    total = db.scalar(select(func.coalesce(func.sum(Transaction.amount), 0))
                      .where(*mine, Transaction.direction == "credit", Transaction.ts >= since)) or Decimal(0)
    first = db.scalar(select(func.min(Transaction.ts)).where(*mine))
    if first is None:
        return Decimal("0.00")
    span_days = max(min((now - first).days, 90), 30)
    return _q(Decimal(total) / Decimal(span_days) * Decimal(30))


def _forecast(db: Session, user) -> ForecastSummary:
    # C's real contract (finguard_ml_forecast.py):
    #   POST /forecast {"transactions": [...], "horizon": 30}
    #   -> {"total_predicted_spending", "low_confidence", "history_days", "forecast_days",
    #       "method", "category_forecasts", "confidence_note"}
    txns = _ml_transactions(db, user)
    if not txns:
        raise HTTPException(409, "No transaction history yet")
    try:
        r = httpx.post(f"{settings.ml_forecast_url}/forecast",
                       json={"transactions": txns, "horizon": 30}, timeout=10.0)
        r.raise_for_status()
        d = r.json()
        spend = Decimal(str(d["total_predicted_spending"]))
        low_conf = bool(d["low_confidence"])
    except (httpx.HTTPError, KeyError, ValueError):
        raise HTTPException(503, "Forecast service unavailable") from None
    income = _income_estimate(db, user)
    return ForecastSummary(predicted_spend_inr=_q(spend), predicted_income_inr=income,
                           predicted_surplus_inr=_q(income - spend), low_confidence=low_conf)


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
def forecast(user=Depends(get_current_user), db: Session = Depends(get_db)):
    return _forecast(db, user)


def _free_cash(db: Session, user) -> tuple[ForecastSummary, Decimal, Decimal]:
    f = _forecast(db, user)
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