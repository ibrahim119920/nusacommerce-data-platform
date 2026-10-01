"""Lake integrity and operational health against a dedicated test database."""

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from nusacommerce.ingestion.repository import OrderIngestionRepository
from nusacommerce.ingestion.service import IncrementalOrderIngestion
from nusacommerce.lake.snapshot import export_snapshot, load_snapshot
from nusacommerce.monitoring import collect_health
from nusacommerce.platform import bootstrap

URL = os.getenv("TEST_POSTGRES_URL")


@unittest.skipUnless(URL, "TEST_POSTGRES_URL is required")
class Day14Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (make_url(URL).database or "").endswith("_test"):
            raise ValueError("Dedicated test database required")
        cls.engine = create_engine(URL)
        bootstrap(cls.engine)

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def setUp(self):
        with self.engine.begin() as conn:
            conn.execute(
                text("""
                TRUNCATE quality.order_conflicts,control.ingestion_checkpoints,
                landing.raw_order_versions,landing.staged_orders,landing.ingestion_runs,
                source.orders,landing.raw_payment_versions,landing.clickstream_events,
                control.quality_runs
            """)
            )
        bootstrap(self.engine)
        self.service = IncrementalOrderIngestion(
            OrderIngestionRepository(self.engine), page_size=2
        )
        self.service.run(datetime.fromisoformat("2026-10-02T00:00:00+00:00"))
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.addCleanup(self.temporary.cleanup)

    def mark_quality(self, passed):
        from uuid import uuid4

        with self.engine.begin() as conn:
            conn.execute(
                text("""
                INSERT INTO control.quality_runs(run_id,results,passed)
                VALUES (:id,'{}'::jsonb,:passed)
            """),
                {"id": uuid4(), "passed": passed},
            )

    def test_snapshot_roundtrip_and_partitioning(self):
        manifest = export_snapshot(self.engine, self.root)
        directory, loaded = load_snapshot(self.root)
        self.assertEqual(manifest, loaded)
        self.assertEqual(manifest["tables"]["orders"]["rows"], 8)
        self.assertEqual(manifest["tables"]["payments"]["rows"], 0)
        self.assertTrue(
            any(
                "event_date=" in entry["path"]
                for entry in manifest["tables"]["orders"]["files"]
            )
        )
        self.assertTrue((directory / "payments/empty.parquet").exists())

    def test_rerun_publishes_new_snapshot_without_raw_duplicates(self):
        first = export_snapshot(self.engine, self.root)
        second = export_snapshot(self.engine, self.root)
        self.assertNotEqual(first["snapshot_id"], second["snapshot_id"])
        self.assertEqual(
            first["tables"]["orders"]["rows"], second["tables"]["orders"]["rows"]
        )
        self.assertTrue((self.root / first["snapshot_id"] / "manifest.json").exists())
        self.assertEqual(
            load_snapshot(self.root)[1]["snapshot_id"], second["snapshot_id"]
        )

    def test_partial_export_does_not_replace_latest(self):
        first = export_snapshot(self.engine, self.root)
        with patch(
            "nusacommerce.lake.snapshot.pq.write_to_dataset",
            side_effect=OSError("simulated disk failure"),
        ):
            with self.assertRaises(OSError):
                export_snapshot(self.engine, self.root)
        self.assertEqual(
            load_snapshot(self.root)[1]["snapshot_id"], first["snapshot_id"]
        )

    def test_tampered_parquet_is_rejected(self):
        manifest = export_snapshot(self.engine, self.root)
        directory = self.root / manifest["snapshot_id"]
        data_file = directory / manifest["tables"]["orders"]["files"][0]["path"]
        with data_file.open("ab") as stream:
            stream.write(b"damaged")
        with self.assertRaisesRegex(ValueError, "checksum"):
            load_snapshot(self.root)

    def test_snapshot_path_traversal_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "snapshot_id"):
            load_snapshot(self.root, "../outside")

    def test_manifest_path_traversal_is_rejected(self):
        manifest = export_snapshot(self.engine, self.root)
        manifest["tables"]["orders"]["files"][0]["path"] = "../../outside.parquet"
        path = self.root / manifest["snapshot_id"] / "manifest.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "unsafe_parquet_path"):
            load_snapshot(self.root)

    def test_monitor_healthy_after_quality_pass(self):
        self.mark_quality(True)
        report = collect_health(self.engine)
        self.assertTrue(report["healthy"])
        self.assertEqual(report["raw_orders"], 8)
        self.assertEqual(report["reasons"], [])

    def test_monitor_stale_success_is_unhealthy(self):
        self.mark_quality(True)
        report = collect_health(
            self.engine, now=datetime.now(timezone.utc) + timedelta(days=2)
        )
        self.assertFalse(report["healthy"])
        self.assertIn("ingestion_stale", report["reasons"])

    def test_monitor_missing_quality_is_unhealthy(self):
        report = collect_health(self.engine)
        self.assertIn("missing_or_failed_quality", report["reasons"])

    def test_monitor_failed_quality_is_unhealthy(self):
        self.mark_quality(False)
        self.assertFalse(collect_health(self.engine)["healthy"])

    def test_monitor_latest_failed_ingestion_is_unhealthy(self):
        self.mark_quality(True)
        cutoff = datetime.fromisoformat("2026-10-02T00:00:00+00:00")
        with patch.object(
            self.service.repository,
            "fetch_order_page",
            side_effect=RuntimeError("source unavailable"),
        ):
            with self.assertRaises(RuntimeError):
                self.service.run(cutoff)
        report = collect_health(self.engine)
        self.assertIn("latest_ingestion_failed", report["reasons"])
        self.assertEqual(report["failed_runs"], 1)

    def test_monitor_naive_now_is_rejected(self):
        with self.assertRaises(ValueError):
            collect_health(self.engine, now=datetime(2026, 10, 2))
