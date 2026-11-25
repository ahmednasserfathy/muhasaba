"""Install the initial sourced catalog on an empty staging deployment."""

import argparse
import csv
from collections import defaultdict
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.db import get_engine
from app.modules.auth import models as auth_models  # noqa: F401
from app.modules.catalog.models import (
    Activity,
    AdhkarItem,
    CatalogRelease,
    LibraryEntry,
)

RELEASE = "staging-adhkar-v1"
COLLECTIONS = {
    "bukhari": "صحيح البخاري",
    "muslim": "صحيح مسلم",
    "abudawud": "سنن أبي داود",
}
AFTER_PRAYER = [
    f"{prayer}_after_dhikr" for prayer in ("fajr", "dhuhr", "asr", "maghrib", "isha")
]


def install(db: Session, effective_from: date) -> str:
    db.execute(text("LOCK TABLE catalog_releases IN SHARE ROW EXCLUSIVE MODE"))
    published = db.scalars(
        select(CatalogRelease).where(CatalogRelease.status == "PUBLISHED")
    ).all()
    if len(published) == 1 and published[0].code == RELEASE:
        return f"Already published: {RELEASE} since {published[0].effective_from}"
    if published:
        raise ValueError("Initial catalog can only be installed before any publication")

    reference = db.scalar(
        select(CatalogRelease).where(CatalogRelease.code == "2026-11-19-reference")
    )
    if reference is None or len(reference.activities) != 34:
        raise ValueError("Expected the 34-card reference catalog")
    by_group = defaultdict(list)
    now = datetime.now(UTC)
    with Path(__file__).with_name("staging_adhkar.csv").open(encoding="utf-8") as file:
        for record in csv.DictReader(file):
            collection, number = record["reference"].split(":")
            source = LibraryEntry(
                code=record["code"],
                type=record["type"],
                title_ar=record["title_ar"],
                text_ar=record["text_ar"],
                default_target_count=int(record["target_count"]),
                source_name=f"{COLLECTIONS[collection]} {number}",
                source_url=f"https://sunnah.com/{record['reference']}",
                license_notes="صيغة عربية تراثية، دون ترجمة أو تعليق أو تسجيل حديث.",
                reviewed_at=now,
                review_status="VERIFIED",
                status="ACTIVE",
            )
            db.add(source)
            for group in record["groups"].split():
                for code in AFTER_PRAYER if group == "after_prayer" else [group]:
                    by_group[code].append(source)

    expected = {card.code for card in reference.activities if card.kind == "ADHKAR_SET"}
    if set(by_group) != expected:
        raise ValueError("Sourced items must cover exactly the reference adhkar groups")

    release = CatalogRelease(code=RELEASE, effective_from=effective_from)
    db.add(release)
    db.flush()
    for old in reference.activities:
        card = Activity(
            catalog_release_id=release.id,
            category_id=old.category_id,
            code=old.code,
            title_ar=old.title_ar,
            sort_order=old.sort_order,
            points=old.points,
            kind=old.kind,
            schedule_kind=old.schedule_kind,
            is_active=old.is_active,
            description_ar=old.description_ar,
            show_details=old.show_details,
        )
        db.add(card)
        db.flush()
        for index, source in enumerate(by_group.get(card.code, []), start=1):
            db.add(
                AdhkarItem(
                    activity_id=card.id,
                    library_entry_id=source.id,
                    code=source.code,
                    text_ar=source.text_ar,
                    sort_order=index,
                    target_count=source.default_target_count,
                    source_name=source.source_name,
                    source_url=source.source_url,
                    license_notes=source.license_notes,
                    review_status="VERIFIED",
                )
            )
    db.flush()
    release.status = "PUBLISHED"
    release.published_at = now
    db.flush()
    return (
        f"{RELEASE}: {len(reference.activities)} activities, {len(expected)} groups, "
        f"{sum(map(len, by_group.values()))} bindings, effective {effective_from}"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("effective_from", type=date.fromisoformat)
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    engine = get_engine()
    if (
        engine.url.get_backend_name() != "postgresql"
        or engine.url.database != "muhasaba"
    ):
        raise SystemExit("Select the Muhasaba staging PostgreSQL database")
    with Session(engine) as db:
        result = install(db, args.effective_from)
        if args.publish:
            db.commit()
        else:
            db.rollback()
    print(f"{'Publish' if args.publish else 'Dry run (rolled back)'}: {result}")


if __name__ == "__main__":
    main()
