"""add maneuver_candidates table and maneuver_direction enum

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-09-07 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == 'postgresql'

    if is_postgres:
        direction_enum = postgresql.ENUM(
            'along_track_earlier',
            'along_track_later',
            'radial_positive',
            'radial_negative',
            'cross_track_positive',
            'cross_track_negative',
            name='maneuver_direction',
            create_type=True
        )
        direction_enum.create(bind, checkfirst=True)
        risk_enum = postgresql.ENUM('low', 'medium', 'high', 'critical', name='risk_level', create_type=False)
        uuid_type = postgresql.UUID(as_uuid=True)
    else:
        direction_enum = sa.String()
        risk_enum = sa.String()
        uuid_type = sa.UUID()

    op.create_table(
        'maneuver_candidates',
        sa.Column('id', uuid_type, nullable=False),
        sa.Column('alert_id', uuid_type, nullable=False),
        sa.Column('direction', direction_enum, nullable=False),
        sa.Column('delta_v_m_s', sa.Float(), nullable=False),
        sa.Column('delta_v_r_m_s', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('delta_v_t_m_s', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('delta_v_n_m_s', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('burn_epoch', sa.DateTime(timezone=True), nullable=False),
        sa.Column('time_before_tca_hours', sa.Float(), nullable=False),
        sa.Column('resulting_tca', sa.DateTime(timezone=True), nullable=False),
        sa.Column('resulting_miss_distance_m', sa.Float(), nullable=False),
        sa.Column('resulting_miss_distance_km', sa.Float(), nullable=False),
        sa.Column('resulting_relative_velocity_km_s', sa.Float(), nullable=True),
        sa.Column('resulting_probability', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('resulting_risk_level', risk_enum, nullable=False, server_default='low'),
        sa.Column('miss_distance_improvement_m', sa.Float(), nullable=False),
        sa.Column('risk_level_change', sa.String(), nullable=True),
        sa.Column('efficiency_m_per_m_s', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('fuel_cost_proxy_m_s', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['alert_id'], ['conjunction_alerts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_index(
        'idx_maneuver_candidates_alert_id',
        'maneuver_candidates',
        ['alert_id']
    )
    op.create_index(
        'idx_maneuver_candidates_efficiency',
        'maneuver_candidates',
        ['alert_id', sa.text('efficiency_m_per_m_s DESC')]
    )
    op.create_index(
        'idx_maneuver_candidates_burn_epoch',
        'maneuver_candidates',
        ['burn_epoch']
    )
    op.create_index(
        'idx_maneuver_candidates_direction',
        'maneuver_candidates',
        ['direction']
    )


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == 'postgresql'

    op.drop_index('idx_maneuver_candidates_direction', table_name='maneuver_candidates')
    op.drop_index('idx_maneuver_candidates_burn_epoch', table_name='maneuver_candidates')
    op.drop_index('idx_maneuver_candidates_efficiency', table_name='maneuver_candidates')
    op.drop_index('idx_maneuver_candidates_alert_id', table_name='maneuver_candidates')
    op.drop_table('maneuver_candidates')

    if is_postgres:
        op.execute("DROP TYPE IF EXISTS maneuver_direction")
