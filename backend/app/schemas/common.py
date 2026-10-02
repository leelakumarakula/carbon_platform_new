"""Shared schema types: pagination, e-mail normalisation, reason text."""
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Annotated, Generic, TypeVar

from email_validator import EmailNotValidError, validate_email
from pydantic import AfterValidator, BaseModel, ConfigDict, PlainSerializer, StringConstraints, ValidationError

T = TypeVar("T")


def _utc_iso(value: datetime) -> str:
    """DB timestamps are naive UTC (datetime2); emit unambiguous ISO-8601 with a Z suffix."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


UtcDatetime = Annotated[datetime, PlainSerializer(_utc_iso, return_type=str, when_used="json")]


@dataclass(frozen=True)
class PageParams:
    page: int = 1
    page_size: int = 25
    sort: str | None = None

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


def _normalise_email(value: str) -> str:
    try:
        # Deliverability is not checked; reserved/test domains are accepted for demo data.
        return validate_email(value.strip(), check_deliverability=False, globally_deliverable=False).normalized.lower()
    except EmailNotValidError as e:
        raise ValueError(str(e)) from e


Email = Annotated[str, StringConstraints(max_length=320), AfterValidator(_normalise_email)]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=1000)]


def upper_code(pattern: str, label: str) -> AfterValidator:
    """Normalise to upper case first, then validate (StringConstraints checks the pattern before to_upper)."""
    rx = re.compile(pattern)

    def _v(value: str) -> str:
        value = value.strip().upper()
        if not rx.fullmatch(value):
            raise ValueError(f"{label} must match {pattern}")
        return value
    return AfterValidator(_v)


Code = Annotated[str, StringConstraints(max_length=40), upper_code(r"[A-Z][A-Z0-9_-]{1,39}", "Code")]
RoleCode = Annotated[str, StringConstraints(max_length=60), upper_code(r"[A-Z][A-Z0-9_]{2,59}", "Role code")]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Message(BaseModel):
    success: bool = True
    message: str


class IdRef(BaseModel):
    id: uuid.UUID


M = TypeVar("M", bound=BaseModel)


def validate_payload(schema: type[M], data: object) -> M:
    """Validate a dynamically-chosen schema inside a route/service; failures become the standard 422 envelope."""
    from app.core.errors import ValidationFailed
    try:
        return schema.model_validate(data)
    except ValidationError as e:
        raise ValidationFailed(details={"errors": [{"field": ".".join(str(p) for p in err["loc"]), "message": err["msg"],
                                                    "type": err["type"]} for err in e.errors()]}) from e
