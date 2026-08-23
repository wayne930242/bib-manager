"""Add academic fields to bibliography entries.

Revision ID: 20260823_02
Revises: 20260822_01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260823_02"
down_revision: Union[str, Sequence[str], None] = "20260822_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("entries") as batch_op:
        batch_op.add_column(sa.Column("academic_fields", sa.JSON(), nullable=True))

    entries = sa.table("entries", sa.column("academic_fields", sa.JSON()))
    op.execute(entries.update().values(academic_fields=["philosophy"]))

    with op.batch_alter_table("entries") as batch_op:
        batch_op.alter_column("academic_fields", nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("entries") as batch_op:
        batch_op.drop_column("academic_fields")
