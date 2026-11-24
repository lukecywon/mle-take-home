from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter


class CompanyData(BaseModel):
    companyName: str | None = None
    natureOfBusiness: str | None = None
    state: str | None = None
    industry: str | None = None

class CompanyEvent(BaseModel):
    registerationNumber: str
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

event_parser = TypeAdapter