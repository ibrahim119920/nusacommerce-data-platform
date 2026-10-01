"""Command-line entry point for the Day 2 ingestion exercise."""

import argparse
import json
import logging
import os
from datetime import datetime

from sqlalchemy import create_engine

from nusacommerce.ingestion.repository import OrderIngestionRepository
from nusacommerce.ingestion.service import IncrementalOrderIngestion


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--safe-cutoff", required=True, help="Timezone-aware ISO-8601 datetime")
    parser.add_argument("--page-size", type=int, default=1000)
    args = parser.parse_args()
    database_url = os.getenv("POSTGRES_URL")
    if not database_url:
        parser.error("Set POSTGRES_URL before running the pipeline")
    try:
        cutoff = datetime.fromisoformat(args.safe_cutoff.replace("Z", "+00:00"))
    except ValueError:
        parser.error("--safe-cutoff must be an ISO-8601 datetime")

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    engine = create_engine(database_url, connect_args={"connect_timeout": 5})
    try:
        service = IncrementalOrderIngestion(
            OrderIngestionRepository(engine), page_size=args.page_size
        )
        print(json.dumps(service.run(cutoff), indent=2))
        return 0
    except Exception as exc:
        # Do not print SQL parameters, credentials, or source payloads.
        logging.error("Pipeline stopped: error_code=%s", type(exc).__name__)
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
