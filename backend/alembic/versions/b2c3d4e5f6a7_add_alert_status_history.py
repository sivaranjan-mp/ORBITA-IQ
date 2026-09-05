"""add alert_status_history table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-09-05 22:10:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == 'postgresql'

    if is_postgres:
        status_enum = postgresql.ENUM('open', 'monitoring', 'resolved', 'dismissed', name='alert_status', create_type=False)
        uuid_type = postgresql.UUID(as_uuid=True)
    else:
        status_enum = sa.String()
        uuid_type = sa.UUID()

    op.create_table(
        'alert_status_history',
        sa.Column('id', uuid_type, nullable=False),
        sa.Column('alert_id', uuid_type, nullable=False),
        sa.Column('previous_status', status_enum, nullable=False),
        sa.Column('new_status', status_enum, nullable=False),
        sa.Column('changed_by', uuid_type, nullable=True),
        sa.Column('changed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['alert_id'], ['conjunction_alerts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['changed_by'], ['profiles.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_index(
        'idx_alert_status_history_alert_id',
        'alert_status_history',
        ['alert_id', sa.text('changed_at DESC')]
    )
    op.create_index(
        'idx_alert_status_history_changed_at',
        'alert_status_history',
        [sa.text('changed_at DESC')]
    )
    op.create_index(
        'idx_alert_status_history_changed_by',
        'alert_status_history',
        ['changed_by']
    )


def downgrade() -> None:
    op.drop_index('idx_alert_status_history_changed_by', table_name='alert_status_history')
    op.drop_index('idx_alert_status_history_changed_at', table_name='alert_status_history')
    op.drop_index('idx_alert_status_history_alert_id', table_name='alert_status_history')
    op.drop_table('alert_status_history')
