from datetime import datetime

from pgvector.sqlalchemy import VECTOR
from sqlalchemy import DateTime, text
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Field, SQLModel, create_engine, Session


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

def save_company(registration_number: str, updated_at: datetime, **changes) -> None:
    table = Company.__table__

    incoming = insert(table).values(
        registration_number=registration_number,
        updated_at=updated_at,
        **changes
    )

    statement = incoming.on_conflict_do_update(
        index_elements = [table.c.registration_number],
        set_ = {**changes, "updated_at": incoming.excluded.updated_at},
        where = incoming.excluded.updated_at > table.c.updated_at
    )

    with Session(engine) as session:
        session.exec(statement)
        session.commit()

def init_db() -> None:
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        SQLModel.metadata.create_all(connection)


if __name__ == "__main__":
    init_db()