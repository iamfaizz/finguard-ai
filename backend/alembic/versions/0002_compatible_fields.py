"""Add C-compatible fields without replacing existing Member D tables."""
from alembic import op
import sqlalchemy as sa
revision = '0002_compatible'
down_revision = '0001_initial'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('d_users', sa.Column('full_name', sa.String(160)))
    op.add_column('d_users', sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()))
    for table in ('d_users', 'd_goals', 'd_chat_messages'):
        # Batch mode supports SQLite's restriction on adding dynamic defaults.
        with op.batch_alter_table(table, recreate='auto') as batch:
            if op.get_bind().dialect.name == 'sqlite':
                batch.add_column(sa.Column('created_at', sa.DateTime(timezone=True), nullable=True))
        if op.get_bind().dialect.name == 'sqlite':
            op.execute(sa.text(f'UPDATE {table} SET created_at=CURRENT_TIMESTAMP'))
            with op.batch_alter_table(table) as batch:
                batch.alter_column('created_at', existing_type=sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
        else:
            op.add_column(table, sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    for name, typ in [('description',sa.Text()),('channel',sa.String(40)),('reference_id',sa.String(120)),('fraud_label',sa.Boolean()),('risk_level',sa.String(30)),('fraud_reasons',sa.JSON()),('model_version',sa.String(100))]:
        op.add_column('d_transactions', sa.Column(name, typ))

def downgrade():
    raise RuntimeError('Downgrade disabled to protect data')
