"""Private effective plans and editorial versions; preserve official snapshots."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_custom_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("activity_code", sa.String(80), nullable=False),
        sa.Column("type", sa.String(8), nullable=False),
        sa.Column("text_ar", sa.Text(), nullable=False),
        sa.Column("target_count", sa.Integer(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("type IN ('DHIKR','DUA')", name="custom_type"),
        sa.CheckConstraint("target_count BETWEEN 1 AND 1000", name="custom_target"),
    )
    op.create_index("ix_user_custom_items_user_id", "user_custom_items", ["user_id"])
    op.create_table(
        "user_group_plans",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("activity_code", sa.String(80), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("row_version", sa.Integer(), nullable=False),
        sa.Column("definition", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "user_id", "activity_code", "effective_from", name="plan_user_group_date"
        ),
        sa.CheckConstraint("row_version >= 1", name="plan_version"),
    )
    op.add_column("journal_days", sa.Column("group_plans", postgresql.JSONB()))
    op.execute("UPDATE journal_days SET group_plans = '{}'::jsonb")
    op.add_column("journal_adhkar_counts", sa.Column("custom_item_id", sa.Uuid()))
    op.create_foreign_key(
        None,
        "journal_adhkar_counts",
        "user_custom_items",
        ["custom_item_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.alter_column("journal_adhkar_counts", "adhkar_item_id", nullable=True)
    op.drop_constraint("snapshot_source", "journal_adhkar_counts", type_="check")
    op.create_check_constraint(
        "snapshot_source",
        "journal_adhkar_counts",
        "(source_type = 'OFFICIAL' AND adhkar_item_id IS NOT NULL "
        "AND custom_item_id IS NULL) OR (source_type = 'PERSONAL' "
        "AND adhkar_item_id IS NULL AND custom_item_id IS NOT NULL "
        "AND NOT is_score_eligible_snapshot)",
    )
    op.create_unique_constraint(
        "journal_day_custom_item",
        "journal_adhkar_counts",
        ["journal_day_id", "activity_id", "custom_item_id"],
    )
    for table in ["catalog_releases", "library_entries"]:
        op.add_column(
            table,
            sa.Column("row_version", sa.Integer(), server_default="1", nullable=False),
        )
    op.add_column(
        "library_entries", sa.Column("reviewed_at", sa.DateTime(timezone=True))
    )
    op.add_column("library_entries", sa.Column("reviewed_by", sa.Uuid()))
    op.create_foreign_key(
        None, "library_entries", "users", ["reviewed_by"], ["id"], ondelete="RESTRICT"
    )


def downgrade():
    op.drop_column("library_entries", "reviewed_by")
    op.drop_column("library_entries", "reviewed_at")
    for table in ["catalog_releases", "library_entries"]:
        op.drop_column(table, "row_version")
    op.execute("DELETE FROM journal_adhkar_counts WHERE source_type = 'PERSONAL'")
    op.drop_constraint(
        "journal_day_custom_item", "journal_adhkar_counts", type_="unique"
    )
    op.drop_constraint("snapshot_source", "journal_adhkar_counts", type_="check")
    op.drop_column("journal_adhkar_counts", "custom_item_id")
    op.alter_column("journal_adhkar_counts", "adhkar_item_id", nullable=False)
    op.create_check_constraint(
        "snapshot_source", "journal_adhkar_counts", "source_type = 'OFFICIAL'"
    )
    op.drop_column("journal_days", "group_plans")
    op.drop_table("user_group_plans")
    op.drop_table("user_custom_items")
