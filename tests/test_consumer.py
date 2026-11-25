import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.schema import CreateSchema
from sqlmodel import Session, create_engine

from consumer import db
from consumer.embed import embed_description
from consumer.json_parser import (
    CompanyStruckOff,
    CompanyUpserted,
    event_parser,
    parse_updated_at,
)


class EventParsingTests(unittest.TestCase):
    def test_selects_event_class_and_allows_missing_description(self):
        upsert = event_parser.validate_json(
            b'{"type":"company-upserted","registrationNumber":"SYN-000001",'
            b'"data":{"companyName":"Example Cafe"}}'
        )
        struck_off = event_parser.validate_json(
            b'{"type":"company-struck-off","registrationNumber":"SYN-000001"}'
        )

        self.assertIsInstance(upsert, CompanyUpserted)
        self.assertIsNone(upsert.data.natureOfBusiness)
        self.assertIsInstance(struck_off, CompanyStruckOff)
        self.assertEqual(struck_off.registrationNumber, "SYN-000001")

    def test_rejects_malformed_json_and_wrong_event_shape(self):
        for body in (
            b'{"type":',
            b'null',
            b'{"type":"company-upserted","data":{}}',
            b'{"type":"company-upserted","registrationNumber":"SYN-000001","data":"bad"}',
        ):
            with self.subTest(body=body), self.assertRaises(ValidationError):
                event_parser.validate_json(body)

    def test_normalizes_feed_timestamp_formats_to_utc(self):
        expected = datetime(2024, 1, 1, tzinfo=timezone.utc)
        for value in ("2024-01-01T08:00:00+08:00", "2024-01-01T08:00:00", 1704067200000):
            with self.subTest(value=value):
                result = parse_updated_at(value)
                self.assertEqual(result, expected)
                self.assertEqual(result.utcoffset(), timedelta(0))

    def test_rejects_missing_or_invalid_timestamps(self):
        for value in (None, "not a timestamp"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_updated_at(value)


class EmbeddingFormattingTests(unittest.TestCase):
    def test_collapses_whitespace_and_adds_e5_prefix(self):
        model = Mock()
        model.encode.return_value.tolist.return_value = [0.25, 0.75]

        embedding = embed_description(model, "  Kedai\t kopi\n dan kafe!  ")

        model.encode.assert_called_once_with("query: Kedai kopi dan kafe!", normalize_embeddings=True)
        self.assertEqual(embedding, [0.25, 0.75])

    def test_skips_embedding_for_missing_or_blank_descriptions(self):
        model = Mock()
        for description in (None, " \n\t "):
            with self.subTest(description=description):
                self.assertIsNone(embed_description(model, description))
        model.encode.assert_not_called()


@unittest.skipUnless(os.getenv("TEST_DATABASE_URL"), "set TEST_DATABASE_URL to run the Postgres test")
class PostgresUpsertTests(unittest.TestCase):
    def test_newest_company_event_wins(self):
        engine = create_engine(os.environ["TEST_DATABASE_URL"])
        self.addCleanup(engine.dispose)
        schema = f"consumer_test_{uuid4().hex}"
        registration = "SYN-000001"
        created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        updated_at = created_at + timedelta(days=1)
        struck_off_at = updated_at + timedelta(days=1)
        embedding = [1.0] + [0.0] * 383

        # The outer transaction rolls back the test schema and its data when the connection closes.
        with engine.connect() as connection:
            connection.begin()
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public"))
            connection.execute(CreateSchema(schema))
            connection.execute(
                text("SELECT set_config('search_path', :path, true)"),
                {"path": f"{schema}, public"},
            )
            db.Company.__table__.create(connection)

            with patch.object(db, "engine", connection), Session(connection) as session:
                db.save_company(registration, created_at, company_name="Initial Cafe", is_active=True)
                self.assertEqual(session.get(db.Company, registration).company_name, "Initial Cafe")

                db.save_company(registration, updated_at, company_name="Current Cafe", embedding=embedding)
                db.save_company(registration, updated_at, company_name="Same timestamp")
                db.save_company(registration, struck_off_at, is_active=False)
                db.save_company(registration, updated_at, company_name="Stale Cafe", is_active=True)

                session.expire_all()
                company = session.get(db.Company, registration)
                self.assertEqual(company.company_name, "Current Cafe")
                self.assertEqual(list(company.embedding), embedding)
                self.assertFalse(company.is_active)
                self.assertEqual(company.updated_at, struck_off_at)
