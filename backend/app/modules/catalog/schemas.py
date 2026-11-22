from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CatalogModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ItemResponse(CatalogModel):
    code: str
    sort_order: int
    target_count: int
    text_ar: str
    review_status: Literal["VERIFIED"]
    source_type: Literal["OFFICIAL"] = "OFFICIAL"
    is_score_eligible: bool
    source_name: str
    source_url: str
    license_notes: str


class ActivityResponse(CatalogModel):
    code: str
    title_ar: str
    sort_order: int
    points: int
    kind: Literal["TOGGLE", "ADHKAR_SET", "FASTING"]
    schedule_kind: Literal["DAILY", "FASTING_DYNAMIC"]
    show_details: bool
    items: list[ItemResponse]


class CategoryResponse(CatalogModel):
    code: str
    title_ar: str
    sort_order: int
    activities: list[ActivityResponse]


class CatalogResponse(CatalogModel):
    release: str
    categories: list[CategoryResponse]
