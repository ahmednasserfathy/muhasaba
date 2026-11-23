from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel


class FastingModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, extra="forbid"
    )


Version = Annotated[int, Field(strict=True, ge=0, le=2147483646)]


class PlanWrite(FastingModel):
    client_mutation_id: UUID
    expected_version: Version
    mode: Literal["DEFAULT", "ADD", "SKIP"]
    fast_type: Literal["VOLUNTARY", "MAKEUP", "OTHER"] | None = None

    @model_validator(mode="after")
    def validate_type(self):
        if self.mode != "ADD" and self.fast_type is not None:
            raise ValueError("fastType applies only to ADD")
        return self


class FastingView(FastingModel):
    date: date
    region_key: str
    mode: Literal["DEFAULT", "ADD", "SKIP"]
    fast_type: Literal["VOLUNTARY", "MAKEUP", "OTHER"] | None
    row_version: int
    eligible: bool
    reason: Literal["SKIP", "ADDED", "RAMADAN", "WEEKLY", "UNPLANNED"]
    base_reason: Literal["RAMADAN", "WEEKLY", "UNPLANNED"]
    calendar_status: Literal["CONFIRMED", "PROVISIONAL", "UNAVAILABLE"]
    source_url: str | None
    pinned: bool


class CalendarView(FastingModel):
    today: date
    tracking_start_date: date
    days: list[FastingView]
