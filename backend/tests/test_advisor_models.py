import os
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JWT_SECRET_KEY", "test-only-secret-not-for-production-12345")
from app.member_d_models import Transaction, Goal, ChatMessage
from app.database import Base, engine
from sqlalchemy.orm import Session
from datetime import date
from decimal import Decimal

def test_model_aliases():
    t = Transaction(txn_type="debit")
    assert t.direction == "debit"
    g = Goal(target=Decimal("100"), saved=Decimal("10"), target_date=date(2027,1,1))
    assert g.target_amount == Decimal("100")
    assert g.saved_amount == Decimal("10")

def test_chat_table_registered():
    assert ChatMessage.__tablename__ in Base.metadata.tables
