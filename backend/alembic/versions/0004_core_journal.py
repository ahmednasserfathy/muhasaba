"""Daily journal snapshots and idempotent mutation receipts."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "journal_days",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("catalog_release_id", sa.Uuid(), nullable=False),
        sa.Column("timezone_at_creation", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["catalog_release_id"], ["catalog_releases.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "local_date", name="journal_user_date"),
    )
    op.create_table(
        "journal_activity_states",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("journal_day_id", sa.Uuid(), nullable=False),
        sa.Column("activity_id", sa.Uuid(), nullable=False),
        sa.Column("state", sa.String(length=12), nullable=False),
        sa.Column("row_version", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "state IN ('PENDING','COMPLETED','EXCLUDED')", name="journal_state"
        ),
        sa.CheckConstraint("row_version >= 1", name="activity_version"),
        sa.ForeignKeyConstraint(
            ["activity_id"], ["activities.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["journal_day_id"], ["journal_days.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "journal_day_id", "activity_id", name="journal_day_activity"
        ),
    )
    op.create_table(
        "journal_adhkar_counts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("journal_day_id", sa.Uuid(), nullable=False),
        sa.Column("activity_id", sa.Uuid(), nullable=False),
        sa.Column("adhkar_item_id", sa.Uuid(), nullable=False),
        sa.Column("item_code_snapshot", sa.String(length=90), nullable=False),
        sa.Column("text_ar_snapshot", sa.Text(), nullable=False),
        sa.Column("target_count_snapshot", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=12), nullable=False),
        sa.Column("is_score_eligible_snapshot", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("completed_count", sa.Integer(), nullable=False),
        sa.Column("row_version", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("source_type = 'OFFICIAL'", name="snapshot_source"),
        sa.CheckConstraint(
            "completed_count BETWEEN 0 AND target_count_snapshot", name="snapshot_count"
        ),
        sa.CheckConstraint("row_version >= 0", name="count_version"),
        sa.CheckConstraint(
            "target_count_snapshot BETWEEN 1 AND 1000", name="snapshot_target"
        ),
        sa.ForeignKeyConstraint(
            ["activity_id"], ["activities.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["adhkar_item_id"], ["adhkar_items.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["journal_day_id"], ["journal_days.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "journal_day_id", "adhkar_item_id", name="journal_day_item"
        ),
    )
    op.create_table(
        "mutation_receipts",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "result_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("user_id", "id"),
    )


def downgrade() -> None:
    op.drop_table("mutation_receipts")
    op.drop_table("journal_adhkar_counts")
    op.drop_table("journal_activity_states")
    op.drop_table("journal_days")
