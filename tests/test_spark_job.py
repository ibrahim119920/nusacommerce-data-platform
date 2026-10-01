"""Actual Spark transformations; enabled only with Java and PySpark installed."""

import os
import sys
import unittest
from datetime import date, datetime
from decimal import Decimal

from nusacommerce.lake.spark_job import aggregate_orders


@unittest.skipUnless(
    os.getenv("RUN_SPARK_TESTS") == "1", "Set RUN_SPARK_TESTS=1 on a Spark runtime"
)
class SparkJobTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pyspark.sql import SparkSession

        os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
        cls.spark = (
            SparkSession.builder.master("local[2]")
            .appName("NusaCommerceTests")
            .config("spark.ui.enabled", "false")
            .config("spark.sql.shuffle.partitions", "2")
            .getOrCreate()
        )
        cls.spark.sparkContext.setLogLevel("WARN")

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def records(self):
        from pyspark.sql.types import (
            StructType,
            StructField,
            StringType,
            LongType,
            DecimalType,
            DateType,
            TimestampType,
        )

        schema = StructType(
            [
                StructField("order_id", StringType()),
                StructField("version", LongType()),
                StructField("status", StringType()),
                StructField("amount", DecimalType(18, 2)),
                StructField("currency", StringType()),
                StructField("event_date", DateType()),
                StructField("updated_at", TimestampType()),
            ]
        )
        return self.spark.createDataFrame(
            [
                (
                    "a",
                    1,
                    "paid",
                    Decimal("10.00"),
                    "IDR",
                    date(2026, 10, 1),
                    datetime(2026, 10, 1),
                ),
                (
                    "a",
                    2,
                    "cancelled",
                    Decimal("10.00"),
                    "IDR",
                    date(2026, 10, 1),
                    datetime(2026, 10, 2),
                ),
                (
                    "b",
                    1,
                    "paid",
                    Decimal("20.10"),
                    "IDR",
                    date(2026, 10, 1),
                    datetime(2026, 10, 1),
                ),
                (
                    "b",
                    2,
                    "paid",
                    Decimal("21.20"),
                    "IDR",
                    date(2026, 10, 1),
                    datetime(2026, 10, 2),
                ),
            ],
            schema,
        )

    def test_latest_cancelled_order_is_removed_not_old_version_counted(self):
        result = aggregate_orders(self.records()).collect()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].order_count, 1)

    def test_money_remains_exact_decimal_after_dedup(self):
        row = aggregate_orders(self.records()).first()
        self.assertEqual(row.order_value, Decimal("21.20"))
        self.assertIsInstance(row.order_value, Decimal)

    def test_empty_input_produces_no_groups(self):
        self.assertEqual(aggregate_orders(self.records().limit(0)).count(), 0)
