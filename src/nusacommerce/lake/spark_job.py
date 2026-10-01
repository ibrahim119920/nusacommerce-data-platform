"""Latest-order aggregation over one immutable snapshot using Spark SQL."""

import json
import os
import sys
from pathlib import Path
from uuid import uuid4

from .snapshot import load_snapshot


def aggregate_orders(orders):
    """Deduplicate before aggregating; business dates are already Asia/Jakarta."""
    from pyspark.sql import Window, functions as fn

    latest = orders.withColumn(
        "_rank",
        fn.row_number().over(
            Window.partitionBy("order_id").orderBy(
                fn.col("version").desc(), fn.col("updated_at").desc()
            )
        ),
    ).filter(fn.col("_rank") == 1)
    return (
        latest.filter(fn.col("status") != "cancelled")
        .groupBy("event_date", "currency")
        .agg(fn.count("*").alias("order_count"), fn.sum("amount").alias("order_value"))
    )


def build_spark_mart(
    lake_root: Path, *, snapshot_id: str | None = None, master: str = "local[2]"
) -> dict:
    """Publish one complete derived result; never mutate raw Parquet."""
    directory, manifest = load_snapshot(lake_root, snapshot_id)
    from pyspark.sql import SparkSession

    # Avoid using a system Python different from the project environment.
    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    spark = (
        SparkSession.builder.appName("NusaCommerce-Day14")
        .master(master)
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", "4")
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")
    try:
        orders = spark.read.parquet(str(directory / "orders"))
        aggregated = aggregate_orders(orders)
        # collect only the small daily aggregate, not the raw dataset.
        rows = sorted(
            [
                {
                    "event_date": str(row.event_date),
                    "currency": row.currency,
                    "order_count": row.order_count,
                    "order_value": str(row.order_value),
                }
                for row in aggregated.collect()
            ],
            key=lambda row: (row["event_date"], row["currency"]),
        )
        result_root = Path(lake_root) / "derived" / manifest["snapshot_id"]
        result_root.mkdir(parents=True, exist_ok=True)
        run_id = uuid4().hex
        temporary = result_root / ("." + run_id + ".tmp")
        # A single output partition is for the tiny demo, not a large-data default.
        aggregated.coalesce(1).write.mode("errorifexists").parquet(
            str(temporary / "data")
        )
        report = {
            "snapshot_id": manifest["snapshot_id"],
            "spark_version": spark.version,
            "master": master,
            "raw_order_versions": manifest["tables"]["orders"]["rows"],
            "daily_orders": rows,
        }
        (temporary / "report.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        os.replace(temporary, result_root / run_id)
        return report
    finally:
        spark.stop()
