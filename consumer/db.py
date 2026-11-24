from datetime import datetime

from pgvector.sqlalchemy import VECTOR
from sqlalchemy import DateTime, text
from sqlmodel import Field, SQLModel, create_engine


class Company(SQLModel, table=True):
    __tablename__ = "companies"

    registration_number: str = Field(primary_key=True)
    company_name: str | None = None
    description: str | None = None
    state: str | None = None
    industry: str | None = None
    embedding: list[float] | None = Field(default=None, sa_type=VECTOR(384))
    updated_at: datetime = Field(sa_type=DateTime(timezone=True))
    is_active: bool = True


engine = create_engine(
    "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/companies"
)


def init_db() -> None:
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        SQLModel.metadata.create_all(connection)


if __name__ == "__main__":
    init_db()