"""catalog schema

Revision ID: 0001
Revises:
Create Date: 2026-11-22 18:46:40.552381

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.create_table(
        "catalog_releases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column(
            "status", sa.String(length=12), server_default="DRAFT", nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(status = 'PUBLISHED') = (published_at IS NOT NULL)",
            name="release_publication_time",
        ),
        sa.CheckConstraint("status IN ('DRAFT','PUBLISHED')", name="release_status"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
        sa.UniqueConstraint("effective_from"),
    )
    op.create_table(
        "categories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("title_ar", sa.String(length=100), nullable=False),
        sa.Column("sort_order", sa.SmallInteger(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
        sa.UniqueConstraint("sort_order"),
    )
    op.create_table(
        "library_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("type", sa.String(length=8), nullable=False),
        sa.Column("title_ar", sa.Text(), nullable=True),
        sa.Column("text_ar", sa.Text(), nullable=False),
        sa.Column("default_target_count", sa.SmallInteger(), nullable=False),
        sa.Column("source_name", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("license_notes", sa.Text(), nullable=True),
        sa.Column(
            "review_status",
            sa.String(length=12),
            server_default="DRAFT",
            nullable=False,
        ),
        sa.Column(
            "status", sa.String(length=12), server_default="DRAFT", nullable=False
        ),
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
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "review_status IN ('DRAFT','VERIFIED')", name="library_review"
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT','ACTIVE','ARCHIVED')", name="library_status"
        ),
        sa.CheckConstraint("type IN ('DHIKR','DUA')", name="library_type"),
        sa.CheckConstraint(
            "default_target_count BETWEEN 1 AND 1000", name="library_target"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "activities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("catalog_release_id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("title_ar", sa.String(length=200), nullable=False),
        sa.Column("sort_order", sa.SmallInteger(), nullable=False),
        sa.Column("points", sa.SmallInteger(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column(
            "schedule_kind",
            sa.String(length=24),
            server_default="DAILY",
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("description_ar", sa.Text(), nullable=True),
        sa.Column("show_details", sa.Boolean(), server_default="false", nullable=False),
        sa.CheckConstraint(
            "(kind = 'FASTING') = (schedule_kind = 'FASTING_DYNAMIC')",
            name="fasting_schedule",
        ),
        sa.CheckConstraint(
            "kind IN ('TOGGLE','ADHKAR_SET','FASTING')", name="activity_kind"
        ),
        sa.CheckConstraint(
            "schedule_kind IN ('DAILY','FASTING_DYNAMIC')", name="activity_schedule"
        ),
        sa.CheckConstraint("points >= 0", name="activity_points"),
        sa.ForeignKeyConstraint(
            ["catalog_release_id"], ["catalog_releases.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["category_id"], ["categories.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "catalog_release_id", "category_id", "sort_order", name="activity_order"
        ),
        sa.UniqueConstraint("catalog_release_id", "code", name="activity_release_code"),
    )
    op.create_table(
        "adhkar_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("activity_id", sa.Uuid(), nullable=False),
        sa.Column("library_entry_id", sa.Uuid(), nullable=True),
        sa.Column("code", sa.String(length=90), nullable=False),
        sa.Column("text_ar", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.SmallInteger(), nullable=False),
        sa.Column("target_count", sa.SmallInteger(), nullable=False),
        sa.Column("source_name", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("license_notes", sa.Text(), nullable=True),
        sa.Column(
            "review_status",
            sa.String(length=12),
            server_default="DRAFT",
            nullable=False,
        ),
        sa.Column(
            "is_score_eligible", sa.Boolean(), server_default="true", nullable=False
        ),
        sa.CheckConstraint("review_status IN ('DRAFT','VERIFIED')", name="item_review"),
        sa.CheckConstraint("target_count BETWEEN 1 AND 1000", name="item_target"),
        sa.ForeignKeyConstraint(
            ["activity_id"], ["activities.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["library_entry_id"], ["library_entries.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("activity_id", "code", name="item_activity_code"),
        sa.UniqueConstraint("activity_id", "sort_order", name="item_order"),
    )

    op.execute(CATALOG_GUARDS)


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_table("adhkar_items")
    op.drop_table("activities")
    op.drop_table("library_entries")
    op.drop_table("categories")
    op.drop_table("catalog_releases")
    op.execute("DROP FUNCTION protect_catalog_definition()")
    op.execute("DROP FUNCTION protect_catalog_release()")


CATALOG_GUARDS = r"""
CREATE FUNCTION protect_catalog_release() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP <> 'INSERT' AND OLD.status = 'PUBLISHED' THEN
        RAISE EXCEPTION 'published release is immutable';
    END IF;
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    IF TG_OP = 'INSERT' AND NEW.status = 'PUBLISHED' THEN
        RAISE EXCEPTION 'create a draft before publication';
    END IF;
    IF NEW.status = 'PUBLISHED' THEN
        IF NOT EXISTS (
            SELECT 1 FROM activities WHERE catalog_release_id = NEW.id AND is_active
        ) THEN
            RAISE EXCEPTION 'release requires active activities';
        END IF;
        IF EXISTS (
            SELECT 1 FROM activities a
            WHERE a.catalog_release_id = NEW.id AND a.is_active
              AND a.kind = 'ADHKAR_SET'
              AND NOT EXISTS (
                SELECT 1 FROM adhkar_items i WHERE i.activity_id = a.id
                  AND i.is_score_eligible AND i.review_status = 'VERIFIED'
              )
        ) THEN
            RAISE EXCEPTION 'set requires verified official scoring items';
        END IF;
        IF EXISTS (
            SELECT 1 FROM adhkar_items i JOIN activities a ON a.id = i.activity_id
            WHERE a.catalog_release_id = NEW.id AND (
                a.kind <> 'ADHKAR_SET' OR i.review_status <> 'VERIFIED'
                OR length(trim(i.text_ar)) = 0
                OR coalesce(length(trim(i.source_name)), 0) = 0
                OR coalesce(length(trim(i.source_url)), 0) = 0
                OR coalesce(length(trim(i.license_notes)), 0) = 0
            )
        ) THEN
            RAISE EXCEPTION 'all bindings require verified text and provenance';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER protect_catalog_release BEFORE INSERT OR UPDATE OR DELETE
