# Compatible Member D storage; physical table names retained for existing data.
from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, Text, UniqueConstraint, Index
from sqlalchemy import Date, JSON, Boolean, func
from sqlalchemy.orm import synonym
from .database import Base
class User(Base):
    __tablename__ = 'd_users'
    id = Column(Integer, primary_key=True)
    email = Column(String(254), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    role = Column(String(20), default='user', nullable=False)
    hashed_password = synonym('password')
    full_name = Column(String(160))
    is_active = Column(Boolean, nullable=False, server_default='true')
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
class Transaction(Base):
    __tablename__ = 'd_transactions'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('d_users.id'), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    amount = Column(Numeric(12,2), nullable=False)
    merchant = Column(String(200), nullable=False)
    category = Column(String(100), default='Uncategorized')
    txn_type = Column(String(10), nullable=False)
    fingerprint = Column(String(64), nullable=False)
    status = Column(String(30), default='pending_review', index=True)
    score = Column(Numeric(8,6))
    reason = Column(Text)
    description = Column(Text)
    channel = Column(String(40))
    reference_id = Column(String(120))
    fraud_label = Column(Boolean)
    fraud_score = synonym('score')
    risk_level = Column(String(30))
    fraud_reasons = Column(JSON)
    model_version = Column(String(100))
    __table_args__ = (UniqueConstraint('user_id','fingerprint'), Index('ix_d_user_ts','user_id','timestamp'))
    ts = synonym('timestamp')
    direction = synonym('txn_type')

class Goal(Base):
    __tablename__ = 'd_goals'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('d_users.id'), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    target = Column(Numeric(12,2), nullable=False)
    saved = Column(Numeric(12,2), nullable=False)

    target_amount = synonym('target')
    saved_amount = synonym('saved')
    target_date = Column(Date, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

class ChatMessage(Base):
    __tablename__ = 'd_chat_messages'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('d_users.id'), nullable=False, index=True)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    sources = Column(JSON, default=list, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
