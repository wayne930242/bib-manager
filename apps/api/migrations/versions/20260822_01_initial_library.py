"""Create the database-first research library schema."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260822_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "library_settings",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )
    op.create_table(
        "entries",
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("entry_type", sa.String(length=50), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("author", sa.Text(), nullable=False),
        sa.Column("year", sa.String(length=50), nullable=False),
        sa.Column("journal", sa.Text(), nullable=False),
        sa.Column("publisher", sa.Text(), nullable=False),
        sa.Column("fields", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )
    op.create_table(
        "blog_posts",
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("slug"),
    )
    op.create_table(
        "entry_summaries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("entry_key", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=50), nullable=False),
        sa.Column("language", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["entry_key"], ["entries.key"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entry_key", "kind", "language", name="uq_entry_summary"),
    )
    op.create_table(
        "entry_blog_posts",
        sa.Column("entry_key", sa.String(length=255), nullable=False),
        sa.Column("blog_slug", sa.String(length=255), nullable=False),
        sa.Column("relation_type", sa.String(length=50), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["blog_slug"], ["blog_posts.slug"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entry_key"], ["entries.key"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("entry_key", "blog_slug"),
    )


def downgrade() -> None:
    op.drop_table("entry_blog_posts")
    op.drop_table("entry_summaries")
    op.drop_table("blog_posts")
    op.drop_table("entries")
    op.drop_table("library_settings")
