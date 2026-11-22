import csv
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from conftest import migration_config
from sqlalchemy import delete, func, inspect, select, update
from sqlalchemy.exc import DBAPIError

from alembic import command
from app.modules.catalog.models import (
    Activity,
    AdhkarItem,
    CatalogRelease,
    Category,
    LibraryEntry,
)
from app.modules.catalog.scoring import ItemProgress, score_card, score_day


def draft(session, effective=date(2026, 12, 1), points=2):
    release = CatalogRelease(code=str(uuid4()), effective_from=effective)
    session.add(release)
    session.flush()
    category = session.scalar(select(Category).where(Category.code == "DHIKR"))
    activity = Activity(
        catalog_release_id=release.id,
        category_id=category.id,
        code="test_set",
        title_ar="مجموعة اختبار فقط",
        sort_order=1,
        points=points,
        kind="ADHKAR_SET",
        show_details=True,
    )
    session.add(activity)
    session.flush()
    library = LibraryEntry(
        code=str(uuid4()),
        type="DHIKR",
        text_ar="نص اختبار فقط",
        default_target_count=1,
        review_status="VERIFIED",
        status="ACTIVE",
    )
    session.add(library)
    session.flush()
    item = AdhkarItem(
        activity_id=activity.id,
        library_entry_id=library.id,
        code="test_item",
        text_ar="نص اختبار فقط وليس محتوى دينيًا",
        sort_order=1,
        target_count=3,
        review_status="VERIFIED",
        source_name="Synthetic test fixture",
        source_url="https://example.test/fixture",
        license_notes="Test-only fixture",
    )
    session.add(item)
    session.flush()
    return release, activity, item, library


def publish(session, release):
    release.status = "PUBLISHED"
    release.published_at = datetime.now(UTC)
    session.flush()


def test_reference_seed_and_coverage(session, client):
    rows = list(
        csv.DictReader(
            (
                Path(__file__).parents[3]
                / "docs/blueprint/seed/catalog_reference_34.csv"
            ).open()
        )
    )
    release = session.scalar(
        select(CatalogRelease).where(CatalogRelease.code == "2026-11-19-reference")
    )
    assert release.status == "DRAFT"
    cards = session.scalars(
        select(Activity).where(Activity.catalog_release_id == release.id)
    ).all()
    assert len(cards) == 34
    assert session.scalar(select(func.count()).select_from(Category)) == 8
    assert {card.code: card.points for card in cards} == {
        row["activity_code"]: int(row["points_observed"]) for row in rows
    }
    coverage = list(
        csv.DictReader(
            (
                Path(__file__).parents[3] / "docs/blueprint/seed/adhkar_coverage.csv"
            ).open()
        )
    )
    assert {card.code for card in cards if card.kind == "ADHKAR_SET"} == {
        row["activity_code"] for row in coverage
    }
    assert session.scalar(select(func.count()).select_from(AdhkarItem)) == 0
    assert session.scalar(select(func.count()).select_from(LibraryEntry)) == 0
    for fasting, expected in [(True, 74), (False, 69)]:
        scores = tuple(
            score_card(
                card.points,
                card.kind,
                eligible=fasting or card.kind != "FASTING",
                items=(ItemProgress("synthetic", 1),)
                if card.kind == "ADHKAR_SET"
                else (),
            )
            for card in cards
        )
        assert score_day(scores).possible == expected
    assert client.get("/api/v1/catalog?date=2026-11-19").status_code == 404
    with pytest.raises(DBAPIError, match="requires verified"):
        with session.begin_nested():
            publish(session, release)


def test_api_date_selection_and_snapshot_survives_library_edit(session, client):
    first, activity, item, library = draft(session)
    publish(session, first)
    original = client.get("/api/v1/catalog?date=2026-12-01")
    assert original.status_code == 200
    payload = original.json()
    assert payload["release"] == first.code
    response_item = payload["categories"][0]["activities"][0]["items"][0]
    assert response_item["sourceType"] == "OFFICIAL"
    assert response_item["isScoreEligible"] is True
    assert response_item["targetCount"] == 3
    assert response_item["reviewStatus"] == "VERIFIED"
    library.text_ar = "تعديل مصدر الاختبار"
    library.status = "ARCHIVED"
    session.flush()
    newer, _, _, _ = draft(session, date(2026, 12, 5), points=4)
    publish(session, newer)
    draft(session, date(2026, 12, 6))  # A later draft must never shadow a release.
    assert client.get("/api/v1/catalog?date=2026-12-04").json() == payload
    assert client.get("/api/v1/catalog?date=2026-12-06").json()["release"] == newer.code
    assert client.get("/api/v1/catalog?date=2026-11-30").status_code == 404
    assert client.get("/api/v1/catalog?date=invalid").status_code == 422
    assert client.get("/api/v1/catalog").status_code == 422


@pytest.mark.parametrize(
    "field,value",
    [
        ("review_status", "DRAFT"),
        ("is_score_eligible", False),
        ("source_name", None),
        ("source_url", ""),
        ("license_notes", " "),
        ("text_ar", " "),
    ],
)
def test_publication_rejects_unverified_or_incomplete_content(session, field, value):
    release, _, item, _ = draft(session)
    setattr(item, field, value)
    session.flush()
    with pytest.raises(DBAPIError):
        with session.begin_nested():
            publish(session, release)


