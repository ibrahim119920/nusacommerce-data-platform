"""Prometheus formatting without database or server side effects."""

import unittest
from nusacommerce.monitoring import prometheus_metrics


class MonitoringTests(unittest.TestCase):
    def test_metrics_are_explicit_gauges_without_credentials(self):
        metrics = prometheus_metrics(
            {
                "healthy": True,
                "last_success_age_seconds": 3.5,
                "latest_ingestion_failed": False,
                "quality_passed": True,
                "raw_orders": 8,
                "raw_payments": 6,
                "clickstream": 6,
                "failed_runs": 0,
                "running_runs": 0,
                "stale_runs": 0,
            }
        )
        self.assertIn("# TYPE nusa_raw_orders_total gauge", metrics)
        self.assertIn("nusa_pipeline_healthy 1", metrics)
        self.assertIn("nusa_ingestion_last_success_age_seconds 3.5", metrics)
        self.assertNotIn("postgresql", metrics)

    def test_missing_success_has_sentinel_not_fresh_age_zero(self):
        metrics = prometheus_metrics(
            {
                "healthy": False,
                "last_success_age_seconds": None,
                "latest_ingestion_failed": False,
                "quality_passed": False,
                "raw_orders": 0,
                "raw_payments": 0,
                "clickstream": 0,
                "failed_runs": 0,
                "running_runs": 0,
                "stale_runs": 0,
            }
        )
        self.assertIn("nusa_ingestion_last_success_age_seconds -1", metrics)
