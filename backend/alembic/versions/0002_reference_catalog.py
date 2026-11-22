"""Seed the unverified reference catalog as a draft, never published content.

Revision ID: 0002
Revises: 0001
"""

from datetime import date
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def stable_id(key):
    return uuid5(NAMESPACE_URL, "muhasaba:reference:" + key)


# Frozen from blueprint seed; later edits require a new revision/release.
ROWS = [
    ("FAJR", "الفجر", 1, "fajr_awake", "أذكار الاستيقاظ", 1, 2, True, False),
    ("FAJR", "الفجر", 1, "fajr_pre_sunnah", "السنة القبلية", 2, 2, False, False),
    ("FAJR", "الفجر", 1, "fajr_first_jamaa", "الجماعة الأولى", 3, 2, False, False),
    ("FAJR", "الفجر", 1, "fajr_after_dhikr", "أذكار بعد الصلاة", 4, 2, True, False),
    ("FAJR", "الفجر", 1, "fajr_morning_dhikr", "أذكار الصباح", 5, 2, True, False),
    ("FAJR", "الفجر", 1, "fajr_duha", "الضحى ٤ ركعات", 6, 2, False, False),
    (
        "DHUHR",
        "الظهر",
        2,
        "dhuhr_pre_sunnah",
        "السنة القبلية ٤ ركعات",
        1,
        2,
        False,
        False,
    ),
    ("DHUHR", "الظهر", 2, "dhuhr_first_jamaa", "الجماعة الأولى", 2, 2, False, False),
    ("DHUHR", "الظهر", 2, "dhuhr_after_dhikr", "أذكار بعد الصلاة", 3, 2, True, False),
    ("DHUHR", "الظهر", 2, "dhuhr_post_sunnah", "السنة البعدية", 4, 2, False, False),
    ("ASR", "العصر", 3, "asr_first_jamaa", "الجماعة الأولى", 1, 2, False, False),
    ("ASR", "العصر", 3, "asr_after_dhikr", "أذكار بعد الصلاة", 2, 2, True, False),
    ("ASR", "العصر", 3, "asr_evening_dhikr", "أذكار المساء", 3, 2, True, False),
    (
        "MAGHRIB",
        "المغرب",
        4,
        "maghrib_first_jamaa",
        "الجماعة الأولى",
        1,
        2,
        False,
        False,
    ),
    (
        "MAGHRIB",
        "المغرب",
        4,
        "maghrib_after_dhikr",
        "أذكار بعد الصلاة",
        2,
        2,
        True,
        False,
    ),
    (
        "MAGHRIB",
        "المغرب",
        4,
        "maghrib_post_sunnah",
        "السنة البعدية",
        3,
        2,
        False,
        False,
    ),
    ("ISHA", "العشاء", 5, "isha_first_jamaa", "الجماعة الأولى", 1, 2, False, False),
    ("ISHA", "العشاء", 5, "isha_after_dhikr", "أذكار بعد الصلاة", 2, 2, True, False),
    ("ISHA", "العشاء", 5, "isha_post_sunnah", "السنة البعدية", 3, 2, False, False),
    (
        "NIGHT",
        "قيام الليل والوتر",
        6,
        "night_two_rakats",
        "ركعتان قيام ليل",
        1,
        4,
        False,
        False,
    ),
    (
        "NIGHT",
        "قيام الليل والوتر",
        6,
        "night_wird",
        "الورد (ربعين)",
        2,
        4,
        False,
        False,
    ),
    ("NIGHT", "قيام الليل والوتر", 6, "night_witr", "الوتر", 3, 1, False, False),
    (
        "QURAN_FAST",
        "القرآن والصيام",
        7,
        "quran_half_page",
        "حفظ نصف صفحة",
        1,
        2,
        False,
        False,
    ),
    (
        "QURAN_FAST",
        "القرآن والصيام",
        7,
        "quran_six_quarters",
        "قراءة ستة أرباع",
        2,
        2,
        False,
        False,
    ),
    (
        "QURAN_FAST",
        "القرآن والصيام",
        7,
        "fast_mon_thu",
        "الصيام (الاثنين والخميس)",
        3,
        5,
        False,
        True,
    ),
    ("DHIKR", "أذكار متنوعة", 8, "dhikr_restroom", "الخلاء", 1, 2, True, False),
    ("DHIKR", "أذكار متنوعة", 8, "dhikr_clothes", "لبس الثوب وخلعه", 2, 2, True, False),
    ("DHIKR", "أذكار متنوعة", 8, "dhikr_wudu", "الوضوء", 3, 2, True, False),
    (
        "DHIKR",
        "أذكار متنوعة",
        8,
        "dhikr_home",
        "دخول المنزل والخروج",
        4,
        2,
        True,
        False,
    ),
    (
        "DHIKR",
        "أذكار متنوعة",
        8,
        "dhikr_mosque",
        "المسجد دخول وخروج",
        5,
        2,
        True,
        False,
    ),
    (
        "DHIKR",
        "أذكار متنوعة",
        8,
        "dhikr_walk_to_mosque",
        "المشي إلى المسجد",
        6,
        2,
        True,
        False,
    ),
    ("DHIKR", "أذكار متنوعة", 8, "dhikr_food_drink", "الأكل والشرب", 7, 2, True, False),
    ("DHIKR", "أذكار متنوعة", 8, "dhikr_riding", "الركوب", 8, 2, True, False),
    ("DHIKR", "أذكار متنوعة", 8, "dhikr_before_sleep", "قبل النوم", 9, 2, True, False),
]


