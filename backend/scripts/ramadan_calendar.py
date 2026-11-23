"""Operator-only entry of reviewed regional dates; no estimated Ramadan seed."""

import argparse
import os
from datetime import date
from urllib.parse import urlsplit

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.modules.fasting.models import CalendarPeriod


def configure(db, region, start, end, status, source):
    if (
        not region.strip()
        or len(region) > 32
        or end < start
        or (end - start).days >= 31
    ):
        raise ValueError("Use a region and an ordered period of at most 31 days")
    if status not in ("PROVISIONAL", "CONFIRMED"):
        raise ValueError("Unknown confirmation status")
    if source and (
        len(source) > 2048
        or urlsplit(source).scheme != "https"
        or not urlsplit(source).hostname
    ):
        raise ValueError("Source must be an HTTPS URL")
    if status == "CONFIRMED" and not source:
        raise ValueError("Confirmed dates require a reviewed source URL")
    # Serialize operator edits and reject ambiguous overlapping date ranges.
    db.execute(text("LOCK TABLE calendar_periods IN SHARE ROW EXCLUSIVE MODE"))
    row = db.scalar(
        select(CalendarPeriod).where(
            CalendarPeriod.region_key == region, CalendarPeriod.start_date == start
        )
    )
    overlap = db.scalar(
        select(CalendarPeriod).where(
            CalendarPeriod.region_key == region,
            CalendarPeriod.start_date != start,
            CalendarPeriod.start_date <= end,
            CalendarPeriod.end_date >= start,
        )
    )
    if overlap:
        raise ValueError("Period overlaps another entry for this region")
    if row is None:
        row = CalendarPeriod(region_key=region, start_date=start)
        db.add(row)
    row.end_date, row.confirmation_status, row.source_url = end, status, source
    db.flush()
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region", required=True)
    parser.add_argument("--start", required=True, type=date.fromisoformat)
    parser.add_argument("--end", required=True, type=date.fromisoformat)
    parser.add_argument("--status", required=True, choices=["PROVISIONAL", "CONFIRMED"])
    parser.add_argument("--source-url")
    args = parser.parse_args()
    engine = create_engine(os.environ["DATABASE_URL"])
    with Session(engine) as db:
        configure(db, args.region, args.start, args.end, args.status, args.source_url)
        db.commit()
    engine.dispose()
    print("Regional calendar saved. Existing journal baselines remain unchanged.")


if __name__ == "__main__":
    main()
