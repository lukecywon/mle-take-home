import os
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.schema import CreateSchema, DropSchema
from sqlmodel import Session, create_engine

from api import api
from consumer.db import Company


@unittest.skipUnless(os.getenv("TEST_DATABASE_URL"), "set TEST_DATABASE_URL to run API integration tests")
class CompanyApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        schema = f"api_test_{uuid4().hex}"
        engine = create_engine(os.environ["TEST_DATABASE_URL"])
        cls.addClassCleanup(engine.dispose)
        with engine.begin() as connection:
            connection.execute(CreateSchema(schema))

        def drop_test_schema():
            with engine.begin() as connection:
                connection.execute(DropSchema(schema, cascade=True))

        cls.addClassCleanup(drop_test_schema)
        test_engine = engine.execution_options(schema_translate_map={None: schema})
        Company.__table__.create(test_engine)

        def vector(x: float, y: float) -> list[float]:
            return [x, y] + [0.0] * 382

        updated_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        target = Company(
            registration_number="SYN-000100",
            company_name="Example Cafe",
            description="Operates a cafe",
            state="Selangor",
            industry="Food & Beverage",
            embedding=vector(1, 0),
            updated_at=updated_at,
        )
        # The closest IDs sort after less similar IDs. Two candidates also share a score.
        candidates = [
            Company(registration_number=registration, embedding=embedding, updated_at=updated_at, is_active=active)
            for registration, embedding, active in (
                ("SYN-000001", vector(-1, 0), True),
                ("SYN-000010", vector(0, 1), True),
                ("SYN-000020", vector(1, 1), True),
                ("SYN-000040", vector(1, 0.1), True),
                ("SYN-000030", vector(1, 0.1), True),
                ("SYN-000002", vector(1, 0), False),
                ("SYN-000003", None, True),
            )
        ]
        with Session(test_engine) as session:
            session.add_all([target, *candidates])
            session.commit()

        cls.enterClassContext(patch.object(api, "engine", test_engine))
        cls.client = cls.enterClassContext(TestClient(api.app))

    def test_company_lookup_normalizes_id_and_returns_one_card(self):
        response = self.client.get("/companies/%20syn-000100%20")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "registration_number": "SYN-000100",
            "company_name": "Example Cafe",
            "description": "Operates a cafe",
            "state": "Selangor",
            "industry": "Food & Beverage",
        })

    def test_recommendations_rank_by_distance_and_filter_ineligible_companies(self):
        response = self.client.get("/companies/SYN-000100/similar")

        self.assertEqual(response.status_code, 200)
        cards = response.json()
        self.assertEqual(
            [card["registration_number"] for card in cards],
            ["SYN-000030", "SYN-000040", "SYN-000020", "SYN-000010"],
        )
        self.assertEqual(
            set(cards[0]), {"registration_number", "company_name", "description", "state", "industry"}
        )

    def test_recommendations_respect_valid_limits(self):
        for limit, expected_count in ((1, 1), (25, 5)):
            with self.subTest(limit=limit):
                response = self.client.get("/companies/SYN-000100/similar", params={"limit": limit})

                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(response.json()), expected_count)
                self.assertEqual(response.json()[0]["registration_number"], "SYN-000030")

    def test_invalid_limits_return_422(self):
        for limit in (0, 26, "abc"):
            with self.subTest(limit=limit):
                response = self.client.get("/companies/SYN-000100/similar", params={"limit": limit})

                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.json()["detail"][0]["loc"], ["query", "limit"])

    def test_unknown_and_struck_off_companies_return_404_on_both_routes(self):
        for registration in ("SYN-999999", "SYN-000002"):
            for suffix in ("", "/similar"):
                with self.subTest(registration=registration, suffix=suffix):
                    response = self.client.get(f"/companies/{registration}{suffix}")

                    self.assertEqual(response.status_code, 404)

    def test_active_company_without_embedding_is_visible_but_has_no_recommendations(self):
        company = self.client.get("/companies/SYN-000003")
        similar = self.client.get("/companies/SYN-000003/similar")

        self.assertEqual(company.status_code, 200)
        self.assertEqual(company.json()["registration_number"], "SYN-000003")
        self.assertEqual(similar.status_code, 200)
        self.assertEqual(similar.json(), [])