def test_published_definitions_reject_update_delete_insert_and_moves(session):
    release, activity, item, _ = draft(session)
    other, other_activity, other_item, _ = draft(session, date(2026, 12, 5))
    publish(session, release)
    statements = [
        update(CatalogRelease)
        .where(CatalogRelease.id == release.id)
        .values(status="DRAFT"),
        delete(CatalogRelease).where(CatalogRelease.id == release.id),
        update(Activity).where(Activity.id == activity.id).values(points=99),
        update(Activity)
        .where(Activity.id == activity.id)
        .values(catalog_release_id=other.id),
        delete(Activity).where(Activity.id == activity.id),
        update(AdhkarItem).where(AdhkarItem.id == item.id).values(target_count=9),
        update(AdhkarItem)
        .where(AdhkarItem.id == item.id)
        .values(activity_id=other_activity.id),
        update(AdhkarItem)
        .where(AdhkarItem.id == other_item.id)
        .values(activity_id=activity.id),
        delete(AdhkarItem).where(AdhkarItem.id == item.id),
        update(Category)
        .where(Category.id == activity.category_id)
        .values(title_ar="تغيير"),
    ]
    for statement in statements:
        with pytest.raises(DBAPIError, match="immutable"):
            with session.begin_nested():
                session.execute(statement)
    with pytest.raises(DBAPIError, match="immutable"):
        with session.begin_nested():
            session.add(
                AdhkarItem(
                    activity_id=activity.id,
                    code="extra",
                    text_ar="اختبار",
                    sort_order=2,
                    target_count=1,
                )
            )
            session.flush()


@pytest.mark.parametrize(
    "field,value",
    [("target_count", 0), ("target_count", 1001), ("review_status", "BAD")],
)
def test_database_item_constraints(session, field, value):
    _, _, item, _ = draft(session)
    with pytest.raises(DBAPIError):
        with session.begin_nested():
            setattr(item, field, value)
            session.flush()


def test_duplicate_binding_rejected(session):
    _, activity, item, _ = draft(session)
    with pytest.raises(DBAPIError):
        with session.begin_nested():
            session.add(
                AdhkarItem(
                    activity_id=activity.id,
                    code=item.code,
                    text_ar="اختبار",
                    sort_order=2,
                    target_count=1,
                )
            )
            session.flush()


def test_migration_roundtrip_and_metadata_match(migrated_engine):
    with migrated_engine.begin() as connection:
        config = migration_config(connection)
        command.check(config)
        command.downgrade(config, "base")
        assert inspect(connection).get_table_names() == ["alembic_version"]
        command.upgrade(config, "head")
        assert connection.scalar(select(func.count()).select_from(Activity)) == 34
        command.check(config)


def test_api_orders_categories_activities_items_and_excludes_inactive(session, client):
    release, activity, _, _ = draft(session)
    fajr = session.scalar(select(Category).where(Category.code == "FAJR"))
    session.add_all(
        [
            Activity(
                catalog_release_id=release.id,
                category_id=fajr.id,
                code="later",
                title_ar="اختبار",
                sort_order=2,
                points=2,
                kind="TOGGLE",
            ),
            Activity(
                catalog_release_id=release.id,
                category_id=fajr.id,
                code="first",
                title_ar="اختبار",
                sort_order=1,
                points=2,
                kind="TOGGLE",
            ),
            Activity(
                catalog_release_id=release.id,
                category_id=fajr.id,
                code="inactive",
                title_ar="اختبار",
                sort_order=3,
                points=2,
                kind="TOGGLE",
                is_active=False,
            ),
            AdhkarItem(
                activity_id=activity.id,
                code="second",
                text_ar="اختبار فقط",
                sort_order=2,
                target_count=1,
                review_status="VERIFIED",
                source_name="Test",
                source_url="https://example.test/fixture",
                license_notes="Synthetic test fixture",
                is_score_eligible=False,
            ),
        ]
    )
    session.flush()
    publish(session, release)
    categories = client.get("/api/v1/catalog?date=2026-12-01").json()["categories"]
    assert [category["code"] for category in categories] == ["FAJR", "DHIKR"]
    assert [card["code"] for card in categories[0]["activities"]] == ["first", "later"]
    response_items = categories[1]["activities"][0]["items"]
    assert [item["code"] for item in response_items] == ["test_item", "second"]
    assert response_items[1]["isScoreEligible"] is False


def test_empty_release_and_direct_publication_rejected(session):
    empty = CatalogRelease(code=str(uuid4()), effective_from=date(2026, 12, 1))
    session.add(empty)
    session.flush()
    with pytest.raises(DBAPIError, match="requires active"):
        with session.begin_nested():
            publish(session, empty)
    with pytest.raises(DBAPIError, match="create a draft"):
        with session.begin_nested():
            session.add(
                CatalogRelease(
                    code=str(uuid4()),
                    effective_from=date(2026, 12, 2),
                    status="PUBLISHED",
                    published_at=datetime.now(UTC),
                )
            )
            session.flush()


def test_toggle_cannot_publish_with_adhkar_bindings(session):
    release, activity, _, _ = draft(session)
    activity.kind = "TOGGLE"
    session.flush()
    with pytest.raises(DBAPIError, match="all bindings"):
        with session.begin_nested():
            publish(session, release)
