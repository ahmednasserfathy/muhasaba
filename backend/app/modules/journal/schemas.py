from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.modules.fasting.schemas import FastingView


class JournalModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, extra="forbid"
    )


Version = Annotated[int, Field(strict=True, ge=0, le=2147483646)]


class Mutation(JournalModel):
    client_mutation_id: UUID
    catalog_release: str = Field(min_length=1, max_length=50)


class StateWrite(Mutation):
    expected_version: Version
    state: Literal["PENDING", "COMPLETED", "EXCLUDED"]


class CountWrite(Mutation):
    expected_version: Version
    completed_count: int = Field(strict=True, ge=0, le=1000)


class SetWrite(Mutation):
    action: Literal["COMPLETE_ALL", "CLEAR_ALL"]
    expected_versions: dict[str, Version] = Field(max_length=1000)


class ItemView(JournalModel):
    item_key: str
    code: str
    text_ar: str
    target_count: int
    completed_count: int
    row_version: int
    source_type: Literal["OFFICIAL"] = "OFFICIAL"
    is_score_eligible: bool
    source_name: str
    source_url: str
    license_notes: str


class CardView(JournalModel):
    code: str
    category_code: str
    category_title_ar: str
    title_ar: str
    kind: Literal["TOGGLE", "ADHKAR_SET", "FASTING"]
    weight: int
    state: Literal["PENDING", "COMPLETED", "EXCLUDED"]
    status: Literal["PENDING", "PARTIAL", "COMPLETED", "EXCLUDED"]
    row_version: int
    eligible: bool
    earned_points: float
    possible_points: int
    official_completed: int
    official_total: int
    items: list[ItemView]


class Summary(JournalModel):
    earned: float
    possible: int
    percent: int | None


class DayView(JournalModel):
    date: date
    today: date
    tracking_start_date: date
    timezone: str
    catalog_release: str
    fasting: FastingView | None = None
    activities: list[CardView]
    summary: Summary
