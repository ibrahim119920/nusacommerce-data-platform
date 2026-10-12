import argparse
import json
import logging
import os
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, text

from .ingestion.payment_api import PaymentApiClient
from .ingestion.payment_repository import PaymentRepository
from .ingestion.payment_service import PaymentIngestionService
from .ingestion.repository import OrderIngestionRepository
from .ingestion.service import IncrementalOrderIngestion
from .platform import ROOT, bootstrap, check_quality


def positive_int(value):
    try:
        parsed = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be a positive integer") from None
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def run_dbt(command="build"):
    executable = Path(sys.executable).parent / ("dbt.exe" if os.name == "nt" else "dbt")
    subprocess.run(
        [
            str(executable),
            command,
            "--project-dir",
            str(ROOT / "dbt"),
            "--profiles-dir",
            str(ROOT / "dbt"),
        ],
        check=True,
    )


def ingest_payments(engine):
    client = PaymentApiClient(os.getenv("PAYMENT_API_URL", "http://127.0.0.1:8019"))
    try:
        return asdict(PaymentIngestionService(client, PaymentRepository(engine)).run())
    finally:
        client.close()


def run_batch(engine, order_service, cutoff):
    bootstrap(engine)
    result = {
        "orders": order_service.run(cutoff),
        "payments": ingest_payments(engine),
    }
    run_dbt()
    result["quality"] = check_quality(engine)
    return result


def main():
    parser = argparse.ArgumentParser(
        description="NusaCommerce local data platform tools."
    )
    parser.add_argument(
        "command",
        choices=[
            "bootstrap",
            "orders",
            "payments",
            "dbt",
            "quality",
            "batch",
            "backfill",
            "kafka-produce",
            "kafka-consume",
            "summary",
            "lake-export",
            "spark-build",
            "monitor",
            "metrics-serve",
            "run",
        ],
    )
    parser.add_argument("--cutoff", default="2026-09-29T00:00:00+07:00")
    parser.add_argument("--start")
    parser.add_argument("--page-size", type=positive_int, default=1000)
    parser.add_argument("--group", default="nusacommerce")
    parser.add_argument("--max-messages", type=int, default=6)
    parser.add_argument(
        "--lake-root",
        type=Path,
        default=Path(os.getenv("LAKE_ROOT", str(ROOT / "artifacts/lake"))),
    )
    parser.add_argument("--snapshot-id")
    parser.add_argument(
        "--snapshot-id-only",
        action="store_true",
        help="lake-export: print the snapshot ID for orchestration",
    )
    parser.add_argument("--spark-master", default="local[2]")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=positive_int, default=8024)
    parser.add_argument("--max-age-seconds", type=positive_int, default=86400)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    postgres_url = os.getenv("POSTGRES_URL")
    if not postgres_url:
        parser.error("POSTGRES_URL is required")
    engine = create_engine(postgres_url, connect_args={"connect_timeout": 5})
    try:
        service = IncrementalOrderIngestion(
            OrderIngestionRepository(engine), page_size=args.page_size
        )
        cutoff = datetime.fromisoformat(args.cutoff)
        if args.command == "bootstrap":
            bootstrap(engine)
            result = {"bootstrap": "ok"}
        elif args.command == "orders":
            result = service.run(cutoff)
        elif args.command == "payments":
            result = ingest_payments(engine)
        elif args.command == "dbt":
            run_dbt()
            result = {"dbt": "ok"}
        elif args.command == "quality":
            result = check_quality(engine)
        elif args.command in ("batch", "run"):
            result = run_batch(engine, service, cutoff)
            if args.command == "run":
                from .lake.snapshot import export_snapshot
                from .lake.spark_job import build_spark_mart
                from .monitoring import collect_health

                snapshot = export_snapshot(engine, args.lake_root)
                result["lake"] = snapshot
                result["spark"] = build_spark_mart(
                    args.lake_root,
                    snapshot_id=snapshot["snapshot_id"],
                    master=args.spark_master,
                )
                result["monitor"] = collect_health(
                    engine, max_age_seconds=args.max_age_seconds
                )
                if not result["monitor"]["healthy"]:
                    raise RuntimeError("run_health_failed")
        elif args.command == "backfill":
            if not args.start:
                parser.error("backfill requires --start")
            result = service.backfill(datetime.fromisoformat(args.start), cutoff)
        elif args.command.startswith("kafka"):
            from .streaming.clickstream import consume, produce_fixture

            servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:19099")
            if args.command == "kafka-produce":
                result = {
                    "produced": produce_fixture(servers, ROOT / "data/clickstream.json")
                }
            else:
                if args.max_messages < 1:
                    parser.error("--max-messages must be positive")
                result = consume(
                    servers, engine, group=args.group, max_messages=args.max_messages
                )
        elif args.command == "lake-export":
            from .lake.snapshot import export_snapshot

            result = export_snapshot(engine, args.lake_root)
            if args.snapshot_id_only:
                print(result["snapshot_id"])
                return 0
        elif args.command == "spark-build":
            from .lake.spark_job import build_spark_mart

            result = build_spark_mart(
                args.lake_root, snapshot_id=args.snapshot_id, master=args.spark_master
            )
        elif args.command in ("monitor", "metrics-serve"):
            from .monitoring import collect_health, serve_metrics

            if args.command == "metrics-serve":
                serve_metrics(
                    engine,
                    host=args.host,
                    port=args.port,
                    max_age_seconds=args.max_age_seconds,
                )
                return 0
            result = collect_health(engine, max_age_seconds=args.max_age_seconds)
            print(json.dumps(result, indent=2))
            return 0 if result["healthy"] else 1
        else:
            with engine.connect() as conn:
                result = {
                    "finance": [
                        dict(row)
                        for row in conn.execute(
                            text("SELECT * FROM marts.daily_finance ORDER BY date_day")
                        ).mappings()
                    ],
                    "clickstream": [
                        dict(row)
                        for row in conn.execute(
                            text(
                                "SELECT * FROM marts.daily_clickstream ORDER BY date_day,event_type"
                            )
                        ).mappings()
                    ],
                }
        print(json.dumps(result, default=str, indent=2))
        return 0
    except Exception as exc:
        logging.error("command_failed code=%s", type(exc).__name__)
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
