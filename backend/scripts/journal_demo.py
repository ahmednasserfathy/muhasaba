"""Explicit synthetic demo for a disposable *_test database; never real content."""

import os
from datetime import UTC, date, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.modules.auth import models as auth_models  # noqa: F401
from app.modules.catalog.models import Activity, AdhkarItem, CatalogRelease


def create_demo(db: Session, effective: date):
    existing = db.scalar(
        select(CatalogRelease).where(CatalogRelease.code == "demo-synthetic-pr03")
    )
    if existing:
        return existing
    release = CatalogRelease(code="demo-synthetic-pr03", effective_from=effective)
    db.add(release)
    db.flush()
    reference = db.scalar(
        select(CatalogRelease).where(CatalogRelease.code == "2026-11-19-reference")
    )
    if reference is None:
        raise ValueError("Apply migrations first")
    for source in reference.activities:
        activity = Activity(
            catalog_release_id=release.id,
            category_id=source.category_id,
            code=source.code,
            title_ar="اختبار — " + source.title_ar,
            sort_order=source.sort_order,
            points=source.points,
            kind=source.kind,
            schedule_kind=source.schedule_kind,
            is_active=source.is_active,
            show_details=source.show_details,
        )
        db.add(activity)
        db.flush()
        if activity.kind == "ADHKAR_SET":
            for index, target in [(1, 1), (2, 3)]:
                db.add(
                    AdhkarItem(
                        activity_id=activity.id,
                        code=f"demo_{index}",
                        text_ar=(
                            f"عنصر تجربة {index} — "
                            "هذه بيانات اختبار وليست أذكارًا معتمدة."
                        ),
                        sort_order=index,
                        target_count=target,
                        review_status="VERIFIED",
                        source_name="Synthetic software test fixture",
                        source_url="https://example.test/muhasaba-demo",
                        license_notes="Synthetic UI test text, not religious content",
                    )
                )
    db.flush()
    release.status = "PUBLISHED"
    release.published_at = datetime.now(UTC)
    db.flush()
    return release


def main():
    url = make_url(os.environ["DATABASE_URL"])
    if url.get_backend_name() != "postgresql" or not (url.database or "").endswith(
        "_test"
    ):
        raise SystemExit(
            "Demo requires an explicitly selected disposable PostgreSQL *_test database"
        )
    engine = create_engine(url)
    with Session(engine) as db:
        create_demo(db, date.today())
        db.commit()
    engine.dispose()
    print("Synthetic 34-card demo ready. This is not approved religious content.")


if __name__ == "__main__":
    main()
