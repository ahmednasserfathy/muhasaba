from datetime import UTC, date, datetime
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)
from pydantic.alias_generators import to_camel


class AuthModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, extra="forbid"
    )


class Credentials(AuthModel):
    email: EmailStr = Field(max_length=320)
    password: SecretStr = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value):
        return str(value).lower()


class RegisterRequest(Credentials):
    password: SecretStr = Field(min_length=12, max_length=128)
    timezone: str = Field(default="Africa/Cairo", min_length=1, max_length=64)
    tracking_start_date: date | None = None

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Use a valid IANA timezone") from exc
        return value

    @model_validator(mode="after")
    def valid_start_date(self):
        today = datetime.now(UTC).astimezone(ZoneInfo(self.timezone)).date()
        if self.tracking_start_date is None:
            self.tracking_start_date = today
        if self.tracking_start_date > today:
            raise ValueError("Tracking cannot start in the future")
        return self


class RefreshRequest(AuthModel):
    refresh_token: SecretStr = Field(min_length=45, max_length=45)


class UserResponse(AuthModel):
    id: UUID
    email: str | None
    registration_source: Literal["NATIVE", "IMPORTED"]
    role: Literal["USER", "ADMIN"]
    timezone: str
    locale: str
    tracking_start_date: date
    email_verified: bool


class TokenResponse(AuthModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = 900
    user: UserResponse
