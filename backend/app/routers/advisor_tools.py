"""Step 5.3 - verified-number endpoints the advisor calls. (Written by B, reviewed by D.)

ADAPT THESE 5 IMPORTS to D's/C's real names:
  get_current_user -> returns the logged-in User (has .id)
  get_db           -> sync SQLAlchemy Session dependency
  Transaction, Goal, ChatMessage -> models from Step 1.3
  settings.ml_forecast_url
Forecast + goal maths come from C's ml-forecast (/forecast, /goal-plan). Income is computed here from the user's credits.
The user comes ONLY from get_current_user (the JWT). No endpoint takes a user id.
Include in main.py:  app.include_router(advisor_tools.router)
"""
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.dependencies import get_current_user  # D's dependency
from app.database import get_db  # D's dependency
from app.member_d_models import ChatMessage, Goal, Transaction  # Step 1.3 models
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


def _forecast_raw(db: Session, user) -> dict:
    """Call C's POST /forecast and return its raw response.

    C's real contract (ml-forecast/projecttt.py, forecast_spending):
      request  {"transactions": [{amount, category, timestamp, type}], "horizon": 30}
      response {"total_predicted_spending", "low_confidence", "history_days",
                "category_forecasts": {cat: {"next_30_days_estimate": ...}}, ...}
    """
    txns = _ml_transactions(db, user)
    if not txns:
        raise HTTPException(409, "No transaction history yet")
    try:
        r = httpx.post(f"{settings.ml_forecast_url}/forecast",
                       json={"transactions": txns, "horizon": 30}, timeout=10.0)
        r.raise_for_status()
        return r.json()
    except (httpx.HTTPError, ValueError):
        raise HTTPException(503, "Forecast service unavailable") from None


def _summary(raw: dict, income: Decimal) -> ForecastSummary:
    try:
        spend = Decimal(str(raw["total_predicted_spending"]))
        low_conf = bool(raw["low_confidence"])
    except (KeyError, ValueError, ArithmeticError):
        raise HTTPException(503, "Forecast service returned an unexpected response") from None
    return ForecastSummary(predicted_spend_inr=_q(spend), predicted_income_inr=income,
                           predicted_surplus_inr=_q(income - spend), low_confidence=low_conf)


def _forecast(db: Session, user) -> ForecastSummary:
    return _summary(_forecast_raw(db, user), _income_estimate(db, user))


def months_left(target: date, today: date) -> int:
    """Whole months from today to the target date, minimum 1 (C's planner needs an int >= 1).

    Rounded DOWN on purpose: fewer months = a higher monthly amount = the safe side.
    Example: 25 Nov -> 25 May = 6 months. The frontend must show the backend's number,
    never recompute this.
    """
    months = (target.year - today.year) * 12 + (target.month - today.month)
    if target.day < today.day:
        months -= 1
    return max(months, 1)


def _goal_plan(payload: dict) -> dict:
    """Ask C's POST /goal-plan. The goal maths lives ONLY in C's plan_goal() - never duplicated here."""
    try:
        r = httpx.post(f"{settings.ml_forecast_url}/goal-plan", json=payload, timeout=5.0)
        r.raise_for_status()
        return r.json()
    except (httpx.HTTPError, ValueError):
        raise HTTPException(503, "Goal planner unavailable") from None


def _goal_items(db: Session, user, raw: dict, income: Decimal) -> list[GoalItem]:
    # NOTE: each goal is checked against the full forecast surplus on its own.
    spend = float(raw["total_predicted_spending"])
    cats = {k: float(v["next_30_days_estimate"]) for k, v in raw.get("category_forecasts", {}).items()}
    items = []
    for g in db.scalars(select(Goal).where(Goal.user_id == user.id)):
        if g.target_date is None:
            raise HTTPException(409, "Set a target date for each goal before planning")
        target, saved = Decimal(g.target_amount), Decimal(g.saved_amount)
        plan = _goal_plan({
            "target_amount": float(target), "saved_amount": float(saved),
            "months_left": months_left(g.target_date, date.today()),
            "forecast_income": float(income), "forecast_spending": spend,
            "category_forecasts": cats,
        })
        required = _q(Decimal(str(plan["goal"]["required_monthly_savings"])))
        pct = float(saved / target * 100) if target > 0 else 0.0
        items.append(GoalItem(name=g.name, target_inr=_q(target), saved_inr=_q(saved),
                              target_date=g.target_date, required_monthly_inr=required,
                              progress_pct=round(pct, 1), on_track=not plan["infeasible"]))
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
    raw, income = _forecast_raw(db, user), _income_estimate(db, user)
    f = _summary(raw, income)
    commitments = sum((g.required_monthly_inr for g in _goal_items(db, user, raw, income)), Decimal(0))
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
    raw, income = _forecast_raw(db, user), _income_estimate(db, user)
    return GoalStatus(goals=_goal_items(db, user, raw, income))


@router.post("/chat-messages", status_code=204)
def save_chat(body: ChatLogRequest, user=Depends(get_current_user), db: Session = Depends(get_db)):
    db.add(ChatMessage(user_id=user.id, role="user", content=body.question, sources=[]))
    db.add(ChatMessage(user_id=user.id, role="assistant", content=body.answer,
                       sources=[s.model_dump(mode="json") for s in body.sources]))
    db.commit()
