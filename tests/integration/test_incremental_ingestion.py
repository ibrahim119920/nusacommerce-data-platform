"""Three Day 2 checks against an explicitly configured test database."""

import os
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from nusacommerce.ingestion.repository import OrderIngestionRepository
from nusacommerce.ingestion.service import IncrementalOrderIngestion

ROOT = Path(__file__).resolve().parents[2]
TEST_URL = os.getenv("TEST_POSTGRES_URL")


@unittest.skipUnless(TEST_URL, "Set TEST_POSTGRES_URL to a dedicated *_test database")
class IncrementalIngestionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # These tests clear tables. Never allow the application's normal database.
        database = make_url(TEST_URL).database or ""
        if not database.endswith("_test"):
            raise ValueError("Integration tests require a database name ending in _test")
        cls.engine = create_engine(TEST_URL, connect_args={"connect_timeout": 5})
        with cls.engine.connect() as connection:
            exists = connection.execute(text("SELECT to_regclass('source.orders')")).scalar()
        if exists is None:
            cls.execute_script(ROOT / "sql/migrations/001_reliable_ingestion.sql")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.engine.dispose()

    @classmethod
    def execute_script(cls, path: Path) -> None:
        connection = cls.engine.raw_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(path.read_text(encoding="utf-8"))
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def setUp(self) -> None:
        with self.engine.begin() as connection:
            connection.execute(text("""
                TRUNCATE quality.order_conflicts, control.ingestion_checkpoints,
                         landing.raw_order_versions, landing.staged_orders,
                         landing.ingestion_runs, source.orders
            """))
        self.execute_script(ROOT / "sql/seeds/day_02_orders.sql")
        self.repository = OrderIngestionRepository(self.engine)
        self.service = IncrementalOrderIngestion(self.repository, page_size=2)
        self.cutoff = datetime.fromisoformat("2026-09-28T10:20:00+07:00")

    def raw_count(self) -> int:
        with self.engine.connect() as connection:
            return connection.execute(text("SELECT COUNT(*) FROM landing.raw_order_versions")).scalar_one()

    def test_initial_load_paginates_all_eight_orders(self) -> None:
        result = self.service.run(self.cutoff)
        self.assertEqual(result["extracted"], 8)
        self.assertEqual(result["inserted"], 8)
        self.assertEqual(self.raw_count(), 8)
        self.assertEqual(self.repository.load_checkpoint("orders_incremental"), self.cutoff)
        with self.engine.connect() as connection:
            status = connection.execute(text("""
                SELECT status FROM landing.ingestion_runs WHERE run_id = CAST(:id AS UUID)
            """), {"id": result["run_id"]}).scalar_one()
        self.assertEqual(status, "succeeded")

    def test_rerun_reads_overlap_without_duplicate_raw_rows(self) -> None:
        self.service.run(self.cutoff)
        result = self.service.run(self.cutoff)
        self.assertEqual(result["extracted"], 2)
        self.assertEqual(result["inserted"], 0)
        self.assertEqual(result["duplicates"], 2)
        self.assertEqual(self.raw_count(), 8)

    def test_failure_after_raw_insert_rolls_back_and_retry_succeeds(self) -> None:
        self.service.run(self.cutoff)
        with self.engine.begin() as connection:
            connection.execute(text("""
                UPDATE source.orders
                SET version = 2, status = 'delivered',
                    updated_at = TIMESTAMPTZ '2026-09-28 10:25:00+07:00'
                WHERE order_id = 'ord-1008'
            """))
        next_cutoff = datetime.fromisoformat("2026-09-28T10:30:00+07:00")
        with patch.object(self.repository, "_advance_checkpoint",
                          side_effect=RuntimeError("simulated failure before commit")):
            with self.assertLogs("nusacommerce.ingestion.service", level="ERROR"):
                with self.assertRaises(RuntimeError):
                    self.service.run(next_cutoff)
        self.assertEqual(self.raw_count(), 8)
        self.assertEqual(self.repository.load_checkpoint("orders_incremental"), self.cutoff)
        with self.engine.connect() as connection:
            failed = connection.execute(text("""
                SELECT COUNT(*) FROM landing.ingestion_runs
                WHERE status = 'failed' AND error_code = 'RuntimeError'
            """)).scalar_one()
        self.assertEqual(failed, 1)
        retry = self.service.run(next_cutoff)
        self.assertEqual(retry["inserted"], 1)
        self.assertEqual(self.raw_count(), 9)
        self.assertEqual(self.repository.load_checkpoint("orders_incremental"), next_cutoff)


if __name__ == "__main__":
    unittest.main()
