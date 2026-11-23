"""Fasting plans, regional calendars and stable journal eligibility."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fasting_overrides",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("mode", sa.String(length=8), nullable=False),
        sa.Column("fast_type", sa.String(length=16), nullable=True),
        sa.Column("row_version", sa.Integer(), nullable=False),
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
        sa.CheckConstraint(
            "fast_type IN ('VOLUNTARY','MAKEUP','OTHER')", name="fasting_type"
        ),
        sa.CheckConstraint(
            "mode = 'ADD' OR fast_type IS NULL", name="fasting_type_only_add"
        ),
        sa.CheckConstraint("mode IN ('DEFAULT','ADD','SKIP')", name="fasting_mode"),
        sa.CheckConstraint("row_version >= 1", name="fasting_version"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "local_date", name="fasting_user_date"),
    )
    op.create_table(
        "calendar_periods",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("region_key", sa.String(length=32), nullable=False),
        sa.Column("period_kind", sa.String(length=20), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("confirmation_status", sa.String(length=12), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "confirmation_status <> 'CONFIRMED' OR "
            "(source_url IS NOT NULL AND length(trim(source_url)) > 0)",
            name="calendar_confirmed_source",
        ),
        sa.CheckConstraint(
            "confirmation_status IN ('PROVISIONAL','CONFIRMED')",
            name="calendar_confirmation",
        ),
        sa.CheckConstraint("period_kind = 'RAMADAN'", name="calendar_kind"),
        sa.CheckConstraint("end_date >= start_date", name="calendar_dates"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "region_key", "period_kind", "start_date", name="calendar_region_start"
        ),
    )
    op.add_column(
        "journal_days",
        sa.Column(
            "fasting_baseline", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )
    # Preserve PR-03 weekly-only scoring on already materialized journals.
    op.execute("""
        UPDATE journal_days AS d SET fasting_baseline = jsonb_build_object(
            'regionKey', u.region_key,
            'baseReason', CASE WHEN EXTRACT(ISODOW FROM d.local_date) IN (1,4)
                THEN 'WEEKLY' ELSE 'UNPLANNED' END,
            'calendarStatus', 'UNAVAILABLE', 'sourceUrl', NULL)
        FROM users AS u WHERE u.id = d.user_id
    """)


def downgrade() -> None:
    op.drop_column("journal_days", "fasting_baseline")
    op.drop_table("calendar_periods")
    op.drop_table("fasting_overrides")
