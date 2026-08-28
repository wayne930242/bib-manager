"""Add private source-asset metadata.

Revision ID: 20260828_03
Revises: 20260823_02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260828_03"
down_revision: str | Sequence[str] | None = "20260823_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "source_assets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("entry_key", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=50), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("media_type", sa.String(length=255), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("byte_size > 0", name="ck_source_asset_byte_size"),
        sa.CheckConstraint(
            "status IN ('pending', 'ready', 'failed')",
            name="ck_source_asset_status",
        ),
        sa.ForeignKeyConstraint(["entry_key"], ["entries.key"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entry_key", "sha256", name="uq_source_asset_entry_sha256"),
        sa.UniqueConstraint("storage_key", name="uq_source_asset_storage_key"),
    )
    op.create_index(
        "ix_source_assets_entry_status",
        "source_assets",
        ["entry_key", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_source_assets_entry_status", table_name="source_assets")
    op.drop_table("source_assets")
