"""add hard_body_radius_m to satellites and catalog_satellites

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-07 11:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('satellites', sa.Column('hard_body_radius_m', sa.Float(), nullable=True))
    op.add_column('catalog_satellites', sa.Column('hard_body_radius_m', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('catalog_satellites', 'hard_body_radius_m')
    op.drop_column('satellites', 'hard_body_radius_m')
