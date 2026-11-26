"""Baseline existing Member D schema without deleting data."""
from alembic import op
import sqlalchemy as sa
# Provisional integration tables; reconcile with Member C before production.
from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, Text, UniqueConstraint, Index
from sqlalchemy import Date, JSON
from sqlalchemy.orm import synonym
from sqlalchemy.orm import declarative_base
Base = declarative_base()
class User(Base):
    __tablename__ = 'd_users'
    id = Column(Integer, primary_key=True)
    email = Column(String(254), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    role = Column(String(20), default='user', nullable=False)
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

class ChatMessage(Base):
    __tablename__ = 'd_chat_messages'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('d_users.id'), nullable=False, index=True)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    sources = Column(JSON, default=list, nullable=False)


revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    Base.metadata.create_all(bind, checkfirst=True)
    inspector = sa.inspect(bind)
    if 'target_date' not in {c['name'] for c in inspector.get_columns('d_goals')}:
        op.add_column('d_goals', sa.Column('target_date', sa.Date(), nullable=True))
    inspector = sa.inspect(bind)
    for table in Base.metadata.sorted_tables:
        actual = {c['name'] for c in inspector.get_columns(table.name)}
        missing = set(table.columns.keys()) - actual
        if missing:
            raise RuntimeError(f'{table.name}: missing columns {sorted(missing)}')

def downgrade():
    raise RuntimeError('Baseline downgrade disabled to protect existing data')
