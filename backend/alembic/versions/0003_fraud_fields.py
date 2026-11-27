from alembic import op
import sqlalchemy as sa

revision = "0003_fraud_fields"
down_revision = "0002_compatible"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("d_transactions", sa.Column("balance", sa.Numeric(14, 2), nullable=True))
    op.add_column("d_transactions", sa.Column("device", sa.String(200), nullable=True))
    op.add_column("d_transactions", sa.Column("location", sa.String(200), nullable=True))

def downgrade():
    raise RuntimeError("Downgrade disabled to protect data")