def upgrade():
    categories = sa.table(
        "categories",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("title_ar", sa.String()),
        sa.column("sort_order", sa.SmallInteger()),
    )
    releases = sa.table(
        "catalog_releases",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("effective_from", sa.Date()),
        sa.column("status", sa.String()),
    )
    activities = sa.table(
        "activities",
        sa.column("id", sa.Uuid()),
        sa.column("catalog_release_id", sa.Uuid()),
        sa.column("category_id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("title_ar", sa.String()),
        sa.column("sort_order", sa.SmallInteger()),
        sa.column("points", sa.SmallInteger()),
        sa.column("kind", sa.String()),
        sa.column("schedule_kind", sa.String()),
        sa.column("show_details", sa.Boolean()),
    )
    unique_categories = {row[0]: row[:3] for row in ROWS}
    op.bulk_insert(
        categories,
        [
            dict(id=stable_id(code), code=code, title_ar=title, sort_order=order)
            for code, title, order in unique_categories.values()
        ],
    )
    release_id = stable_id("2026-11-19-reference")
    op.bulk_insert(
        releases,
        [
            dict(
                id=release_id,
                code="2026-11-19-reference",
                effective_from=date(2026, 11, 19),
                status="DRAFT",
            )
        ],
    )
    op.bulk_insert(
        activities,
        [
            dict(
                id=stable_id(code),
                catalog_release_id=release_id,
                category_id=stable_id(category),
                code=code,
                title_ar=title,
                sort_order=order,
                points=points,
                kind="FASTING" if fasting else "ADHKAR_SET" if details else "TOGGLE",
                schedule_kind="FASTING_DYNAMIC" if fasting else "DAILY",
                show_details=details,
            )
            for category, _, _, code, title, order, points, details, fasting in ROWS
        ],
    )


def downgrade():
    # FK/immutability guards intentionally refuse if later data references this seed.
    release_id = stable_id("2026-11-19-reference")
    activities = sa.table("activities", sa.column("catalog_release_id", sa.Uuid()))
    releases = sa.table("catalog_releases", sa.column("id", sa.Uuid()))
    categories = sa.table("categories", sa.column("id", sa.Uuid()))
    op.execute(activities.delete().where(activities.c.catalog_release_id == release_id))
    op.execute(releases.delete().where(releases.c.id == release_id))
    op.execute(
        categories.delete().where(
            categories.c.id.in_([stable_id(code) for code in {row[0] for row in ROWS}])
        )
    )
