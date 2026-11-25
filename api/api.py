from typing import Annotated

from pydantic import BaseModel
from fastapi import FastAPI, Query, HTTPException
from sqlmodel import Session, col, select

from consumer.db import Company, engine

app = FastAPI()

class CompanyCard(BaseModel):
    registration_number: str
    company_name: str | None
    description: str | None
    state: str | None
    industry: str | None

@app.get("/companies/{registration_number}", response_model=CompanyCard)
def get_company(
    registration_number: str
):
    registration_number = registration_number.strip().upper()

    with Session(engine) as session:
            company = session.get(Company, registration_number)

            if company is None:
                raise HTTPException(
                    status_code = 404,
                    detail = "Company with registeration number: " + registration_number + " not found."
                )

            if not company.is_active:
               raise HTTPException(
                   status_code = 404,
                   detail = "Company with registeration number: " + registration_number + " exists but not active."
               )

            return company

@app.get("/companies/{registration_number}/similar", response_model=list[CompanyCard])
def similar_companies(
    registration_number: str,
    limit: Annotated[int, Query(ge=1, le=25)] = 4
):
    registration_number = registration_number.strip().upper()

    with Session(engine) as session:
        company = session.get(Company, registration_number)

        if company is None:
            raise HTTPException(
                status_code = 404,
                detail = "Company with registeration number: " + registration_number + " not found."
            )

        if not company.is_active:
           raise HTTPException(
               status_code = 404,
               detail = "Company with registeration number: " + registration_number + " exists but not active."
           )

        if company.embedding is None:
            return []

        embedding = col(Company.embedding)
        statement = (
            select(Company)
            .where(
                Company.registration_number != registration_number,
                col(Company.is_active).is_(True),
                embedding.is_not(None)
            )
            .order_by(
                embedding.cosine_distance(company.embedding),
                Company.registration_number
            )
            .limit(limit)
        )
        return session.exec(statement).all()