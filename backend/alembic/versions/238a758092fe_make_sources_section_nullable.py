"""make sources section nullable

Revision ID: 238a758092fe
Revises: f16da429c593
Create Date: 2026-09-04 00:54:01.967900

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '238a758092fe'
down_revision: Union[str, None] = 'f16da429c593'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('sources', schema=None) as batch_op:
        batch_op.alter_column('section',
               existing_type=sa.VARCHAR(length=255),
               nullable=True)

def downgrade() -> None:
    with op.batch_alter_table('sources', schema=None) as batch_op:
        batch_op.alter_column('section',
               existing_type=sa.VARCHAR(length=255),
               nullable=False)
