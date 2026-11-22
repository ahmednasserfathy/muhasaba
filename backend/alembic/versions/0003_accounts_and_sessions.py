"""accounts and sessions

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-22 21:56:00.869799

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email_normalized", sa.String(length=320), nullable=True),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column(
            "registration_source",
            sa.String(length=12),
            server_default="NATIVE",
            nullable=False,
        ),
        sa.Column("role", sa.String(length=8), server_default="USER", nullable=False),
        sa.Column(
            "timezone",
            sa.String(length=64),
            server_default="Africa/Cairo",
            nullable=False,
        ),
        sa.Column(
            "locale", sa.String(length=16), server_default="ar-EG", nullable=False
        ),
        sa.Column(
            "region_key", sa.String(length=32), server_default="EG", nullable=False
        ),
        sa.Column("tracking_start_date", sa.Date(), nullable=False),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "registration_source <> 'NATIVE' OR "
            "(email_normalized IS NOT NULL AND password_hash IS NOT NULL)",
            name="native_credentials",
        ),
        sa.CheckConstraint(
            "registration_source IN ('NATIVE','IMPORTED')", name="user_source"
        ),
        sa.CheckConstraint("role IN ('USER','ADMIN')", name="user_role"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email_normalized"),
    )
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("access_token_hash", sa.String(length=64), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=64), nullable=False),
        sa.Column("access_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("access_token_hash"),
        sa.UniqueConstraint("refresh_token_hash"),
    )
    op.create_index(
        op.f("ix_auth_sessions_user_id"), "auth_sessions", ["user_id"], unique=False
    )
    op.create_table(
        "external_identities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("source_system", sa.String(length=60), nullable=False),
        sa.Column("external_subject", sa.String(length=255), nullable=False),
        sa.Column(
            "link_status",
            sa.String(length=12),
            server_default="PENDING",
            nullable=False,
        ),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "link_status IN ('PENDING','VERIFIED','REVOKED')", name="identity_status"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_system", "external_subject", name="external_source_subject"
        ),
    )
    op.create_index(
        op.f("ix_external_identities_user_id"),
        "external_identities",
        ["user_id"],
        unique=False,
    )
    op.create_table(
        "user_settings",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("theme", sa.String(length=12), server_default="DARK", nullable=False),
        sa.Column(
            "reminder_settings",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "quiet_hours", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.add_column(
        "library_entries", sa.Column("created_by_admin", sa.Uuid(), nullable=True)
    )
    op.create_foreign_key(
        "fk_library_created_by_admin",
        "library_entries",
        "users",
        ["created_by_admin"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "fk_library_created_by_admin", "library_entries", type_="foreignkey"
    )
    op.drop_column("library_entries", "created_by_admin")
    op.drop_table("user_settings")
    op.drop_index(
        op.f("ix_external_identities_user_id"), table_name="external_identities"
    )
    op.drop_table("external_identities")
    op.drop_index(op.f("ix_auth_sessions_user_id"), table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_table("users")
