"""Standalone payment ingestion entry point, retained from the Day 3 exercise."""

import logging
import os

from sqlalchemy import create_engine

from nusacommerce.ingestion.payment_api import PaymentApiClient
from nusacommerce.ingestion.payment_repository import PaymentRepository
from nusacommerce.ingestion.payment_service import PaymentIngestionService


def main() -> int:
    """Read configuration, assemble the pipeline, and print run counts."""
    payment_api_url = os.getenv("PAYMENT_API_URL", "http://127.0.0.1:8009")
    postgres_url = os.getenv("POSTGRES_URL")
    if not postgres_url:
        raise SystemExit("Set POSTGRES_URL before running the pipeline")

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    engine = create_engine(postgres_url, connect_args={"connect_timeout": 5})
    client = PaymentApiClient(payment_api_url)
    try:
        service = PaymentIngestionService(
            client,
            PaymentRepository(engine),
        )
        result = service.run()
        print(result)
        return 0
    finally:
        client.close()
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