ON catalog_releases FOR EACH ROW EXECUTE FUNCTION protect_catalog_release();

CREATE FUNCTION protect_catalog_definition() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    release_ids uuid[];
    old_parent uuid;
    new_parent uuid;
    release_row record;
BEGIN
    IF TG_TABLE_NAME = 'activities' THEN
        IF TG_OP <> 'INSERT' THEN old_parent := OLD.catalog_release_id; END IF;
        IF TG_OP <> 'DELETE' THEN new_parent := NEW.catalog_release_id; END IF;
        release_ids := ARRAY[old_parent, new_parent];
    ELSIF TG_TABLE_NAME = 'adhkar_items' THEN
        IF TG_OP <> 'INSERT' THEN old_parent := OLD.activity_id; END IF;
        IF TG_OP <> 'DELETE' THEN new_parent := NEW.activity_id; END IF;
        -- Lock parent activities before resolving their release, including reparenting.
        PERFORM id FROM activities WHERE id = ANY(ARRAY[old_parent, new_parent])
            ORDER BY id FOR UPDATE;
        SELECT array_agg(catalog_release_id) INTO release_ids
            FROM activities WHERE id = ANY(ARRAY[old_parent, new_parent]);
    ELSE
        IF TG_OP <> 'INSERT' THEN old_parent := OLD.id; END IF;
        IF TG_OP <> 'DELETE' THEN new_parent := NEW.id; END IF;
        SELECT array_agg(catalog_release_id) INTO release_ids
            FROM activities WHERE category_id = ANY(ARRAY[old_parent, new_parent]);
    END IF;
    -- Serialize changes with publication; inspect both old and new release on moves.
    FOR release_row IN SELECT status FROM catalog_releases
        WHERE id = ANY(release_ids) ORDER BY id FOR UPDATE
    LOOP
        IF release_row.status = 'PUBLISHED' THEN
            RAISE EXCEPTION 'published catalog definition is immutable';
        END IF;
    END LOOP;
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER protect_activity BEFORE INSERT OR UPDATE OR DELETE
ON activities FOR EACH ROW EXECUTE FUNCTION protect_catalog_definition();
CREATE TRIGGER protect_item BEFORE INSERT OR UPDATE OR DELETE
ON adhkar_items FOR EACH ROW EXECUTE FUNCTION protect_catalog_definition();
CREATE TRIGGER protect_category BEFORE UPDATE OR DELETE
ON categories FOR EACH ROW EXECUTE FUNCTION protect_catalog_definition();
"""
