"""add relative state, ric decomposition, and encounter geometry to conjunction_alerts

Revision ID: b1c2d3e4f5a6
Revises: a1b2c3d4e5f6
Create Date: 2026-09-07 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add relative state vectors
    op.add_column('conjunction_alerts', sa.Column('relative_position_x', sa.Float(), nullable=True))
    op.add_column('conjunction_alerts', sa.Column('relative_position_y', sa.Float(), nullable=True))
    op.add_column('conjunction_alerts', sa.Column('relative_position_z', sa.Float(), nullable=True))
    op.add_column('conjunction_alerts', sa.Column('relative_velocity_x', sa.Float(), nullable=True))
    op.add_column('conjunction_alerts', sa.Column('relative_velocity_y', sa.Float(), nullable=True))
    op.add_column('conjunction_alerts', sa.Column('relative_velocity_z', sa.Float(), nullable=True))

    # Add RIC frame separation components
    op.add_column('conjunction_alerts', sa.Column('radial_separation_km', sa.Float(), nullable=True))
    op.add_column('conjunction_alerts', sa.Column('along_track_separation_km', sa.Float(), nullable=True))
    op.add_column('conjunction_alerts', sa.Column('cross_track_separation_km', sa.Float(), nullable=True))

    # Add encounter geometry angles and classification label
    op.add_column('conjunction_alerts', sa.Column('relative_velocity_angle_deg', sa.Float(), nullable=True))
    op.add_column('conjunction_alerts', sa.Column('relative_inclination_deg', sa.Float(), nullable=True))
    op.add_column('conjunction_alerts', sa.Column('encounter_geometry', sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column('conjunction_alerts', 'encounter_geometry')
    op.drop_column('conjunction_alerts', 'relative_inclination_deg')
    op.drop_column('conjunction_alerts', 'relative_velocity_angle_deg')
    op.drop_column('conjunction_alerts', 'cross_track_separation_km')
    op.drop_column('conjunction_alerts', 'along_track_separation_km')
    op.drop_column('conjunction_alerts', 'radial_separation_km')
    op.drop_column('conjunction_alerts', 'relative_velocity_z')
    op.drop_column('conjunction_alerts', 'relative_velocity_y')
    op.drop_column('conjunction_alerts', 'relative_velocity_x')
    op.drop_column('conjunction_alerts', 'relative_position_z')
    op.drop_column('conjunction_alerts', 'relative_position_y')
    op.drop_column('conjunction_alerts', 'relative_position_x')
