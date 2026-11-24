from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.modules.journal.schemas import JournalModel, Version


class PersonalItem(JournalModel):
    id: UUID
    type: Literal["DHIKR", "DUA"] = "DHIKR"
    text_ar: str = Field(min_length=1, max_length=10000)
    target_count: int = Field(strict=True, ge=1, le=1000)

    @field_validator("text_ar")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Text must not be blank")
        return value


class PlanWrite(JournalModel):
    client_mutation_id: UUID
    expected_version: Version
    catalog_release: str = Field(min_length=1, max_length=50)
    effective_from: date
    hidden_default_codes: list[str] = Field(default_factory=list, max_length=1000)
    official_order: list[str] = Field(default_factory=list, max_length=1000)
    custom_items: list[PersonalItem] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def unique(self):
        for values in (
            self.hidden_default_codes,
            self.official_order,
            [i.id for i in self.custom_items],
        ):
            if len(values) != len(set(values)):
                raise ValueError("Duplicate plan item")
        return self


class PlanView(JournalModel):
    activity_code: str
    date: date
    catalog_release: str
    row_version: int
    effective_from: date | None
    hidden_default_codes: list[str]
    official_order: list[str]
    custom_items: list[PersonalItem]
    official_items: list[dict]


class ItemContext(JournalModel):
    client_mutation_id: UUID
    expected_version: Version
    catalog_release: str = Field(min_length=1, max_length=50)
    effective_from: date
    activity_code: str = Field(min_length=1, max_length=80)


class ItemWrite(ItemContext):
    item: PersonalItem
