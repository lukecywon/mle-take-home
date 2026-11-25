from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter

# JSON Parser
class CompanyData(BaseModel):
    companyName: str | None = None
    natureOfBusiness: str | None = None
    state: str | None = None
    industry: str | None = None

class CompanyEvent(BaseModel):
    registrationNumber: str
    updatedAt: str | int | None = None

class CompanyUpserted(CompanyEvent):
    type: Literal["company-upserted"]
    data: CompanyData

class CompanyStruckOff(CompanyEvent):
    type: Literal["company-struck-off"]

Event = Annotated[
    CompanyUpserted | CompanyStruckOff,
    Field(discriminator = "type")
]

event_parser = TypeAdapter(Event)

# Datetime parser

MALAYSIA_TIME = timezone(timedelta(hours=8))

def parse_updated_at(value: str | int | None) -> datetime:
    if value is None:
        raise ValueError("updatedAt is missing")

    if isinstance(value, int):
        return datetime.fromtimestamp(value / 1000, tz = timezone.utc)

    timestamp = datetime.fromisoformat(value)

    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=MALAYSIA_TIME)

    return timestamp.astimezone(timezone.utc)